from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Awaitable, Callable

from .adapters.base import GenerateAdapter
from .capture import TraceStore
from .features import FingerprintFeatureBundle, MethodFingerprint, TokenAuditFeatures, analyze_fingerprint_traces, analyze_token_traces
from .models import AuditReport, ProbeResult
from .probes import FingerprintProbePack, ProtocolProbePack, TokenAuditProbePack
from .scoring import build_report
from .scoring.fingerprint import FingerprintFusionResult, fuse_fingerprint_features


@dataclass
class AuditOptions:
    enable_protocol_probe: bool = True
    enable_token_probe: bool = False
    enable_context_probe: bool = False
    enable_fingerprint_probe: bool = False
    fingerprint_profile: str = "standard"
    fingerprint_repeats: int = 3
    enable_auxiliary_llm_judge: bool = False
    auxiliary_judge_fn: Callable[[str], Awaitable[str]] | None = None
    strict_mode: bool = False


class AuditEngine:
    def __init__(self, adapter: GenerateAdapter, options: AuditOptions | None = None) -> None:
        self.adapter = adapter
        self.options = options or AuditOptions()

    async def run(self) -> AuditReport:
        probe_results: list[ProbeResult] = []
        token_features: TokenAuditFeatures | None = None
        fingerprint_bundle: FingerprintFeatureBundle | None = None
        fingerprint_result: FingerprintFusionResult | None = None

        if self.options.enable_protocol_probe:
            probe_results.extend(await ProtocolProbePack().run(self.adapter))

        if self.options.enable_token_probe:
            token_traces = await TokenAuditProbePack().run(self.adapter)
            token_features, token_results = analyze_token_traces(token_traces)
            probe_results.extend(token_results)

        if self.options.enable_fingerprint_probe:
            fingerprint_traces = await FingerprintProbePack(
                profile=self.options.fingerprint_profile,
                repeats=self.options.fingerprint_repeats,
            ).run(self.adapter)
            fingerprint_bundle, fingerprint_results = analyze_fingerprint_traces(fingerprint_traces)
            auxiliary_method = await self._run_auxiliary_judge(fingerprint_bundle)
            if auxiliary_method is not None:
                fingerprint_bundle.methods.append(auxiliary_method)
                fingerprint_results.append(_auxiliary_probe_result(auxiliary_method))
            fingerprint_result = fuse_fingerprint_features(fingerprint_bundle)
            probe_results.extend(fingerprint_results)

        return build_report(
            provider_id=self.adapter.provider_id,
            claimed_model=self.adapter.claimed_model,
            adapter_type=self.adapter.adapter_type,
            probe_results=probe_results,
            traces=self.adapter.trace_store.traces,
            token_features=token_features,
            fingerprint_result=fingerprint_result,
            strict_mode=self.options.strict_mode,
        )

    async def _run_auxiliary_judge(self, bundle: FingerprintFeatureBundle | None) -> MethodFingerprint | None:
        if not self.options.enable_auxiliary_llm_judge or self.options.auxiliary_judge_fn is None or bundle is None or not bundle.methods:
            return None
        prompt = _auxiliary_judge_prompt(bundle)
        try:
            judgment = await self.options.auxiliary_judge_fn(prompt)
        except Exception as exc:
            return MethodFingerprint(
                method="auxiliary_llm_judge",
                family_scores={"unknown": 1.0, "openai_like": 0.0, "anthropic_like": 0.0, "google_like": 0.0, "open_source_or_relay": 0.0},
                quality=0.05,
                evidence={"error": str(exc)},
            )
        return _parse_auxiliary_judgment(judgment)


def make_trace_store() -> TraceStore:
    return TraceStore()


def _auxiliary_judge_prompt(bundle: FingerprintFeatureBundle) -> str:
    summary = {
        "method_scores": {method.method: method.family_scores for method in bundle.methods},
        "method_quality": {method.method: method.quality for method in bundle.methods},
        "database_status": bundle.database_status,
    }
    return (
        "You are an auxiliary LLM fingerprint judge. Compare only the extracted audit features below; "
        "do not infer from provider names or hidden assumptions. Return compact JSON with keys "
        "family, confidence, rationale. Allowed family values: openai_like, anthropic_like, "
        "google_like, open_source_or_relay, unknown.\n"
        f"FEATURES:\n{json.dumps(summary, sort_keys=True)}"
    )


def _parse_auxiliary_judgment(judgment: str) -> MethodFingerprint:
    text = str(judgment or "").strip()
    lower = text.lower()
    family = _family_from_judgment(lower)
    confidence = _confidence_from_judgment(lower)
    scores = {"openai_like": 0.0, "anthropic_like": 0.0, "google_like": 0.0, "open_source_or_relay": 0.0, "unknown": 0.0}
    scores[family] = confidence
    for other in scores:
        if other != family:
            scores[other] = (1.0 - confidence) / 4.0
    return MethodFingerprint(
        method="auxiliary_llm_judge",
        family_scores={key: round(value, 4) for key, value in scores.items()},
        quality=0.45 if family != "unknown" else 0.2,
        evidence={"raw_judgment": text[:1200], "parsed_family": family, "parsed_confidence": confidence},
    )


def _family_from_judgment(lower: str) -> str:
    if "anthropic" in lower or "claude" in lower:
        return "anthropic_like"
    if "google" in lower or "gemini" in lower or "gemma" in lower:
        return "google_like"
    if "openai" in lower or "gpt" in lower or "chatgpt" in lower:
        return "openai_like"
    if "open source" in lower or "llama" in lower or "qwen" in lower or "mistral" in lower or "relay" in lower:
        return "open_source_or_relay"
    return "unknown"


def _confidence_from_judgment(lower: str) -> float:
    match = re.search(r"(0\.\d+|1\.0|\d{1,3}%)", lower)
    if not match:
        return 0.55
    value = match.group(1)
    if value.endswith("%"):
        return max(0.05, min(0.95, float(value[:-1]) / 100.0))
    return max(0.05, min(0.95, float(value)))


def _auxiliary_probe_result(method: MethodFingerprint) -> ProbeResult:
    top_family = max(method.family_scores.items(), key=lambda item: item[1])[0]
    score = max(method.family_scores.values()) * 0.7 + method.quality * 0.3
    return ProbeResult(
        category="fingerprint",
        name="auxiliary_llm_judge",
        score=round(score, 4),
        status="pass" if score >= 0.7 else "warn" if score >= 0.45 else "fail",
        detail=f"Auxiliary LLM judge points most strongly to {top_family}.",
        evidence={"family_scores": method.family_scores, "quality": method.quality, **method.evidence},
    )
