from __future__ import annotations

import time
from typing import Any

from ..capture import Trace, build_trace_summary
from ..features import TokenAuditFeatures
from ..models import AuditReport, ProbeResult
from ..mixture import detect_mixture_or_provider_switching
from .fingerprint import FingerprintFusionResult
from ..i18n import t
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
    language: str | None = None,
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
    mixture_detection = detect_mixture_or_provider_switching(probe_results=probe_results, traces=traces, token_features=token_features, fingerprint_result=fingerprint_result)
    mixture_probability = mixture_detection.probability
    prompt_injection_risk = 0.0 if prompt_injection_risk is None else prompt_injection_risk
    drift_risk = _drift_risk(branch_evidence or [])
    findings = _findings(protocol_score, token_features, fingerprint_result, proxy_probability, mixture_probability, degraded_modes, mixture_detection.findings, language)
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
        risk_analysis={"proxy_probability": proxy_probability, "mixture_probability": mixture_probability, "prompt_injection_risk": prompt_injection_risk, "drift_risk": drift_risk, "mixture_signals": mixture_detection.signals},
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


def format_text_report(report: AuditReport, language: str | None = None) -> str:
    lines = [
        t("report.title", language),
        f"{t('report.provider_id', language)}: {report.provider_id}",
        f"{t('report.claimed_model', language)}: {report.claimed_model}",
        f"{t('report.adapter', language)}: {report.adapter_type}",
        f"{t('report.model_family', language)}: {report.model_family_guess}",
        f"{t('report.confidence', language)}: {report.confidence:.0%}",
        f"{t('report.risk_level', language)}: {report.risk_level}",
        f"{t('report.proxy_probability', language)}: {report.proxy_probability:.0%}",
        f"{t('report.mixture_probability', language)}: {report.mixture_probability:.0%}",
    ]
    if report.protocol_score is not None:
        lines.append(f"{t('report.protocol_score', language)}: {report.protocol_score:.0%}")
    if report.token_truth_score is not None:
        lines.append(f"{t('report.token_truth_score', language)}: {report.token_truth_score:.0%}")
    if report.fingerprint_confidence is not None:
        lines.append(f"{t('report.fingerprint_confidence', language)}: {report.fingerprint_confidence:.0%}")
    if report.spoofing_risk is not None:
        lines.append(f"{t('report.spoofing_risk', language)}: {report.spoofing_risk:.0%}")
    if report.context_truth_score is not None:
        lines.append(f"{t('report.context_truth_score', language)}: {report.context_truth_score:.0%}")
    if report.prompt_injection_risk is not None:
        lines.append(f"{t('report.prompt_injection_risk', language)}: {report.prompt_injection_risk:.0%}")
    if report.fingerprint_database_status:
        empty = [name for name, count in report.fingerprint_database_status.items() if count == 0]
        lines.append(f"{t('report.fingerprint_databases_empty', language)}: {len(empty)}")
    if report.degraded_modes:
        lines.append(f"{t('report.degraded_modes_count', language)}: {len(report.degraded_modes)}")
    if report.corpus_metadata:
        versions = sorted({str(item.get("corpus_version", "unknown")) for item in report.corpus_metadata})
        lines.append(f"{t('report.corpus_versions', language)}: {', '.join(versions)}")
    lines.extend(["", t("report.identity_posterior", language)])
    for name, value in sorted(report.identity_posterior.items(), key=lambda item: item[1], reverse=True):
        lines.append(f"- {name}: {value:.0%}")
    lines.extend(["", t("report.authenticity_posterior", language)])
    for name, value in sorted(report.authenticity_posterior.items(), key=lambda item: item[1], reverse=True):
        lines.append(f"- {name}: {value:.0%}")
    lines.extend(["", t("report.security_posterior", language)])
    for name, value in sorted(report.security_posterior.items(), key=lambda item: item[1], reverse=True):
        lines.append(f"- {name}: {value:.0%}")
    if report.fingerprint_candidates:
        lines.extend(["", t("report.fingerprint_candidates", language)])
        for candidate in report.fingerprint_candidates:
            methods = ", ".join(candidate.methods) if candidate.methods else t("report.no_direct_method_wins", language)
            lines.append(f"- {candidate.name}: {candidate.confidence:.0%} ({methods})")
    lines.extend(["", t("report.evidence_summary", language)])
    summary = report.evidence_summary or {}
    lines.append(f"- {t('report.supporting', language)}: {len(summary.get('supporting_evidence', []))}")
    lines.append(f"- {t('report.contradicting', language)}: {len(summary.get('contradicting_evidence', []))}")
    lines.append(f"- {t('report.unknown', language)}: {len(summary.get('unknown_evidence', []))}")
    lines.extend(["", t("report.evidence_sources", language)])
    if report.evidence_sources:
        for source in report.evidence_sources:
            source_id = getattr(source, "source_id", "unknown")
            status = getattr(source, "status", "unknown")
            source_type = getattr(source, "source_type", "unknown")
            lines.append(f"- {source_id} ({source_type}): {status}")
    else:
        lines.append(f"- {t('report.no_external_sources', language)}")
    if report.corpus_metadata:
        lines.extend(["", t("report.trusted_corpus", language)])
        for item in report.corpus_metadata:
            source_id = item.get("source_id", "unknown")
            corpus_version = item.get("corpus_version", "unknown")
            schema_version = item.get("schema_version", "unknown")
            status = item.get("status", "unknown")
            lines.append(f"- {source_id}: {t('report.corpus_line', language, corpus_version=corpus_version, schema_version=schema_version, status=status)}")
    if report.judge_invocations:
        lines.extend(["", t("report.external_judges", language)])
        for invocation in report.judge_invocations:
            model = getattr(invocation, "model", "unknown")
            status = getattr(invocation, "execution_status", "unknown")
            lines.append(f"- {model}: {status}")
    if report.degraded_modes:
        lines.extend(["", t("report.degraded_modes", language)])
        for item in report.degraded_modes:
            lines.append(f"- {item}")
    lines.extend(["", t("report.findings", language)])
    for finding in report.findings or [t("report.no_findings", language)]:
        lines.append(f"- {finding}")
    lines.extend(["", t("report.probe_results", language)])
    for item in report.probe_results:
        lines.append(f"- [{item.category}] {item.name}: {item.status}, {item.detail}")
        if item.sample:
            lines.append(f"  {t('report.sample', language)}: {item.sample}")
    lines.extend(
        [
            "",
            t("report.notes", language),
            f"- {t('report.note_probabilistic', language)}",
            f"- {t('report.note_relays', language)}",
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
    mixture_findings: list[str] | None = None,
    language: str | None = None,
) -> list[str]:
    findings: list[str] = []
    if protocol_score is not None and protocol_score < 0.65:
        findings.append(t("finding.protocol_diverges", language))
    if token_features:
        if not token_features.usage_available:
            findings.append(t("finding.token_missing", language))
        if token_features.constant_count_detected:
            findings.append(t("finding.token_constant", language))
        if not token_features.input_token_monotonic and token_features.usage_available:
            findings.append(t("finding.token_not_monotonic", language))
        if token_features.token_truth_score < 0.6:
            findings.append(t("finding.token_weak", language))
    if fingerprint_result:
        findings.extend(fingerprint_result.findings)
    if proxy_probability >= 0.65:
        findings.append(t("finding.proxy_plausible", language))
    if mixture_probability >= 0.45:
        findings.append(t("finding.mixture_plausible", language))
    findings.extend(mixture_findings or [])
    if degraded_modes:
        findings.append(t("finding.degraded", language))
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
