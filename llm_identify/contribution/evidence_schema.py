from __future__ import annotations

from dataclasses import asdict, is_dataclass
from typing import Any

from .official_endpoint_detector import OfficialEndpoint
from .sanitizer import coarse_timestamp_bucket, sanitize_value, stable_hash

SCHEMA_VERSION = "trusted-reference-candidate/v1"
PROBE_PACK_VERSION = "bundled-fingerprint-packs/v1"


def build_evidence_package(*, task_id: str, report: dict[str, Any], feature_vector: dict[str, Any] | None, official_endpoint: OfficialEndpoint, plugin_version: str) -> dict[str, Any]:
    probe_results = report.get("probe_results") or []
    return {
        "schema_version": SCHEMA_VERSION,
        "sample_type": "trusted_reference_candidate",
        "verification_status": "maintainer_review_required",
        "privacy_notice": "Contains sanitized aggregate evidence only; raw prompts, completions, keys, headers, URLs, account identifiers, IPs, and private content are excluded.",
        "task_ref": stable_hash(task_id, "task"),
        "endpoint": {
            "provider": official_endpoint.provider,
            "official_host": official_endpoint.host,
            "matched_path": official_endpoint.matched_path or "/",
        },
        "model": {"claimed_by_official_endpoint": sanitize_value(report.get("claimed_model") or "unknown")},
        "versions": {"plugin": plugin_version, "probe_pack": PROBE_PACK_VERSION},
        "time": {"created_at_bucket_utc": coarse_timestamp_bucket(report.get("created_at"))},
        "scores": sanitize_value({
            "protocol_score": report.get("protocol_score"),
            "token_truth_score": report.get("token_truth_score"),
            "context_truth_score": report.get("context_truth_score"),
            "fingerprint_score": report.get("fingerprint_score"),
            "fingerprint_confidence": report.get("fingerprint_confidence"),
            "prompt_injection_risk": report.get("prompt_injection_risk"),
            "drift_risk": report.get("drift_risk"),
            "identity_posterior": report.get("identity_posterior"),
            "authenticity_posterior": report.get("authenticity_posterior"),
            "security_posterior": report.get("security_posterior"),
        }),
        "protocol_features": sanitize_value(report.get("trace_summary") or {}),
        "timing_statistics": sanitize_value(_timing_stats(report)),
        "token_cadence_statistics": sanitize_value(_token_stats(report)),
        "probe_ids": [str(item.get("name") or "")[:120] for item in probe_results if isinstance(item, dict)],
        "capability_scores": sanitize_value({str(item.get("name") or "probe")[:120]: item.get("score") for item in probe_results if isinstance(item, dict)}),
        "fingerprint_vector": sanitize_value(feature_vector or {}),
        "maintainer_notes": "Candidate only. Do not promote to verified reference until maintainer review and multi-source consistency checks pass.",
    }


def dataclass_to_dict(value: Any) -> Any:
    if is_dataclass(value):
        return asdict(value)
    return value


def _timing_stats(report: dict[str, Any]) -> dict[str, Any]:
    summary = report.get("trace_summary") or {}
    return {"latency_ms_min": summary.get("latency_ms_min"), "latency_ms_max": summary.get("latency_ms_max"), "latency_ms_avg": summary.get("latency_ms_avg")}


def _token_stats(report: dict[str, Any]) -> dict[str, Any]:
    return {"usage_trace_count": (report.get("trace_summary") or {}).get("usage_trace_count"), "token_truth_score": report.get("token_truth_score")}