from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from .features.fingerprint import FAMILIES


TRUST_TIERS = {"T0", "T1", "T2", "T3"}
SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+(?:[-+][A-Za-z0-9._-]+)?$")
SECRET_RE = re.compile(
    r"(sk-[A-Za-z0-9_-]{12,}|api[_-]?key|authorization|bearer\s+[A-Za-z0-9._-]{10,}|"
    r"-----BEGIN [A-Z ]*PRIVATE KEY-----)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class CorpusValidationIssue:
    code: str
    path: str
    message: str
    severity: str = "error"


@dataclass
class CorpusValidationReport:
    schema_version: str | None = None
    errors: list[CorpusValidationIssue] = field(default_factory=list)
    warnings: list[CorpusValidationIssue] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors

    def as_metadata(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "schema_version": self.schema_version,
            "errors": [issue.__dict__ for issue in self.errors],
            "warnings": [issue.__dict__ for issue in self.warnings],
        }


def validate_trusted_corpus(raw: Any) -> CorpusValidationReport:
    report = CorpusValidationReport()
    if not isinstance(raw, dict):
        _error(report, "root_type", "$", "trusted corpus root must be a JSON object")
        return report

    schema_version = raw.get("schema_version")
    report.schema_version = str(schema_version) if schema_version is not None else None
    if not isinstance(schema_version, str) or not SEMVER_RE.match(schema_version):
        _error(report, "schema_version", "$.schema_version", "schema_version must be a semantic version string")

    corpus_version = raw.get("corpus_version") or raw.get("version")
    if not isinstance(corpus_version, str) or not corpus_version.strip():
        _error(report, "corpus_version", "$.corpus_version", "corpus_version must be a non-empty string")

    _detect_sensitive_values(raw, report)
    _validate_source_attribution(raw, report)
    _validate_provider_families(raw, report)
    _validate_model_profiles(raw, report)
    _validate_protocol_traits(raw, report)
    _validate_references(raw, report)
    _validate_alias_contradictions(raw, report)
    return report


def validate_trusted_corpus_or_raise(raw: Any) -> CorpusValidationReport:
    report = validate_trusted_corpus(raw)
    if not report.ok:
        summary = "; ".join(f"{issue.path}: {issue.code}" for issue in report.errors[:6])
        raise ValueError(f"trusted corpus validation failed: {summary}")
    return report


def _validate_source_attribution(raw: dict[str, Any], report: CorpusValidationReport) -> None:
    attribution = raw.get("source_attribution") or raw.get("sources")
    if not isinstance(attribution, list) or not attribution:
        _warn(report, "source_attribution_missing", "$.source_attribution", "source_attribution should contain at least one source")
        return
    for index, item in enumerate(attribution):
        path = f"$.source_attribution[{index}]"
        if not isinstance(item, dict):
            _error(report, "source_attribution_type", path, "source attribution entries must be objects")
            continue
        if not item.get("id") or not item.get("kind"):
            _error(report, "source_attribution_fields", path, "source attribution entries require id and kind")


def _validate_provider_families(raw: dict[str, Any], report: CorpusValidationReport) -> None:
    families = raw.get("provider_families")
    if not isinstance(families, list) or not families:
        _warn(report, "provider_families_missing", "$.provider_families", "provider_families should enumerate allowed provider families")
        return
    seen: set[str] = set()
    for index, item in enumerate(families):
        path = f"$.provider_families[{index}]"
        if not isinstance(item, dict):
            _error(report, "provider_family_type", path, "provider family entries must be objects")
            continue
        family_id = str(item.get("id") or "")
        if family_id not in FAMILIES:
            _error(report, "provider_family_unknown", f"{path}.id", f"unknown provider family {family_id!r}")
        if family_id in seen:
            _error(report, "provider_family_duplicate", f"{path}.id", f"duplicate provider family {family_id!r}")
        seen.add(family_id)


def _validate_model_profiles(raw: dict[str, Any], report: CorpusValidationReport) -> None:
    profiles = raw.get("model_profiles")
    if not isinstance(profiles, list):
        _error(report, "model_profiles_type", "$.model_profiles", "model_profiles must be a list")
        return
    seen_ids: set[str] = set()
    for index, profile in enumerate(profiles):
        path = f"$.model_profiles[{index}]"
        if not isinstance(profile, dict):
            _error(report, "model_profile_type", path, "model profile entries must be objects")
            continue
        profile_id = str(profile.get("id") or "")
        if not profile_id:
            _error(report, "model_profile_id", f"{path}.id", "model profile id is required")
        elif profile_id in seen_ids:
            _error(report, "model_profile_duplicate", f"{path}.id", f"duplicate model profile {profile_id!r}")
        seen_ids.add(profile_id)
        _validate_family(profile.get("provider_family_id") or profile.get("family"), f"{path}.provider_family_id", report)
        _validate_tier(profile.get("trust_tier", "T2"), f"{path}.trust_tier", report)
        aliases = profile.get("aliases", [])
        if aliases is not None and (not isinstance(aliases, list) or not all(isinstance(alias, str) and alias.strip() for alias in aliases)):
            _error(report, "model_profile_aliases", f"{path}.aliases", "aliases must be a list of non-empty strings")


def _validate_protocol_traits(raw: dict[str, Any], report: CorpusValidationReport) -> None:
    traits = raw.get("protocol_traits", [])
    if traits is None:
        return
    if not isinstance(traits, list):
        _error(report, "protocol_traits_type", "$.protocol_traits", "protocol_traits must be a list")
        return
    seen_ids: set[str] = set()
    for index, trait in enumerate(traits):
        path = f"$.protocol_traits[{index}]"
        if not isinstance(trait, dict):
            _error(report, "protocol_trait_type", path, "protocol trait entries must be objects")
            continue
        trait_id = str(trait.get("id") or "")
        if not trait_id:
            _error(report, "protocol_trait_id", f"{path}.id", "protocol trait id is required")
        elif trait_id in seen_ids:
            _error(report, "protocol_trait_duplicate", f"{path}.id", f"duplicate protocol trait {trait_id!r}")
        seen_ids.add(trait_id)
        _validate_family(trait.get("provider_family_id") or trait.get("family"), f"{path}.provider_family_id", report)
        confidence = trait.get("confidence")
        if confidence is not None and not _number_between(confidence, 0.0, 1.0):
            _error(report, "protocol_trait_confidence", f"{path}.confidence", "confidence must be between 0 and 1")


def _validate_references(raw: dict[str, Any], report: CorpusValidationReport) -> None:
    records = raw.get("accepted_references") or raw.get("references") or raw.get("records") or []
    if not isinstance(records, list):
        _error(report, "references_type", "$.accepted_references", "accepted references must be a list")
        return
    seen_ids: set[str] = set()
    for index, record in enumerate(records):
        path = f"$.accepted_references[{index}]"
        if not isinstance(record, dict):
            _error(report, "reference_type", path, "accepted reference entries must be objects")
            continue
        record_id = str(record.get("record_id") or record.get("id") or "")
        if not record_id:
            _error(report, "reference_id", f"{path}.record_id", "accepted reference requires record_id")
        elif record_id in seen_ids:
            _error(report, "reference_duplicate", f"{path}.record_id", f"duplicate accepted reference {record_id!r}")
        seen_ids.add(record_id)
        _validate_tier(record.get("trust_tier", "T2"), f"{path}.trust_tier", report)
        if not record.get("provider"):
            _error(report, "reference_provider", f"{path}.provider", "accepted reference requires provider")
        if not (record.get("model_claim") or record.get("model_id")):
            _error(report, "reference_model", f"{path}.model_claim", "accepted reference requires model_claim or model_id")
        endpoint = record.get("endpoint_class")
        if not isinstance(endpoint, dict):
            _error(report, "reference_endpoint", f"{path}.endpoint_class", "accepted reference requires endpoint_class object")
            continue
        if not endpoint.get("host"):
            _error(report, "reference_endpoint_host", f"{path}.endpoint_class.host", "endpoint_class.host is required")
        tier = str(record.get("trust_tier") or "T2").upper()
        if tier in {"T0", "T1"} and endpoint.get("official_match") is not True:
            _error(report, "reference_tier_official", f"{path}.endpoint_class.official_match", "T0/T1 references must come from official endpoints")
        if not record.get("probe_pack_version"):
            _warn(report, "reference_probe_pack", f"{path}.probe_pack_version", "accepted reference should include probe_pack_version")
        if not record.get("sanitizer_version"):
            _warn(report, "reference_sanitizer", f"{path}.sanitizer_version", "accepted reference should include sanitizer_version")


def _validate_alias_contradictions(raw: dict[str, Any], report: CorpusValidationReport) -> None:
    owners: dict[str, tuple[str, str]] = {}
    for index, profile in enumerate(raw.get("model_profiles", []) or []):
        if not isinstance(profile, dict):
            continue
        family = str(profile.get("provider_family_id") or profile.get("family") or "unknown")
        values = [profile.get("id"), *(profile.get("aliases") or [])]
        for value in values:
            alias = _alias_key(value)
            if not alias:
                continue
            previous = owners.get(alias)
            if previous is not None and previous[1] != family:
                _error(
                    report,
                    "alias_family_conflict",
                    f"$.model_profiles[{index}].aliases",
                    f"alias {alias!r} maps to both {previous[1]!r} and {family!r}",
                )
            owners[alias] = (str(profile.get("id") or ""), family)


def _detect_sensitive_values(value: Any, report: CorpusValidationReport, path: str = "$") -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            key_path = f"{path}.{key}"
            if SECRET_RE.search(str(key)):
                _error(report, "sensitive_key", key_path, "trusted corpus must not contain secret-bearing keys")
            _detect_sensitive_values(item, report, key_path)
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _detect_sensitive_values(item, report, f"{path}[{index}]")
    elif isinstance(value, str) and SECRET_RE.search(value):
        _error(report, "sensitive_value", path, "trusted corpus must not contain raw secrets or authorization values")


def _validate_family(value: Any, path: str, report: CorpusValidationReport) -> None:
    if str(value or "") not in FAMILIES:
        _error(report, "family_unknown", path, f"unknown family {value!r}")


def _validate_tier(value: Any, path: str, report: CorpusValidationReport) -> None:
    if str(value or "").upper() not in TRUST_TIERS:
        _error(report, "trust_tier_unknown", path, f"unknown trust tier {value!r}")


def _number_between(value: Any, low: float, high: float) -> bool:
    return isinstance(value, (int, float)) and low <= float(value) <= high


def _alias_key(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "-", str(value or "").lower()).strip("-")


def _error(report: CorpusValidationReport, code: str, path: str, message: str) -> None:
    report.errors.append(CorpusValidationIssue(code=code, path=path, message=message, severity="error"))


def _warn(report: CorpusValidationReport, code: str, path: str, message: str) -> None:
    report.warnings.append(CorpusValidationIssue(code=code, path=path, message=message, severity="warning"))
