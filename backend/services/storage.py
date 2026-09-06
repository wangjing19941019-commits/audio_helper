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
