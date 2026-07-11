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


class ProbeCircuitOpen(RuntimeError):
    """Raised after a probe failure proves the endpoint is unhealthy."""

    def __init__(self, *, probe_id: str, category: str, error_type: str, message: str, consecutive_errors: int) -> None:
        super().__init__(message)
        self.probe_id = probe_id
        self.category = category
        self.error_type = error_type
        self.message = message
        self.consecutive_errors = consecutive_errors


@dataclass
class GenerateAdapter:
    adapter_type: str
    provider_id: str
    claimed_model: str
    generate_fn: GenerateFn
    trace_store: TraceStore
    count_tokens_fn: CountTokensFn | None = None
    max_consecutive_errors: int = 3
    _consecutive_errors: int = 0

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
        try:
            reply = await self.generate_fn(prompt, **kwargs)
        except Exception as exc:
            self._consecutive_errors += 1
            error_type = type(exc).__name__
            error_message = "Probe request timed out." if isinstance(exc, TimeoutError) else "Probe request failed."
            reply = ModelReply(
                text="",
                raw_type="generation_error",
                meta={
                    "generation_error": {
                        "type": error_type,
                        "message": error_message,
                    }
                },
            )
        else:
            self._consecutive_errors = 0
            error_type = ""
            error_message = ""
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
        # Isolated timeouts and transport failures can be transient. Keep probing
        # until the configured consecutive-error threshold proves the endpoint
        # unhealthy; every failed request remains recorded as audit evidence.
        if self._consecutive_errors >= max(1, self.max_consecutive_errors):
            raise ProbeCircuitOpen(
                probe_id=probe_id,
                category=category,
                error_type=error_type,
                message=error_message,
                consecutive_errors=self._consecutive_errors,
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
