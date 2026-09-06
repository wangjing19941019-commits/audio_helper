import logging
from pathlib import Path

from fastapi import APIRouter, File, Request, UploadFile

from config import settings
from errors import AppError
from schemas import UploadData, UploadResponse
from services.audio_probe import probe_audio, validate_upload_probe
from services.storage import delete_upload, save_upload

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/upload", response_model=UploadResponse)
async def upload_audio(request: Request, file: UploadFile = File(...)) -> UploadResponse:
    content = await file.read()
    if len(content) > settings.max_upload_bytes:
        raise AppError(413, "PAYLOAD_TOO_LARGE", "录音文件不能超过5MB，请缩短录音后重试。", "upload")
    if not content:
        raise AppError(
            415,
            "UNSUPPORTED_MEDIA_TYPE",
            "仅支持浏览器录制的 WebM/Opus 音频，请更换浏览器后重试。",
            "upload",
        )

    audio_id = save_upload(content)
    file_path = Path(settings.storage_dir) / "audio" / f"{audio_id}.webm"
    try:
        probe = probe_audio(file_path)
        validate_upload_probe(probe)
    except Exception:
        delete_upload(audio_id)
        raise

    logger.info(
        "stage=upload audio_id=%s size_bytes=%s duration_ms=%s",
        audio_id,
        len(content),
        int(probe.duration_s * 1000),
    )
    return UploadResponse(
        request_id=request.state.request_id,
        data=UploadData(audio_id=audio_id),
    )
