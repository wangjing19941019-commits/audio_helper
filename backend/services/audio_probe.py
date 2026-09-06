import json
import logging
import subprocess
from dataclasses import dataclass
from pathlib import Path

from config import settings
from errors import AppError

logger = logging.getLogger(__name__)


@dataclass
class ProbeResult:
    duration_s: float
    format_name: str
    codec_name: str


def _run_ffprobe(args: list[str], timeout: float) -> dict:
    try:
        completed = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except FileNotFoundError as exc:
        raise AppError(
            500,
            "INTERNAL_ERROR",
            "无法校验音频格式，请确认本机已安装 FFmpeg 且 ffprobe 在 PATH 中可用。",
            "upload",
        ) from exc
    except subprocess.TimeoutExpired as exc:
        raise AppError(504, "UPSTREAM_TIMEOUT", "音频校验超时，请缩短录音后重试。", "upload") from exc
    if completed.returncode != 0:
        logger.warning("stage=upload ffprobe_failed returncode=%s", completed.returncode)
        raise AppError(
            415,
            "UNSUPPORTED_MEDIA_TYPE",
            "仅支持浏览器录制的 WebM/Opus 音频，请更换浏览器后重试。",
            "upload",
        )
    try:
        return json.loads(completed.stdout or "{}")
    except json.JSONDecodeError as exc:
        raise AppError(
            415,
            "UNSUPPORTED_MEDIA_TYPE",
            "仅支持浏览器录制的 WebM/Opus 音频，请更换浏览器后重试。",
            "upload",
        ) from exc


def _parse_duration(raw: object) -> float | None:
    if raw in (None, "", "N/A"):
        return None
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return None
    if value < 0:
        return None
    return value


def _duration_from_packets(path: Path, timeout: float) -> float | None:
    payload = _run_ffprobe(
        [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "a:0",
            "-show_entries",
            "packet=pts_time,duration_time",
            "-print_format",
            "json",
            str(path),
        ],
        timeout=timeout,
    )
    last_end = None
    for packet in payload.get("packets") or []:
        pts = _parse_duration(packet.get("pts_time"))
        dur = _parse_duration(packet.get("duration_time")) or 0.0
        if pts is None:
            continue
        end = pts + dur
        last_end = end if last_end is None else max(last_end, end)
    return last_end


def probe_audio(path: Path) -> ProbeResult:
    payload = _run_ffprobe(
        [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "a:0",
            "-show_entries",
            "format=format_name,duration:stream=codec_name,codec_type,duration",
            "-print_format",
            "json",
            str(path),
        ],
        timeout=settings.ffprobe_timeout_s,
    )
    fmt = payload.get("format") or {}
    streams = payload.get("streams") or []
    audio_stream = next((item for item in streams if item.get("codec_type") == "audio"), None)
    if audio_stream is None:
        raise AppError(
            415,
            "UNSUPPORTED_MEDIA_TYPE",
            "仅支持浏览器录制的 WebM/Opus 音频，请更换浏览器后重试。",
            "upload",
        )

    format_name = str(fmt.get("format_name") or "")
    codec_name = str(audio_stream.get("codec_name") or "").lower()
    duration = _parse_duration(fmt.get("duration"))
    if duration is None:
        duration = _parse_duration(audio_stream.get("duration"))
    if duration is None:
        # Browser WebM often omits EBML Duration; packet timestamps still give length.
        duration = _duration_from_packets(path, timeout=max(settings.ffprobe_timeout_s, 4.0))
    if duration is None:
        raise AppError(422, "INVALID_DURATION", "无法读取录音时长，请重新录制。", "upload")

    return ProbeResult(duration_s=duration, format_name=format_name, codec_name=codec_name)


def validate_upload_probe(probe: ProbeResult) -> None:
    names = {part.strip().lower() for part in probe.format_name.split(",")}
    if "webm" not in names or probe.codec_name != "opus":
        raise AppError(
            415,
            "UNSUPPORTED_MEDIA_TYPE",
            "仅支持浏览器录制的 WebM/Opus 音频，请更换浏览器后重试。",
            "upload",
        )
    if probe.duration_s < settings.min_duration_s or probe.duration_s > settings.max_duration_s:
        raise AppError(422, "INVALID_DURATION", "录音须在1到60秒之间，请重新录制。", "upload")
