from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable
from urllib.parse import urlparse


DEFAULT_OFFICIAL_ENDPOINTS = {
    "api.openai.com": {"provider": "openai", "paths": ("/v1",)},
    "api.anthropic.com": {"provider": "anthropic", "paths": ("", "/v1")},
    "generativelanguage.googleapis.com": {"provider": "google", "paths": ("", "/v1", "/v1beta")},
    "api.mistral.ai": {"provider": "mistral", "paths": ("/v1",)},
    "api.cohere.com": {"provider": "cohere", "paths": ("", "/v1", "/v2")},
    "dashscope.aliyuncs.com": {"provider": "alibaba_bailian", "paths": ("/compatible-mode/v1", "/api/v1", "/v1")},
    "dashscope-intl.aliyuncs.com": {"provider": "alibaba_bailian", "paths": ("/compatible-mode/v1", "/api/v1", "/v1")},
    "api.deepseek.com": {"provider": "deepseek", "paths": ("", "/v1")},
    "ark.cn-beijing.volces.com": {"provider": "volcengine_ark", "paths": ("/api/v3", "/api/v3/chat/completions")},
    "open.bigmodel.cn": {"provider": "zhipu", "paths": ("/api/paas/v4",)},
    "api.moonshot.cn": {"provider": "moonshot", "paths": ("/v1",)},
    "api.minimax.chat": {"provider": "minimax", "paths": ("/v1",)},
    "api.siliconflow.cn": {"provider": "siliconflow", "paths": ("/v1",)},
}


@dataclass(frozen=True)
class OfficialEndpoint:
    provider: str
    host: str
    matched_path: str
    label: str


def detect_official_endpoint(base_url: str, allowlist: Iterable[str] | None = None) -> OfficialEndpoint | None:
    parsed = urlparse(_with_scheme(base_url or ""))
    if parsed.scheme != "https" or not parsed.hostname:
        return None
    host = parsed.hostname.lower().strip(".")
    path = (parsed.path or "").rstrip("/")
    endpoints = dict(DEFAULT_OFFICIAL_ENDPOINTS)
    for raw in allowlist or []:
        item = urlparse(_with_scheme(str(raw)))
        if item.scheme == "https" and item.hostname:
            endpoints[item.hostname.lower().strip(".")] = {"provider": item.hostname.lower().split(".")[0], "paths": ((item.path or "").rstrip("/"),)}
    spec = endpoints.get(host)
    if spec is None:
        return None
    for allowed_path in spec["paths"]:
        normalized = str(allowed_path).rstrip("/")
        if path == normalized or (normalized and path.startswith(normalized + "/")):
            return OfficialEndpoint(provider=str(spec["provider"]), host=host, matched_path=normalized, label=f"{spec['provider']} official endpoint")
    return None


def _with_scheme(value: str) -> str:
    text = value.strip()
    if not text:
        return ""
    if not text.startswith(("http://", "https://")):
        return "https://" + text
    return text
