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
    reasoning_content: str | None = None
    reasoning_signature: str | None = None
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
class ModelCandidate:
    name: str
    confidence: float
    basis: list[str] = field(default_factory=list)


@dataclass
class DetectionReport:
    provider_id: str
    claimed_model: str
    model_family: str
    protocol_profile: str
    base_model_guess: str
    certainty_label: str
    certainty_score: float
    risk_level: str
    category_scores: dict[str, float]
    candidates: list[ModelCandidate]
    results: list[ProbeResult]
    created_at: int
