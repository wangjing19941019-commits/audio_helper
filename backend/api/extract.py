import logging

from fastapi import APIRouter, Body, Request

from schemas import ExtractRequest, ExtractResponse
from services.extract import extract_slots

logger = logging.getLogger(__name__)

router = APIRouter()

EXTRACT_EXAMPLES = {
    "normal": {
        "summary": "正常提取",
        "value": {
            "text": "我在杭州东站，朋友在西湖龙翔桥地铁站，帮我们找个中间的咖啡店。",
            "city": "杭州",
        },
    },
    "spoken_city_wins": {
        "summary": "口述城市优先",
        "value": {
            "text": "我在杭州东站，朋友在西湖龙翔桥地铁站，找个咖啡店。",
            "city": "宁波",
        },
    },
    "page_city_fallback": {
        "summary": "口述未说城市，用页面城市",
        "value": {
            "text": "我在东站，朋友在龙翔桥地铁站，帮我们找个中间碰面的地方。",
            "city": "杭州",
        },
    },
    "category_coffee": {
        "summary": "喝咖啡归一化为咖啡店",
        "value": {
            "text": "我在杭州东站，朋友在西湖龙翔桥，想喝咖啡。",
            "city": "杭州",
        },
    },
    "missing_address": {
        "summary": "地址缺失",
        "value": {
            "text": "我在杭州东站，帮我们找个咖啡店。",
            "city": "杭州",
        },
    },
    "party_count_three": {
        "summary": "人数不符",
        "value": {
            "text": "我、小李和小王，我在杭州东站，小李在龙翔桥，小王在西湖，找个咖啡店。",
            "city": "杭州",
        },
    },
    "cross_city": {
        "summary": "跨城：杭州与宁波",
        "value": {
            "text": "我在杭州东站，朋友在宁波站，找个咖啡店。",
            "city": "杭州",
        },
    },
    "yuhang_vs_hangzhou": {
        "summary": "跨城：杭州与余杭",
        "value": {
            "text": "我在杭州东站，朋友在余杭西溪印象城，找个咖啡店。",
            "city": "杭州",
        },
    },
    "vague_home": {
        "summary": "我家等含糊地点",
        "value": {
            "text": "我在我家，朋友在西湖龙翔桥地铁站，找个咖啡店。",
            "city": "杭州",
        },
    },
}


@router.post("/extract", response_model=ExtractResponse)
async def extract_meetup(
    request: Request,
    payload: ExtractRequest = Body(openapi_examples=EXTRACT_EXAMPLES),
) -> ExtractResponse:
    logger.info("stage=extract text_chars=%s city=%s", len(payload.text), payload.city)
    data = await extract_slots(payload.text, payload.city)
    return ExtractResponse(request_id=request.state.request_id, data=data)
