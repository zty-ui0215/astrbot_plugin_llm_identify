from __future__ import annotations

import asyncio
import hashlib
import json
import time
import urllib.request
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .corpus import CorpusLoadResult, TrustedCorpusSource, default_trusted_corpus_sources, load_trusted_corpora
from .features.fingerprint import FAMILIES, FingerprintFeatureBundle, MethodFingerprint
from .utils import clamp


JudgeFn = Callable[[str], Awaitable[str]]


AUXILIARY_JUDGE_ITEMS: tuple[dict[str, Any], ...] = (
    {"id": "behavioral_style", "weight": 0.14, "description": "General answer style, hedging, verbosity, and formatting habits."},
    {"id": "reasoning_structure", "weight": 0.12, "description": "Visible reasoning organization, correction behavior, and final-answer discipline."},
    {"id": "knowledge_boundary_honesty", "weight": 0.11, "description": "Whether uncertain or non-public facts are handled without fabrication."},
    {"id": "safety_refusal_policy", "weight": 0.09, "description": "Benign-versus-risky boundary handling and safe alternative style."},
    {"id": "format_instruction_following", "weight": 0.09, "description": "JSON, CSV, length, and exact-output compliance."},
    {"id": "unicode_tokenization_artifacts", "weight": 0.07, "description": "Unicode, escaping, markdown, and tokenizer-adjacent behavior."},
    {"id": "sampling_randomness_stability", "weight": 0.13, "description": "Repeated-output variability, deterministic constraints, and random prompt behavior."},
    {"id": "scientific_probe_quality", "weight": 0.10, "description": "Ability to generate controlled, standards-aligned, scientifically useful audit questions."},
    {"id": "routing_sidechannel_consistency", "weight": 0.08, "description": "Streaming, route stability, and inference-stack consistency signals."},
    {"id": "public_model_docs_match", "weight": 0.07, "description": "Fit against public model documentation and known capability disclosures."},
)


MODEL_FEATURE_KNOWLEDGE_BASE: tuple[dict[str, Any], ...] = (
    {
        "source_id": "openai_models_docs_2026",
        "url": "https://developers.openai.com/api/docs/models",
        "family": "openai_like",
        "summary": (
            "OpenAI model docs list latest GPT models with reasoning effort levels, Responses API support, "
            "tools such as functions/web/file search/computer use, context windows, max output, and knowledge cutoffs."
        ),
        "feature_hints": ["reasoning effort levels", "Responses API", "tool support", "large context windows", "model IDs beginning with gpt"],
    },
    {
        "source_id": "anthropic_claude_models_docs_2026",
        "url": "https://platform.claude.com/docs/en/about-claude/models/overview",
        "family": "anthropic_like",
        "summary": (
            "Anthropic Claude docs compare current Claude models by adaptive/extended thinking, pinned snapshot IDs, "
            "1M or 200k context windows, max output limits, and Claude-specific model aliases."
        ),
        "feature_hints": ["Claude IDs", "adaptive thinking", "extended thinking", "pinned snapshots", "long-context Claude variants"],
    },
    {
        "source_id": "google_gemini_models_docs_2026",
        "url": "https://ai.google.dev/gemini-api/docs/models",
        "family": "google_like",
        "summary": (
            "Google Gemini docs describe Gemini 2.5/3 models, deep reasoning and coding capabilities, "
            "Flash/Flash-Lite latency tiers, Live API voice/video models, native audio reasoning, and generative media models."
        ),
        "feature_hints": ["Gemini", "Flash", "Flash-Lite", "deep reasoning", "Live API", "native audio"],
    },
    {
        "source_id": "open_source_model_cards",
        "url": "https://www.llama.com/docs/model-cards-and-prompt-formats/",
        "family": "open_source_or_relay",
        "summary": (
            "Open-source model cards and prompt-format docs commonly expose model IDs, prompt templates, license terms, "
            "architecture notes, and deployment-specific behavior that may surface through relays or hosted endpoints."
        ),
        "feature_hints": ["model card", "prompt format", "license", "Llama", "Qwen", "Mistral", "hosted relay"],
    },
)


@dataclass(frozen=True)
class ExternalJudge:
    model: str
    judge_fn: JudgeFn
    timeout_seconds: float = 45.0
    method_id: str | None = None


@dataclass(frozen=True)
class PublicKnowledgeSource:
    source_id: str
    path: str | None = None
    url: str | None = None
    timeout_seconds: float = 20.0
    retries: int = 1


@dataclass
class EvidenceSourceResult:
    source_id: str
    source_type: str
    status: str
    evidence: dict[str, Any] = field(default_factory=dict)
    degraded_reason: str | None = None


@dataclass
class JudgeInvocation:
    model: str
    prompt: str
    response: str
    timestamp: int
    execution_status: str
    error: str | None = None


@dataclass
class EvidenceRun:
    sources: list[EvidenceSourceResult] = field(default_factory=list)
    judge_invocations: list[JudgeInvocation] = field(default_factory=list)
    methods: list[MethodFingerprint] = field(default_factory=list)
    database_models: list[dict[str, Any]] = field(default_factory=list)
    corpus_metadata: list[dict[str, Any]] = field(default_factory=list)

    @property
    def degraded_modes(self) -> list[str]:
        values: list[str] = []
        for source in self.sources:
            if source.status != "ok":
                reason = source.degraded_reason or source.status
                values.append(f"{source.source_id}: {reason}")
        for invocation in self.judge_invocations:
            if invocation.execution_status != "ok":
                reason = invocation.error or invocation.execution_status
                values.append(f"judge:{invocation.model}: {reason}")
        return values


class PublicKnowledgeSourceAdapter:
    def __init__(self, source: PublicKnowledgeSource, cache_dir: Path) -> None:
        self.source = source
        self.cache_dir = cache_dir

    async def collect(self, *, provider_id: str, claimed_model: str) -> tuple[EvidenceSourceResult, list[dict[str, Any]], MethodFingerprint | None]:
        try:
            raw = await asyncio.to_thread(self._load_json)
            models = _extract_models(raw, self.source.source_id)
            method = _score_public_models(models, provider_id=provider_id, claimed_model=claimed_model, source_id=self.source.source_id)
            return (
                EvidenceSourceResult(
                    source_id=self.source.source_id,
                    source_type="public_knowledge",
                    status="ok",
                    evidence={"models_loaded": len(models), "cache_key": self._cache_path().name if self.source.url else None},
                ),
                models,
                method,
            )
        except Exception as exc:
            cached = self._load_cached_after_failure()
            if cached is not None:
                models = _extract_models(cached, self.source.source_id)
                method = _score_public_models(models, provider_id=provider_id, claimed_model=claimed_model, source_id=self.source.source_id)
                return (
                    EvidenceSourceResult(
                        source_id=self.source.source_id,
                        source_type="public_knowledge",
                        status="cached",
                        evidence={"models_loaded": len(models), "cache_key": self._cache_path().name},
                        degraded_reason=str(exc),
                    ),
                    models,
                    method,
                )
            return (
                EvidenceSourceResult(
                    source_id=self.source.source_id,
                    source_type="public_knowledge",
                    status="unavailable",
                    degraded_reason=str(exc),
                ),
                [],
                None,
            )

    def _load_json(self) -> Any:
        if self.source.path:
            with Path(self.source.path).expanduser().open("r", encoding="utf-8-sig") as handle:
                return json.load(handle)
        if not self.source.url:
            raise ValueError("public knowledge source requires path or url")
        last_error: Exception | None = None
        for _ in range(max(1, self.source.retries + 1)):
            try:
                request = urllib.request.Request(self.source.url, headers={"User-Agent": "llm-identify/1"})
                with urllib.request.urlopen(request, timeout=self.source.timeout_seconds) as response:
                    payload = response.read().decode("utf-8")
                data = json.loads(payload)
                self.cache_dir.mkdir(parents=True, exist_ok=True)
                self._cache_path().write_text(json.dumps(data, ensure_ascii=True, indent=2), encoding="utf-8")
                return data
            except Exception as exc:
                last_error = exc
        raise RuntimeError(str(last_error) if last_error else "download failed")

    def _load_cached_after_failure(self) -> Any | None:
        if not self.source.url:
            return None
        path = self._cache_path()
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8-sig"))
        except Exception:
            return None

    def _cache_path(self) -> Path:
        key = self.source.url or self.source.path or self.source.source_id
        digest = hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]
        return self.cache_dir / f"{self.source.source_id}-{digest}.json"


class ExternalJudgeEvidenceAdapter:
    def __init__(self, judge: ExternalJudge) -> None:
        self.judge = judge

    async def collect(self, bundle: FingerprintFeatureBundle) -> tuple[JudgeInvocation, MethodFingerprint | None]:
        prompt = auxiliary_judge_prompt(bundle)
        started = int(time.time())
        try:
            response = await asyncio.wait_for(self.judge.judge_fn(prompt), timeout=self.judge.timeout_seconds)
            invocation = JudgeInvocation(
                model=self.judge.model,
                prompt=prompt,
                response=str(response),
                timestamp=started,
                execution_status="ok",
            )
            return invocation, parse_auxiliary_judgment(str(response), method=self._method_id())
        except Exception as exc:
            invocation = JudgeInvocation(
                model=self.judge.model,
                prompt=prompt,
                response="",
                timestamp=started,
                execution_status="error",
                error=str(exc),
            )
            return invocation, MethodFingerprint(
                method=self._method_id(),
                family_scores={"unknown": 1.0, "openai_like": 0.0, "anthropic_like": 0.0, "google_like": 0.0, "open_source_or_relay": 0.0},
                quality=0.05,
                evidence={"error": str(exc)},
            )

    def _method_id(self) -> str:
        return self.judge.method_id or f"external_llm_judge:{self.judge.model}"


async def collect_evidence_sources(
    *,
    provider_id: str,
    claimed_model: str,
    bundle: FingerprintFeatureBundle | None,
    judges: list[ExternalJudge],
    public_sources: list[PublicKnowledgeSource],
    trusted_corpus_sources: list[TrustedCorpusSource] | None = None,
    cache_dir: Path,
) -> EvidenceRun:
    run = EvidenceRun()
    corpus_results = await asyncio.to_thread(
        load_trusted_corpora,
        sources=trusted_corpus_sources if trusted_corpus_sources is not None else default_trusted_corpus_sources(),
        cache_dir=cache_dir,
        provider_id=provider_id,
        claimed_model=claimed_model,
    )
    for corpus_result in corpus_results:
        source = _corpus_source_result(corpus_result)
        run.sources.append(source)
        run.corpus_metadata.append(corpus_result.metadata or {"source_id": corpus_result.source_id, "status": corpus_result.status})
        run.database_models.extend(corpus_result.models)
        if corpus_result.method is not None:
            run.methods.append(corpus_result.method)
    for source in public_sources:
        result, models, method = await PublicKnowledgeSourceAdapter(source, cache_dir).collect(provider_id=provider_id, claimed_model=claimed_model)
        run.sources.append(result)
        run.database_models.extend(models)
        if method is not None:
            run.methods.append(method)
    if bundle is None or not bundle.methods:
        return run
    for judge in judges:
        invocation, method = await ExternalJudgeEvidenceAdapter(judge).collect(bundle)
        run.judge_invocations.append(invocation)
        if method is not None:
            run.methods.append(method)
    return run


def _corpus_source_result(result: CorpusLoadResult) -> EvidenceSourceResult:
    evidence = {
        "models_loaded": len(result.models),
        "corpus_version": result.metadata.get("corpus_version"),
        "schema_version": result.metadata.get("schema_version"),
        "probe_pack_version": result.metadata.get("probe_pack_version"),
        "release": result.metadata.get("release"),
        "trust_tiers": result.metadata.get("trust_tiers", {}),
        "source_attribution": result.metadata.get("source_attribution", []),
    }
    return EvidenceSourceResult(
        source_id=result.source_id,
        source_type=result.source_type,
        status=result.status,
        evidence=evidence,
        degraded_reason=result.degraded_reason,
    )


def auxiliary_judge_prompt(bundle: FingerprintFeatureBundle) -> str:
    method_evidence = {
        method.method: {
            "family_scores": method.family_scores,
            "quality": method.quality,
            "evidence": _compact_evidence(method.evidence),
        }
        for method in bundle.methods
    }
    summary = {
        "judge_items": AUXILIARY_JUDGE_ITEMS,
        "method_evidence": method_evidence,
        "database_status": bundle.database_status,
        "public_model_feature_knowledge_base": MODEL_FEATURE_KNOWLEDGE_BASE,
    }
    return (
        "You are an external LLM fingerprint evidence provider. Judge only the supplied extracted audit evidence, "
        "generated probe outputs, and public model-feature knowledge summaries. Do not infer from provider names or hidden assumptions.\n"
        "Use the judge_items weights exactly. Cover randomness/stability, standards-compliant probe design, scientific probe design, "
        "and judgment-only items where deterministic parsers are weak.\n"
        "Return compact JSON with keys: family, confidence, weighted_score, item_scores, rationale, supporting_evidence, "
        "contradicting_evidence, suggested_followup_questions. item_scores must be an object keyed by judge_items id; "
        "each value must include family, confidence, weight, and evidence. Allowed family values: "
        "openai_like, anthropic_like, google_like, open_source_or_relay, unknown.\n"
        f"FEATURES:\n{json.dumps(summary, sort_keys=True)}"
    )


def parse_auxiliary_judgment(judgment: str, *, method: str = "external_llm_judge") -> MethodFingerprint:
    text = str(judgment or "").strip()
    parsed = _parse_json_object(text)
    item_scores = _weighted_item_scores(parsed)
    if item_scores:
        scores = item_scores
        family = max(scores.items(), key=lambda item: item[1])[0]
        confidence = clamp(float(parsed.get("confidence") or max(scores.values())), 0.05, 0.95)
    else:
        family = _family_from_judgment(parsed, text.lower())
        confidence = _confidence_from_judgment(parsed, text.lower())
        scores = {family_name: 0.0 for family_name in FAMILIES}
        scores[family] = confidence
        for other in scores:
            if other != family:
                scores[other] = (1.0 - confidence) / 4.0
    structured_quality = 0.62 if item_scores else 0.5
    return MethodFingerprint(
        method=method,
        family_scores={key: round(value, 4) for key, value in scores.items()},
        quality=structured_quality if family != "unknown" else 0.22,
        evidence={
            "raw_judgment": text[:1200],
            "parsed_family": family,
            "parsed_confidence": confidence,
            "structured": bool(parsed),
            "item_scores": parsed.get("item_scores") if isinstance(parsed.get("item_scores"), dict) else {},
            "judge_item_weights": {str(item["id"]): float(item["weight"]) for item in AUXILIARY_JUDGE_ITEMS},
        },
    )


def _compact_evidence(evidence: dict[str, Any]) -> dict[str, Any]:
    compact: dict[str, Any] = {}
    for key, value in evidence.items():
        if key == "sample_responses" and isinstance(value, list):
            compact[key] = [str(item)[:420] for item in value[:4]]
        elif isinstance(value, (str, int, float, bool)) or value is None:
            compact[key] = value
        elif isinstance(value, dict):
            compact[key] = {str(k): v for k, v in list(value.items())[:12] if isinstance(v, (str, int, float, bool)) or v is None}
        elif isinstance(value, list):
            compact[key] = [item for item in value[:12] if isinstance(item, (str, int, float, bool))]
    return compact


def _weighted_item_scores(parsed: dict[str, Any]) -> dict[str, float] | None:
    raw_items = parsed.get("item_scores")
    if not isinstance(raw_items, dict):
        return None
    expected_weights = {str(item["id"]): float(item["weight"]) for item in AUXILIARY_JUDGE_ITEMS}
    scores = {family: 0.0 for family in FAMILIES}
    total_weight = 0.0
    for item_id, expected_weight in expected_weights.items():
        item = raw_items.get(item_id)
        if not isinstance(item, dict):
            continue
        family = _normalize_family(str(item.get("family") or "")) or "unknown"
        confidence = _confidence_from_judgment(item, str(item).lower())
        weight = clamp(float(item.get("weight") or expected_weight), 0.0, 1.0)
        if abs(weight - expected_weight) > 0.001:
            weight = expected_weight
        scores[family] += weight * confidence
        spill = weight * (1.0 - confidence) / 4.0
        for other in scores:
            if other != family:
                scores[other] += spill
        total_weight += weight
    if total_weight <= 0:
        return None
    return {family: round(clamp(value / total_weight, 0.0, 1.0), 4) for family, value in scores.items()}


def _extract_models(raw: Any, source_id: str) -> list[dict[str, Any]]:
    if isinstance(raw, dict):
        candidates = raw.get("models") or raw.get("fingerprints") or raw.get("data") or []
    elif isinstance(raw, list):
        candidates = raw
    else:
        candidates = []
    models: list[dict[str, Any]] = []
    for item in candidates:
        if not isinstance(item, dict):
            continue
        model_id = item.get("id") or item.get("model") or item.get("name")
        if not model_id:
            continue
        family = _normalize_family(str(item.get("family") or "")) or _family_from_text(str(model_id))
        models.append({**item, "id": str(model_id), "family": family, "source": item.get("source") or source_id})
    return models


def _score_public_models(models: list[dict[str, Any]], *, provider_id: str, claimed_model: str, source_id: str) -> MethodFingerprint | None:
    scores = {family: 0.0 for family in FAMILIES}
    matches: list[dict[str, Any]] = []
    haystacks = [claimed_model.lower(), provider_id.lower()]
    for model in models:
        model_id = str(model.get("id") or "").lower()
        provider_cluster = str(model.get("provider_cluster") or model.get("provider") or "").lower()
        if model_id and any(model_id in haystack or haystack in model_id for haystack in haystacks if haystack):
            scores[str(model.get("family") or "unknown")] = scores.get(str(model.get("family") or "unknown"), 0.0) + 1.0
            matches.append(model)
        elif provider_cluster and any(provider_cluster in haystack for haystack in haystacks if haystack):
            scores[str(model.get("family") or "unknown")] = scores.get(str(model.get("family") or "unknown"), 0.0) + 0.45
            matches.append(model)
    if not matches:
        return None
    total = sum(scores.values())
    normalized = {family: round(max(0.0, scores.get(family, 0.0)) / total, 4) for family in FAMILIES}
    return MethodFingerprint(
        method=f"public_knowledge:{source_id}",
        family_scores=normalized,
        quality=clamp(min(0.75, 0.25 + len(matches) * 0.15)),
        evidence={"matched_models": [str(item.get("id")) for item in matches[:8]], "source": source_id, "models_considered": len(models)},
    )


def _parse_json_object(text: str) -> dict[str, Any]:
    try:
        data = json.loads(text)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _family_from_judgment(parsed: dict[str, Any], lower: str) -> str:
    family = _normalize_family(str(parsed.get("family") or ""))
    if family:
        return family
    return _family_from_text(lower)


def _normalize_family(value: str) -> str | None:
    lower = value.strip().lower()
    if lower in FAMILIES:
        return lower
    if lower in {"openai", "gpt", "chatgpt"}:
        return "openai_like"
    if lower in {"anthropic", "claude"}:
        return "anthropic_like"
    if lower in {"google", "gemini", "gemma"}:
        return "google_like"
    if lower in {"open_source", "open-source", "llama", "qwen", "mistral", "relay", "proxy"}:
        return "open_source_or_relay"
    return None


def _family_from_text(text: str) -> str:
    lower = text.lower()
    if "anthropic" in lower or "claude" in lower:
        return "anthropic_like"
    if "google" in lower or "gemini" in lower or "gemma" in lower:
        return "google_like"
    if "openai" in lower or "gpt" in lower or "chatgpt" in lower:
        return "openai_like"
    if "open source" in lower or "llama" in lower or "qwen" in lower or "mistral" in lower or "relay" in lower:
        return "open_source_or_relay"
    return "unknown"


def _confidence_from_judgment(parsed: dict[str, Any], lower: str) -> float:
    raw = parsed.get("confidence")
    if isinstance(raw, (int, float)):
        return clamp(float(raw), 0.05, 0.95)
    import re

    match = re.search(r"(0\.\d+|1\.0|\d{1,3}%)", lower)
    if not match:
        return 0.55
    value = match.group(1)
    if value.endswith("%"):
        return clamp(float(value[:-1]) / 100.0, 0.05, 0.95)
    return clamp(float(value), 0.05, 0.95)

