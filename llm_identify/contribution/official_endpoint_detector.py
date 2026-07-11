from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable
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


def detect_official_provider_endpoint(provider: Any) -> OfficialEndpoint | None:
    """Resolve an AstrBot provider's effective API URL without relying on its display name."""
    client = _provider_client(provider)
    client_urls = _provider_base_url_candidates(client) if client is not None else []
    if client_urls:
        for base_url in client_urls:
            endpoint = detect_official_endpoint(base_url)
            if endpoint is not None:
                return endpoint
        return None
    for base_url in _provider_base_url_candidates(provider):
        endpoint = detect_official_endpoint(base_url)
        if endpoint is not None:
            return endpoint
    return None


def _provider_client(provider: Any) -> Any:
    if isinstance(provider, tuple) and len(provider) == 2:
        provider = provider[1]
    if isinstance(provider, dict):
        return provider.get("client")
    return getattr(provider, "client", None)


def _provider_base_url_candidates(provider: Any) -> list[str]:
    candidates: list[str] = []
    visited: set[int] = set()

    def collect(value: Any) -> None:
        if value is None or id(value) in visited:
            return
        visited.add(id(value))
        if isinstance(value, tuple) and len(value) == 2:
            collect(value[1])
            return
        if isinstance(value, dict):
            for key in ("api_base", "base_url", "api_base_url", "endpoint", "api_url"):
                append(value.get(key))
            collect(value.get("provider_config"))
            return
        for attr in ("api_base", "base_url", "api_base_url", "endpoint", "api_url"):
            append(getattr(value, attr, None))
        collect(getattr(value, "provider_config", None))

    def append(value: Any) -> None:
        if value is None:
            return
        text = str(value).strip()
        if text and text not in candidates:
            candidates.append(text)

    collect(provider)
    return candidates


def _with_scheme(value: str) -> str:
    text = value.strip()
    if not text:
        return ""
    if not text.startswith(("http://", "https://")):
        return "https://" + text
    return text
