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
    confidence = protocol_value * 0.30 + token_value * 0.30 + fingerprint_value * 0.30 + 0.10
    if strict_mode:
        confidence -= 0.05 * sum(1 for item in probe_results if item.status == "fail")
    confidence = round(clamp(confidence), 4)
    proxy_probability = _proxy_probability(protocol_value, token_features, fingerprint_result, traces)
    mixture_probability = _mixture_probability(probe_results, token_features, fingerprint_result)
    findings = _findings(protocol_score, token_features, fingerprint_result, proxy_probability, mixture_probability)
    risk_level = _risk_level(confidence, proxy_probability, token_truth_score, fingerprint_result.spoofing_risk if fingerprint_result else None)
    return AuditReport(
        provider_id=provider_id,
        claimed_model=claimed_model,
        adapter_type=adapter_type,
        model_family_guess=model_family,
        provider_probabilities=_provider_probabilities(model_family, confidence, fingerprint_result),
        protocol_score=protocol_score,
        token_truth_score=token_truth_score,
        context_truth_score=None,
        fingerprint_score=fingerprint_score,
        fingerprint_confidence=fingerprint_confidence,
        fingerprint_candidates=fingerprint_result.fingerprint_candidates if fingerprint_result else [],
        fingerprint_method_scores=fingerprint_result.fingerprint_method_scores if fingerprint_result else {},
        fingerprint_database_status=fingerprint_result.database_status if fingerprint_result else {},
        fingerprint_disagreement=fingerprint_result.fingerprint_disagreement if fingerprint_result else None,
        spoofing_risk=fingerprint_result.spoofing_risk if fingerprint_result else None,
        proxy_probability=proxy_probability,
        mixture_probability=mixture_probability,
        confidence=confidence,
        risk_level=risk_level,
        findings=findings,
        probe_results=probe_results,
        trace_summary=build_trace_summary(traces),
        created_at=int(time.time()),
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
    if report.fingerprint_database_status:
        empty = [name for name, count in report.fingerprint_database_status.items() if count == 0]
        lines.append(f"Fingerprint databases empty: {len(empty)}")
    lines.extend(["", "Provider probabilities:"])
    for name, value in sorted(report.provider_probabilities.items(), key=lambda item: item[1], reverse=True):
        lines.append(f"- {name}: {value:.0%}")
    if report.fingerprint_candidates:
        lines.extend(["", "Fingerprint candidates:"])
        for candidate in report.fingerprint_candidates:
            methods = ", ".join(candidate.methods) if candidate.methods else "no direct method wins"
            lines.append(f"- {candidate.name}: {candidate.confidence:.0%} ({methods})")
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
    base = {
        "openai_like": 0.12,
        "anthropic_like": 0.12,
        "google_like": 0.10,
        "open_source_or_relay": 0.28,
        "unknown": 0.38,
    }
    mapping = {
        "openai": "openai_like",
        "claude": "anthropic_like",
        "gemini": "google_like",
        "qwen": "open_source_or_relay",
        "deepseek": "open_source_or_relay",
        "glm": "open_source_or_relay",
    }
    key = mapping.get(model_family, "unknown")
    base[key] += confidence * 0.35
    if fingerprint_result:
        for family, score in _fingerprint_distribution(fingerprint_result).items():
            if family in base:
                base[family] += score * 0.35
    base["unknown"] = max(0.05, base["unknown"] - confidence * 0.20)
    total = sum(base.values())
    return {name: round(value / total, 4) for name, value in base.items()}


def _fingerprint_distribution(fingerprint_result: FingerprintFusionResult) -> dict[str, float]:
    distribution: dict[str, float] = {}
    for candidate in fingerprint_result.fingerprint_candidates:
        distribution[candidate.family] = max(distribution.get(candidate.family, 0.0), candidate.confidence)
    return distribution


def _findings(
    protocol_score: float | None,
    token_features: TokenAuditFeatures | None,
    fingerprint_result: FingerprintFusionResult | None,
    proxy_probability: float,
    mixture_probability: float,
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
    return findings


def _risk_level(confidence: float, proxy_probability: float, token_truth_score: float | None, spoofing_risk: float | None) -> str:
    token_value = token_truth_score if token_truth_score is not None else 0.7
    spoof_value = spoofing_risk if spoofing_risk is not None else 0.2
    if confidence >= 0.8 and proxy_probability < 0.35 and token_value >= 0.75 and spoof_value < 0.35:
        return "low"
    if confidence >= 0.62 and proxy_probability < 0.55 and token_value >= 0.55 and spoof_value < 0.55:
        return "medium"
    if confidence >= 0.42:
        return "medium_high"
    return "high"


