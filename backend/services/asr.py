import base64
import logging
import re
import time

import httpx

from config import settings
from errors import AppError

logger = logging.getLogger(__name__)

_PUNCT_ONLY = re.compile(r"^[\s\W_]*$", re.UNICODE)


def _is_empty_transcript(text: str) -> bool:
    if not text or not text.strip():
        return True
    stripped = re.sub(r"[\s\W_]+", "", text, flags=re.UNICODE)
    return not stripped


def _extract_text(payload: dict) -> str | None:
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        return None
    message = choices[0].get("message") if isinstance(choices[0], dict) else None
    if not isinstance(message, dict):
        return None
    content = message.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict) and isinstance(item.get("text"), str):
                parts.append(item["text"])
        return "".join(parts) if parts else None
    return None


async def transcribe(audio_bytes: bytes) -> str:
    if not settings.bailian_api_key:
        raise AppError(502, "UPSTREAM_ERROR", "语音识别服务未配置密钥。", "asr")

    encoded = base64.b64encode(audio_bytes).decode("ascii")
    data_url = f"data:audio/webm;base64,{encoded}"
    if len(data_url.encode("utf-8")) > settings.max_asr_base64_bytes:
        raise AppError(
            413,
            "PAYLOAD_TOO_LARGE",
            "编码后的音频超过识别服务限制，请缩短录音后重试。",
            "asr",
        )

    headers = {
        "Authorization": f"Bearer {settings.bailian_api_key}",
        "Content-Type": "application/json",
    }
    body = {
        "model": settings.bailian_asr_model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_audio",
                        "input_audio": {"data": data_url},
                    }
                ],
            }
        ],
        "asr_options": {"language": "zh", "enable_itn": True},
    }

    started = time.monotonic()
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                settings.bailian_asr_url,
                headers=headers,
                json=body,
                timeout=settings.asr_upstream_timeout_s,
            )
    except (httpx.TimeoutException, httpx.ConnectTimeout, httpx.ReadTimeout) as exc:
        logger.warning(
            "stage=asr elapsed_ms=%s error=%s",
            int((time.monotonic() - started) * 1000),
            type(exc).__name__,
        )
        raise AppError(504, "UPSTREAM_TIMEOUT", "语音识别超时，请稍后重试。", "asr") from exc
    except httpx.HTTPError as exc:
        logger.warning(
            "stage=asr elapsed_ms=%s error=%s",
            int((time.monotonic() - started) * 1000),
            type(exc).__name__,
        )
        raise AppError(502, "UPSTREAM_ERROR", "语音识别服务暂时不可用，请稍后重试。", "asr") from exc

    logger.info(
        "stage=asr status=%s elapsed_ms=%s",
        response.status_code,
        int((time.monotonic() - started) * 1000),
    )
    if response.status_code >= 400:
        raise AppError(502, "UPSTREAM_ERROR", "语音识别服务暂时不可用，请稍后重试。", "asr")

    try:
        payload = response.json()
    except ValueError as exc:
        raise AppError(502, "UPSTREAM_ERROR", "语音识别服务返回无法解析。", "asr") from exc

    text = _extract_text(payload)
    if text is None:
        raise AppError(502, "MODEL_OUTPUT_INVALID", "语音识别结果格式不符合约定。", "asr")
    if _is_empty_transcript(text):
        raise AppError(422, "EMPTY_TRANSCRIPT", "没有识别到有效文字，请重新说一遍。", "asr")
    return text.strip()
