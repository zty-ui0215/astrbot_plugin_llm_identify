from __future__ import annotations

from typing import Any

from ..models import ModelReply, TokenSnapshot
from .trace_normalization import normalize_reply_meta, normalize_usage


def reply_from_astrbot_response(response: Any) -> ModelReply:
    raw = getattr(response, "raw_completion", None)
    return ModelReply(
        text=_extract_text(response),
        usage=_extract_usage(response),
        response_id=_string_attr(response, "id"),
        raw_type=type(raw).__name__ if raw is not None else type(response).__name__,
        meta=normalize_reply_meta(_extract_response_meta(response)),
    )


def _extract_usage(response: Any) -> TokenSnapshot | None:
    usage = getattr(response, "usage", None)
    if usage is None and isinstance(response, dict):
        usage = response.get("usage")
    raw = getattr(response, "raw_completion", None)
    if usage is None:
        usage = _read_any(raw, "usage") or _read_any(raw, "usageMetadata")
    if usage is None:
        return None

    def read(*names: str) -> int | None:
        for name in names:
            value = _read_any(usage, name)
            if value is None:
                continue
            try:
                return int(value)
            except (TypeError, ValueError):
                return None
        return None

    input_tokens = read("input", "prompt_tokens", "input_tokens", "promptTokenCount")
    output_tokens = read("output", "completion_tokens", "output_tokens", "candidatesTokenCount")
    total_tokens = read("total", "total_tokens", "totalTokenCount")
    if total_tokens is None and input_tokens is not None and output_tokens is not None:
        total_tokens = input_tokens + output_tokens
    normalized, _ = normalize_usage(_usage_to_dict(usage))
    return normalized or TokenSnapshot(input=input_tokens, output=output_tokens, total=total_tokens)


def _extract_response_meta(response: Any) -> dict[str, Any]:
    raw = getattr(response, "raw_completion", None)
    meta: dict[str, Any] = {
        "response_type": type(response).__name__,
        "raw_type": type(raw).__name__ if raw is not None else "",
    }
    for key in ("id", "model", "object", "type", "created", "role", "stop_reason", "finish_reason", "modelVersion", "responseId"):
        value = _read_any(raw, key)
        if value is not None:
            meta[key] = str(value)
    usage = _read_any(raw, "usage") or _read_any(raw, "usageMetadata")
    if usage is not None:
        raw_usage: dict[str, Any] = {}
        for key in ("prompt_tokens", "completion_tokens", "total_tokens", "input_tokens", "output_tokens", "promptTokenCount", "candidatesTokenCount", "totalTokenCount", "cached_tokens", "cached_input_tokens", "cachedContentTokenCount"):
            value = _read_any(usage, key)
            if value is not None:
                raw_usage[key] = value
        meta["raw_usage"] = raw_usage
        meta["raw_usage_type"] = type(usage).__name__
    return meta


def _extract_text(response: Any) -> str:
    if response is None:
        return ""
    if isinstance(response, str):
        return response
    for attr in ("completion_text", "text", "content", "result"):
        value = getattr(response, attr, None)
        if isinstance(value, str):
            return value
    if isinstance(response, dict):
        for key in ("completion_text", "text", "content", "result"):
            value = response.get(key)
            if isinstance(value, str):
                return value
    return str(response)


def _string_attr(response: Any, attr: str) -> str | None:
    value = getattr(response, attr, None)
    if value is None and isinstance(response, dict):
        value = response.get(attr)
    return str(value) if value else None


def _read_any(obj: Any, key: str) -> Any:
    if obj is None:
        return None
    if isinstance(obj, dict):
        return obj.get(key)
    return getattr(obj, key, None)


def _usage_to_dict(usage: Any) -> dict[str, Any]:
    if usage is None:
        return {}
    if isinstance(usage, dict):
        return dict(usage)
    values: dict[str, Any] = {}
    for key in (
        "input", "output", "total", "prompt_tokens", "completion_tokens", "total_tokens",
        "input_tokens", "output_tokens", "promptTokenCount", "candidatesTokenCount",
        "totalTokenCount", "cached_tokens", "cached_input_tokens", "cachedContentTokenCount",
    ):
        value = getattr(usage, key, None)
        if value is not None:
            values[key] = value
    return values