import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from config import settings


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


def delete_upload(audio_id: str) -> None:
    audio_dir = _audio_dir()
    for path in (audio_dir / f"{audio_id}.webm", audio_dir / f"{audio_id}.meta.json"):
        path.unlink(missing_ok=True)
