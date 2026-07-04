from __future__ import annotations

import time
from typing import Any

from ..capture import Trace, build_trace_summary
from ..features import TokenAuditFeatures
from ..models import AuditReport, ProbeResult
from .fingerprint import FingerprintFusionResult
from ..utils import clamp, detect_model_family


def build_report(
    *,
    provider_id: str,
    claimed_model: str,
    adapter_type: str,
    probe_results: list[ProbeResult],
    traces: list[Trace],
    token_features: TokenAuditFeatures | None,
    fingerprint_result: FingerprintFusionResult | None = None,
    context_truth_score: float | None = None,
    prompt_injection_risk: float | None = None,
    branch_evidence: list[dict[str, Any]] | None = None,
    thresholds: dict[str, float] | None = None,
    evidence_sources: list[Any] | None = None,
    judge_invocations: list[Any] | None = None,
    degraded_modes: list[str] | None = None,
    corpus_metadata: list[dict[str, Any]] | None = None,
    strict_mode: bool = False,
) -> AuditReport:
    model_family = detect_model_family(claimed_model, provider_id)
    protocol_score = _category_score(probe_results, "protocol")
    token_truth_score = token_features.token_truth_score if token_features else None
    fingerprint_score = fingerprint_result.fingerprint_score if fingerprint_result else None
    fingerprint_confidence = fingerprint_result.fingerprint_confidence if fingerprint_result else None
    protocol_value = protocol_score if protocol_score is not None else 0.5
    token_value = token_truth_score if token_truth_score is not None else 0.65
    fingerprint_value = fingerprint_confidence if fingerprint_confidence is not None else 0.55
    context_value = context_truth_score if context_truth_score is not None else 0.65
    confidence = protocol_value * 0.25 + token_value * 0.25 + fingerprint_value * 0.25 + context_value * 0.15 + 0.10
    if strict_mode:
        confidence -= 0.05 * sum(1 for item in probe_results if item.status == "fail")
    confidence = round(clamp(confidence), 4)
    proxy_probability = _proxy_probability(protocol_value, token_features, fingerprint_result, traces)
    mixture_probability = _mixture_probability(probe_results, token_features, fingerprint_result)
    prompt_injection_risk = 0.0 if prompt_injection_risk is None else prompt_injection_risk
    drift_risk = _drift_risk(branch_evidence or [])
    findings = _findings(protocol_score, token_features, fingerprint_result, proxy_probability, mixture_probability, degraded_modes)
    risk_level = _risk_level(confidence, proxy_probability, token_truth_score, fingerprint_result.spoofing_risk if fingerprint_result else None, prompt_injection_risk, drift_risk)
    identity = _provider_probabilities(model_family, confidence, fingerprint_result)
    authenticity = {
        "authentic": round(clamp(confidence * 0.65 + (1.0 - proxy_probability) * 0.20 + (token_value or 0.5) * 0.15), 4),
        "degraded_or_wrapped": round(clamp(proxy_probability * 0.65 + mixture_probability * 0.20 + (1.0 - confidence) * 0.15), 4),
    }
    security = {
        "low": round(clamp(1.0 - max(proxy_probability, prompt_injection_risk, drift_risk)), 4),
        "medium": round(clamp(max(proxy_probability, prompt_injection_risk, drift_risk) * 0.65), 4),
        "high": round(clamp(max(proxy_probability, prompt_injection_risk, drift_risk) * 0.35), 4),
    }
    trace_summary = build_trace_summary(traces)
    return AuditReport(
        provider_id=provider_id,
        claimed_model=claimed_model,
        adapter_type=adapter_type,
        model_family_guess=model_family,
        provider_probabilities=identity,
        protocol_score=protocol_score,
        token_truth_score=token_truth_score,
        context_truth_score=context_truth_score,
        fingerprint_score=fingerprint_score,
        fingerprint_confidence=fingerprint_confidence,
        prompt_injection_risk=prompt_injection_risk,
        drift_risk=drift_risk,
        identity_posterior=identity,
        authenticity_posterior=authenticity,
        security_posterior=security,
        branch_evidence=branch_evidence or [],
        thresholds=thresholds or {},
        fingerprint_candidates=fingerprint_result.fingerprint_candidates if fingerprint_result else [],
        fingerprint_method_scores=fingerprint_result.fingerprint_method_scores if fingerprint_result else {},
        fingerprint_database_status=fingerprint_result.database_status if fingerprint_result else {},
        fingerprint_disagreement=fingerprint_result.fingerprint_disagreement if fingerprint_result else None,
        spoofing_risk=fingerprint_result.spoofing_risk if fingerprint_result else None,
        proxy_probability=proxy_probability,
        mixture_probability=mixture_probability,
        confidence=confidence,
        risk_level=risk_level,
        risk_analysis={"proxy_probability": proxy_probability, "mixture_probability": mixture_probability, "prompt_injection_risk": prompt_injection_risk, "drift_risk": drift_risk},
        evidence_summary=_evidence_summary(probe_results),
        findings=findings,
        probe_results=probe_results,
        evidence_sources=evidence_sources or [],
        judge_invocations=judge_invocations or [],
        degraded_modes=degraded_modes or [],
        execution_trace={"judge_invocation_count": len(judge_invocations or []), "evidence_source_count": len(evidence_sources or []), "degraded_mode_count": len(degraded_modes or [])},
        trace_summary=trace_summary,
        created_at=int(time.time()),
        corpus_metadata=corpus_metadata or [],
    )


def format_text_report(report: AuditReport) -> str:
    lines = [
        "LLM Identify Audit Report",
        f"Provider ID: {report.provider_id}",
        f"Claimed model: {report.claimed_model}",
        f"Adapter: {report.adapter_type}",
        f"Model family guess: {report.model_family_guess}",
        f"Confidence: {report.confidence:.0%}",
        f"Risk level: {report.risk_level}",
        f"Proxy probability: {report.proxy_probability:.0%}",
        f"Mixture probability: {report.mixture_probability:.0%}",
    ]
    if report.protocol_score is not None:
        lines.append(f"Protocol score: {report.protocol_score:.0%}")
    if report.token_truth_score is not None:
        lines.append(f"Token truth score: {report.token_truth_score:.0%}")
    if report.fingerprint_confidence is not None:
        lines.append(f"Fingerprint confidence: {report.fingerprint_confidence:.0%}")
    if report.spoofing_risk is not None:
        lines.append(f"Spoofing risk: {report.spoofing_risk:.0%}")
    if report.context_truth_score is not None:
        lines.append(f"Context truth score: {report.context_truth_score:.0%}")
    if report.prompt_injection_risk is not None:
        lines.append(f"Prompt injection risk: {report.prompt_injection_risk:.0%}")
    if report.fingerprint_database_status:
        empty = [name for name, count in report.fingerprint_database_status.items() if count == 0]
        lines.append(f"Fingerprint databases empty: {len(empty)}")
    if report.degraded_modes:
        lines.append(f"Degraded modes: {len(report.degraded_modes)}")
    if report.corpus_metadata:
        versions = sorted({str(item.get("corpus_version", "unknown")) for item in report.corpus_metadata})
        lines.append(f"Corpus versions: {', '.join(versions)}")
    lines.extend(["", "Identity posterior:"])
    for name, value in sorted(report.identity_posterior.items(), key=lambda item: item[1], reverse=True):
        lines.append(f"- {name}: {value:.0%}")
    lines.extend(["", "Authenticity posterior:"])
    for name, value in sorted(report.authenticity_posterior.items(), key=lambda item: item[1], reverse=True):
        lines.append(f"- {name}: {value:.0%}")
    lines.extend(["", "Security posterior:"])
    for name, value in sorted(report.security_posterior.items(), key=lambda item: item[1], reverse=True):
        lines.append(f"- {name}: {value:.0%}")
    if report.fingerprint_candidates:
        lines.extend(["", "Fingerprint candidates:"])
        for candidate in report.fingerprint_candidates:
            methods = ", ".join(candidate.methods) if candidate.methods else "no direct method wins"
            lines.append(f"- {candidate.name}: {candidate.confidence:.0%} ({methods})")
    lines.extend(["", "Evidence summary:"])
    summary = report.evidence_summary or {}
    lines.append(f"- Supporting: {len(summary.get('supporting_evidence', []))}")
    lines.append(f"- Contradicting: {len(summary.get('contradicting_evidence', []))}")
    lines.append(f"- Unknown: {len(summary.get('unknown_evidence', []))}")
    lines.extend(["", "Evidence sources:"])
    if report.evidence_sources:
        for source in report.evidence_sources:
            source_id = getattr(source, "source_id", "unknown")
            status = getattr(source, "status", "unknown")
            source_type = getattr(source, "source_type", "unknown")
            lines.append(f"- {source_id} ({source_type}): {status}")
    else:
        lines.append("- No external evidence sources configured.")
    if report.corpus_metadata:
        lines.extend(["", "Trusted corpus:"])
        for item in report.corpus_metadata:
            source_id = item.get("source_id", "unknown")
            corpus_version = item.get("corpus_version", "unknown")
            schema_version = item.get("schema_version", "unknown")
            status = item.get("status", "unknown")
            lines.append(f"- {source_id}: version {corpus_version}, schema {schema_version}, status {status}")
    if report.judge_invocations:
        lines.extend(["", "External judge invocations:"])
        for invocation in report.judge_invocations:
            model = getattr(invocation, "model", "unknown")
            status = getattr(invocation, "execution_status", "unknown")
            lines.append(f"- {model}: {status}")
    if report.degraded_modes:
        lines.extend(["", "Degraded modes:"])
        for item in report.degraded_modes:
            lines.append(f"- {item}")
    lines.extend(["", "Findings:"])
    for finding in report.findings or ["No major findings."]:
        lines.append(f"- {finding}")
    lines.extend(["", "Probe results:"])
    for item in report.probe_results:
        lines.append(f"- [{item.category}] {item.name}: {item.status}, {item.detail}")
        if item.sample:
            lines.append(f"  Sample: {item.sample}")
    lines.extend(
        [
            "",
            "Notes:",
            "- This report is a probabilistic black-box audit, not proof of model identity.",
            "- Relays can wrap prompts, rewrite usage, cache responses, spoof style, or route traffic dynamically.",
        ]
    )
    return "\n".join(lines)


def _category_score(results: list[ProbeResult], category: str) -> float | None:
    values = [item.score for item in results if item.category == category]
    if not values:
        return None
    return round(sum(values) / len(values), 4)


def _proxy_probability(protocol_score: float, token_features: TokenAuditFeatures | None, fingerprint_result: FingerprintFusionResult | None, traces: list[Trace]) -> float:
    probability = 0.15 + max(0.0, 0.78 - protocol_score) * 0.55
    if token_features:
        if "usage_missing" in token_features.anomaly_flags:
            probability += 0.12
        if "constant_or_nearly_constant_input_counts" in token_features.anomaly_flags:
            probability += 0.16
        if token_features.token_truth_score < 0.5:
            probability += 0.12
    if fingerprint_result and fingerprint_result.spoofing_risk is not None:
        probability += fingerprint_result.spoofing_risk * 0.20
    direct_headers = any(trace.reply.meta.get("headers") for trace in traces)
    if direct_headers:
        probability = max(0.05, probability - 0.04)
    return round(clamp(probability), 4)


def _mixture_probability(results: list[ProbeResult], token_features: TokenAuditFeatures | None, fingerprint_result: FingerprintFusionResult | None) -> float:
    failures = sum(1 for item in results if item.status == "fail")
    warnings = sum(1 for item in results if item.status == "warning")
    probability = min(0.65, failures * 0.08 + warnings * 0.04)
    if token_features and token_features.cache_signal_consistency is False:
        probability += 0.08
    if fingerprint_result and fingerprint_result.fingerprint_disagreement is not None:
        probability += fingerprint_result.fingerprint_disagreement * 0.25
    return round(clamp(probability), 4)


def _provider_probabilities(model_family: str, confidence: float, fingerprint_result: FingerprintFusionResult | None) -> dict[str, float]:
    base = {"openai_like": 0.15, "anthropic_like": 0.15, "google_like": 0.15, "open_source_or_relay": 0.15, "unknown": 0.4}
    if fingerprint_result:
        for candidate in fingerprint_result.fingerprint_candidates:
            if candidate.family in base:
                base[candidate.family] = max(base[candidate.family], candidate.confidence)
        for scores in fingerprint_result.fingerprint_method_scores.values():
            for family, value in scores.items():
                if family in base:
                    base[family] = max(base[family], float(value))
    elif model_family in base:
        base[model_family] = max(base[model_family], confidence)
    total = sum(base.values()) or 1.0
    return {key: round(value / total, 4) for key, value in base.items()}


def _risk_level(confidence: float, proxy_probability: float, token_truth_score: float | None, spoofing_risk: float | None = None, prompt_injection_risk: float | None = None, drift_risk: float | None = None) -> str:
    risk_score = max(proxy_probability, 1.0 - confidence)
    if token_truth_score is not None:
        risk_score = max(risk_score, 1.0 - token_truth_score)
    if spoofing_risk is not None:
        risk_score = max(risk_score, spoofing_risk)
    if prompt_injection_risk is not None:
        risk_score = max(risk_score, prompt_injection_risk)
    if drift_risk is not None:
        risk_score = max(risk_score, drift_risk)
    if risk_score >= 0.7:
        return "high"
    if risk_score >= 0.4:
        return "medium"
    return "low"


def _findings(
    protocol_score: float | None,
    token_features: TokenAuditFeatures | None,
    fingerprint_result: FingerprintFusionResult | None,
    proxy_probability: float,
    mixture_probability: float,
    degraded_modes: list[str] | None = None,
) -> list[str]:
    findings: list[str] = []
    if protocol_score is not None and protocol_score < 0.65:
        findings.append("Protocol behavior diverges from the claimed endpoint surface.")
    if token_features:
        if not token_features.usage_available:
            findings.append("Most token probes did not expose usable token metadata.")
        if token_features.constant_count_detected:
            findings.append("Reported token counts are constant or nearly constant across varied prompts.")
        if not token_features.input_token_monotonic and token_features.usage_available:
            findings.append("Reported input tokens do not increase with controlled prompt length.")
        if token_features.token_truth_score < 0.6:
            findings.append("Token accounting evidence is weak or inconsistent.")
    if fingerprint_result:
        findings.extend(fingerprint_result.findings)
    if proxy_probability >= 0.65:
        findings.append("Proxy, wrapper, or relay behavior is plausible based on observable evidence.")
    if mixture_probability >= 0.45:
        findings.append("Mixed routing remains plausible; repeat sampling is recommended.")
    if degraded_modes:
        findings.append("One or more external evidence sources degraded; confidence is based on the remaining available evidence.")
    return findings


def _evidence_summary(results: list[ProbeResult]) -> dict[str, list[str]]:
    supporting = [item.name for item in results if item.status == "pass"]
    contradicting = [item.name for item in results if item.status == "fail"]
    unknown = [item.name for item in results if item.status not in {"pass", "fail"}]
    return {"supporting_evidence": supporting, "contradicting_evidence": contradicting, "unknown_evidence": unknown}


def _drift_risk(branches: list[dict[str, Any]]) -> float:
    if not branches:
        return 0.0
    timing = next((item for item in branches if item.get("name") == "timing"), None)
    if not timing:
        return 0.0
    return round(clamp(1.0 - float(timing.get("score", 0.7))), 4)
