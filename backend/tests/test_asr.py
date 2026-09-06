import json
from datetime import datetime, timedelta, timezone

from errors import AppError
from services.storage import save_upload


def test_asr_missing_audio_id(client):
    response = client.post("/asr", json={})
    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert body["error"]["stage"] == "asr"


def test_asr_unknown_id_is_not_found(client):
    response = client.post("/asr", json={"audio_id": "11111111-1111-4111-8111-111111111111"})
    assert response.status_code == 404
    body = response.json()
    assert body["error"]["code"] == "NOT_FOUND"
    assert body["error"]["stage"] == "asr"
    assert "request_id" in body


def test_asr_expired_id_is_not_found(client, tmp_path):
    audio_id = save_upload(b"webm-bytes")
    meta_path = tmp_path / "audio" / f"{audio_id}.meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta["created_at"] = (datetime.now(timezone.utc) - timedelta(hours=25)).isoformat()
    meta_path.write_text(json.dumps(meta), encoding="utf-8")

    response = client.post("/asr", json={"audio_id": audio_id})
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


def test_asr_success_uses_mock_text(client, monkeypatch):
    audio_id = save_upload(b"webm-bytes")

    async def fake_transcribe(audio_bytes: bytes) -> str:
        assert audio_bytes == b"webm-bytes"
        return "我在杭州东站，朋友在西湖龙翔桥地铁站，帮我们找个中间的咖啡店。"

    monkeypatch.setattr("api.asr.transcribe", fake_transcribe)
    response = client.post("/asr", json={"audio_id": audio_id})
    assert response.status_code == 200
    body = response.json()
    assert body["data"]["text"].startswith("我在杭州东站")
    assert "error" not in body


def test_asr_empty_transcript(client, monkeypatch):
    audio_id = save_upload(b"webm-bytes")

    async def fake_transcribe(_audio_bytes: bytes) -> str:
        raise AppError(422, "EMPTY_TRANSCRIPT", "没有识别到有效文字，请重新说一遍。", "asr")

    monkeypatch.setattr("api.asr.transcribe", fake_transcribe)
    response = client.post("/asr", json={"audio_id": audio_id})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "EMPTY_TRANSCRIPT"


def test_asr_upstream_timeout(client, monkeypatch):
    audio_id = save_upload(b"webm-bytes")

    async def fake_transcribe(_audio_bytes: bytes) -> str:
        raise AppError(504, "UPSTREAM_TIMEOUT", "语音识别超时，请稍后重试。", "asr")

    monkeypatch.setattr("api.asr.transcribe", fake_transcribe)
    response = client.post("/asr", json={"audio_id": audio_id})
    assert response.status_code == 504
    assert response.json()["error"]["code"] == "UPSTREAM_TIMEOUT"


def test_asr_upstream_error(client, monkeypatch):
    audio_id = save_upload(b"webm-bytes")

    async def fake_transcribe(_audio_bytes: bytes) -> str:
        raise AppError(502, "UPSTREAM_ERROR", "语音识别服务暂时不可用，请稍后重试。", "asr")

    monkeypatch.setattr("api.asr.transcribe", fake_transcribe)
    response = client.post("/asr", json={"audio_id": audio_id})
    assert response.status_code == 502
    assert response.json()["error"]["code"] == "UPSTREAM_ERROR"
