from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..features.fingerprint import FAMILIES, FingerprintFeatureBundle, MethodFingerprint
from ..models import FingerprintCandidate
from ..utils import clamp


@dataclass
class FingerprintFusionResult:
    fingerprint_score: float | None
    fingerprint_confidence: float | None
    fingerprint_candidates: list[FingerprintCandidate]
    fingerprint_method_scores: dict[str, dict[str, float]]
    fingerprint_disagreement: float | None
    spoofing_risk: float | None
    findings: list[str]
    database_status: dict[str, Any]


def fuse_fingerprint_features(bundle: FingerprintFeatureBundle | None) -> FingerprintFusionResult:
    if bundle is None or not bundle.methods:
        return FingerprintFusionResult(None, None, [], {}, None, None, [], {})

    weighted: dict[str, float] = {family: 0.0 for family in FAMILIES}
    total_quality = 0.0
    method_scores: dict[str, dict[str, float]] = {}
    winners: list[str] = []
    for method in bundle.methods:
        method_scores[method.method] = method.family_scores
        total_quality += method.quality
        winner = _winner(method)
        winners.append(winner)
        for family, score in method.family_scores.items():
            weighted[family] = weighted.get(family, 0.0) + score * method.quality

    distribution = {family: weighted.get(family, 0.0) / total_quality for family in FAMILIES} if total_quality > 0 else {"unknown": 1.0}
    sorted_families = sorted(distribution.items(), key=lambda item: item[1], reverse=True)
    top_family, top_score = sorted_families[0]
    agreement = winners.count(top_family) / max(1, len(winners))
    disagreement = round(1.0 - agreement, 4)
    evidence_quality = min(1.0, total_quality / max(2.0, len(bundle.methods) * 0.75))
    cross_validated = agreement >= 0.4 and winners.count(top_family) >= 2
    confidence = top_score * 0.55 + agreement * 0.30 + evidence_quality * 0.15
    if not cross_validated:
        confidence *= 0.72
    confidence = round(clamp(confidence), 4)
    spoofing_risk = round(clamp(disagreement * 0.95 + (0.25 if not cross_validated else 0.0) + (0.15 if top_score > 0.72 and disagreement > 0.45 else 0.0)), 4)

    candidates = _family_candidates(sorted_families, winners, bundle.methods)
    candidates.extend(_database_model_candidates(bundle.database_models, candidates))
    candidates.sort(key=lambda item: item.confidence, reverse=True)
    candidates = candidates[:12]

    findings: list[str] = []
    if cross_validated:
        findings.append(f"Fingerprint methods cross-validate around {top_family}.")
    else:
        findings.append("Fingerprint methods do not cross-validate strongly enough for a high-confidence identity claim.")
    if spoofing_risk >= 0.55:
        findings.append("Fingerprint disagreement suggests possible wrapping, mixed routing, or spoofing.")
    if bundle.database_models:
        findings.append(f"Public fingerprint baseline database contributed {len(bundle.database_models)} model candidates.")
    if any(value == 0 for value in bundle.database_status.values()):
        findings.append("One or more optional fingerprint databases are empty; rule-only scoring was used for those methods.")

    return FingerprintFusionResult(
        fingerprint_score=round(clamp(top_score), 4),
        fingerprint_confidence=confidence,
        fingerprint_candidates=candidates,
        fingerprint_method_scores=method_scores,
        fingerprint_disagreement=disagreement,
        spoofing_risk=spoofing_risk,
        findings=findings,
        database_status=bundle.database_status,
    )


def _family_candidates(sorted_families: list[tuple[str, float]], winners: list[str], methods: list[MethodFingerprint]) -> list[FingerprintCandidate]:
    return [
        FingerprintCandidate(
            name=_candidate_name(family),
            family=family,
            confidence=round(clamp(score * 0.70 + (winners.count(family) / max(1, len(winners))) * 0.30), 4),
            methods=[method.method for method in methods if _winner(method) == family],
            evidence={"candidate_type": "family_cluster", "distribution_score": round(score, 4), "method_wins": winners.count(family)},
        )
        for family, score in sorted_families[:4]
        if score > 0.01
    ]


def _database_model_candidates(database_models: list[dict[str, Any]], family_candidates: list[FingerprintCandidate]) -> list[FingerprintCandidate]:
    if not database_models or not family_candidates:
        return []
    by_family = {candidate.family: candidate for candidate in family_candidates}
    exact_candidates: list[FingerprintCandidate] = []
    per_family_count: dict[str, int] = {}
    for model in database_models:
        family = str(model.get("family") or "unknown")
        family_candidate = by_family.get(family)
        if family_candidate is None:
            continue
        per_family_count[family] = per_family_count.get(family, 0) + 1
        if per_family_count[family] > 5:
            continue
        confidence = round(clamp(family_candidate.confidence * 0.88), 4)
        exact_candidates.append(
            FingerprintCandidate(
                name=str(model.get("id") or "unknown-model"),
                family=family,
                confidence=confidence,
                methods=family_candidate.methods,
                evidence={
                    "candidate_type": "public_database_model",
                    "source": model.get("source", "fingerprint_database"),
                    "provider_cluster": model.get("provider_cluster", "unknown"),
                    "family_cluster_confidence": family_candidate.confidence,
                },
            )
        )
    return exact_candidates


def _winner(method: MethodFingerprint) -> str:
    return max(method.family_scores.items(), key=lambda item: item[1])[0]


def _candidate_name(family: str) -> str:
    return {
        "openai_like": "OpenAI-like behavior cluster",
        "anthropic_like": "Anthropic-like behavior cluster",
        "google_like": "Google/Gemini-like behavior cluster",
        "open_source_or_relay": "Open-source or relay-shaped cluster",
        "unknown": "Unknown behavior cluster",
    }.get(family, family)
