from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Awaitable, Callable

from .adapters.base import GenerateAdapter
from .capture import Trace, TraceStore
from .branches import analyze_branch_evidence, branch_payload
from .corpus import TrustedCorpusSource
from .evidence import ExternalJudge, PublicKnowledgeSource, auxiliary_judge_prompt, collect_evidence_sources, parse_auxiliary_judgment
from .features import FingerprintFeatureBundle, MethodFingerprint, TokenAuditFeatures, analyze_fingerprint_traces, analyze_token_traces
from .models import AuditReport, ProbeResult
from .probes import ContextWindowProbePack, FingerprintProbePack, ProtocolProbePack, TokenAuditProbePack
from .scoring import build_report
from .scoring.fingerprint import FingerprintFusionResult, fuse_fingerprint_features


@dataclass
class AuditOptions:
    enable_protocol_probe: bool = True
    enable_token_probe: bool = False
    enable_context_probe: bool = False
    context_probe_target_tokens: int = 4096
    enable_fingerprint_probe: bool = False
    fingerprint_profile: str = "standard"
    fingerprint_repeats: int = 3
    randomize_fingerprint_probes: bool = True
    fingerprint_probes_per_method: int = 2
    fingerprint_probe_seed: int | None = None
    enable_auxiliary_llm_judge: bool = False
    auxiliary_judge_fn: Callable[[str], Awaitable[str]] | None = None
    auxiliary_judge_model: str = "auxiliary"
    external_judges: list[ExternalJudge] | None = None
    public_knowledge_sources: list[PublicKnowledgeSource] | None = None
    trusted_corpus_sources: list[TrustedCorpusSource] | None = None
    public_cache_dir: str | None = None
    traffic_mode: str = "mixed"
    thresholds: dict[str, float] | None = None
    strict_mode: bool = False
    language: str = "en-US"


class AuditEngine:
    def __init__(self, adapter: GenerateAdapter, options: AuditOptions | None = None) -> None:
        self.adapter = adapter
        self.options = options or AuditOptions()

    async def run(self) -> AuditReport:
        probe_results: list[ProbeResult] = []
        token_features: TokenAuditFeatures | None = None
        fingerprint_bundle: FingerprintFeatureBundle | None = None
        fingerprint_result: FingerprintFusionResult | None = None
        evidence_run = None
        branch_evidence = []
        context_truth_score = None
        prompt_injection_risk = 0.0

        if self.options.enable_protocol_probe:
            probe_results.extend(await ProtocolProbePack().run(self.adapter, language=self.options.language))

        if self.options.enable_token_probe:
            token_traces = await TokenAuditProbePack().run(self.adapter)
            token_features, token_results = analyze_token_traces(token_traces, language=self.options.language)
            probe_results.extend(token_results)

        if self.options.enable_context_probe:
            await ContextWindowProbePack(target_tokens=self.options.context_probe_target_tokens).run(self.adapter)

        if self.options.enable_fingerprint_probe:
            fingerprint_traces = await FingerprintProbePack(
                profile=self.options.fingerprint_profile,
                repeats=self.options.fingerprint_repeats,
                randomize=self.options.randomize_fingerprint_probes,
                probes_per_method=self.options.fingerprint_probes_per_method,
                seed=self.options.fingerprint_probe_seed,
            ).run(self.adapter)
            fingerprint_bundle, fingerprint_results = analyze_fingerprint_traces(fingerprint_traces)
            evidence_run = await self._collect_external_evidence(fingerprint_bundle)
            fingerprint_bundle.methods.extend(evidence_run.methods)
            fingerprint_bundle.database_models.extend(evidence_run.database_models)
            for source in evidence_run.sources:
                fingerprint_bundle.database_status[f"external_source:{source.source_id}"] = source.status
            for method in evidence_run.methods:
                fingerprint_results.append(_auxiliary_probe_result(method))
            fingerprint_result = fuse_fingerprint_features(fingerprint_bundle, language=self.options.language)
            probe_results.extend(fingerprint_results)

        if self.options.enable_token_probe or self.options.enable_context_probe or self.options.enable_fingerprint_probe:
            branch_evidence, branch_results, context_truth_score, prompt_injection_risk = analyze_branch_evidence(
                probe_results=probe_results,
                traces=self.adapter.trace_store.traces,
                token_features=token_features,
                prompt_injection_warn=(self.options.thresholds or {}).get("prompt_injection_warn", 0.55),
                language=self.options.language,
            )
            probe_results.extend(branch_results)

        return build_report(
            provider_id=self.adapter.provider_id,
            claimed_model=self.adapter.claimed_model,
            adapter_type=self.adapter.adapter_type,
            probe_results=probe_results,
            traces=self.adapter.trace_store.traces,
            token_features=token_features,
            fingerprint_result=fingerprint_result,
            context_truth_score=context_truth_score,
            prompt_injection_risk=prompt_injection_risk,
            branch_evidence=branch_payload(branch_evidence),
            thresholds=self.options.thresholds or {},
            evidence_sources=evidence_run.sources if evidence_run else [],
            judge_invocations=evidence_run.judge_invocations if evidence_run else [],
            degraded_modes=[
                *(evidence_run.degraded_modes if evidence_run else []),
                *_generation_degraded_modes(self.adapter.trace_store.traces),
            ],
            corpus_metadata=evidence_run.corpus_metadata if evidence_run else [],
            strict_mode=self.options.strict_mode,
            language=self.options.language,
        )

    async def _collect_external_evidence(self, bundle: FingerprintFeatureBundle | None):
        judges = list(self.options.external_judges or [])
        if self.options.enable_auxiliary_llm_judge and self.options.auxiliary_judge_fn is not None:
            judges.append(ExternalJudge(model=self.options.auxiliary_judge_model, judge_fn=self.options.auxiliary_judge_fn, method_id="auxiliary_llm_judge"))
        return await collect_evidence_sources(
            provider_id=self.adapter.provider_id,
            claimed_model=self.adapter.claimed_model,
            bundle=bundle,
            judges=judges,
            public_sources=list(self.options.public_knowledge_sources or []),
            trusted_corpus_sources=self.options.trusted_corpus_sources,
            cache_dir=Path(self.options.public_cache_dir or ".llm_identify_cache"),
        )


def make_trace_store() -> TraceStore:
    return TraceStore()


def _auxiliary_judge_prompt(bundle: FingerprintFeatureBundle) -> str:
    return auxiliary_judge_prompt(bundle)


def _parse_auxiliary_judgment(judgment: str) -> MethodFingerprint:
    return parse_auxiliary_judgment(judgment, method="auxiliary_llm_judge")


def _auxiliary_probe_result(method: MethodFingerprint) -> ProbeResult:
    top_family = max(method.family_scores.items(), key=lambda item: item[1])[0]
    score = max(method.family_scores.values()) * 0.7 + method.quality * 0.3
    return ProbeResult(
        category="fingerprint",
        name=method.method,
        score=round(score, 4),
        status="pass" if score >= 0.7 else "warning" if score >= 0.45 else "fail",
        detail=f"External evidence method {method.method} points most strongly to {top_family}.",
        evidence={"family_scores": method.family_scores, "quality": method.quality, **method.evidence},
    )


def _generation_degraded_modes(traces: list[Trace]) -> list[str]:
    degraded: list[str] = []
    for trace in traces:
        error = trace.reply.meta.get("generation_error")
        if not isinstance(error, dict):
            continue
        error_type = str(error.get("type") or "Error")
        message = str(error.get("message") or "Probe request failed.")
        degraded.append(f"probe:{trace.probe_id}: {error_type}: {message}")
    return degraded

