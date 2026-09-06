import logging

from config import settings
from errors import AppError
from schemas import FinalizeData
from services.deadline import Deadline
from services.reply import generate_reply
from services.storage import get_search
from services.tts import synthesize_and_store

logger = logging.getLogger(__name__)


def _first_valid_poi(record: dict) -> tuple[str, str]:
    pois = record.get("pois")
    if not isinstance(pois, list):
        pois = []
    for item in pois:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        address = str(item.get("address") or "").strip()
        if name and address:
            return name, address
    raise AppError(422, "NO_POI", "没有可推荐的店铺，请重新查找。", "finalize")


def _tts_warning(exc: AppError) -> str:
    if exc.code == "UPSTREAM_TIMEOUT":
        return "语音生成超时，已保留文字推荐。"
    return "语音生成失败，已保留文字推荐。"


async def finalize_meetup(search_id: str) -> FinalizeData:
    record = get_search(search_id, stage="finalize")
    name, address = _first_valid_poi(record)
    deadline = Deadline(
        settings.finalize_total_timeout_s,
        "finalize",
        "生成推荐超时，请稍后重试。",
    )
    reply_text = await generate_reply(
        name,
        address,
        timeout=deadline.timeout_for(settings.reply_upstream_timeout_s),
    )

    try:
        tts_timeout = deadline.timeout_for(settings.tts_upstream_timeout_s)
        download_timeout = deadline.timeout_for(settings.tts_download_timeout_s)
        audio_id = await synthesize_and_store(
            reply_text,
            tts_timeout=tts_timeout,
            download_timeout=download_timeout,
        )
    except AppError as exc:
        logger.warning("stage=finalize code=%s step=tts_degraded", exc.code)
        return FinalizeData(
            reply_text=reply_text,
            audio_url=None,
            warning=_tts_warning(exc),
        )

    audio_url = f"{settings.public_base_url.rstrip('/')}/audio/{audio_id}"
    return FinalizeData(reply_text=reply_text, audio_url=audio_url, warning=None)
