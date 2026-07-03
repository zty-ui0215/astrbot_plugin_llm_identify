from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from ..capture import Trace
from ..models import ProbeResult
from ..rules import FeatureRule, load_rules
from ..utils import clamp, status_for_score


FAMILIES = ("openai_like", "anthropic_like", "google_like", "open_source_or_relay", "unknown")


@dataclass
class MethodFingerprint:
    method: str
    family_scores: dict[str, float]
    quality: float
    evidence: dict[str, Any] = field(default_factory=dict)


@dataclass
class FingerprintFeatureBundle:
    methods: list[MethodFingerprint]
    probe_count: int
    database_status: dict[str, Any] = field(default_factory=dict)
    database_models: list[dict[str, Any]] = field(default_factory=list)


def analyze_fingerprint_traces(traces: list[Trace]) -> tuple[FingerprintFeatureBundle, list[ProbeResult]]:
    rules = load_rules()
    fingerprint_traces = [trace for trace in traces if trace.category == "fingerprint"]
    grouped: dict[str, list[Trace]] = {}
    for trace in fingerprint_traces:
        method = _method_from_probe_id(trace.probe_id, rules.feature_rules)
        grouped.setdefault(method, []).append(trace)

    methods: list[MethodFingerprint] = []
    for method, feature_rule in rules.feature_rules.items():
        method_fp = _score_rule_method(method, grouped.get(method, []), feature_rule, rules.databases)
        if method_fp.quality > 0.0:
            methods.append(method_fp)

    database_status = _database_status(rules.databases)
    bundle = FingerprintFeatureBundle(
        methods=methods,
        probe_count=len(fingerprint_traces),
        database_status=database_status,
        database_models=list(rules.databases.get("fingerprint", {}).get("models", [])),
    )
    return bundle, [_method_result(method) for method in methods]


def _method_from_probe_id(probe_id: str, feature_rules: dict[str, FeatureRule]) -> str:
    base = probe_id.split("__", 1)[0]
    for method in sorted(feature_rules, key=len, reverse=True):
        if base.startswith(method):
            return method
    return base.rsplit("_", 1)[0]


def _score_rule_method(method: str, traces: list[Trace], rule: FeatureRule, databases: dict[str, Any]) -> MethodFingerprint:
    texts = _texts(traces)
    if not texts and method not in {"static_scan", "longitudinal_drift"}:
        return MethodFingerprint(method, _normalize({"unknown": 1.0}), 0.0)
    joined = "\n".join(texts).lower()
    scores = _empty_scores()
    marker_hits: dict[str, int] = {}
    for family, markers in rule.family_markers.items():
        hits = _count(joined, markers)
        marker_hits[family] = hits
        scores[family] = scores.get(family, 0.0) + hits
    computed = _computed_method_evidence(method, traces, joined, databases)
    for family, value in computed.get("family_score_boosts", {}).items():
        scores[family] = scores.get(family, 0.0) + float(value)
    if not any(scores.values()):
        scores["unknown"] = 1.0
    quality = min(1.0, max(len(texts), computed.get("synthetic_observations", 0)) / max(1, rule.quality_divisor))
    evidence_hits = {marker: joined.count(marker) for marker in rule.evidence_markers}
    return MethodFingerprint(
        method=method,
        family_scores=_normalize(scores),
        quality=quality,
        evidence={
            "responses": len(texts),
            "marker_hits": marker_hits,
            "evidence_hits": evidence_hits,
            **computed,
        },
    )


def _computed_method_evidence(method: str, traces: list[Trace], joined: str, databases: dict[str, Any]) -> dict[str, Any]:
    if method == "reasoning_structure":
        numbered = len(re.findall(r"(^|\n)\s*(\d+\.|\d+\)|- )", joined))
        final_markers = joined.count("final:")
        return {
            "numbered_lines": numbered,
            "final_markers": final_markers,
            "family_score_boosts": {"openai_like": final_markers * 0.5, "anthropic_like": numbered * 0.2},
        }
    if method == "refusal_style":
        refusals = _count(joined, ("i can't", "i cannot", "can't help", "cannot help", "not able to"))
        safe_alt = _count(joined, ("safe alternative", "instead", "can help with", "safely"))
        over_refusal = 1 if "store household cleaning products" in joined and refusals else 0
        return {
            "refusal_markers": refusals,
            "safe_alternative_markers": safe_alt,
            "over_refusal": over_refusal,
            "family_score_boosts": {"anthropic_like": refusals * 0.35, "openai_like": safe_alt * 0.25, "open_source_or_relay": over_refusal * 0.7},
        }
    if method == "api_sidechannel" or method == "inference_stack":
        stream_traces = [trace for trace in traces if trace.reply.meta.get("stream_chunk_count") or trace.reply.meta.get("sse_event_types")]
        chunk_counts = [int(trace.reply.meta.get("stream_chunk_count") or 0) for trace in stream_traces]
        avg_chunks = sum(chunk_counts) / max(1, len(chunk_counts)) if chunk_counts else 0.0
        db_count = len(databases.get("inference_stack", {}).get("signatures", []))
        return {
            "stream_observations": len(stream_traces),
            "avg_stream_chunks": round(avg_chunks, 2),
            "database_signatures": db_count,
            "family_score_boosts": {"openai_like": 0.5 if avg_chunks > 1 else 0.0, "open_source_or_relay": 0.3 if traces and avg_chunks <= 1 else 0.0},
        }
    if method == "sampling_distribution" or method == "mixed_routing":
        normalized = [trace.reply.text.strip().lower() for trace in traces]
        unique_count = len(set(normalized))
        instability = unique_count / max(1, len(normalized))
        return {
            "unique_response_count": unique_count,
            "instability_ratio": round(instability, 4),
            "family_score_boosts": {"open_source_or_relay": 0.8 if instability > 0.6 else 0.0, "openai_like": 0.25 if instability <= 0.3 and normalized else 0.0},
        }
    if method == "embedding_fingerprint":
        db_vectors = len(databases.get("embedding", {}).get("vectors", []))
        lexical_diversity = _lexical_diversity(joined)
        return {
            "database_vectors": db_vectors,
            "lexical_diversity": lexical_diversity,
            "family_score_boosts": {"unknown": 0.5 if db_vectors == 0 else 0.0, "openai_like": lexical_diversity * 0.2},
        }
    if method == "knowledge_boundary":
        fact_count = len(databases.get("knowledge_boundary", {}).get("facts", []))
        cautious = _count(joined, ("unknown", "not publicly disclosed", "not public", "cannot verify", "not certain"))
        hallucinated = _count(joined, ("auditstar", "2028 benchmark", "released on", "exactly"))
        return {
            "database_facts": fact_count,
            "cautious_markers": cautious,
            "hallucination_markers": hallucinated,
            "family_score_boosts": {"anthropic_like": cautious * 0.45, "openai_like": cautious * 0.35, "open_source_or_relay": hallucinated * 0.55},
        }
    if method == "adversarial_robustness":
        spoofing_patterns = len(databases.get("adversarial", {}).get("spoofing_patterns", []))
        nonce_followed = joined.count("ready nonce_audit")
        return {
            "database_spoofing_patterns": spoofing_patterns,
            "nonce_followed": nonce_followed,
            "family_score_boosts": {"openai_like": nonce_followed * 0.25, "open_source_or_relay": 0.5 if "cached" in joined else 0.0},
        }
    if method == "context_truth":
        sentinel = joined.count("ctx-sentinel-alpha")
        return {"sentinel_recall": sentinel, "family_score_boosts": {"openai_like": sentinel * 0.15, "unknown": 0.2 if sentinel == 0 else 0.0}}
    return {}


def _database_status(databases: dict[str, Any]) -> dict[str, Any]:
    return {
        "fingerprint_models": len(databases.get("fingerprint", {}).get("models", [])),
        "knowledge_facts": len(databases.get("knowledge_boundary", {}).get("facts", [])),
        "embedding_vectors": len(databases.get("embedding", {}).get("vectors", [])),
        "drift_histories": len(databases.get("drift", {}).get("histories", [])),
        "static_signatures": len(databases.get("static_scan", {}).get("signatures", [])),
        "inference_signatures": len(databases.get("inference_stack", {}).get("signatures", [])),
        "adversarial_patterns": len(databases.get("adversarial", {}).get("spoofing_patterns", [])),
    }


def _empty_scores() -> dict[str, float]:
    return {family: 0.0 for family in FAMILIES}


def _normalize(scores: dict[str, float]) -> dict[str, float]:
    total = sum(max(0.0, value) for value in scores.values())
    if total <= 0:
        return {"unknown": 1.0, "openai_like": 0.0, "anthropic_like": 0.0, "google_like": 0.0, "open_source_or_relay": 0.0}
    return {family: round(max(0.0, scores.get(family, 0.0)) / total, 4) for family in FAMILIES}


def _texts(traces: list[Trace]) -> list[str]:
    return [trace.reply.text.strip() for trace in traces if trace.reply.text.strip()]


def _count(text: str, markers: tuple[str, ...]) -> int:
    return sum(text.count(marker) for marker in markers)


def _lexical_diversity(text: str) -> float:
    tokens = re.findall(r"[a-z0-9_]+", text.lower())
    if not tokens:
        return 0.0
    return round(len(set(tokens)) / len(tokens), 4)


def _method_result(method: MethodFingerprint) -> ProbeResult:
    top_family, top_score = max(method.family_scores.items(), key=lambda item: item[1])
    score = clamp(top_score * 0.7 + method.quality * 0.3)
    return ProbeResult(
        category="fingerprint",
        name=method.method,
        score=round(score, 4),
        status=status_for_score(score),
        detail=f"{method.method} points most strongly to {top_family} with quality {method.quality:.0%}.",
        evidence={
            "family_scores": method.family_scores,
            "quality": method.quality,
            **method.evidence,
        },
    )
