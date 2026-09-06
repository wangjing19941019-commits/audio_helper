import logging
import re
import time
import unicodedata

import httpx

from config import BACKEND_ROOT, settings
from errors import AppError

logger = logging.getLogger(__name__)

_FENCE = re.compile(r"^```(?:\w+)?\s*|\s*```$", re.MULTILINE)


def _load_prompt() -> str:
    return (BACKEND_ROOT / "prompts" / "reply.txt").read_text(encoding="utf-8")


def _content_text(content: object) -> str | None:
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


def _clean_reply(raw: str) -> str:
    text = _FENCE.sub("", raw).strip().strip("\"“”")
    return re.sub(r"\s+", " ", text).strip()


def _fold(text: str) -> str:
    return re.sub(r"\s+", "", unicodedata.normalize("NFKC", text))


def _contains_folded(text: str, needle: str) -> bool:
    folded_needle = _fold(needle)
    return bool(folded_needle) and folded_needle in _fold(text)


def _replace_official(text: str, official: str) -> str:
    if not official or official in text:
        return text
    target = _fold(official)
    if not target:
        return text
    for start in range(len(text)):
        for end in range(start + 1, len(text) + 1):
            if _fold(text[start:end]) == target:
                return text[:start] + official + text[end:]
    return text


def validate_reply(text: str, name: str, address: str) -> str:
    cleaned = _clean_reply(text)
    if not cleaned:
        raise AppError(502, "MODEL_OUTPUT_INVALID", "生成推荐语失败，请稍后重试。", "finalize")
    name_ok = _contains_folded(cleaned, name)
    address_ok = _contains_folded(cleaned, address)
    if not name_ok or not address_ok:
        logger.warning(
            "stage=finalize step=reply_invalid name_match=%s address_match=%s",
            name_ok,
            address_ok,
        )
        raise AppError(502, "MODEL_OUTPUT_INVALID", "生成推荐语失败，请稍后重试。", "finalize")
    cleaned = _replace_official(cleaned, name)
    cleaned = _replace_official(cleaned, address)
    return cleaned


async def generate_reply(name: str, address: str, timeout: float) -> str:
    if not settings.deepseek_api_key:
        raise AppError(502, "UPSTREAM_ERROR", "推荐语服务未配置密钥。", "finalize")

    headers = {
        "Authorization": f"Bearer {settings.deepseek_api_key}",
        "Content-Type": "application/json",
    }
    body = {
        "model": settings.deepseek_model,
        "messages": [
            {"role": "system", "content": _load_prompt()},
            {
                "role": "user",
                "content": f"第一家店名：{name}\n第一家地址：{address}",
            },
        ],
        "thinking": {"type": "disabled"},
        "temperature": 0.3,
        "max_tokens": settings.reply_max_tokens,
    }

    started = time.monotonic()
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                settings.deepseek_url,
                headers=headers,
                json=body,
                timeout=timeout,
            )
    except (httpx.TimeoutException, httpx.ConnectTimeout, httpx.ReadTimeout) as exc:
        logger.warning(
            "stage=finalize elapsed_ms=%s error=%s step=reply",
            int((time.monotonic() - started) * 1000),
            type(exc).__name__,
        )
        raise AppError(504, "UPSTREAM_TIMEOUT", "生成推荐语超时，请稍后重试。", "finalize") from exc
    except httpx.HTTPError as exc:
        logger.warning(
            "stage=finalize elapsed_ms=%s error=%s step=reply",
            int((time.monotonic() - started) * 1000),
            type(exc).__name__,
        )
        raise AppError(502, "UPSTREAM_ERROR", "推荐语服务暂时不可用，请稍后重试。", "finalize") from exc

    logger.info(
        "stage=finalize status=%s elapsed_ms=%s step=reply",
        response.status_code,
        int((time.monotonic() - started) * 1000),
    )
    if response.status_code >= 400:
        raise AppError(502, "UPSTREAM_ERROR", "推荐语服务暂时不可用，请稍后重试。", "finalize")
    try:
        payload = response.json()
    except ValueError as exc:
        raise AppError(502, "UPSTREAM_ERROR", "推荐语服务返回无法解析。", "finalize") from exc

    choices = payload.get("choices") if isinstance(payload, dict) else None
    if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
        raise AppError(502, "MODEL_OUTPUT_INVALID", "生成推荐语失败，请稍后重试。", "finalize")
    message = choices[0].get("message")
    if not isinstance(message, dict):
        raise AppError(502, "MODEL_OUTPUT_INVALID", "生成推荐语失败，请稍后重试。", "finalize")
    content = _content_text(message.get("content"))
    if not isinstance(content, str) or not content.strip():
        raise AppError(502, "MODEL_OUTPUT_INVALID", "生成推荐语失败，请稍后重试。", "finalize")
    return validate_reply(content, name, address)
