from __future__ import annotations

import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from ..capture import TraceStore
from ..models import ModelReply
from ..utils import rough_token_estimate


GenerateFn = Callable[..., Awaitable[ModelReply]]


@dataclass
class GenerateAdapter:
    adapter_type: str
    provider_id: str
    claimed_model: str
    generate_fn: GenerateFn
    trace_store: TraceStore

    async def generate(
        self,
        prompt: str,
        *,
        probe_id: str,
        category: str,
        **kwargs: Any,
    ) -> ModelReply:
        started = time.perf_counter()
        reply = await self.generate_fn(prompt, **kwargs)
        latency_ms = int((time.perf_counter() - started) * 1000)
        self.trace_store.record(
            probe_id=probe_id,
            category=category,
            prompt_estimate=rough_token_estimate(prompt),
            reply=reply,
            latency_ms=latency_ms,
            request_options={key: _safe_option_value(value) for key, value in kwargs.items()},
        )
        return reply


def _safe_option_value(value: Any) -> Any:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, (list, tuple)):
        return [_safe_option_value(item) for item in value[:8]]
    if isinstance(value, dict):
        return {str(key): _safe_option_value(item) for key, item in list(value.items())[:16]}
    return type(value).__name__
