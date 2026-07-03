from __future__ import annotations

import json
import re
from typing import Any


def detect_model_family(claimed_model: str, provider_id: str = "") -> str:
    text = f"{claimed_model} {provider_id}".lower()
    if any(token in text for token in ("claude", "anthropic")):
        return "claude"
    if any(token in text for token in ("gemini", "google")):
        return "gemini"
    if any(token in text for token in ("qwen", "qwq", "qvq", "dashscope", "bailian")):
        return "qwen"
    if "deepseek" in text:
        return "deepseek"
    if any(token in text for token in ("glm", "zhipu")):
        return "glm"
    if any(token in text for token in ("gpt", "openai", "o1", "o3", "o4")):
        return "openai"
    return "generic"


def rough_token_estimate(text: str) -> int:
    ascii_words = len(re.findall(r"[A-Za-z0-9_]+", text))
    cjk_chars = len(re.findall(r"[\u4e00-\u9fff]", text))
    symbols = len(re.findall(r"[^\w\s\u4e00-\u9fff]", text))
    whitespace_groups = len(re.findall(r"\s+", text))
    return max(1, ascii_words + cjk_chars + max(1, symbols // 2) + max(0, whitespace_groups // 4))


def try_parse_json_object(text: str) -> dict[str, Any] | None:
    candidates = [text.strip()]
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        candidates.append(match.group(0))
    for candidate in candidates:
        try:
            value = json.loads(candidate)
        except Exception:
            continue
        if isinstance(value, dict):
            return value
    return None


def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def status_for_score(score: float) -> str:
    if score >= 0.8:
        return "pass"
    if score >= 0.5:
        return "warning"
    return "fail"


def shorten(value: str, limit: int = 420) -> str:
    text = str(value).strip()
    return text if len(text) <= limit else text[:limit] + "..."
