from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class TokenSnapshot:
    input: int | None = None
    output: int | None = None
    total: int | None = None


@dataclass
class ModelReply:
    text: str
    usage: TokenSnapshot | None = None
    response_id: str | None = None
    raw_type: str = ""
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass
class ProbeResult:
    category: str
    name: str
    score: float
    status: str
    detail: str
    sample: str = ""
    evidence: dict[str, Any] = field(default_factory=dict)


@dataclass
class FingerprintCandidate:
    name: str
    family: str
    confidence: float
    methods: list[str] = field(default_factory=list)
    evidence: dict[str, Any] = field(default_factory=dict)


@dataclass
class AuditReport:
    provider_id: str
    claimed_model: str
    adapter_type: str
    model_family_guess: str
    provider_probabilities: dict[str, float]
    protocol_score: float | None
    token_truth_score: float | None
    context_truth_score: float | None
    fingerprint_score: float | None
    fingerprint_confidence: float | None
    fingerprint_candidates: list[FingerprintCandidate]
    fingerprint_method_scores: dict[str, dict[str, float]]
    fingerprint_database_status: dict[str, Any]
    fingerprint_disagreement: float | None
    spoofing_risk: float | None
    proxy_probability: float
    mixture_probability: float
    confidence: float
    risk_level: str
    findings: list[str]
    probe_results: list[ProbeResult]
    trace_summary: dict[str, Any]
    created_at: int

