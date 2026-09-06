import logging

from fastapi import APIRouter, Body, Request

from schemas import FinalizeRequest, FinalizeResponse
from services.finalize import finalize_meetup

logger = logging.getLogger(__name__)

router = APIRouter()

FINALIZE_EXAMPLES = {
    "normal": {
        "summary": "用搜索返回的 search_id 生成推荐语和语音",
        "value": {"search_id": "把 /search 返回的 search_id 粘贴到这里"},
    }
}


@router.post("/finalize", response_model=FinalizeResponse)
async def finalize_recommendation(
    request: Request,
    payload: FinalizeRequest = Body(openapi_examples=FINALIZE_EXAMPLES),
) -> FinalizeResponse:
    logger.info("stage=finalize search_id=%s", payload.search_id)
    data = await finalize_meetup(payload.search_id)
    return FinalizeResponse(request_id=request.state.request_id, data=data)
