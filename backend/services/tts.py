import logging
import time

import httpx

from config import settings
from errors import AppError
from services.audio_format import sniff_audio_format
from services.storage import save_tts

logger = logging.getLogger(__name__)


def _tts_audio_url(payload: dict) -> str:
    output = payload.get("output")
    if isinstance(output, dict):
        audio = output.get("audio")
        if isinstance(audio, dict):
            url = audio.get("url")
            if isinstance(url, str) and url.startswith("http"):
                return url
        if isinstance(audio, str) and audio.startswith("http"):
            return audio
    raise AppError(502, "MODEL_OUTPUT_INVALID", "语音生成结果格式不符合约定。", "finalize")


async def synthesize_and_store(text: str, *, tts_timeout: float, download_timeout: float) -> str:
    if not settings.bailian_api_key:
        raise AppError(502, "UPSTREAM_ERROR", "语音合成服务未配置密钥。", "finalize")

    headers = {
        "Authorization": f"Bearer {settings.bailian_api_key}",
        "Content-Type": "application/json",
    }
    body = {
        "model": settings.bailian_tts_model,
        "input": {
            "text": text,
            "voice": settings.bailian_tts_voice,
            "language_type": "Chinese",
        },
    }

    started = time.monotonic()
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                settings.bailian_tts_url,
                headers=headers,
                json=body,
                timeout=tts_timeout,
            )
    except (httpx.TimeoutException, httpx.ConnectTimeout, httpx.ReadTimeout) as exc:
        logger.warning(
            "stage=finalize elapsed_ms=%s error=%s step=tts",
            int((time.monotonic() - started) * 1000),
            type(exc).__name__,
        )
        raise AppError(504, "UPSTREAM_TIMEOUT", "语音生成超时，请稍后重试。", "finalize") from exc
    except httpx.HTTPError as exc:
        logger.warning(
            "stage=finalize elapsed_ms=%s error=%s step=tts",
            int((time.monotonic() - started) * 1000),
            type(exc).__name__,
        )
        raise AppError(502, "UPSTREAM_ERROR", "语音合成服务暂时不可用，请稍后重试。", "finalize") from exc

    logger.info(
        "stage=finalize status=%s elapsed_ms=%s step=tts",
        response.status_code,
        int((time.monotonic() - started) * 1000),
    )
    if response.status_code >= 400:
        raise AppError(502, "UPSTREAM_ERROR", "语音合成服务暂时不可用，请稍后重试。", "finalize")
    try:
        payload = response.json()
    except ValueError as exc:
        raise AppError(502, "UPSTREAM_ERROR", "语音合成服务返回无法解析。", "finalize") from exc
    if not isinstance(payload, dict):
        raise AppError(502, "MODEL_OUTPUT_INVALID", "语音生成结果格式不符合约定。", "finalize")

    audio_url = _tts_audio_url(payload)
    started = time.monotonic()
    try:
        async with httpx.AsyncClient(follow_redirects=True) as client:
            download = await client.get(audio_url, timeout=download_timeout)
    except (httpx.TimeoutException, httpx.ConnectTimeout, httpx.ReadTimeout) as exc:
        logger.warning(
            "stage=finalize elapsed_ms=%s error=%s step=tts_download",
            int((time.monotonic() - started) * 1000),
            type(exc).__name__,
        )
        raise AppError(504, "UPSTREAM_TIMEOUT", "语音下载超时，请稍后重试。", "finalize") from exc
    except httpx.HTTPError as exc:
        logger.warning(
            "stage=finalize elapsed_ms=%s error=%s step=tts_download",
            int((time.monotonic() - started) * 1000),
            type(exc).__name__,
        )
        raise AppError(502, "UPSTREAM_ERROR", "语音下载失败，请稍后重试。", "finalize") from exc

    logger.info(
        "stage=finalize status=%s elapsed_ms=%s step=tts_download size_bytes=%s",
        download.status_code,
        int((time.monotonic() - started) * 1000),
        len(download.content or b""),
    )
    if download.status_code >= 400 or not download.content:
        raise AppError(502, "UPSTREAM_ERROR", "语音下载失败，请稍后重试。", "finalize")

    extension, content_type = sniff_audio_format(
        download.content,
        download.headers.get("content-type", ""),
    )
    return save_tts(download.content, extension=extension, content_type=content_type)
