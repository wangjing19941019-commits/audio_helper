from errors import AppError
from services.extract import _parse_model_json, evaluate_extract


def test_extract_validation_error(client):
    response = client.post("/extract", json={"city": "杭州"})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
    assert response.json()["error"]["stage"] == "extract"


def test_extract_success_mock(client, monkeypatch):
    from schemas import ExtractData

    async def fake_extract(text: str, city: str) -> ExtractData:
        assert "杭州东站" in text
        assert city == "杭州"
        return ExtractData(
            city_a="杭州",
            address_a="杭州东站",
            city_b="杭州",
            address_b="西湖龙翔桥地铁站",
            category="咖啡店",
        )

    monkeypatch.setattr("api.extract.extract_slots", fake_extract)
    response = client.post(
        "/extract",
        json={
            "text": "我在杭州东站，朋友在西湖龙翔桥地铁站，帮我们找个中间的咖啡店。",
            "city": "杭州",
        },
    )
    assert response.status_code == 200
    assert response.json()["data"] == {
        "city_a": "杭州",
        "address_a": "杭州东站",
        "city_b": "杭州",
        "address_b": "西湖龙翔桥地铁站",
        "category": "咖啡店",
    }
    assert "party_count" not in response.json()["data"]
    assert "incomplete_reason" not in response.json()["data"]


def test_extract_incomplete_via_api(client, monkeypatch):
    async def fake_extract(_text: str, _city: str):
        raise AppError(
            422,
            "INCOMPLETE_ADDRESS",
            "请补充两个人的具体地点，不要只说我家或公司。",
            "extract",
        )

    monkeypatch.setattr("api.extract.extract_slots", fake_extract)
    response = client.post(
        "/extract",
        json={"text": "我在杭州东站，帮我们找个咖啡店。", "city": "杭州"},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INCOMPLETE_ADDRESS"
    assert response.json()["error"]["stage"] == "extract"


def test_evaluate_missing_address():
    try:
        evaluate_extract(
            {
                "city_a": "杭州",
                "address_a": "杭州东站",
                "city_b": "杭州",
                "address_b": None,
                "category": "咖啡店",
                "party_count": 2,
                "incomplete_reason": "missing_address",
            },
            "杭州",
        )
    except AppError as exc:
        assert exc.status_code == 422
        assert exc.code == "INCOMPLETE_ADDRESS"
    else:
        raise AssertionError("expected INCOMPLETE_ADDRESS")


def test_evaluate_party_count_null():
    try:
        evaluate_extract(
            {
                "city_a": "杭州",
                "address_a": "杭州东站",
                "city_b": "杭州",
                "address_b": "龙翔桥",
                "category": "咖啡店",
                "party_count": None,
                "incomplete_reason": None,
            },
            "杭州",
        )
    except AppError as exc:
        assert exc.code == "INVALID_PARTY_COUNT"
        assert exc.status_code == 422
    else:
        raise AssertionError("expected INVALID_PARTY_COUNT")


def test_evaluate_party_count_three():
    try:
        evaluate_extract(
            {
                "city_a": "杭州",
                "address_a": "杭州东站",
                "city_b": "杭州",
                "address_b": "龙翔桥",
                "category": "咖啡店",
                "party_count": 3,
                "incomplete_reason": "invalid_party_count",
            },
            "杭州",
        )
    except AppError as exc:
        assert exc.code == "INVALID_PARTY_COUNT"
    else:
        raise AssertionError("expected INVALID_PARTY_COUNT")


def test_evaluate_cross_city():
    try:
        evaluate_extract(
            {
                "city_a": "杭州",
                "address_a": "杭州东站",
                "city_b": "宁波",
                "address_b": "宁波站",
                "category": "咖啡店",
                "party_count": 2,
                "incomplete_reason": "cross_city",
            },
            "杭州",
        )
    except AppError as exc:
        assert exc.code == "CROSS_CITY"
        assert exc.status_code == 422
    else:
        raise AssertionError("expected CROSS_CITY")


def test_evaluate_yuhang_vs_hangzhou():
    try:
        evaluate_extract(
            {
                "city_a": "杭州",
                "address_a": "杭州东站",
                "city_b": "余杭",
                "address_b": "西溪印象城",
                "category": "咖啡店",
                "party_count": 2,
                "incomplete_reason": "cross_city",
            },
            "杭州",
        )
    except AppError as exc:
        assert exc.code == "CROSS_CITY"
    else:
        raise AssertionError("expected CROSS_CITY")


def test_evaluate_vague_home():
    try:
        evaluate_extract(
            {
                "city_a": "杭州",
                "address_a": "我家",
                "city_b": "杭州",
                "address_b": "西湖龙翔桥地铁站",
                "category": "咖啡店",
                "party_count": 2,
                "incomplete_reason": "unspecific_place",
            },
            "杭州",
        )
    except AppError as exc:
        assert exc.code == "INCOMPLETE_ADDRESS"
    else:
        raise AssertionError("expected INCOMPLETE_ADDRESS")


def test_evaluate_same_city_with_suffix_and_coffee_phrase():
    data = evaluate_extract(
        {
            "city_a": "杭州",
            "address_a": "杭州东站",
            "city_b": "杭州市",
            "address_b": "西湖龙翔桥地铁站",
            "category": "喝咖啡",
            "party_count": 2,
            "incomplete_reason": None,
        },
        "宁波",
    )
    assert data.category == "咖啡店"
    assert data.city_a == "杭州"
    assert data.city_b == "杭州市"


def test_evaluate_page_city_and_default_category():
    data = evaluate_extract(
        {
            "city_a": None,
            "address_a": "东站",
            "city_b": None,
            "address_b": "龙翔桥地铁站",
            "category": None,
            "party_count": 2,
            "incomplete_reason": None,
        },
        "杭州",
    )
    assert data.city_a == "杭州"
    assert data.city_b == "杭州"
    assert data.category == "咖啡店"


def test_evaluate_spoken_city_not_overwritten():
    data = evaluate_extract(
        {
            "city_a": "杭州",
            "address_a": "杭州东站",
            "city_b": "杭州",
            "address_b": "西湖龙翔桥地铁站",
            "category": "咖啡店",
            "party_count": 2,
            "incomplete_reason": None,
        },
        "宁波",
    )
    assert data.city_a == "杭州"
    assert data.city_b == "杭州"


def test_parse_missing_key_is_model_error_not_incomplete():
    try:
        _parse_model_json('{"city_a":"杭州"}')
    except AppError as exc:
        assert exc.status_code == 502
        assert exc.code == "MODEL_OUTPUT_INVALID"
    else:
        raise AssertionError("expected MODEL_OUTPUT_INVALID")


def test_parse_illegal_json_is_model_error():
    try:
        _parse_model_json("not-json")
    except AppError as exc:
        assert exc.status_code == 502
        assert exc.code == "MODEL_OUTPUT_INVALID"
    else:
        raise AssertionError("expected MODEL_OUTPUT_INVALID")


def test_parse_wrong_party_count_type_is_model_error():
    try:
        _parse_model_json(
            '{"city_a":"杭州","address_a":"东站","city_b":"杭州","address_b":"龙翔桥",'
            '"category":"咖啡店","party_count":"2","incomplete_reason":null}'
        )
    except AppError as exc:
        assert exc.status_code == 502
        assert exc.code == "MODEL_OUTPUT_INVALID"
    else:
        raise AssertionError("expected MODEL_OUTPUT_INVALID")
