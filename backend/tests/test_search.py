from errors import AppError
from services.geo_match import (
    GeoPoint,
    haversine_m,
    midpoint,
    resolve_geocode,
    select_pois,
)
from schemas import SearchData, SearchRequest


def _geocode_item(location: str, level: str, formatted: str, city: str = "杭州市") -> dict:
    return {
        "location": location,
        "level": level,
        "formatted_address": formatted,
        "city": city,
        "district": "西湖区",
        "street": [],
        "number": [],
        "province": "浙江省",
    }


def test_search_validation_error(client):
    response = client.post("/search", json={"city_a": "杭州"})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
    assert response.json()["error"]["stage"] == "search"


def test_search_success_mock(client, monkeypatch):
    async def fake_search(payload: SearchRequest) -> SearchData:
        assert payload.address_a == "杭州东站"
        return SearchData.model_validate(
            {
                "search_id": "11111111-1111-4111-8111-111111111111",
                "midpoint": {"longitude": 120.21, "latitude": 30.25},
                "pois": [
                    {
                        "name": "测试咖啡店",
                        "address": "测试路1号",
                        "distance_to_midpoint_m": 120.5,
                    }
                ],
            }
        )

    monkeypatch.setattr("api.search.search_meetup", fake_search)
    response = client.post(
        "/search",
        json={
            "city_a": "杭州",
            "address_a": "杭州东站",
            "city_b": "杭州",
            "address_b": "西湖龙翔桥地铁站",
            "category": "咖啡店",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["data"]["search_id"]
    assert body["data"]["midpoint"]["longitude"] == 120.21
    assert body["data"]["pois"][0]["distance_to_midpoint_m"] == 120.5


def test_search_ambiguous_via_api(client, monkeypatch):
    async def fake_search(_payload: SearchRequest):
        raise AppError(422, "AMBIGUOUS_LOCATION", "地点不够明确，请补充更具体的地点。", "search")

    monkeypatch.setattr("api.search.search_meetup", fake_search)
    response = client.post(
        "/search",
        json={
            "city_a": "杭州",
            "address_a": "西湖",
            "city_b": "杭州",
            "address_b": "市中心",
            "category": "咖啡店",
        },
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "AMBIGUOUS_LOCATION"


def test_search_no_poi_via_api(client, monkeypatch):
    async def fake_search(_payload: SearchRequest):
        raise AppError(422, "NO_POI", "中点附近没有找到合适的店，请换个地点再试。", "search")

    monkeypatch.setattr("api.search.search_meetup", fake_search)
    response = client.post(
        "/search",
        json={
            "city_a": "杭州",
            "address_a": "杭州东站",
            "city_b": "杭州",
            "address_b": "西湖龙翔桥地铁站",
            "category": "不存在的品类xyz123",
        },
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "NO_POI"


def test_midpoint_is_lng_lat_average():
    a = GeoPoint(120.0, 30.0, "a", "a", "杭州", "兴趣点")
    b = GeoPoint(122.0, 32.0, "b", "b", "杭州", "兴趣点")
    lng, lat = midpoint(a, b)
    assert lng == 121.0
    assert lat == 31.0


def test_resolve_single_poi_level():
    point = resolve_geocode(
        "杭州",
        "杭州东站",
        [_geocode_item("120.212,30.291", "兴趣点", "浙江省杭州市杭州东站")],
    )
    assert point.longitude == 120.212
    assert point.latitude == 30.291


def test_resolve_hangzhou_east_amap_payload():
    point = resolve_geocode(
        "杭州",
        "杭州东站",
        [_geocode_item("120.212600,30.290851", "门牌号", "杭州东站")],
    )
    assert point.longitude == 120.2126


def test_resolve_longxiang_amap_parenthetical_address():
    point = resolve_geocode(
        "杭州",
        "西湖龙翔桥地铁站",
        [
            _geocode_item(
                "120.164052,30.254642",
                "公交地铁站点",
                "浙江省杭州市上城区杭州西湖(湖滨店)龙翔桥(地铁站)",
            )
        ],
    )
    assert point.latitude == 30.254642


def test_resolve_rejects_city_level():
    try:
        resolve_geocode("杭州", "杭州", [_geocode_item("120.15,30.28", "市", "浙江省杭州市")])
    except AppError as exc:
        assert exc.code == "AMBIGUOUS_LOCATION"
        assert exc.status_code == 422
    else:
        raise AssertionError("expected AMBIGUOUS_LOCATION")


def test_resolve_does_not_merge_300m_different_names():
    try:
        resolve_geocode(
            "杭州",
            "西湖",
            [
                _geocode_item("120.1500,30.2500", "兴趣点", "浙江省杭州市西湖风景区"),
                _geocode_item("120.1532,30.2500", "兴趣点", "浙江省杭州市西湖博物馆"),
            ],
        )
    except AppError as exc:
        assert exc.code == "AMBIGUOUS_LOCATION"
    else:
        raise AssertionError("expected AMBIGUOUS_LOCATION")


def test_resolve_does_not_merge_close_but_different_names():
    try:
        resolve_geocode(
            "杭州",
            "杭州东站",
            [
                _geocode_item("120.21200,30.29100", "兴趣点", "浙江省杭州市杭州东站"),
                _geocode_item("120.21240,30.29100", "兴趣点", "浙江省杭州市杭州东站到达口"),
            ],
        )
    except AppError as exc:
        assert exc.code == "AMBIGUOUS_LOCATION"
    else:
        raise AssertionError("expected AMBIGUOUS_LOCATION")


def test_resolve_merges_80m_same_name():
    point = resolve_geocode(
        "杭州",
        "杭州东站",
        [
            _geocode_item("120.21200,30.29100", "兴趣点", "浙江省杭州市杭州东站"),
            _geocode_item("120.21240,30.29100", "兴趣点", "浙江省杭州市杭州东站"),
        ],
    )
    assert abs(point.longitude - 120.2122) < 0.0001
    assert point.latitude == 30.291


def test_resolve_uses_all_candidates_not_first_two():
    try:
        resolve_geocode(
            "杭州",
            "西湖",
            [
                _geocode_item("120.1500,30.2500", "兴趣点", "浙江省杭州市西湖A"),
                _geocode_item("120.1502,30.2500", "兴趣点", "浙江省杭州市西湖A"),
                _geocode_item("120.1800,30.2800", "兴趣点", "浙江省杭州市西湖A"),
            ],
        )
    except AppError as exc:
        assert exc.code == "AMBIGUOUS_LOCATION"
    else:
        raise AssertionError("expected AMBIGUOUS_LOCATION")


def test_select_pois_computes_missing_distance_not_zero():
    mid_lng, mid_lat = 120.2, 30.3
    far_lng, far_lat = 120.21, 30.31
    expected = round(haversine_m(far_lng, far_lat, mid_lng, mid_lat), 1)
    pois = select_pois(
        [
            {
                "id": "p1",
                "name": "远一点的店",
                "address": "测试路",
                "location": f"{far_lng},{far_lat}",
                "distance": [],
                "cityname": "杭州市",
            },
            {
                "id": "p2",
                "name": "更近的店",
                "address": "近路",
                "location": "120.2005,30.3004",
                "distance": "80",
                "cityname": "杭州市",
            },
            {
                "id": "bad",
                "name": "没有坐标也没有距离",
                "address": "未知",
                "location": [],
                "distance": [],
                "cityname": "杭州市",
            },
        ],
        request_city="杭州",
        mid_lng=mid_lng,
        mid_lat=mid_lat,
        limit=3,
    )
    assert [item["name"] for item in pois] == ["更近的店", "远一点的店"]
    assert pois[0]["distance_to_midpoint_m"] == 80.0
    assert pois[1]["distance_to_midpoint_m"] == expected
    assert expected > 0


def test_select_pois_drops_unusable_and_caps_at_three():
    pois = select_pois(
        [
            {
                "id": str(i),
                "name": f"店{i}",
                "address": "路",
                "location": f"120.20{i},30.30",
                "distance": str(100 - i),
                "cityname": "杭州市",
            }
            for i in range(5)
        ],
        request_city="杭州",
        mid_lng=120.2,
        mid_lat=30.3,
        limit=3,
    )
    assert len(pois) == 3
    distances = [item["distance_to_midpoint_m"] for item in pois]
    assert distances == sorted(distances)


def test_save_search_keeps_created_at(tmp_path, monkeypatch):
    from config import settings
    from services.storage import get_search, save_search

    monkeypatch.setattr(settings, "storage_dir", str(tmp_path))
    search_id = save_search(
        {
            "request": {"category": "咖啡店"},
            "midpoint": {"longitude": 120.21, "latitude": 30.25},
            "pois": [],
        }
    )
    record = get_search(search_id, stage="search")
    assert record["id"] == search_id
    assert record["kind"] == "search"
    assert record["created_at"]
    assert record["midpoint"]["longitude"] == 120.21
