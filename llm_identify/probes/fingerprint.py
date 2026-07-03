from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..adapters.base import GenerateAdapter
from ..capture import Trace
from ..rules import ProbeRule, load_rules


@dataclass(frozen=True)
class FingerprintProbeCase:
    probe_id: str
    method: str
    prompt: str
    options: dict[str, Any] | None = None


class FingerprintProbePack:
    category = "fingerprint"

    def __init__(self, *, profile: str = "standard", repeats: int = 3) -> None:
        self.profile = profile if profile in {"light", "standard", "exhaustive"} else "standard"
        self.repeats = max(1, min(8, int(repeats)))
        self.rules = load_rules()

    def build_cases(self) -> list[FingerprintProbeCase]:
        return [self._case_from_rule(rule) for rule in self.rules.probe_rules if rule.enabled_for(self.profile)]

    async def run(self, adapter: GenerateAdapter) -> list[Trace]:
        traces: list[Trace] = []
        cases = self.build_cases()
        for repeat in range(self.repeats):
            for case in cases:
                before = len(adapter.trace_store.traces)
                prompt = f"{case.prompt}\nAudit nonce: fp-{repeat}-{case.probe_id}."
                await adapter.generate(
                    prompt,
                    probe_id=f"{case.probe_id}__r{repeat}",
                    category=self.category,
                    **(case.options or {}),
                )
                traces.extend(adapter.trace_store.traces[before:])
        return traces

    @staticmethod
    def _case_from_rule(rule: ProbeRule) -> FingerprintProbeCase:
        return FingerprintProbeCase(
            probe_id=rule.rule_id,
            method=rule.method,
            prompt=rule.prompt,
            options=rule.options,
        )
