import logging

from fastapi import APIRouter, Request
from fastapi.responses import Response

from services.storage import get_tts

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/audio/{audio_id}")
async def download_tts_audio(request: Request, audio_id: str) -> Response:
    content, content_type = get_tts(audio_id, stage="audio")
    logger.info("stage=audio audio_id=%s size_bytes=%s", audio_id, len(content))
    return Response(
        content=content,
        media_type=content_type,
        headers={"Cache-Control": "private, max-age=0"},
    )
