from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from ..features.fingerprint import FAMILIES, FingerprintFeatureBundle, MethodFingerprint
from ..i18n import t
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


def fuse_fingerprint_features(bundle: FingerprintFeatureBundle | None, language: str | None = None) -> FingerprintFusionResult:
    if bundle is None or not bundle.methods:
        return FingerprintFusionResult(None, None, [], {}, None, None, [], {})

    pooled_log = {family: 0.0 for family in FAMILIES}
    method_scores: dict[str, dict[str, float]] = {}
    winners: list[str] = []
    method_diagnostics: list[dict[str, Any]] = []
    total_weight = 0.0

    for method in bundle.methods:
        calibrated_scores, diagnostics = _calibrated_method_distribution(method)
        method_scores[method.method] = calibrated_scores
        winners.append(_winner_from_scores(calibrated_scores))
        method_diagnostics.append({"method": method.method, **diagnostics})
        weight = float(diagnostics["weight"])
        total_weight += weight
        for family, score in calibrated_scores.items():
            pooled_log[family] += math.log(clamp(score, 1e-6, 1.0)) * weight

    distribution = _softmax_logs(pooled_log) if total_weight > 0 else _unknown_distribution()
    if len(bundle.methods) == 1:
        distribution = _mix_with_unknown(distribution, 0.18)

    sorted_families = sorted(distribution.items(), key=lambda item: item[1], reverse=True)
    top_family, top_score = sorted_families[0]
    runner_up = sorted_families[1][1] if len(sorted_families) > 1 else 0.0
    margin = top_score - runner_up
    entropy = _entropy(distribution)
    agreement = _weighted_agreement(method_diagnostics, top_family)
    winner_count = sum(1 for item in method_diagnostics if item.get("winner") == top_family)
    disagreement = round(clamp(1.0 - agreement + entropy * 0.18), 4)
    evidence_quality = min(1.0, total_weight / max(2.0, len(bundle.methods) * 0.75))
    cross_validated = agreement >= 0.45 and winner_count >= 2
    confidence = top_score * 0.42 + margin * 0.22 + agreement * 0.20 + evidence_quality * 0.16 - _calibration_penalty(method_diagnostics, entropy=entropy, margin=margin)
    if not cross_validated:
        confidence *= 0.74
    confidence = round(clamp(confidence), 4)
    spoofing_risk = round(clamp(disagreement * 0.72 + entropy * 0.25 + (0.22 if not cross_validated else 0.0) + (0.14 if top_score > 0.72 and disagreement > 0.45 else 0.0)), 4)

    candidates = _family_candidates(sorted_families, winners, bundle.methods, language, method_diagnostics, entropy=entropy, margin=margin)
    candidates.extend(_database_model_candidates(bundle.database_models, candidates))
    candidates.sort(key=lambda item: item.confidence, reverse=True)
    candidates = candidates[:12]

    findings: list[str] = []
    if cross_validated:
        findings.append(t("fingerprint.cross_validate.ok", language, family=top_family))
    else:
        findings.append(t("fingerprint.cross_validate.bad", language))
    if spoofing_risk >= 0.55:
        findings.append(t("fingerprint.disagreement.bad", language))
    if entropy >= 0.78:
        findings.append("Fingerprint evidence is high-entropy after calibration; treat the top family as tentative.")
    if bundle.database_models:
        corpus_count = sum(1 for item in bundle.database_models if item.get("corpus_source"))
        public_count = len(bundle.database_models) - corpus_count
        if corpus_count:
            findings.append(t("fingerprint.trusted_corpus.ok", language, count=corpus_count))
        if public_count:
            findings.append(t("fingerprint.public_database.ok", language, count=public_count))
    if any(value == 0 for value in bundle.database_status.values()):
        findings.append(t("fingerprint.empty_database.bad", language))

    return FingerprintFusionResult(
        fingerprint_score=round(clamp(top_score), 4),
        fingerprint_confidence=confidence,
        fingerprint_candidates=candidates,
        fingerprint_method_scores=method_scores,
        fingerprint_disagreement=disagreement,
        spoofing_risk=spoofing_risk,
        findings=findings,
        database_status={
            **bundle.database_status,
            "fusion_calibration": {
                "mode": "tempered_log_opinion_pool/v1",
                "entropy": round(entropy, 4),
                "margin": round(margin, 4),
                "agreement": round(agreement, 4),
                "evidence_quality": round(evidence_quality, 4),
                "method_diagnostics": method_diagnostics,
            },
        },
    )


def _calibrated_method_distribution(method: MethodFingerprint) -> tuple[dict[str, float], dict[str, Any]]:
    raw = _normalize_distribution(method.family_scores)
    reliability = _method_reliability(method)
    temperature = _temperature_for_reliability(reliability, method.quality)
    tempered = _temperature_scale(raw, temperature)
    unknown_mix = clamp((1.0 - method.quality) * 0.22 + (1.0 - reliability) * 0.18, 0.0, 0.45)
    calibrated = _mix_with_unknown(tempered, unknown_mix)
    sorted_scores = sorted(calibrated.items(), key=lambda item: item[1], reverse=True)
    winner, top = sorted_scores[0]
    runner_up = sorted_scores[1][1] if len(sorted_scores) > 1 else 0.0
    entropy = _entropy(calibrated)
    weight = clamp(method.quality, 0.05, 1.0) * reliability * (1.0 - min(0.45, entropy * 0.22))
    return calibrated, {
        "raw_quality": round(method.quality, 4),
        "reliability": round(reliability, 4),
        "temperature": round(temperature, 4),
        "unknown_mix": round(unknown_mix, 4),
        "entropy": round(entropy, 4),
        "margin": round(top - runner_up, 4),
        "weight": round(weight, 4),
        "winner": winner,
    }


def _method_reliability(method: MethodFingerprint) -> float:
    name = method.method.lower()
    base = 0.58
    if name.startswith("trusted_corpus:"):
        base = 0.82
    elif name.startswith("public_knowledge:"):
        base = 0.62
    elif name.startswith("external_llm_judge") or name == "auxiliary_llm_judge":
        base = 0.46
    elif name in {"api_sidechannel", "inference_stack", "tokenizer_unicode", "context_truth"}:
        base = 0.72
    elif name in {"mixed_routing", "sampling_distribution", "adversarial_robustness"}:
        base = 0.68
    elif name == "scientific_probe_design":
        base = 0.6
    elif name in {"embedding_fingerprint", "static_scan"}:
        base = 0.55
    if method.evidence.get("error"):
        base *= 0.25
    if method.evidence.get("source") == "embedded_trusted_reference":
        base = min(base, 0.74)
    return clamp(base, 0.05, 0.95)


def _temperature_for_reliability(reliability: float, quality: float) -> float:
    return clamp(1.45 - reliability * 0.55 - quality * 0.25, 0.55, 1.65)


def _temperature_scale(scores: dict[str, float], temperature: float) -> dict[str, float]:
    logs = {family: math.log(clamp(scores.get(family, 0.0), 1e-6, 1.0)) / max(temperature, 1e-6) for family in FAMILIES}
    return _softmax_logs(logs)


def _normalize_distribution(scores: dict[str, float]) -> dict[str, float]:
    total = sum(max(0.0, float(scores.get(family, 0.0))) for family in FAMILIES)
    if total <= 0:
        return _unknown_distribution()
    return {family: max(0.0, float(scores.get(family, 0.0))) / total for family in FAMILIES}


def _softmax_logs(log_values: dict[str, float]) -> dict[str, float]:
    max_log = max(log_values.values()) if log_values else 0.0
    exps = {family: math.exp(value - max_log) for family, value in log_values.items()}
    total = sum(exps.values()) or 1.0
    return {family: round(exps.get(family, 0.0) / total, 6) for family in FAMILIES}


def _mix_with_unknown(distribution: dict[str, float], amount: float) -> dict[str, float]:
    amount = clamp(amount)
    mixed = {family: distribution.get(family, 0.0) * (1.0 - amount) for family in FAMILIES}
    mixed["unknown"] = mixed.get("unknown", 0.0) + amount
    return _normalize_distribution(mixed)


def _unknown_distribution() -> dict[str, float]:
    return {"openai_like": 0.0, "anthropic_like": 0.0, "google_like": 0.0, "open_source_or_relay": 0.0, "unknown": 1.0}


def _entropy(distribution: dict[str, float]) -> float:
    max_entropy = math.log(len(FAMILIES))
    value = -sum(score * math.log(score) for score in distribution.values() if score > 0)
    return clamp(value / max_entropy if max_entropy else 0.0)


def _weighted_agreement(method_diagnostics: list[dict[str, Any]], family: str) -> float:
    total = sum(float(item.get("weight") or 0.0) for item in method_diagnostics)
    if total <= 0:
        return 0.0
    agree = sum(float(item.get("weight") or 0.0) for item in method_diagnostics if item.get("winner") == family)
    return clamp(agree / total)


def _calibration_penalty(method_diagnostics: list[dict[str, Any]], *, entropy: float, margin: float) -> float:
    low_reliability_weight = sum(float(item.get("weight") or 0.0) for item in method_diagnostics if float(item.get("reliability") or 0.0) < 0.5)
    total_weight = sum(float(item.get("weight") or 0.0) for item in method_diagnostics) or 1.0
    low_reliability_share = low_reliability_weight / total_weight
    return clamp(entropy * 0.08 + max(0.0, 0.18 - margin) * 0.25 + low_reliability_share * 0.08, 0.0, 0.22)


def _family_candidates(
    sorted_families: list[tuple[str, float]],
    winners: list[str],
    methods: list[MethodFingerprint],
    language: str | None = None,
    method_diagnostics: list[dict[str, Any]] | None = None,
    *,
    entropy: float = 0.0,
    margin: float = 0.0,
) -> list[FingerprintCandidate]:
    diagnostics = method_diagnostics or []
    return [
        FingerprintCandidate(
            name=_candidate_name(family, language),
            family=family,
            confidence=round(clamp(score * 0.64 + (winners.count(family) / max(1, len(winners))) * 0.22 + margin * 0.14), 4),
            methods=[item["method"] for item in diagnostics if item.get("winner") == family] or [method.method for method in methods if _winner(method) == family],
            evidence={
                "candidate_type": "family_cluster",
                "distribution_score": round(score, 4),
                "method_wins": winners.count(family),
                "calibration": {
                    "mode": "tempered_log_opinion_pool/v1",
                    "entropy": round(entropy, 4),
                    "margin": round(margin, 4),
                    "method_diagnostics": [item for item in diagnostics if item.get("winner") == family],
                },
            },
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
                    "candidate_type": "trusted_reference_model" if model.get("corpus_source") else "public_database_model",
                    "source": model.get("source", "fingerprint_database"),
                    "corpus_source": model.get("corpus_source"),
                    "corpus_version": model.get("corpus_version"),
                    "trust_tier": model.get("trust_tier"),
                    "provider_cluster": model.get("provider_cluster", "unknown"),
                    "family_cluster_confidence": family_candidate.confidence,
                },
            )
        )
    return exact_candidates


def _winner(method: MethodFingerprint) -> str:
    return max(method.family_scores.items(), key=lambda item: item[1])[0]


def _winner_from_scores(scores: dict[str, float]) -> str:
    return max(scores.items(), key=lambda item: item[1])[0]


def _candidate_name(family: str, language: str | None = None) -> str:
    return t(f"fingerprint.{family}", language) if family in {"openai_like", "anthropic_like", "google_like", "open_source_or_relay", "unknown"} else family
