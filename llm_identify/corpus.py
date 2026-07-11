from __future__ import annotations

import hashlib
import json
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .corpus_validation import validate_trusted_corpus_or_raise
from .features.fingerprint import FAMILIES, MethodFingerprint
from .utils import clamp


EMBEDDED_CORPUS_PATH = Path(__file__).resolve().parent / "data" / "trusted_reference_corpus.json"
COMMUNITY_REPOSITORY_PATH = Path(__file__).resolve().parent / "data" / "trusted_references"
COMMUNITY_ACCEPTED_PATH = COMMUNITY_REPOSITORY_PATH / "data" / "accepted"


@dataclass(frozen=True)
class TrustedCorpusSource:
    source_id: str
    path: str | None = None
    url: str | None = None
    sha256: str | None = None
    timeout_seconds: float = 20.0
    retries: int = 1
    required: bool = False


@dataclass
class CorpusLoadResult:
    source_id: str
    status: str
    source_type: str
    metadata: dict[str, Any] = field(default_factory=dict)
    models: list[dict[str, Any]] = field(default_factory=list)
    method: MethodFingerprint | None = None
    degraded_reason: str | None = None


class TrustedCorpusLoader:
    def __init__(self, source: TrustedCorpusSource, cache_dir: str | Path) -> None:
        self.source = source
        self.cache_dir = Path(cache_dir)

    def load(self, *, provider_id: str, claimed_model: str) -> CorpusLoadResult:
        try:
            raw, status = self._load_json()
            return self._result(raw, status=status, provider_id=provider_id, claimed_model=claimed_model)
        except Exception as exc:
            cached = self._load_cached_after_failure()
            if cached is not None:
                return self._result(cached, status="cached", provider_id=provider_id, claimed_model=claimed_model, degraded_reason=str(exc))
            if self.source.required:
                raise
            return CorpusLoadResult(
                source_id=self.source.source_id,
                status="unavailable",
                source_type="trusted_reference_corpus",
                degraded_reason=str(exc),
            )

    def _load_json(self) -> tuple[dict[str, Any], str]:
        if self.source.path:
            path = Path(self.source.path).expanduser()
            if path.is_dir():
                data = _load_accepted_directory(path, self.source.source_id)
                payload = json.dumps(data, ensure_ascii=True, sort_keys=True)
                self._verify_integrity(payload)
                return data, "ok"
            payload = path.read_text(encoding="utf-8-sig")
            self._verify_integrity(payload)
            data = json.loads(payload)
            return _object(data), "ok"
        if not self.source.url:
            raise ValueError("trusted corpus source requires path or url")
        last_error: Exception | None = None
        for _ in range(max(1, self.source.retries + 1)):
            try:
                request = urllib.request.Request(self.source.url, headers={"User-Agent": "llm-identify/1"})
                with urllib.request.urlopen(request, timeout=self.source.timeout_seconds) as response:
                    payload = response.read().decode("utf-8")
                self._verify_integrity(payload)
                data = _object(json.loads(payload))
                self.cache_dir.mkdir(parents=True, exist_ok=True)
                self._cache_path().write_text(json.dumps(data, ensure_ascii=True, indent=2), encoding="utf-8")
                return data, "ok"
            except Exception as exc:
                last_error = exc
        raise RuntimeError(str(last_error) if last_error else "download failed")

    def _load_cached_after_failure(self) -> dict[str, Any] | None:
        if not self.source.url:
            return None
        path = self._cache_path()
        if not path.exists():
            return None
        try:
            return _object(json.loads(path.read_text(encoding="utf-8-sig")))
        except Exception:
            return None

    def _cache_path(self) -> Path:
        key = self.source.url or self.source.path or self.source.source_id
        digest = hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]
        return self.cache_dir / f"trusted-corpus-{self.source.source_id}-{digest}.json"

    def _verify_integrity(self, payload: str) -> None:
        if not self.source.sha256:
            return
        digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        if digest.lower() != self.source.sha256.lower():
            raise ValueError(f"integrity check failed for trusted corpus {self.source.source_id}")

    def _result(
        self,
        raw: dict[str, Any],
        *,
        status: str,
        provider_id: str,
        claimed_model: str,
        degraded_reason: str | None = None,
    ) -> CorpusLoadResult:
        validation = validate_trusted_corpus_or_raise(raw)
        metadata = _metadata(raw, self.source.source_id, status)
        metadata["validation"] = validation.as_metadata()
        models = _extract_corpus_models(raw, self.source.source_id)
        method = _score_corpus(models, raw, provider_id=provider_id, claimed_model=claimed_model, source_id=self.source.source_id)
        return CorpusLoadResult(
            source_id=self.source.source_id,
            status=status,
            source_type="trusted_reference_corpus",
            metadata=metadata,
            models=models,
            method=method,
            degraded_reason=degraded_reason,
        )


def default_trusted_corpus_sources() -> list[TrustedCorpusSource]:
    sources: list[TrustedCorpusSource] = []
    if EMBEDDED_CORPUS_PATH.exists():
        sources.append(TrustedCorpusSource(source_id="embedded_trusted_reference", path=str(EMBEDDED_CORPUS_PATH)))
    if COMMUNITY_ACCEPTED_PATH.is_dir():
        sources.append(TrustedCorpusSource(source_id="community_trusted_references", path=str(COMMUNITY_ACCEPTED_PATH)))
    return sources


def load_trusted_corpora(
    *,
    sources: list[TrustedCorpusSource],
    cache_dir: str | Path,
    provider_id: str,
    claimed_model: str,
) -> list[CorpusLoadResult]:
    return [
        TrustedCorpusLoader(source, cache_dir).load(provider_id=provider_id, claimed_model=claimed_model)
        for source in sources
    ]


def _object(data: Any) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise ValueError("trusted corpus root must be a JSON object")
    return data


def _load_accepted_directory(path: Path, source_id: str) -> dict[str, Any]:
    records: list[dict[str, Any]] = []
    profiles: list[dict[str, Any]] = []
    for json_path in sorted(path.rglob("*.json")):
        raw = _object(json.loads(json_path.read_text(encoding="utf-8-sig")))
        if isinstance(raw.get("model_profiles"), list):
            profiles.extend(item for item in raw["model_profiles"] if isinstance(item, dict))
        corpus_records = _records(raw)
        if corpus_records:
            records.extend(corpus_records)
        elif _is_corpus_row(raw):
            records.append(raw)
        elif _is_candidate_package(raw):
            records.append(_candidate_to_corpus_row(raw))
        else:
            raise ValueError(f"unsupported accepted reference format: {json_path}")

    digest_payload = json.dumps({"model_profiles": profiles, "accepted_references": records}, ensure_ascii=True, sort_keys=True)
    digest = hashlib.sha256(digest_payload.encode("utf-8")).hexdigest()[:12]
    return {
        "schema_version": "1.0.0",
        "corpus_version": f"community-{digest}",
        "probe_pack_version": "community-mixed",
        "release": "git-submodule",
        "source_attribution": [
            {
                "id": source_id,
                "kind": "maintainer_reviewed_community_submodule",
                "notes": "Only records under data/accepted are loaded; candidate submissions are excluded.",
            }
        ],
        "provider_families": [
            {"id": "openai_like", "name": "OpenAI-like"},
            {"id": "anthropic_like", "name": "Anthropic-like"},
            {"id": "google_like", "name": "Google/Gemini-like"},
            {"id": "open_source_or_relay", "name": "Open-source or relay-shaped"},
            {"id": "unknown", "name": "Unknown"},
        ],
        "model_profiles": profiles,
        "accepted_references": records,
    }


def _is_corpus_row(raw: dict[str, Any]) -> bool:
    return bool(raw.get("record_id") and raw.get("provider") and (raw.get("model_claim") or raw.get("model_id")))


def _is_candidate_package(raw: dict[str, Any]) -> bool:
    return raw.get("sample_type") == "trusted_reference_candidate" and isinstance(raw.get("endpoint"), dict) and isinstance(raw.get("model"), dict)


def _candidate_to_corpus_row(raw: dict[str, Any]) -> dict[str, Any]:
    endpoint = raw["endpoint"]
    model = raw["model"]
    versions = raw.get("versions") if isinstance(raw.get("versions"), dict) else {}
    review = raw.get("review") if isinstance(raw.get("review"), dict) else {}
    identity = json.dumps(raw, ensure_ascii=True, sort_keys=True)
    return {
        "record_id": str(review.get("record_id") or f"community_{hashlib.sha256(identity.encode('utf-8')).hexdigest()[:20]}"),
        "schema_version": "1.0.0",
        "provider": str(endpoint.get("provider") or "unknown"),
        "trust_tier": str(review.get("trust_tier") or raw.get("trust_tier") or "T2").upper(),
        "endpoint_class": {
            "host": str(endpoint.get("official_host") or ""),
            "path_family": str(endpoint.get("matched_path") or "/"),
            "official_match": True,
        },
        "model_claim": str(model.get("claimed_by_official_endpoint") or "unknown"),
        "probe_pack_version": str(versions.get("probe_pack") or "unknown"),
        "sanitizer_version": str(versions.get("sanitizer") or "unknown"),
        "accepted_in_release": str(review.get("accepted_in_release") or "community-submodule"),
        "fingerprint_vector": raw.get("fingerprint_vector") or {},
        "capability_scores": raw.get("capability_scores") or {},
        "source_task_ref": raw.get("task_ref"),
    }


def _metadata(raw: dict[str, Any], source_id: str, status: str) -> dict[str, Any]:
    version = raw.get("corpus_version") or raw.get("version") or "unknown"
    schema = raw.get("schema_version") or "unknown"
    release = raw.get("release") or raw.get("accepted_in_release") or "embedded"
    return {
        "source_id": source_id,
        "status": status,
        "corpus_version": str(version),
        "schema_version": str(schema),
        "probe_pack_version": str(raw.get("probe_pack_version") or "unknown"),
        "release": str(release),
        "source_attribution": raw.get("source_attribution") or raw.get("sources") or [],
        "trust_tiers": _trust_tier_counts(raw),
        "integrity": "sha256" if raw.get("sha256") else "not_provided",
    }


def _trust_tier_counts(raw: dict[str, Any]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in _records(raw):
        tier = str(item.get("trust_tier") or item.get("tier") or "unknown").upper()
        counts[tier] = counts.get(tier, 0) + 1
    return counts


def _extract_corpus_models(raw: dict[str, Any], source_id: str) -> list[dict[str, Any]]:
    models: list[dict[str, Any]] = []
    for profile in raw.get("model_profiles", []) or []:
        if not isinstance(profile, dict):
            continue
        model_id = str(profile.get("id") or "").strip()
        if not model_id:
            continue
        family = _normalize_family(str(profile.get("provider_family_id") or profile.get("family") or ""))
        aliases = [str(alias) for alias in profile.get("aliases", []) if alias]
        models.append(
            {
                "id": model_id,
                "family": family or "unknown",
                "aliases": aliases,
                "provider_cluster": profile.get("provider_cluster") or profile.get("provider_family_id") or "",
                "trust_tier": profile.get("trust_tier") or "T2",
                "source": source_id,
                "corpus_source": source_id,
                "corpus_version": raw.get("corpus_version") or raw.get("version") or "unknown",
                "release": raw.get("release") or "embedded",
            }
        )
    for record in _records(raw):
        if not isinstance(record, dict):
            continue
        model_id = str(record.get("model_claim") or record.get("model_id") or record.get("id") or "").strip()
        if not model_id:
            continue
        provider = str(record.get("provider") or record.get("provider_family") or "")
        family = _normalize_family(str(record.get("family") or provider))
        endpoint = record.get("endpoint_class") if isinstance(record.get("endpoint_class"), dict) else {}
        models.append(
            {
                "id": model_id,
                "family": family or "unknown",
                "provider_cluster": provider.lower(),
                "trust_tier": str(record.get("trust_tier") or "T2").upper(),
                "source": source_id,
                "corpus_source": source_id,
                "corpus_version": raw.get("corpus_version") or raw.get("version") or record.get("schema_version") or "unknown",
                "release": raw.get("release") or record.get("accepted_in_release") or "unknown",
                "endpoint_official": endpoint.get("official_match"),
            }
        )
    return models


def _records(raw: dict[str, Any]) -> list[dict[str, Any]]:
    values = raw.get("accepted_references") or raw.get("references") or raw.get("records") or []
    return [item for item in values if isinstance(item, dict)]


def _score_corpus(
    models: list[dict[str, Any]],
    raw: dict[str, Any],
    *,
    provider_id: str,
    claimed_model: str,
    source_id: str,
) -> MethodFingerprint | None:
    scores = {family: 0.0 for family in FAMILIES}
    matches: list[dict[str, Any]] = []
    haystacks = [claimed_model.lower(), provider_id.lower()]
    for model in models:
        model_id = str(model.get("id") or "").lower()
        aliases = [str(alias).lower() for alias in model.get("aliases", [])]
        provider_cluster = str(model.get("provider_cluster") or "").lower()
        tier_weight = _tier_weight(str(model.get("trust_tier") or "T2"))
        family = str(model.get("family") or "unknown")
        if _matches_any([model_id, *aliases], haystacks):
            scores[family] = scores.get(family, 0.0) + 1.0 * tier_weight
            matches.append(model)
        elif provider_cluster and any(provider_cluster in haystack for haystack in haystacks if haystack):
            scores[family] = scores.get(family, 0.0) + 0.40 * tier_weight
            matches.append(model)
    trait_matches = _score_protocol_traits(raw, haystacks)
    for family, value in trait_matches.items():
        scores[family] = scores.get(family, 0.0) + value
    if not matches and not any(trait_matches.values()):
        return None
    total = sum(scores.values())
    normalized = {family: round(max(0.0, scores.get(family, 0.0)) / total, 4) for family in FAMILIES}
    quality = clamp(min(0.85, 0.30 + len(matches) * 0.12 + sum(trait_matches.values()) * 0.08))
    return MethodFingerprint(
        method=f"trusted_corpus:{source_id}",
        family_scores=normalized,
        quality=quality,
        evidence={
            "matched_models": [str(item.get("id")) for item in matches[:8]],
            "matched_trust_tiers": sorted({str(item.get("trust_tier") or "unknown") for item in matches}),
            "protocol_trait_matches": trait_matches,
            "source": source_id,
            "corpus_version": raw.get("corpus_version") or raw.get("version") or "unknown",
            "records_considered": len(models),
        },
    )


def _score_protocol_traits(raw: dict[str, Any], haystacks: list[str]) -> dict[str, float]:
    scores: dict[str, float] = {}
    for trait in raw.get("protocol_traits", []) or []:
        if not isinstance(trait, dict):
            continue
        text = " ".join(str(trait.get(key) or "").lower() for key in ("surface", "field", "expected_behavior", "provider_family_id"))
        if not any(token and token in " ".join(haystacks) for token in ("openai", "anthropic", "google", "gemini", "claude")):
            continue
        family = _normalize_family(str(trait.get("provider_family_id") or trait.get("family") or text)) or "unknown"
        confidence = clamp(float(trait.get("confidence") or 0.5), 0.05, 1.0)
        if any(word in text for word in ("openai", "anthropic", "google", "gemini", "claude")):
            scores[family] = scores.get(family, 0.0) + confidence * 0.25
    return scores


def _matches_any(needles: list[str], haystacks: list[str]) -> bool:
    for needle in needles:
        if not needle:
            continue
        for haystack in haystacks:
            if haystack and (needle in haystack or haystack in needle):
                return True
    return False


def _tier_weight(tier: str) -> float:
    return {"T0": 1.0, "T1": 0.9, "T2": 0.65, "T3": 0.35}.get(tier.upper(), 0.5)


def _normalize_family(value: str) -> str | None:
    lower = value.strip().lower()
    if lower in FAMILIES:
        return lower
    if lower in {"openai", "openai_like", "gpt", "chatgpt"}:
        return "openai_like"
    if lower in {"anthropic", "anthropic_like", "claude"}:
        return "anthropic_like"
    if lower in {"google", "google_like", "gemini", "gemma"}:
        return "google_like"
    if lower in {"open_source", "open-source", "open_source_or_relay", "relay", "proxy", "llama", "qwen", "mistral"}:
        return "open_source_or_relay"
    return None

