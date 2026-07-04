from __future__ import annotations

import hashlib
import re
from typing import Any

SENSITIVE_KEYS = {"api_key", "authorization", "cookie", "set-cookie", "account", "organization", "user", "email", "phone", "ip", "base_url", "url", "prompt", "completion", "response", "text", "sample", "headers"}


def stable_hash(value: str, prefix: str = "h") -> str:
    return f"{prefix}_{hashlib.sha256(value.encode('utf-8', errors='ignore')).hexdigest()[:16]}"


def coarse_timestamp_bucket(ts: int | float | None, bucket_seconds: int = 86400) -> int | None:
    if ts is None:
        return None
    try:
        value = int(float(ts))
    except (TypeError, ValueError):
        return None
    return value - (value % bucket_seconds)


def sanitize_value(value: Any, *, depth: int = 0) -> Any:
    if depth > 5:
        return "[MAX_DEPTH]"
    if isinstance(value, dict):
        clean: dict[str, Any] = {}
        for key, item in value.items():
            lowered = str(key).lower()
            if lowered in SENSITIVE_KEYS or any(token in lowered for token in ("secret", "token", "key", "auth", "cookie", "prompt", "completion", "header")):
                continue
            clean[str(key)] = sanitize_value(item, depth=depth + 1)
        return clean
    if isinstance(value, list):
        return [sanitize_value(item, depth=depth + 1) for item in value[:200]]
    if isinstance(value, str):
        return _scrub_string(value)
    if isinstance(value, (int, float, bool)) or value is None:
        return value
    return str(type(value).__name__)


def _scrub_string(value: str) -> str:
    text = value[:500]
    text = re.sub(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", "[EMAIL]", text)
    text = re.sub(r"\b(?:\+?\d[\d .-]{7,}\d)\b", "[PHONE_OR_ID]", text)
    text = re.sub(r"\b(?:sk|ak|pk|rk)-[A-Za-z0-9_-]{16,}\b", "[API_KEY]", text, flags=re.I)
    text = re.sub(r"\b\d{1,3}(?:\.\d{1,3}){3}\b", "[IP]", text)
    return text