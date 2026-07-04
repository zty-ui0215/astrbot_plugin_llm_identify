from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from typing import Any


EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
PHONE_RE = re.compile(r"(?<!\d)(?:\+?\d[\d\s().-]{6,}\d)(?!\d)")
API_KEY_RE = re.compile(r"\b(?:sk|ak|pk|rk|xoxb|ghp|github_pat)_[A-Za-z0-9_\-]{12,}\b")
ID_RE = re.compile(r"\b[A-Z0-9]{6,}[-_][A-Z0-9_-]{6,}\b", re.IGNORECASE)


@dataclass(frozen=True)
class RedactionPolicy:
    enabled: bool = True
    deterministic_hash: bool = True
    mask_json_fields: tuple[str, ...] = ("api_key", "authorization", "access_token", "refresh_token", "password", "secret")
    extra_patterns: tuple[str, ...] = field(default_factory=tuple)


def redact_value(value: Any, policy: RedactionPolicy | None = None) -> Any:
    policy = policy or RedactionPolicy()
    if not policy.enabled:
        return value
    if isinstance(value, str):
        return _redact_text(value, policy)
    if isinstance(value, list):
        return [redact_value(item, policy) for item in value]
    if isinstance(value, tuple):
        return [redact_value(item, policy) for item in value]
    if isinstance(value, dict):
        masked: dict[str, Any] = {}
        mask_fields = {field.lower() for field in policy.mask_json_fields}
        for key, item in value.items():
            key_text = str(key)
            if key_text.lower() in mask_fields:
                masked[key_text] = _token("field", str(item), policy)
            else:
                masked[key_text] = redact_value(item, policy)
        return masked
    return value


def redact_json_text(value: str, policy: RedactionPolicy | None = None) -> str:
    try:
        parsed = json.loads(value)
    except Exception:
        return _redact_text(value, policy or RedactionPolicy())
    return json.dumps(redact_value(parsed, policy), ensure_ascii=True, sort_keys=True)


def _redact_text(value: str, policy: RedactionPolicy) -> str:
    text = EMAIL_RE.sub(lambda match: _token("email", match.group(0), policy), value)
    text = PHONE_RE.sub(lambda match: _token("phone", match.group(0), policy), text)
    text = API_KEY_RE.sub(lambda match: _token("secret", match.group(0), policy), text)
    text = ID_RE.sub(lambda match: _token("id", match.group(0), policy), text)
    for index, pattern in enumerate(policy.extra_patterns):
        try:
            compiled = re.compile(pattern)
        except re.error:
            continue
        text = compiled.sub(lambda match: _token(f"custom{index}", match.group(0), policy), text)
    return text


def _token(kind: str, raw: str, policy: RedactionPolicy) -> str:
    if not policy.deterministic_hash:
        return f"[REDACTED:{kind}]"
    digest = hashlib.sha256(raw.encode("utf-8", errors="replace")).hexdigest()[:12]
    return f"[REDACTED:{kind}:{digest}]"
