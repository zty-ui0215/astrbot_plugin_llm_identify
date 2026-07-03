from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from ..adapters.base import GenerateAdapter
from ..capture import Trace
from ..utils import rough_token_estimate


@dataclass(frozen=True)
class TokenProbeCase:
    probe_id: str
    prompt: str
    expected_output: str = "OK"
    options: dict[str, Any] | None = None


class TokenAuditProbePack:
    category = "token"

    def build_cases(self) -> list[TokenProbeCase]:
        nonce = uuid.uuid4().hex[:10]
        repeated_prefix = "alpha beta gamma delta " * 80
        return [
            TokenProbeCase(
                "usage_ascii_short",
                "Reply with exactly OK. Audit text: The quick brown fox jumps over 13 lazy dogs.",
            ),
            TokenProbeCase(
                "usage_cjk_mixed",
                "Reply with exactly OK. Audit text: model audit mixes escaped CJK characters \u6a21\u578b\u771f\u5b9e\u6027\u68c0\u6d4b, English words, digits 12345, and punctuation.",
            ),
            TokenProbeCase(
                "usage_unicode_edge",
                "Reply with exactly OK. Audit text: emoji \U0001f600\U0001f680, combining e\u0301, zero-width A\u200bB, full-width \uff21\uff22\uff23, JSON braces {\"x\":1}.",
            ),
            TokenProbeCase(
                "usage_long_1",
                "Reply with exactly OK. Audit text: " + ("red green blue " * 90),
            ),
            TokenProbeCase(
                "usage_long_2",
                "Reply with exactly OK. Audit text: " + ("red green blue " * 180),
            ),
            TokenProbeCase(
                "cache_prefix_plain",
                "Reply with exactly OK. Shared prefix: " + repeated_prefix + " End marker: CACHE_PLAIN.",
            ),
            TokenProbeCase(
                "cache_prefix_nonce",
                "Reply with exactly OK. Shared prefix: " + repeated_prefix + f" End marker nonce: {nonce}.",
            ),
            TokenProbeCase(
                "output_short",
                "Reply with exactly one word: short.",
                options={"max_tokens": 8},
            ),
            TokenProbeCase(
                "output_long",
                "Write exactly four short bullet points about synthetic model-audit probes. Do not mention policies.",
                options={"max_tokens": 120},
            ),
        ]

    async def run(self, adapter: GenerateAdapter) -> list[Trace]:
        traces: list[Trace] = []
        for case in self.build_cases():
            before = len(adapter.trace_store.traces)
            await adapter.generate(
                case.prompt,
                probe_id=case.probe_id,
                category=self.category,
                **(case.options or {}),
            )
            traces.extend(adapter.trace_store.traces[before:])
        return traces


def token_case_estimates(cases: list[TokenProbeCase]) -> dict[str, int]:
    return {case.probe_id: rough_token_estimate(case.prompt) for case in cases}

