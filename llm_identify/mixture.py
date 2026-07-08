from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from .capture import Trace
from .features import TokenAuditFeatures
from .models import ProbeResult
from .scoring.fingerprint import FingerprintFusionResult
from .utils import clamp


@dataclass
class MixtureDetectionResult:
    probability: float
    signals: dict[str, Any] = field(default_factory=dict)
    findings: list[str] = field(default_factory=list)


def detect_mixture_or_provider_switching(
    *,
    probe_results: list[ProbeResult],
    traces: list[Trace],
    token_features: TokenAuditFeatures | None = None,
    fingerprint_result: FingerprintFusionResult | None = None,
) -> MixtureDetectionResult:
    repeated = _repeated_response_signal(traces)
    provider = _provider_switch_signal(traces)
    usage = _usage_shape_signal(traces, token_features)
    latency = _latency_mode_signal(traces)
    status = _probe_status_signal(probe_results)
    fusion = _fusion_signal(fingerprint_result)

    weighted = (
        repeated["score"] * 0.24
        + provider["score"] * 0.24
        + usage["score"] * 0.16
        + latency["score"] * 0.14
        + status["score"] * 0.08
        + fusion["score"] * 0.14
    )
    probability = round(clamp(weighted), 4)
    signals = {
        "response_clusters": repeated,
        "provider_switching": provider,
        "usage_shape_switching": usage,
        "latency_modes": latency,
        "probe_status": status,
        "fusion_disagreement": fusion,
    }
    findings: list[str] = []
    if repeated["score"] >= 0.55:
        findings.append("Repeated probes split into multiple response clusters.")
    if provider["score"] >= 0.45:
        findings.append("Provider trace metadata changes across probes.")
    if usage["score"] >= 0.45:
        findings.append("Usage/token metadata shape changes across probes.")
    if latency["score"] >= 0.45:
        findings.append("Latency observations suggest multiple response modes.")
    if fusion["score"] >= 0.55:
        findings.append("Fingerprint evidence remains materially inconsistent after calibration.")
    return MixtureDetectionResult(probability=probability, signals=signals, findings=findings)


def _repeated_response_signal(traces: list[Trace]) -> dict[str, Any]:
    grouped: dict[str, list[str]] = {}
    for trace in traces:
        if "__r" not in trace.probe_id:
            continue
        base = trace.probe_id.split("__r", 1)[0]
        text = _canonical_text(trace.reply.text)
        if text:
            grouped.setdefault(base, []).append(text)
    cluster_rows: list[dict[str, Any]] = []
    scores: list[float] = []
    for base, values in grouped.items():
        if len(values) < 2:
            continue
        unique = len(set(values))
        ratio = unique / len(values)
        scores.append(ratio)
        cluster_rows.append({"probe_base": base, "observations": len(values), "unique_clusters": unique, "instability_ratio": round(ratio, 4)})
    if not scores:
        return {"score": 0.0, "groups": [], "reason": "insufficient_repeated_probes"}
    avg = sum(scores) / len(scores)
    max_ratio = max(scores)
    score = clamp((avg - 0.34) * 1.3 + max(0.0, max_ratio - 0.67) * 0.55)
    return {"score": round(score, 4), "groups": cluster_rows, "avg_instability": round(avg, 4), "max_instability": round(max_ratio, 4)}


def _provider_switch_signal(traces: list[Trace]) -> dict[str, Any]:
    signatures: list[tuple[str, str, str, str]] = []
    for trace in traces:
        provider_trace = trace.reply.meta.get("provider_trace") if isinstance(trace.reply.meta.get("provider_trace"), dict) else {}
        headers = trace.reply.meta.get("normalized_headers") if isinstance(trace.reply.meta.get("normalized_headers"), dict) else {}
        header_signals = headers.get("signals") if isinstance(headers.get("signals"), dict) else {}
        normalized_usage = trace.reply.meta.get("normalized_usage") if isinstance(trace.reply.meta.get("normalized_usage"), dict) else {}
        usage_shape = provider_trace.get("usage_shape") or normalized_usage.get("provider_shape") or ""
        signature = (
            str(provider_trace.get("provider_hint") or header_signals.get("provider_hint") or ""),
            str(provider_trace.get("model") or trace.reply.meta.get("model") or trace.reply.meta.get("modelVersion") or ""),
            str(usage_shape),
            str(header_signals.get("request_id") or "")[:8],
        )
        if any(signature):
            signatures.append(signature)
    if len(signatures) < 2:
        return {"score": 0.0, "signatures": [], "reason": "insufficient_provider_trace"}
    provider_models = {(item[0], item[1], item[2]) for item in signatures}
    provider_hints = {item[0] for item in signatures if item[0]}
    usage_shapes = {item[2] for item in signatures if item[2]}
    score = clamp((len(provider_models) - 1) * 0.22 + (len(provider_hints) - 1) * 0.32 + (len(usage_shapes) - 1) * 0.18)
    return {
        "score": round(score, 4),
        "signature_count": len(signatures),
        "distinct_provider_model_shapes": len(provider_models),
        "provider_hints": sorted(provider_hints),
        "usage_shapes": sorted(usage_shapes),
    }


def _usage_shape_signal(traces: list[Trace], token_features: TokenAuditFeatures | None) -> dict[str, Any]:
    shapes: list[str] = []
    totals: list[int] = []
    for trace in traces:
        normalized = trace.reply.meta.get("normalized_usage") if isinstance(trace.reply.meta.get("normalized_usage"), dict) else {}
        shape = str(normalized.get("provider_shape") or "")
        if shape and shape != "missing":
            shapes.append(shape)
        if trace.usage and trace.usage.total is not None:
            totals.append(int(trace.usage.total))
    distinct_shapes = sorted(set(shapes))
    total_spread = (max(totals) - min(totals)) / max(1, sum(totals) / len(totals)) if len(totals) >= 2 else 0.0
    score = 0.0
    if len(distinct_shapes) > 1:
        score += min(0.75, (len(distinct_shapes) - 1) * 0.35)
    if token_features and token_features.cache_signal_consistency is False:
        score += 0.18
    if total_spread > 2.5 and len(totals) >= 4:
        score += 0.15
    return {"score": round(clamp(score), 4), "usage_shapes": distinct_shapes, "token_total_spread": round(total_spread, 4)}


def _latency_mode_signal(traces: list[Trace]) -> dict[str, Any]:
    latencies = sorted(float(trace.latency_ms) for trace in traces if trace.latency_ms >= 0)
    if len(latencies) < 4:
        return {"score": 0.0, "reason": "insufficient_latency", "latency_count": len(latencies)}
    median = latencies[len(latencies) // 2]
    low = [value for value in latencies if value <= median]
    high = [value for value in latencies if value > median]
    if not low or not high:
        return {"score": 0.0, "reason": "single_latency_mode", "latency_count": len(latencies)}
    low_avg = sum(low) / len(low)
    high_avg = sum(high) / len(high)
    ratio = high_avg / max(1.0, low_avg)
    spread = (latencies[-1] - latencies[0]) / max(1.0, sum(latencies) / len(latencies))
    score = clamp(max(0.0, ratio - 2.0) * 0.25 + max(0.0, spread - 1.5) * 0.18)
    return {"score": round(score, 4), "latency_count": len(latencies), "low_avg_ms": round(low_avg, 2), "high_avg_ms": round(high_avg, 2), "mode_ratio": round(ratio, 4), "spread": round(spread, 4)}


def _probe_status_signal(results: list[ProbeResult]) -> dict[str, Any]:
    failures = sum(1 for item in results if item.status == "fail")
    warnings = sum(1 for item in results if item.status == "warning")
    total = max(1, len(results))
    score = clamp(failures / total * 0.55 + warnings / total * 0.25)
    return {"score": round(score, 4), "failures": failures, "warnings": warnings, "total": len(results)}


def _fusion_signal(fingerprint_result: FingerprintFusionResult | None) -> dict[str, Any]:
    if fingerprint_result is None:
        return {"score": 0.0, "reason": "no_fingerprint_result"}
    calibration = fingerprint_result.database_status.get("fusion_calibration") if isinstance(fingerprint_result.database_status, dict) else {}
    entropy = float(calibration.get("entropy") or 0.0) if isinstance(calibration, dict) else 0.0
    margin = float(calibration.get("margin") or 0.0) if isinstance(calibration, dict) else 0.0
    disagreement = float(fingerprint_result.fingerprint_disagreement or 0.0)
    score = clamp(disagreement * 0.62 + entropy * 0.28 + max(0.0, 0.2 - margin) * 0.5)
    return {"score": round(score, 4), "disagreement": round(disagreement, 4), "entropy": round(entropy, 4), "margin": round(margin, 4)}


def _canonical_text(text: str) -> str:
    lowered = text.strip().lower()
    lowered = re.sub(r"\s+", " ", lowered)
    lowered = re.sub(r"\b\d{4,}\b", "<num>", lowered)
    return lowered[:600]
