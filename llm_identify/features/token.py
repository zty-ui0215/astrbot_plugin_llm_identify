from __future__ import annotations

from dataclasses import dataclass, field
from statistics import median
from typing import Any

from ..capture import Trace
from ..i18n import t
from ..models import ProbeResult
from ..utils import clamp, status_for_score


@dataclass
class TokenAuditFeatures:
    token_truth_score: float
    usage_available: bool
    input_token_monotonic: bool
    slope_consistency: bool
    constant_count_detected: bool
    cache_signal_consistency: bool | None
    unicode_count_stability: bool
    output_length_consistency: bool
    native_count_consistency: bool | None
    anomaly_flags: list[str] = field(default_factory=list)
    evidence: dict[str, Any] = field(default_factory=dict)


def analyze_token_traces(traces: list[Trace], language: str | None = None) -> tuple[TokenAuditFeatures, list[ProbeResult]]:
    token_traces = [trace for trace in traces if trace.category == "token"]
    by_id = {trace.probe_id: trace for trace in token_traces}
    usage_inputs = {
        trace.probe_id: trace.usage.input
        for trace in token_traces
        if trace.usage is not None and trace.usage.input is not None
    }
    usage_outputs = {
        trace.probe_id: trace.usage.output
        for trace in token_traces
        if trace.usage is not None and trace.usage.output is not None
    }

    anomaly_flags: list[str] = []
    usage_available = len(usage_inputs) >= max(4, len(token_traces) // 2)
    if not usage_available:
        anomaly_flags.append("usage_missing")

    ordered_ids = ["usage_ascii_short", "usage_cjk_mixed", "usage_unicode_edge", "usage_long_1", "usage_long_2"]
    ordered_pairs = [(probe_id, usage_inputs.get(probe_id), by_id.get(probe_id).prompt_estimate if by_id.get(probe_id) else None) for probe_id in ordered_ids]
    monotonic_values = [value for _, value, _ in ordered_pairs if value is not None]
    input_token_monotonic = len(monotonic_values) >= 4 and monotonic_values[-1] > monotonic_values[-2] > max(monotonic_values[:3])
    if usage_available and not input_token_monotonic:
        anomaly_flags.append("input_tokens_not_monotonic")

    slope_consistency, slope_evidence = _slope_consistency(ordered_pairs)
    if usage_available and not slope_consistency:
        anomaly_flags.append("implausible_input_token_slope")

    constant_count_detected = usage_available and len(set(usage_inputs.values())) <= 2
    if constant_count_detected:
        anomaly_flags.append("constant_or_nearly_constant_input_counts")

    cache_signal_consistency = _cache_signal_consistency(by_id)
    if cache_signal_consistency is False:
        anomaly_flags.append("cache_signal_inconsistent")

    unicode_count_stability = _unicode_count_stability(by_id)
    if usage_available and not unicode_count_stability:
        anomaly_flags.append("unicode_count_unstable_or_implausible")

    output_length_consistency = _output_length_consistency(by_id, usage_outputs)
    if usage_outputs and not output_length_consistency:
        anomaly_flags.append("output_tokens_do_not_track_response_length")

    native_count_consistency, native_count_evidence = _native_count_consistency(token_traces)
    if native_count_consistency is False:
        anomaly_flags.append("native_count_disagrees_with_usage")

    score = 1.0
    penalties = {
        "usage_missing": 0.42,
        "input_tokens_not_monotonic": 0.22,
        "implausible_input_token_slope": 0.20,
        "constant_or_nearly_constant_input_counts": 0.25,
        "cache_signal_inconsistent": 0.08,
        "unicode_count_unstable_or_implausible": 0.12,
        "output_tokens_do_not_track_response_length": 0.10,
        "native_count_disagrees_with_usage": 0.18,
    }
    for flag in anomaly_flags:
        score -= penalties.get(flag, 0.05)
    token_truth_score = round(clamp(score), 4)

    evidence = {
        "input_counts": usage_inputs,
        "output_counts": usage_outputs,
        "prompt_estimates": {trace.probe_id: trace.prompt_estimate for trace in token_traces},
        "latencies_ms": {trace.probe_id: trace.latency_ms for trace in token_traces},
        "slope": slope_evidence,
        "native_count": native_count_evidence,
    }
    features = TokenAuditFeatures(
        token_truth_score=token_truth_score,
        usage_available=usage_available,
        input_token_monotonic=input_token_monotonic,
        slope_consistency=slope_consistency,
        constant_count_detected=constant_count_detected,
        cache_signal_consistency=cache_signal_consistency,
        unicode_count_stability=unicode_count_stability,
        output_length_consistency=output_length_consistency,
        native_count_consistency=native_count_consistency,
        anomaly_flags=anomaly_flags,
        evidence=evidence,
    )
    return features, _feature_results(features, language)


def _slope_consistency(ordered_pairs: list[tuple[str, int | None, int | None]]) -> tuple[bool, dict[str, Any]]:
    ratios: list[float] = []
    pair_evidence: list[dict[str, Any]] = []
    for probe_id, reported, estimated in ordered_pairs:
        if reported is None or estimated is None:
            continue
        ratio = reported / max(estimated, 1)
        ratios.append(ratio)
        pair_evidence.append({"probe_id": probe_id, "reported": reported, "estimated": estimated, "ratio": round(ratio, 4)})
    if len(ratios) < 4:
        return False, {"pairs": pair_evidence, "reason": "insufficient_usage"}
    med = median(ratios)
    spread = max(ratios) - min(ratios)
    plausible = 0.25 <= med <= 5.0 and spread <= max(4.0, med * 2.5)
    return plausible, {"pairs": pair_evidence, "median_ratio": round(med, 4), "spread": round(spread, 4)}


def _cache_signal_consistency(by_id: dict[str, Trace]) -> bool | None:
    plain = by_id.get("cache_prefix_plain")
    nonce = by_id.get("cache_prefix_nonce")
    if not plain or not nonce or not plain.usage or not nonce.usage:
        return None
    cached_keys = ("cached_tokens", "cached_input_tokens", "cachedContentTokenCount")
    plain_raw = plain.reply.meta.get("raw_usage") if isinstance(plain.reply.meta.get("raw_usage"), dict) else {}
    nonce_raw = nonce.reply.meta.get("raw_usage") if isinstance(nonce.reply.meta.get("raw_usage"), dict) else {}
    has_cache_meta = any(key in plain_raw or key in nonce_raw for key in cached_keys)
    if has_cache_meta:
        return True
    if plain.usage.input is None or nonce.usage.input is None:
        return None
    delta = abs(plain.usage.input - nonce.usage.input)
    return delta <= max(8, int(max(plain.usage.input, nonce.usage.input) * 0.08))


def _unicode_count_stability(by_id: dict[str, Trace]) -> bool:
    ascii_trace = by_id.get("usage_ascii_short")
    unicode_trace = by_id.get("usage_unicode_edge")
    if not ascii_trace or not unicode_trace or not ascii_trace.usage or not unicode_trace.usage:
        return False
    if ascii_trace.usage.input is None or unicode_trace.usage.input is None:
        return False
    return unicode_trace.usage.input >= ascii_trace.usage.input


def _output_length_consistency(by_id: dict[str, Trace], usage_outputs: dict[str, int]) -> bool:
    short_trace = by_id.get("output_short")
    long_trace = by_id.get("output_long")
    short_usage = usage_outputs.get("output_short")
    long_usage = usage_outputs.get("output_long")
    if not short_trace or not long_trace or short_usage is None or long_usage is None:
        return True
    text_growth = len(long_trace.reply.text.strip()) > len(short_trace.reply.text.strip()) * 2
    token_growth = long_usage > short_usage
    return (not text_growth) or token_growth

def _native_count_consistency(traces: list[Trace]) -> tuple[bool | None, dict[str, Any]]:
    comparisons: list[dict[str, Any]] = []
    error_count = 0
    for trace in traces:
        payload = trace.reply.meta.get("native_token_count") if isinstance(trace.reply.meta.get("native_token_count"), dict) else None
        if not payload:
            continue
        if payload.get("status") != "ok":
            error_count += 1
            comparisons.append({"probe_id": trace.probe_id, "status": payload.get("status"), "error": payload.get("error")})
            continue
        native = payload.get("input_tokens") or payload.get("total_tokens")
        reported = trace.usage.input if trace.usage and trace.usage.input is not None else None
        if native is None or reported is None:
            comparisons.append({"probe_id": trace.probe_id, "status": "missing_comparable_count", "native": native, "reported": reported})
            continue
        try:
            native_int = int(native)
            reported_int = int(reported)
        except (TypeError, ValueError):
            continue
        delta = abs(native_int - reported_int)
        tolerance = max(8, int(max(native_int, reported_int) * 0.18))
        comparisons.append({"probe_id": trace.probe_id, "status": "ok", "native": native_int, "reported": reported_int, "delta": delta, "tolerance": tolerance, "within_tolerance": delta <= tolerance})
    comparable = [item for item in comparisons if item.get("status") == "ok"]
    if not comparisons:
        return None, {"status": "not_available"}
    if not comparable:
        return None, {"status": "not_comparable", "error_count": error_count, "comparisons": comparisons[:12]}
    pass_rate = sum(1 for item in comparable if item.get("within_tolerance")) / len(comparable)
    return pass_rate >= 0.75, {"status": "ok", "pass_rate": round(pass_rate, 4), "error_count": error_count, "comparisons": comparisons[:12]}

def _feature_results(features: TokenAuditFeatures, language: str | None = None) -> list[ProbeResult]:
    checks = [
        ("usage_availability", features.usage_available),
        ("input_monotonicity", features.input_token_monotonic),
        ("slope_plausibility", features.slope_consistency),
        ("constant_count_anomaly", not features.constant_count_detected),
        ("unicode_count_stability", features.unicode_count_stability),
        ("output_length_consistency", features.output_length_consistency),
    ]
    results: list[ProbeResult] = []
    for name, passed in checks:
        score = 1.0 if passed else 0.25
        results.append(
            ProbeResult(
                category="token",
                name=name,
                score=score,
                status=status_for_score(score),
                detail=t(f"token.{name}.ok" if passed else f"token.{name}.bad", language),
                evidence=features.evidence if name in {"slope_plausibility", "usage_availability"} else {},
            )
        )
    if features.native_count_consistency is not None:
        native_score = 1.0 if features.native_count_consistency else 0.25
        results.append(
            ProbeResult(
                category="token",
                name="native_count_consistency",
                score=native_score,
                status=status_for_score(native_score),
                detail="Provider-native token count endpoint agrees with usage metadata." if features.native_count_consistency else "Provider-native token count endpoint disagrees with usage metadata.",
                evidence=features.evidence.get("native_count", {}),
            )
        )
    cache_score = 0.75 if features.cache_signal_consistency is None else (1.0 if features.cache_signal_consistency else 0.45)
    results.append(
        ProbeResult(
            category="token",
            name="cache_signal_consistency",
            score=cache_score,
            status=status_for_score(cache_score),
            detail=t(
                "token.cache_signal_consistency.neutral" if features.cache_signal_consistency is None else "token.cache_signal_consistency.ok" if features.cache_signal_consistency else "token.cache_signal_consistency.bad",
                language,
            ),
        )
    )
    results.append(
        ProbeResult(
            category="token",
            name="token_truth_score",
            score=features.token_truth_score,
            status=status_for_score(features.token_truth_score),
            detail=t("token.token_truth_score.detail", language),
            evidence={
                "token_truth_score": features.token_truth_score,
                "anomaly_flags": features.anomaly_flags,
            },
        )
    )
    return results
