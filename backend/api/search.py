import logging

from fastapi import APIRouter, Body, Request

from schemas import SearchRequest, SearchResponse
from services.search import search_meetup

logger = logging.getLogger(__name__)

router = APIRouter()

SEARCH_EXAMPLES = {
    "normal": {
        "summary": "正常搜店",
        "value": {
            "city_a": "杭州",
            "address_a": "杭州东站",
            "city_b": "杭州",
            "address_b": "西湖龙翔桥地铁站",
            "category": "咖啡店",
        },
    },
    "ambiguous": {
        "summary": "定位不明确",
        "value": {
            "city_a": "杭州",
            "address_a": "西湖",
            "city_b": "杭州",
            "address_b": "市中心",
            "category": "咖啡店",
        },
    },
    "no_poi": {
        "summary": "无候选店铺",
        "value": {
            "city_a": "杭州",
            "address_a": "杭州东站",
            "city_b": "杭州",
            "address_b": "西湖龙翔桥地铁站",
            "category": "不存在的品类xyz123",
        },
    },
}


@router.post("/search", response_model=SearchResponse)
async def search_places(
    request: Request,
    payload: SearchRequest = Body(openapi_examples=SEARCH_EXAMPLES),
) -> SearchResponse:
    logger.info("stage=search category=%s", payload.category)
    data = await search_meetup(payload)
    return SearchResponse(request_id=request.state.request_id, data=data)
