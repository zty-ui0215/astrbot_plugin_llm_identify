from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..corpus_validation import SECRET_RE
from ..utils import clamp
from .evidence_schema import SCHEMA_VERSION
from .official_endpoint_detector import OfficialEndpoint


PROMOTE = "promote_candidate"
MAINTAINER_REVIEW = "maintainer_review_required"
QUARANTINE = "quarantine"
REJECT = "reject"


@dataclass
class ContributionReviewDecision:
    status: str
    reasons: list[str] = field(default_factory=list)
    checks: dict[str, Any] = field(default_factory=dict)

    @property
    def promotable(self) -> bool:
        return self.status == PROMOTE


def review_contribution_candidate(
    package: dict[str, Any],
    *,
    existing_corpus_models: list[dict[str, Any]] | None = None,
    official_endpoint: OfficialEndpoint | None = None,
    min_score: float = 0.72,
) -> ContributionReviewDecision:
    reasons: list[str] = []
    checks: dict[str, Any] = {}

    if package.get("schema_version") != SCHEMA_VERSION:
        reasons.append("schema_version_mismatch")
    if package.get("sample_type") != "trusted_reference_candidate":
        reasons.append("sample_type_invalid")
    if package.get("verification_status") not in {MAINTAINER_REVIEW, PROMOTE}:
        reasons.append("verification_status_invalid")

    sensitive_paths = _sensitive_paths(package)
    checks["sensitive_paths"] = sensitive_paths
    if sensitive_paths:
        return ContributionReviewDecision(status=REJECT, reasons=["sensitive_content_detected", *reasons], checks=checks)

    endpoint = package.get("endpoint") if isinstance(package.get("endpoint"), dict) else {}
    provider = str(endpoint.get("provider") or "")
    official_host = str(endpoint.get("official_host") or "")
    if not provider or not official_host:
        reasons.append("endpoint_missing")
    if official_endpoint is not None:
        checks["official_endpoint_match"] = provider == official_endpoint.provider and official_host == official_endpoint.host
        if not checks["official_endpoint_match"]:
            reasons.append("official_endpoint_mismatch")

    scores = package.get("scores") if isinstance(package.get("scores"), dict) else {}
    evidence_score = _evidence_strength(scores)
    checks["evidence_strength"] = evidence_score
    if evidence_score < min_score:
        reasons.append("evidence_strength_below_floor")

    model_claim = str((package.get("model") or {}).get("claimed_by_official_endpoint") or "").strip()
    if not model_claim:
        reasons.append("model_claim_missing")

    contradiction = _corpus_contradiction(provider, model_claim, existing_corpus_models or [])
    checks["corpus_contradiction"] = contradiction
    if contradiction["contradicts"]:
        return ContributionReviewDecision(status=QUARANTINE, reasons=["corpus_contradiction", *reasons], checks=checks)
    if contradiction["duplicate"]:
        return ContributionReviewDecision(status=MAINTAINER_REVIEW, reasons=["duplicate_reference", *reasons], checks=checks)

    if reasons:
        return ContributionReviewDecision(status=MAINTAINER_REVIEW, reasons=reasons, checks=checks)
    return ContributionReviewDecision(status=PROMOTE, reasons=["all_automated_checks_passed"], checks=checks)


def _evidence_strength(scores: dict[str, Any]) -> float:
    values: list[float] = []
    for key in ("protocol_score", "token_truth_score", "context_truth_score", "fingerprint_confidence"):
        value = scores.get(key)
        if isinstance(value, (int, float)):
            values.append(clamp(float(value)))
    if not values:
        return 0.0
    values.sort()
    return round(sum(values[-3:]) / min(3, len(values)), 4)


def _corpus_contradiction(provider: str, model_claim: str, models: list[dict[str, Any]]) -> dict[str, Any]:
    provider_key = provider.lower()
    model_key = _norm(model_claim)
    duplicate = False
    conflicting: list[dict[str, Any]] = []
    for model in models:
        model_id = _norm(model.get("id"))
        aliases = {_norm(alias) for alias in model.get("aliases", []) if alias}
        cluster = str(model.get("provider_cluster") or "").lower()
        if model_key and (model_key == model_id or model_key in aliases):
            if provider_key and cluster and provider_key not in cluster and cluster not in provider_key:
                conflicting.append({"id": model.get("id"), "provider_cluster": model.get("provider_cluster"), "family": model.get("family")})
            else:
                duplicate = True
    return {"contradicts": bool(conflicting), "duplicate": duplicate, "conflicting_models": conflicting[:8]}


def _sensitive_paths(value: Any, path: str = "$") -> list[str]:
    matches: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            child_path = f"{path}.{key}"
            if SECRET_RE.search(str(key)):
                matches.append(child_path)
            matches.extend(_sensitive_paths(item, child_path))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            matches.extend(_sensitive_paths(item, f"{path}[{index}]"))
    elif isinstance(value, str) and SECRET_RE.search(value):
        matches.append(path)
    return matches


def _norm(value: Any) -> str:
    return "".join(ch for ch in str(value or "").lower() if ch.isalnum())
