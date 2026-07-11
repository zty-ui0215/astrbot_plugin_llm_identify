from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from ..models import ModelReply, TokenSnapshot


@dataclass
class Trace:
    probe_id: str
    category: str
    prompt_estimate: int
    reply: ModelReply
    latency_ms: int
    started_at: int
    request_options: dict[str, Any] = field(default_factory=dict)

    @property
    def usage(self) -> TokenSnapshot | None:
        return self.reply.usage


class TraceStore:
    def __init__(self) -> None:
        self.traces: list[Trace] = []

    def record(
        self,
        *,
        probe_id: str,
        category: str,
        prompt_estimate: int,
        reply: ModelReply,
        latency_ms: int,
        request_options: dict[str, Any] | None = None,
    ) -> Trace:
        trace = Trace(
            probe_id=probe_id,
            category=category,
            prompt_estimate=prompt_estimate,
            reply=reply,
            latency_ms=latency_ms,
            started_at=int(time.time()),
            request_options=request_options or {},
        )
        self.traces.append(trace)
        return trace


def build_trace_summary(traces: list[Trace]) -> dict[str, Any]:
    by_category: dict[str, int] = {}
    usage_count = 0
    latencies: list[int] = []
    raw_types: dict[str, int] = {}
    generation_errors: dict[str, int] = {}
    for trace in traces:
        by_category[trace.category] = by_category.get(trace.category, 0) + 1
        if trace.usage is not None:
            usage_count += 1
        if trace.latency_ms >= 0:
            latencies.append(trace.latency_ms)
        if trace.reply.raw_type:
            raw_types[trace.reply.raw_type] = raw_types.get(trace.reply.raw_type, 0) + 1
        generation_error = trace.reply.meta.get("generation_error")
        if isinstance(generation_error, dict):
            error_type = str(generation_error.get("type") or "Error")
            generation_errors[error_type] = generation_errors.get(error_type, 0) + 1
    return {
        "trace_count": len(traces),
        "by_category": by_category,
        "usage_trace_count": usage_count,
        "latency_ms_min": min(latencies) if latencies else None,
        "latency_ms_max": max(latencies) if latencies else None,
        "latency_ms_avg": round(sum(latencies) / len(latencies), 2) if latencies else None,
        "raw_types": raw_types,
        "generation_error_count": sum(generation_errors.values()),
        "generation_errors_by_type": generation_errors,
    }
