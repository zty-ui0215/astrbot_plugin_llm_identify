from __future__ import annotations

import random
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

    def __init__(self, *, profile: str = "standard", repeats: int = 3, randomize: bool = True, probes_per_method: int = 2, seed: int | None = None) -> None:
        self.profile = profile if profile in {"light", "standard", "exhaustive"} else "standard"
        self.repeats = max(1, min(8, int(repeats)))
        self.randomize = bool(randomize)
        self.probes_per_method = max(1, min(8, int(probes_per_method)))
        self.seed = seed
        self.rules = load_rules()

    def build_cases(self) -> list[FingerprintProbeCase]:
        cases = [self._case_from_rule(rule) for rule in self.rules.probe_rules if rule.enabled_for(self.profile)]
        if self.profile == "exhaustive" or not self.randomize:
            return cases
        return self._sample_redundant_cases(cases)

    async def run(self, adapter: GenerateAdapter) -> list[Trace]:
        traces: list[Trace] = []
        rng = random.Random(self.seed)
        for repeat in range(self.repeats):
            cases = self.build_cases()
            if self.randomize:
                rng.shuffle(cases)
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

    def _sample_redundant_cases(self, cases: list[FingerprintProbeCase]) -> list[FingerprintProbeCase]:
        rng = random.Random(self.seed)
        by_method: dict[str, list[FingerprintProbeCase]] = {}
        for case in cases:
            by_method.setdefault(case.method, []).append(case)
        selected: list[FingerprintProbeCase] = []
        for method_cases in by_method.values():
            shuffled = list(method_cases)
            rng.shuffle(shuffled)
            selected.extend(shuffled[: min(len(shuffled), self.probes_per_method)])
        return selected

    @staticmethod
    def _case_from_rule(rule: ProbeRule) -> FingerprintProbeCase:
        return FingerprintProbeCase(
            probe_id=rule.rule_id,
            method=rule.method,
            prompt=rule.prompt,
            options=rule.options,
        )
