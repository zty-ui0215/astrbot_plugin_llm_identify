from __future__ import annotations

from dataclasses import dataclass

from ..adapters.base import GenerateAdapter
from ..capture import Trace


@dataclass(frozen=True)
class ContextProbeCase:
    probe_id: str
    prompt: str
    expected_sentinels: tuple[str, ...]


class ContextWindowProbePack:
    category = "context"

    def __init__(self, *, target_tokens: int = 4096) -> None:
        self.target_tokens = max(512, int(target_tokens))

    def build_cases(self) -> list[ContextProbeCase]:
        filler_unit = " audit-context-padding-0001 audit-context-padding-0002 audit-context-padding-0003"
        short = "CTX-SENTINEL-SHORT"
        early = "CTX-SENTINEL-EARLY"
        middle = "CTX-SENTINEL-MIDDLE"
        late = "CTX-SENTINEL-LATE"
        quarter = max(16, self.target_tokens // 4)
        early_filler = filler_unit * max(1, quarter // 6)
        middle_filler = filler_unit * max(1, quarter // 4)
        late_filler = filler_unit * max(1, quarter // 3)
        return [
            ContextProbeCase(
                probe_id="context_short_sentinel",
                prompt=(
                    f"Remember sentinel {short}. Return JSON only with key sentinels containing exactly "
                    f"the sentinel you can read."
                ),
                expected_sentinels=(short,),
            ),
            ContextProbeCase(
                probe_id="context_window_sentinels",
                prompt=(
                    f"BEGIN AUDIT CONTEXT. Early marker: {early}.\n"
                    f"{early_filler}\n"
                    f"Middle marker: {middle}.\n"
                    f"{middle_filler}\n"
                    f"Late marker: {late}.\n"
                    f"{late_filler}\n"
                    "END AUDIT CONTEXT. Return JSON only with keys sentinels and missing. "
                    "The sentinels array must list every CTX-SENTINEL marker still visible in the context."
                ),
                expected_sentinels=(early, middle, late),
            ),
            ContextProbeCase(
                probe_id="context_boundary_pressure",
                prompt=(
                    f"High-priority audit marker: {early}. "
                    + (filler_unit * max(1, self.target_tokens // 3))
                    + f" Final audit marker: {late}. Return JSON only with sentinels that are present."
                ),
                expected_sentinels=(early, late),
            ),
        ]

    async def run(self, adapter: GenerateAdapter) -> list[Trace]:
        traces: list[Trace] = []
        for case in self.build_cases():
            before = len(adapter.trace_store.traces)
            await adapter.generate(case.prompt, probe_id=case.probe_id, category=self.category)
            traces.extend(adapter.trace_store.traces[before:])
        return traces
