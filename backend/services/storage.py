import json
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from config import settings
from errors import AppError


def _audio_dir() -> Path:
    path = Path(settings.storage_dir) / "audio"
    path.mkdir(parents=True, exist_ok=True)
    return path


def save_upload(content: bytes) -> str:
    audio_id = str(uuid.uuid4())
    audio_dir = _audio_dir()
    file_path = audio_dir / f"{audio_id}.webm"
    meta_path = audio_dir / f"{audio_id}.meta.json"
    file_path.write_bytes(content)
    meta = {
        "id": audio_id,
        "kind": "upload",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "ttl_hours": settings.audio_ttl_hours,
    }
    meta_path.write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
    return audio_id


def get_upload(audio_id: str, *, stage: str) -> bytes:
    if not audio_id or any(part in audio_id for part in ("/", "\\", "..")):
        raise AppError(404, "NOT_FOUND", "录音不存在或已过期，请重新录音。", stage)

    audio_dir = _audio_dir()
    meta_path = audio_dir / f"{audio_id}.meta.json"
    file_path = audio_dir / f"{audio_id}.webm"
    if not meta_path.exists() or not file_path.exists():
        raise AppError(404, "NOT_FOUND", "录音不存在或已过期，请重新录音。", stage)

    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        created_at = datetime.fromisoformat(meta["created_at"])
    except (OSError, json.JSONDecodeError, KeyError, ValueError) as exc:
        raise AppError(404, "NOT_FOUND", "录音不存在或已过期，请重新录音。", stage) from exc

    ttl_hours = meta.get("ttl_hours", settings.audio_ttl_hours)
    if datetime.now(timezone.utc) - created_at > timedelta(hours=ttl_hours):
        raise AppError(404, "NOT_FOUND", "录音不存在或已过期，请重新录音。", stage)
    if meta.get("kind") != "upload":
        raise AppError(404, "NOT_FOUND", "录音不存在或已过期，请重新录音。", stage)
    return file_path.read_bytes()


def delete_upload(audio_id: str) -> None:
    audio_dir = _audio_dir()
    for path in (audio_dir / f"{audio_id}.webm", audio_dir / f"{audio_id}.meta.json"):
        path.unlink(missing_ok=True)


def _search_dir() -> Path:
    path = Path(settings.storage_dir) / "search"
    path.mkdir(parents=True, exist_ok=True)
    return path


def save_search(payload: dict) -> str:
    search_id = str(uuid.uuid4())
    path = _search_dir() / f"{search_id}.json"
    record = {
        "id": search_id,
        "kind": "search",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "ttl_hours": settings.audio_ttl_hours,
        **payload,
    }
    path.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")
    return search_id


def get_search(search_id: str, *, stage: str) -> dict:
    if not search_id or any(part in search_id for part in ("/", "\\", "..")):
        raise AppError(404, "NOT_FOUND", "查询结果不存在或已过期，请重新查找店铺。", stage)

    path = _search_dir() / f"{search_id}.json"
    if not path.exists():
        raise AppError(404, "NOT_FOUND", "查询结果不存在或已过期，请重新查找店铺。", stage)

    try:
        record = json.loads(path.read_text(encoding="utf-8"))
        created_at = datetime.fromisoformat(record["created_at"])
    except (OSError, json.JSONDecodeError, KeyError, ValueError) as exc:
        raise AppError(404, "NOT_FOUND", "查询结果不存在或已过期，请重新查找店铺。", stage) from exc

    ttl_hours = record.get("ttl_hours", settings.audio_ttl_hours)
    if datetime.now(timezone.utc) - created_at > timedelta(hours=ttl_hours):
        raise AppError(404, "NOT_FOUND", "查询结果不存在或已过期，请重新查找店铺。", stage)
    if record.get("kind") != "search":
        raise AppError(404, "NOT_FOUND", "查询结果不存在或已过期，请重新查找店铺。", stage)
    return record


def save_tts(content: bytes, *, extension: str, content_type: str) -> str:
    audio_id = str(uuid.uuid4())
    audio_dir = _audio_dir()
    file_path = audio_dir / f"{audio_id}.{extension}"
    meta_path = audio_dir / f"{audio_id}.meta.json"
    file_path.write_bytes(content)
    meta = {
        "id": audio_id,
        "kind": "tts",
        "extension": extension,
        "content_type": content_type,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "ttl_hours": settings.audio_ttl_hours,
    }
    meta_path.write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
    return audio_id


def get_tts(audio_id: str, *, stage: str) -> tuple[bytes, str]:
    if not audio_id or any(part in audio_id for part in ("/", "\\", "..")):
        raise AppError(404, "NOT_FOUND", "音频不存在或已过期。", stage)

    audio_dir = _audio_dir()
    meta_path = audio_dir / f"{audio_id}.meta.json"
    if not meta_path.exists():
        raise AppError(404, "NOT_FOUND", "音频不存在或已过期。", stage)

    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        created_at = datetime.fromisoformat(meta["created_at"])
    except (OSError, json.JSONDecodeError, KeyError, ValueError) as exc:
        raise AppError(404, "NOT_FOUND", "音频不存在或已过期。", stage) from exc

    ttl_hours = meta.get("ttl_hours", settings.audio_ttl_hours)
    if datetime.now(timezone.utc) - created_at > timedelta(hours=ttl_hours):
        raise AppError(404, "NOT_FOUND", "音频不存在或已过期。", stage)
    if meta.get("kind") != "tts":
        raise AppError(404, "NOT_FOUND", "音频不存在或已过期。", stage)

    extension = meta.get("extension") or "wav"
    file_path = audio_dir / f"{audio_id}.{extension}"
    if not file_path.exists():
        raise AppError(404, "NOT_FOUND", "音频不存在或已过期。", stage)
    return file_path.read_bytes(), str(meta.get("content_type") or "application/octet-stream")


