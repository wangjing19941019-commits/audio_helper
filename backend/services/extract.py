import json
import logging
import re
import time

import httpx
from pydantic import ValidationError

from config import BACKEND_ROOT, settings
from errors import AppError
from schemas import ExtractData, ExtractModelOutput

logger = logging.getLogger(__name__)

REQUIRED_KEYS = {
    "city_a",
    "address_a",
    "city_b",
    "address_b",
    "category",
    "party_count",
    "incomplete_reason",
}
VAGUE_PLACES = {"我家", "你家", "他家", "公司", "单位", "学校", "家门口", "家"}
DEFAULT_CATEGORY = "咖啡店"


def _load_prompt() -> str:
    return (BACKEND_ROOT / "prompts" / "extract.txt").read_text(encoding="utf-8")


def _strip_json_fence(raw: str) -> str:
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, count=1, flags=re.IGNORECASE)
        text = re.sub(r"\s*```$", "", text)
    return text.strip()


def _blank(value: str | None) -> bool:
    return value is None or not str(value).strip()


def normalize_city(name: str) -> str:
    text = name.strip()
    if text.endswith("市"):
        text = text[:-1]
    return text


def cities_equal(left: str, right: str) -> bool:
    a = normalize_city(left)
    b = normalize_city(right)
    return bool(a) and a == b


def _is_vague_address(address: str) -> bool:
    return address.strip() in VAGUE_PLACES


def _normalize_category(category: str) -> str:
    text = category.strip()
    if text in {"喝咖啡", "咖啡"}:
        return DEFAULT_CATEGORY
    return text


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


def _parse_model_json(content: str) -> dict:
    try:
        parsed = json.loads(_strip_json_fence(content))
    except json.JSONDecodeError as exc:
        raise AppError(502, "MODEL_OUTPUT_INVALID", "整理地点信息失败，请稍后重试。", "extract") from exc
    if not isinstance(parsed, dict):
        raise AppError(502, "MODEL_OUTPUT_INVALID", "整理地点信息失败，请稍后重试。", "extract")
    if not REQUIRED_KEYS.issubset(parsed.keys()):
        raise AppError(502, "MODEL_OUTPUT_INVALID", "整理地点信息失败，请稍后重试。", "extract")
    try:
        ExtractModelOutput.model_validate(parsed)
    except ValidationError as exc:
        raise AppError(502, "MODEL_OUTPUT_INVALID", "整理地点信息失败，请稍后重试。", "extract") from exc
    return parsed


def _filled_text(value: str | None, fallback: str | None = None) -> str | None:
    if not _blank(value):
        return value.strip()
    if fallback is not None and not _blank(fallback):
        return fallback.strip()
    return None


def evaluate_extract(parsed: dict, page_city: str) -> ExtractData:
    try:
        model = ExtractModelOutput.model_validate(parsed)
    except ValidationError as exc:
        raise AppError(502, "MODEL_OUTPUT_INVALID", "整理地点信息失败，请稍后重试。", "extract") from exc

    city_a = _filled_text(model.city_a, page_city)
    city_b = _filled_text(model.city_b, page_city)
    address_a = _filled_text(model.address_a)
    address_b = _filled_text(model.address_b)
    if model.category is None:
        category = DEFAULT_CATEGORY
    elif not model.category.strip():
        raise AppError(502, "MODEL_OUTPUT_INVALID", "整理地点信息失败，请稍后重试。", "extract")
    else:
        category = _normalize_category(model.category)

    if model.party_count is None or model.party_count != 2:
        raise AppError(
            422,
            "INVALID_PARTY_COUNT",
            "第一版只支持两个人，请重新说明两个人的位置。",
            "extract",
        )
    if _blank(city_a) or _blank(city_b) or _blank(address_a) or _blank(address_b):
        raise AppError(
            422,
            "INCOMPLETE_ADDRESS",
            "请补充两个人的具体地点，不要只说我家或公司。",
            "extract",
        )
    if _is_vague_address(address_a) or _is_vague_address(address_b):
        raise AppError(
            422,
            "INCOMPLETE_ADDRESS",
            "请补充两个人的具体地点，不要只说我家或公司。",
            "extract",
        )
    if not cities_equal(city_a, city_b):
        raise AppError(
            422,
            "CROSS_CITY",
            "第一版只支持同一座城市，请重新表达。",
            "extract",
        )

    return ExtractData(
        city_a=city_a,
        address_a=address_a,
        city_b=city_b,
        address_b=address_b,
        category=category,
    )


def _message_content(payload: dict) -> str:
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        raise AppError(502, "MODEL_OUTPUT_INVALID", "整理地点信息失败，请稍后重试。", "extract")
    choice = choices[0] if isinstance(choices[0], dict) else None
    if not isinstance(choice, dict):
        raise AppError(502, "MODEL_OUTPUT_INVALID", "整理地点信息失败，请稍后重试。", "extract")
    if choice.get("finish_reason") == "length":
        raise AppError(502, "MODEL_OUTPUT_INVALID", "整理地点信息失败，请稍后重试。", "extract")
    message = choice.get("message")
    if not isinstance(message, dict):
        raise AppError(502, "MODEL_OUTPUT_INVALID", "整理地点信息失败，请稍后重试。", "extract")
    content = _content_text(message.get("content"))
    if not isinstance(content, str) or not content.strip():
        raise AppError(502, "MODEL_OUTPUT_INVALID", "整理地点信息失败，请稍后重试。", "extract")
    return content


async def extract_slots(text: str, city: str) -> ExtractData:
    if not settings.deepseek_api_key:
        raise AppError(502, "UPSTREAM_ERROR", "信息提取服务未配置密钥。", "extract")
    if not text.strip() or not city.strip():
        raise AppError(422, "VALIDATION_ERROR", "请求缺少必填字段，或字段类型不正确。", "extract")

    headers = {
        "Authorization": f"Bearer {settings.deepseek_api_key}",
        "Content-Type": "application/json",
    }
    body = {
        "model": settings.deepseek_model,
        "messages": [
            {"role": "system", "content": _load_prompt()},
            {"role": "user", "content": f"页面城市：{city.strip()}\n用户原话：{text.strip()}"},
        ],
        "thinking": {"type": "disabled"},
        "response_format": {"type": "json_object"},
        "temperature": 0,
        "max_tokens": settings.extract_max_tokens,
    }

    started = time.monotonic()
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                settings.deepseek_url,
                headers=headers,
                json=body,
                timeout=settings.extract_upstream_timeout_s,
            )
    except (httpx.TimeoutException, httpx.ConnectTimeout, httpx.ReadTimeout) as exc:
        logger.warning(
            "stage=extract elapsed_ms=%s error=%s",
            int((time.monotonic() - started) * 1000),
            type(exc).__name__,
        )
        raise AppError(504, "UPSTREAM_TIMEOUT", "整理地点信息超时，请稍后重试。", "extract") from exc
    except httpx.HTTPError as exc:
        logger.warning(
            "stage=extract elapsed_ms=%s error=%s",
            int((time.monotonic() - started) * 1000),
            type(exc).__name__,
        )
        raise AppError(502, "UPSTREAM_ERROR", "信息提取服务暂时不可用，请稍后重试。", "extract") from exc

    logger.info(
        "stage=extract status=%s elapsed_ms=%s",
        response.status_code,
        int((time.monotonic() - started) * 1000),
    )
    if response.status_code >= 400:
        raise AppError(502, "UPSTREAM_ERROR", "信息提取服务暂时不可用，请稍后重试。", "extract")

    try:
        payload = response.json()
    except ValueError as exc:
        raise AppError(502, "UPSTREAM_ERROR", "信息提取服务返回无法解析。", "extract") from exc

    raw = _parse_model_json(_message_content(payload))
    return evaluate_extract(raw, city)
