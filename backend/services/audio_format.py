from errors import AppError

_CONTENT_TYPE_MAP = {
    "audio/wav": ("wav", "audio/wav"),
    "audio/x-wav": ("wav", "audio/wav"),
    "audio/wave": ("wav", "audio/wav"),
    "audio/mpeg": ("mp3", "audio/mpeg"),
    "audio/mp3": ("mp3", "audio/mpeg"),
    "audio/ogg": ("ogg", "audio/ogg"),
    "audio/webm": ("webm", "audio/webm"),
    "audio/mp4": ("m4a", "audio/mp4"),
    "audio/aac": ("aac", "audio/aac"),
}


def sniff_audio_format(content: bytes, content_type: str = "") -> tuple[str, str]:
    if len(content) < 12:
        raise AppError(502, "UPSTREAM_ERROR", "语音文件无法识别，请稍后重试。", "finalize")
    if content.startswith(b"RIFF") and content[8:12] == b"WAVE":
        return "wav", "audio/wav"
    if content.startswith(b"ID3") or content[:2] in {b"\xff\xfb", b"\xff\xf3", b"\xff\xf2", b"\xff\xfa"}:
        return "mp3", "audio/mpeg"
    if content.startswith(b"OggS"):
        return "ogg", "audio/ogg"
    if content.startswith(b"\x1a\x45\xdf\xa3"):
        return "webm", "audio/webm"
    if content[4:8] == b"ftyp":
        return "m4a", "audio/mp4"

    mime = content_type.split(";")[0].strip().lower()
    mapped = _CONTENT_TYPE_MAP.get(mime)
    if mapped:
        return mapped
    raise AppError(502, "UPSTREAM_ERROR", "语音文件无法识别，请稍后重试。", "finalize")
