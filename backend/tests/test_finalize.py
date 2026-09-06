from errors import AppError
from services.audio_format import sniff_audio_format
from services.reply import validate_reply
from services.storage import get_search, save_search, save_tts, save_upload
from schemas import FinalizeData


def _sample_search_id() -> str:
    return save_search(
        {
            "request": {
                "city_a": "杭州",
                "address_a": "杭州东站",
                "city_b": "杭州",
                "address_b": "西湖龙翔桥地铁站",
                "category": "咖啡店",
            },
            "midpoint": {"longitude": 120.19, "latitude": 30.27},
            "pois": [
                {
                    "name": "测试咖啡店",
                    "address": "测试路1号",
                    "distance_to_midpoint_m": 120.5,
                }
            ],
        }
    )


def test_finalize_validation_error(client):
    response = client.post("/finalize", json={})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
    assert response.json()["error"]["stage"] == "finalize"


def test_finalize_unknown_search_id(client):
    response = client.post(
        "/finalize",
        json={"search_id": "11111111-1111-4111-8111-111111111111"},
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"
    assert response.json()["error"]["stage"] == "finalize"


def test_finalize_success_mock(client, monkeypatch):
    search_id = _sample_search_id()

    async def fake_finalize(sid: str) -> FinalizeData:
        assert sid == search_id
        return FinalizeData(
            reply_text="两人中间附近有家测试咖啡店，地址测试路1号，适合碰面喝杯咖啡。",
            audio_url="http://localhost:8003/audio/22222222-2222-4222-8222-222222222222",
            warning=None,
        )

    monkeypatch.setattr("api.finalize.finalize_meetup", fake_finalize)
    response = client.post("/finalize", json={"search_id": search_id})
    assert response.status_code == 200
    body = response.json()
    assert body["data"]["reply_text"].startswith("两人中间附近")
    assert body["data"]["audio_url"].startswith("http://localhost:8003/audio/")
    assert body["data"]["warning"] is None


def test_finalize_tts_degrades_to_text(client, monkeypatch):
    search_id = _sample_search_id()

    async def fake_finalize(sid: str) -> FinalizeData:
        assert sid == search_id
        return FinalizeData(
            reply_text="两人中间附近有家测试咖啡店，地址测试路1号。",
            audio_url=None,
            warning="语音生成失败，已保留文字推荐。",
        )

    monkeypatch.setattr("api.finalize.finalize_meetup", fake_finalize)
    response = client.post("/finalize", json={"search_id": search_id})
    assert response.status_code == 200
    body = response.json()
    assert body["data"]["reply_text"]
    assert body["data"]["audio_url"] is None
    assert "文字推荐" in body["data"]["warning"]


def test_finalize_reply_failure(client, monkeypatch):
    search_id = _sample_search_id()

    async def fake_finalize(_sid: str):
        raise AppError(502, "UPSTREAM_ERROR", "推荐语服务暂时不可用，请稍后重试。", "finalize")

    monkeypatch.setattr("api.finalize.finalize_meetup", fake_finalize)
    response = client.post("/finalize", json={"search_id": search_id})
    assert response.status_code == 502
    assert response.json()["error"]["code"] == "UPSTREAM_ERROR"
    assert response.json()["error"]["stage"] == "finalize"


def test_get_audio_returns_bytes_and_content_type(client):
    wav = b"RIFF" + b"\x00" * 4 + b"WAVEfmt "
    audio_id = save_tts(wav, extension="wav", content_type="audio/wav")
    response = client.get(f"/audio/{audio_id}")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("audio/wav")
    assert response.content.startswith(b"RIFF")
    assert response.content[8:12] == b"WAVE"


def test_get_audio_rejects_upload_id(client):
    audio_id = save_upload(b"webm-bytes")
    response = client.get(f"/audio/{audio_id}")
    assert response.status_code == 404
    body = response.json()
    assert body["error"]["code"] == "NOT_FOUND"
    assert body["error"]["stage"] == "audio"


def test_get_audio_unknown_id(client):
    response = client.get("/audio/11111111-1111-4111-8111-111111111111")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


def test_sniff_uses_magic_not_suffix():
    wav = b"RIFF" + b"\x00" * 4 + b"WAVEfmt "
    extension, content_type = sniff_audio_format(wav, "audio/mpeg")
    assert extension == "wav"
    assert content_type == "audio/wav"


def test_validate_reply_requires_real_name_and_address():
    text = validate_reply(
        "两人中间附近有家测试咖啡店，地址在测试路1号，适合碰面。",
        "测试咖啡店",
        "测试路1号",
    )
    assert "测试咖啡店" in text
    try:
        validate_reply("附近有家不错的店，环境很好。", "测试咖啡店", "测试路1号")
    except AppError as exc:
        assert exc.status_code == 502
        assert exc.code == "MODEL_OUTPUT_INVALID"
    else:
        raise AssertionError("expected MODEL_OUTPUT_INVALID")


def test_validate_reply_accepts_fullwidth_parentheses():
    text = validate_reply(
        "推荐你们去瑞幸咖啡（物产国际广场店），就在凯旋路445号物产国际广场一层大堂。",
        "瑞幸咖啡(物产国际广场店)",
        "凯旋路445号物产国际广场一层大堂",
    )
    assert "瑞幸咖啡(物产国际广场店)" in text
    assert "（" not in text


def test_expired_search_is_not_found(tmp_path, monkeypatch):
    from datetime import datetime, timedelta, timezone
    import json
    from config import settings

    monkeypatch.setattr(settings, "storage_dir", str(tmp_path))
    search_id = _sample_search_id()
    path = tmp_path / "search" / f"{search_id}.json"
    record = json.loads(path.read_text(encoding="utf-8"))
    record["created_at"] = (datetime.now(timezone.utc) - timedelta(hours=25)).isoformat()
    path.write_text(json.dumps(record), encoding="utf-8")
    try:
        get_search(search_id, stage="finalize")
    except AppError as exc:
        assert exc.status_code == 404
    else:
        raise AssertionError("expected NOT_FOUND")
