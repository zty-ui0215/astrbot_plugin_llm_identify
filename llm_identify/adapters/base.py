from __future__ import annotations

import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from ..capture import TraceStore
from ..models import ModelReply
from ..utils import rough_token_estimate


GenerateFn = Callable[..., Awaitable[ModelReply]]
CountTokensFn = Callable[[str], Awaitable[dict[str, Any]]]


@dataclass
class GenerateAdapter:
    adapter_type: str
    provider_id: str
    claimed_model: str
    generate_fn: GenerateFn
    trace_store: TraceStore
    count_tokens_fn: CountTokensFn | None = None

    async def generate(
        self,
        prompt: str,
        *,
        probe_id: str,
        category: str,
        **kwargs: Any,
    ) -> ModelReply:
        native_count = await self._native_count(prompt)
        started = time.perf_counter()
        reply = await self.generate_fn(prompt, **kwargs)
        latency_ms = int((time.perf_counter() - started) * 1000)
        if native_count is not None:
            reply.meta["native_token_count"] = native_count
        self.trace_store.record(
            probe_id=probe_id,
            category=category,
            prompt_estimate=rough_token_estimate(prompt),
            reply=reply,
            latency_ms=latency_ms,
            request_options={key: _safe_option_value(value) for key, value in kwargs.items()},
        )
        return reply

    async def _native_count(self, prompt: str) -> dict[str, Any] | None:
        if self.count_tokens_fn is None:
            return None
        started = time.perf_counter()
        try:
            result = await self.count_tokens_fn(prompt)
            status = "ok"
            error = None
        except Exception as exc:
            result = {}
            status = "error"
            error = str(exc)
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        payload = {"status": status, "latency_ms": elapsed_ms, **_safe_count_payload(result)}
        if error:
            payload["error"] = error[:300]
        return payload


def _safe_option_value(value: Any) -> Any:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, (list, tuple)):
        return [_safe_option_value(item) for item in value[:8]]
    if isinstance(value, dict):
        return {str(key): _safe_option_value(item) for key, item in list(value.items())[:16]}
    return type(value).__name__


def _safe_count_payload(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {"raw_type": type(value).__name__}
    allowed = {
        "provider",
        "endpoint",
        "input_tokens",
        "total_tokens",
        "billable_tokens",
        "cached_tokens",
        "raw_usage",
        "raw_keys",
        "degraded_reason",
    }
    return {str(key): _safe_option_value(item) for key, item in value.items() if str(key) in allowed}