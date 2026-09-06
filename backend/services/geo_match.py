import math
import re
from dataclasses import dataclass

from config import settings
from errors import AppError

ALLOWED_GEO_LEVELS = {
    "兴趣点",
    "门牌号",
    "门址",
    "单元号",
    "公交地铁站点",
    "道路交叉路口",
    "住宅区",
    "热点商圈",
}

_PLACE_NOISE = re.compile(r"[\s\-_,，。、·（）()【】\[\]'\"“”]+")
_PAREN_CONTENT = re.compile(r"[（(][^）)]*[）)]")
_TRAILING_STATION = re.compile(r"(?:公交)?地铁站$")


@dataclass(frozen=True)
class GeoPoint:
    longitude: float
    latitude: float
    name: str
    formatted_address: str
    city: str
    level: str


def amap_text(value: object) -> str:
    if value is None or value == []:
        return ""
    if isinstance(value, list):
        return "".join(str(item) for item in value if item not in (None, []))
    return str(value).strip()


def normalize_city(name: str) -> str:
    text = name.strip()
    if text.endswith("市"):
        text = text[:-1]
    return text


def cities_equal(left: str, right: str) -> bool:
    a = normalize_city(left)
    b = normalize_city(right)
    return bool(a) and a == b


def normalize_place(text: str) -> str:
    return _PLACE_NOISE.sub("", text).casefold()


def parse_location(raw: object) -> tuple[float, float] | None:
    text = amap_text(raw)
    parts = text.split(",")
    if len(parts) != 2:
        return None
    try:
        longitude = float(parts[0])
        latitude = float(parts[1])
    except ValueError:
        return None
    if not math.isfinite(longitude) or not math.isfinite(latitude):
        return None
    if not (-180 <= longitude <= 180 and -90 <= latitude <= 90):
        return None
    return longitude, latitude


def format_location(longitude: float, latitude: float) -> str:
    return f"{longitude:.6f},{latitude:.6f}"


def haversine_m(lng1: float, lat1: float, lng2: float, lat2: float) -> float:
    radius = 6371000.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lng2 - lng1)
    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    return 2 * radius * math.asin(math.sqrt(min(1.0, a)))


def midpoint(a: GeoPoint, b: GeoPoint) -> tuple[float, float]:
    return (a.longitude + b.longitude) / 2, (a.latitude + b.latitude) / 2


def _city_of(item: dict) -> str:
    city = amap_text(item.get("city"))
    if city:
        return city
    district = amap_text(item.get("district"))
    if district:
        return district
    return ""


def _match_haystacks(item: dict) -> set[str]:
    formatted = amap_text(item.get("formatted_address"))
    extra = "".join(
        (
            amap_text(item.get("district")),
            amap_text(item.get("street")),
            amap_text(item.get("number")),
        )
    )
    blobs = {
        normalize_place(formatted + extra),
        normalize_place(_PAREN_CONTENT.sub("", formatted + extra)),
    }
    return {blob for blob in blobs if blob}


def _query_variants(query: str) -> set[str]:
    raw = normalize_place(query)
    stripped = normalize_place(_PAREN_CONTENT.sub("", query))
    variants = {raw, stripped}
    for item in list(variants):
        trimmed = _TRAILING_STATION.sub("", item)
        if trimmed:
            variants.add(trimmed)
    usable = {item for item in variants if len(item) >= 3}
    return usable or {raw}


def _place_matches(query: str, item: dict) -> bool:
    q = normalize_place(query)
    if len(q) < 2:
        return False
    haystacks = _match_haystacks(item)
    for variant in _query_variants(query):
        for haystack in haystacks:
            if variant in haystack or haystack in variant:
                return True
    return False


def _parse_geocode_item(item: dict) -> GeoPoint | None:
    location = parse_location(item.get("location"))
    if location is None:
        return None
    longitude, latitude = location
    name = amap_text(item.get("formatted_address")) or amap_text(item.get("district"))
    return GeoPoint(
        longitude=longitude,
        latitude=latitude,
        name=name or format_location(longitude, latitude),
        formatted_address=amap_text(item.get("formatted_address")),
        city=_city_of(item),
        level=amap_text(item.get("level")),
    )


def _all_pairs_within(points: list[GeoPoint], max_m: float) -> bool:
    for i, left in enumerate(points):
        for right in points[i + 1 :]:
            if haversine_m(left.longitude, left.latitude, right.longitude, right.latitude) > max_m:
                return False
    return True


def _names_match(points: list[GeoPoint]) -> bool:
    names = {normalize_place(item.name) for item in points if normalize_place(item.name)}
    return len(names) == 1


def resolve_geocode(query_city: str, query_address: str, geocodes: list[object]) -> GeoPoint:
    filtered: list[GeoPoint] = []
    for raw in geocodes:
        if not isinstance(raw, dict):
            continue
        level = amap_text(raw.get("level"))
        if level not in ALLOWED_GEO_LEVELS:
            continue
        city = _city_of(raw)
        if city and not cities_equal(city, query_city):
            continue
        if not _place_matches(query_address, raw):
            continue
        point = _parse_geocode_item(raw)
        if point is None:
            continue
        filtered.append(point)

    if not filtered:
        raise AppError(
            422,
            "AMBIGUOUS_LOCATION",
            "地点不够明确，请补充更具体的地点。",
            "search",
        )
    if len(filtered) == 1:
        return filtered[0]
    if _all_pairs_within(filtered, settings.geo_merge_max_m) and _names_match(filtered):
        lng = sum(item.longitude for item in filtered) / len(filtered)
        lat = sum(item.latitude for item in filtered) / len(filtered)
        first = filtered[0]
        return GeoPoint(
            longitude=lng,
            latitude=lat,
            name=first.name,
            formatted_address=first.formatted_address,
            city=first.city,
            level=first.level,
        )
    raise AppError(
        422,
        "AMBIGUOUS_LOCATION",
        "地点不够明确，请补充更具体的地点。",
        "search",
    )


def parse_distance_m(raw: object) -> float | None:
    text = amap_text(raw)
    if not text:
        return None
    try:
        value = float(text)
    except ValueError:
        return None
    if not math.isfinite(value) or value < 0:
        return None
    return value


def poi_distance_m(poi: dict, mid_lng: float, mid_lat: float) -> float | None:
    reported = parse_distance_m(poi.get("distance"))
    if reported is not None:
        return reported
    location = parse_location(poi.get("location"))
    if location is None:
        return None
    return haversine_m(location[0], location[1], mid_lng, mid_lat)


def select_pois(
    pois: list[object],
    *,
    request_city: str,
    mid_lng: float,
    mid_lat: float,
    limit: int,
) -> list[dict]:
    ranked: list[dict] = []
    seen: set[str] = set()
    for raw in pois:
        if not isinstance(raw, dict):
            continue
        name = amap_text(raw.get("name"))
        if not name:
            continue
        city = amap_text(raw.get("cityname"))
        if city and not cities_equal(city, request_city):
            continue
        location = parse_location(raw.get("location"))
        if location is None:
            continue
        distance = poi_distance_m(raw, mid_lng, mid_lat)
        if distance is None:
            continue
        key = amap_text(raw.get("id")) or f"{name}|{location[0]:.6f}|{location[1]:.6f}"
        if key in seen:
            continue
        seen.add(key)
        ranked.append(
            {
                "name": name,
                "address": amap_text(raw.get("address")),
                "distance_to_midpoint_m": round(distance, 1),
            }
        )
    ranked.sort(key=lambda item: item["distance_to_midpoint_m"])
    return ranked[:limit]
