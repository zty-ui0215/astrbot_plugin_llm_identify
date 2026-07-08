from __future__ import annotations

from typing import Any

from ..models import TokenSnapshot


SENSITIVE_HEADERS = {"authorization", "cookie", "set-cookie", "x-api-key", "api-key", "proxy-authorization"}


def normalize_usage(raw_usage: Any) -> tuple[TokenSnapshot | None, dict[str, Any]]:
    if not isinstance(raw_usage, dict) or not raw_usage:
        return None, {"available": False, "provider_shape": "missing", "raw_keys": []}

    input_tokens = _read_int(raw_usage, "input", "prompt_tokens", "input_tokens", "promptTokenCount", "inputTokenCount")
    output_tokens = _read_int(raw_usage, "output", "completion_tokens", "output_tokens", "candidatesTokenCount", "outputTokenCount")
    total_tokens = _read_int(raw_usage, "total", "total_tokens", "totalTokenCount", "total_tokens_count")
    if total_tokens is None and input_tokens is not None and output_tokens is not None:
        total_tokens = input_tokens + output_tokens

    details = _usage_details(raw_usage)
    shape = _provider_shape(raw_usage)
    snapshot = None
    if input_tokens is not None or output_tokens is not None or total_tokens is not None:
        snapshot = TokenSnapshot(input=input_tokens, output=output_tokens, total=total_tokens)
    return snapshot, {
        "available": snapshot is not None,
        "provider_shape": shape,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total_tokens,
        "details": details,
        "raw_keys": sorted(str(key) for key in raw_usage.keys()),
    }


def normalize_headers(headers: Any) -> dict[str, Any]:
    if not isinstance(headers, dict):
        return {"present": False, "safe": {}, "signals": {}}
    safe: dict[str, str] = {}
    for key, value in headers.items():
        lowered = str(key).lower()
        if lowered in SENSITIVE_HEADERS:
            continue
        safe[str(key)] = str(value)
    lower_keys = {key.lower(): key for key in safe}
    signals = {
        "request_id": _first_header(safe, "x-request-id", "request-id", "x-amzn-requestid", "x-goog-request-id", "cf-ray"),
        "organization": bool(_first_header(safe, "openai-organization", "anthropic-organization")),
        "rate_limit": any("ratelimit" in key or "rate-limit" in key for key in lower_keys),
        "provider_hint": _provider_hint(lower_keys),
        "header_count": len(safe),
    }
    return {"present": bool(safe), "safe": safe, "signals": signals}


def normalize_sse_events(events: Any) -> dict[str, Any]:
    if not isinstance(events, list):
        return {"present": False, "event_count": 0, "event_types": []}
    event_types = [str(item) for item in events[:200]]
    malformed = sum(1 for item in event_types if item == "malformed")
    return {
        "present": bool(event_types),
        "event_count": len(event_types),
        "event_types": event_types,
        "done_seen": "[DONE]" in event_types,
        "malformed_count": malformed,
        "usage_event_seen": any("usage" in item.lower() for item in event_types),
    }


def normalize_reply_meta(meta: dict[str, Any], *, provider_hint: str | None = None) -> dict[str, Any]:
    normalized = dict(meta)
    usage, usage_meta = normalize_usage(meta.get("raw_usage"))
    if usage is not None:
        normalized["normalized_usage"] = usage_meta
    elif "normalized_usage" not in normalized:
        normalized["normalized_usage"] = usage_meta
    headers_meta = normalize_headers(meta.get("headers"))
    normalized["normalized_headers"] = headers_meta
    normalized["normalized_sse"] = normalize_sse_events(meta.get("sse_event_types"))
    normalized["provider_trace"] = {
        "provider_hint": provider_hint or headers_meta["signals"].get("provider_hint") or usage_meta.get("provider_shape") or "unknown",
        "response_id": meta.get("id") or meta.get("response_id"),
        "model": meta.get("model") or meta.get("modelVersion"),
        "finish_reason": meta.get("finish_reason") or meta.get("stop_reason") or meta.get("status"),
        "usage_shape": usage_meta.get("provider_shape"),
        "headers_present": headers_meta["present"],
        "sse_present": normalized["normalized_sse"]["present"],
    }
    return normalized


def _usage_details(raw_usage: dict[str, Any]) -> dict[str, int]:
    details: dict[str, int] = {}
    nested_sources = {
        "prompt_tokens_details": "input",
        "completion_tokens_details": "output",
        "input_token_details": "input",
        "output_token_details": "output",
    }
    for key, prefix in nested_sources.items():
        nested = raw_usage.get(key)
        if not isinstance(nested, dict):
            continue
        for nested_key, value in nested.items():
            parsed = _to_int(value)
            if parsed is not None:
                details[f"{prefix}_{nested_key}"] = parsed
    for key in ("cached_tokens", "cached_input_tokens", "cachedContentTokenCount", "thoughtsTokenCount", "reasoning_tokens", "audio_tokens"):
        parsed = _read_int(raw_usage, key)
        if parsed is not None:
            details[key] = parsed
    return details


def _provider_shape(raw_usage: dict[str, Any]) -> str:
    keys = set(raw_usage.keys())
    if {"prompt_tokens", "completion_tokens"} & keys:
        return "openai_chat"
    if {"input_tokens", "output_tokens"} & keys:
        return "openai_responses_or_anthropic"
    if {"promptTokenCount", "candidatesTokenCount"} & keys:
        return "gemini"
    if {"inputTokenCount", "outputTokenCount"} & keys:
        return "generic_camel"
    return "unknown"


def _first_header(headers: dict[str, str], *names: str) -> str | None:
    lowered = {key.lower(): value for key, value in headers.items()}
    for name in names:
        if name in lowered:
            return lowered[name]
    return None


def _provider_hint(lower_keys: dict[str, str]) -> str | None:
    joined = " ".join(lower_keys)
    if "openai" in joined or "x-request-id" in lower_keys:
        return "openai_like"
    if "anthropic" in joined:
        return "anthropic_like"
    if "x-goog" in joined or "google" in joined:
        return "google_like"
    return None


def _read_int(raw: dict[str, Any], *names: str) -> int | None:
    for name in names:
        value = raw.get(name)
        parsed = _to_int(value)
        if parsed is not None:
            return parsed
    return None


def _to_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
