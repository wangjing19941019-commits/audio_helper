import logging

from fastapi import APIRouter, Request

from schemas import AsrData, AsrRequest, AsrResponse
from services.asr import transcribe
from services.storage import get_upload

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/asr", response_model=AsrResponse)
async def recognize_audio(request: Request, payload: AsrRequest) -> AsrResponse:
    audio_bytes = get_upload(payload.audio_id, stage="asr")
    logger.info("stage=asr audio_id=%s size_bytes=%s", payload.audio_id, len(audio_bytes))
    text = await transcribe(audio_bytes)
    return AsrResponse(
        request_id=request.state.request_id,
        data=AsrData(text=text),
    )
