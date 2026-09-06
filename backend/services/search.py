import asyncio
import logging
import time

import httpx

from config import settings
from errors import AppError
from schemas import Midpoint, PoiItem, SearchData, SearchRequest
from services.deadline import Deadline
from services.geo_match import (
    format_location,
    midpoint,
    resolve_geocode,
    select_pois,
)
from services.storage import save_search

logger = logging.getLogger(__name__)


def _amap_payload_ok(payload: dict) -> bool:
    return str(payload.get("status")) == "1"


async def _amap_get(
    client: httpx.AsyncClient,
    url: str,
    params: dict,
    timeout: float,
) -> dict:
    started = time.monotonic()
    try:
        response = await client.get(url, params=params, timeout=timeout)
    except (httpx.TimeoutException, httpx.ConnectTimeout, httpx.ReadTimeout) as exc:
        logger.warning(
            "stage=search elapsed_ms=%s error=%s",
            int((time.monotonic() - started) * 1000),
            type(exc).__name__,
        )
        raise AppError(504, "UPSTREAM_TIMEOUT", "查找店铺超时，请稍后重试。", "search") from exc
    except httpx.HTTPError as exc:
        logger.warning(
            "stage=search elapsed_ms=%s error=%s",
            int((time.monotonic() - started) * 1000),
            type(exc).__name__,
        )
        raise AppError(502, "UPSTREAM_ERROR", "地图服务暂时不可用，请稍后重试。", "search") from exc

    logger.info(
        "stage=search status=%s elapsed_ms=%s",
        response.status_code,
        int((time.monotonic() - started) * 1000),
    )
    if response.status_code >= 400:
        raise AppError(502, "UPSTREAM_ERROR", "地图服务暂时不可用，请稍后重试。", "search")
    try:
        payload = response.json()
    except ValueError as exc:
        raise AppError(502, "UPSTREAM_ERROR", "地图服务返回无法解析。", "search") from exc
    if not isinstance(payload, dict):
        raise AppError(502, "UPSTREAM_ERROR", "地图服务返回无法解析。", "search")
    if not _amap_payload_ok(payload):
        raise AppError(502, "UPSTREAM_ERROR", "地图服务暂时不可用，请稍后重试。", "search")
    return payload


async def _geocode(
    client: httpx.AsyncClient,
    city: str,
    address: str,
    timeout: float,
):
    payload = await _amap_get(
        client,
        settings.amap_geocode_url,
        {
            "key": settings.amap_api_key,
            "address": address,
            "city": city,
            "output": "json",
        },
        timeout,
    )
    geocodes = payload.get("geocodes")
    if not isinstance(geocodes, list):
        geocodes = []
    return resolve_geocode(city, address, geocodes)


async def _around(
    client: httpx.AsyncClient,
    *,
    city: str,
    keywords: str,
    longitude: float,
    latitude: float,
    radius: int,
    timeout: float,
) -> list[object]:
    payload = await _amap_get(
        client,
        settings.amap_around_url,
        {
            "key": settings.amap_api_key,
            "location": format_location(longitude, latitude),
            "keywords": keywords,
            "city": city,
            "citylimit": "true",
            "radius": str(radius),
            "offset": str(settings.poi_fetch_size),
            "page": "1",
            "extensions": "base",
            "output": "json",
        },
        timeout,
    )
    pois = payload.get("pois")
    if not isinstance(pois, list):
        return []
    return pois


async def search_meetup(payload: SearchRequest) -> SearchData:
    if not settings.amap_api_key:
        raise AppError(502, "UPSTREAM_ERROR", "地图服务未配置密钥。", "search")

    deadline = Deadline(
        settings.search_total_timeout_s,
        "search",
        "查找店铺超时，请稍后重试。",
    )
    call_budget = settings.amap_upstream_timeout_s

    async with httpx.AsyncClient() as client:
        point_a, point_b = await asyncio.gather(
            _geocode(
                client,
                payload.city_a,
                payload.address_a,
                deadline.timeout_for(call_budget),
            ),
            _geocode(
                client,
                payload.city_b,
                payload.address_b,
                deadline.timeout_for(call_budget),
            ),
        )
        mid_lng, mid_lat = midpoint(point_a, point_b)
        request_city = payload.city_a
        raw_pois = await _around(
            client,
            city=request_city,
            keywords=payload.category,
            longitude=mid_lng,
            latitude=mid_lat,
            radius=settings.poi_first_radius_m,
            timeout=deadline.timeout_for(call_budget),
        )
        pois = select_pois(
            raw_pois,
            request_city=request_city,
            mid_lng=mid_lng,
            mid_lat=mid_lat,
            limit=settings.poi_max_results,
        )
        if not pois:
            raw_pois = await _around(
                client,
                city=request_city,
                keywords=payload.category,
                longitude=mid_lng,
                latitude=mid_lat,
                radius=settings.poi_expand_radius_m,
                timeout=deadline.timeout_for(call_budget),
            )
            pois = select_pois(
                raw_pois,
                request_city=request_city,
                mid_lng=mid_lng,
                mid_lat=mid_lat,
                limit=settings.poi_max_results,
            )

    if not pois:
        raise AppError(
            422,
            "NO_POI",
            "中点附近没有找到合适的店，请换个地点再试。",
            "search",
        )

    poi_items = [PoiItem.model_validate(item) for item in pois]
    midpoint_data = Midpoint(longitude=mid_lng, latitude=mid_lat)
    search_id = save_search(
        {
            "request": payload.model_dump(),
            "midpoint": midpoint_data.model_dump(),
            "pois": [item.model_dump() for item in poi_items],
            "points": {
                "a": {
                    "longitude": point_a.longitude,
                    "latitude": point_a.latitude,
                },
                "b": {
                    "longitude": point_b.longitude,
                    "latitude": point_b.latitude,
                },
            },
        }
    )
    return SearchData(search_id=search_id, midpoint=midpoint_data, pois=poi_items)
