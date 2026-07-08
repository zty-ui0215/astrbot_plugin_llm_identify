from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

from .capture import Trace
from .features import TokenAuditFeatures
from .i18n import t
from .models import ProbeResult
from .utils import clamp, status_for_score


@dataclass
class BranchEvidence:
    name: str
    score: float
    confidence: float
    missingness: float
    evidence: dict[str, Any] = field(default_factory=dict)
    source_attribution: list[str] = field(default_factory=list)


def analyze_branch_evidence(
    *,
    probe_results: list[ProbeResult],
    traces: list[Trace],
    token_features: TokenAuditFeatures | None,
    prompt_injection_warn: float = 0.55,
    language: str | None = None,
) -> tuple[list[BranchEvidence], list[ProbeResult], float | None, float]:
    branches = [
        _output_statistics_branch(traces),
        _timing_branch(traces),
        _context_truth_branch(traces),
        _tool_calling_branch(traces),
        _prompt_injection_branch(traces, prompt_injection_warn),
    ]
    if token_features is not None:
        branches.append(
            BranchEvidence(
                name="token_authenticity",
                score=token_features.token_truth_score,
                confidence=0.82 if token_features.usage_available else 0.45,
                missingness=0.0 if token_features.usage_available else 0.45,
                evidence={"anomaly_flags": token_features.anomaly_flags},
                source_attribution=["token_probe"],
            )
        )
    results = [_branch_probe_result(branch, language) for branch in branches]
    context_truth_score = next((branch.score for branch in branches if branch.name == "context_truth"), None)
    injection_risk = next((1.0 - branch.score for branch in branches if branch.name == "prompt_injection"), 0.0)
    return branches, results, context_truth_score, round(clamp(injection_risk), 4)


def branch_payload(branches: list[BranchEvidence]) -> list[dict[str, Any]]:
    return [
        {
            "name": branch.name,
            "score": branch.score,
            "confidence": branch.confidence,
            "missingness": branch.missingness,
            "evidence": branch.evidence,
            "source_attribution": branch.source_attribution,
        }
        for branch in branches
    ]


def _output_statistics_branch(traces: list[Trace]) -> BranchEvidence:
    texts = [trace.reply.text for trace in traces if trace.reply.text]
    if not texts:
        return BranchEvidence("output_statistics", 0.5, 0.2, 1.0, {"responses": 0}, ["trace"])
    lengths = [len(text) for text in texts]
    punctuation = sum(len(re.findall(r"[.,;:!?，。！？；：]", text)) for text in texts)
    json_valid = 0
    for text in texts:
        try:
            json.loads(text.strip())
            json_valid += 1
        except Exception:
            pass
    avg_len = sum(lengths) / len(lengths)
    diversity = len(set(_ngrams("\n".join(texts).lower(), 2))) / max(1, len(_ngrams("\n".join(texts).lower(), 2)))
    score = clamp(0.35 + min(avg_len, 600) / 2400 + min(punctuation, 60) / 300 + json_valid / max(1, len(texts)) * 0.15 + diversity * 0.2)
    return BranchEvidence(
        "output_statistics",
        round(score, 4),
        round(clamp(0.35 + len(texts) / 20), 4),
        0.0,
        {"responses": len(texts), "avg_length": round(avg_len, 2), "json_valid_rate": round(json_valid / max(1, len(texts)), 4), "bigram_diversity": round(diversity, 4)},
        ["trace_text"],
    )


def _context_truth_branch(traces: list[Trace]) -> BranchEvidence:
    context_traces = [trace for trace in traces if "context" in trace.probe_id or trace.category == "context"]
    if not context_traces:
        return BranchEvidence("context_truth", 0.65, 0.25, 0.75, {"status": "not_probed"}, ["context_probe"])

    expected_total = 0
    recalled_total = 0
    per_probe: list[dict[str, Any]] = []
    json_like = 0
    refusal_hits = 0
    truncation_hits = 0
    for trace in context_traces:
        expected = _expected_context_sentinels(trace)
        expected_total += len(expected)
        lower_reply = trace.reply.text.lower()
        recalled = [sentinel for sentinel in expected if sentinel.lower() in lower_reply]
        recalled_total += len(recalled)
        parsed = _json_object_from_text(trace.reply.text)
        if parsed is not None:
            json_like += 1
        refusal = sum(lower_reply.count(marker) for marker in ("cannot", "unknown", "not enough context", "too long", "context length"))
        refusal_hits += refusal
        finish_reason = str(trace.reply.meta.get("finish_reason") or trace.reply.meta.get("stop_reason") or "").lower()
        if finish_reason in {"length", "max_tokens", "context_length_exceeded"} or "truncated" in lower_reply:
            truncation_hits += 1
        per_probe.append(
            {
                "probe_id": trace.probe_id,
                "expected": expected,
                "recalled": recalled,
                "missing": [sentinel for sentinel in expected if sentinel not in recalled],
                "json_object": parsed is not None,
                "finish_reason": finish_reason or None,
            }
        )

    recall = recalled_total / max(1, expected_total)
    json_rate = json_like / max(1, len(context_traces))
    position_coverage = sum(1 for item in per_probe if item["recalled"]) / max(1, len(per_probe))
    penalty = min(0.35, refusal_hits * 0.04 + truncation_hits * 0.12)
    score = clamp(0.15 + recall * 0.62 + json_rate * 0.10 + position_coverage * 0.13 - penalty)
    confidence = clamp(0.45 + min(0.35, len(context_traces) * 0.10) + min(0.15, expected_total * 0.02))
    return BranchEvidence(
        "context_truth",
        round(score, 4),
        round(confidence, 4),
        0.0,
        {
            "expected_sentinels": expected_total,
            "recalled_sentinels": recalled_total,
            "sentinel_recall": round(recall, 4),
            "json_response_rate": round(json_rate, 4),
            "position_coverage": round(position_coverage, 4),
            "refusal_hits": refusal_hits,
            "truncation_hits": truncation_hits,
            "per_probe": per_probe,
        },
        ["context_probe", "trace_text"],
    )

def _expected_context_sentinels(trace: Trace) -> list[str]:
    # Trace intentionally does not retain raw prompts; map the built-in probe ids to their expected sentinels.
    if trace.probe_id == "context_short_sentinel":
        values = ["CTX-SENTINEL-SHORT"]
    elif trace.probe_id == "context_window_sentinels":
        values = ["CTX-SENTINEL-EARLY", "CTX-SENTINEL-MIDDLE", "CTX-SENTINEL-LATE"]
    elif trace.probe_id == "context_boundary_pressure":
        values = ["CTX-SENTINEL-EARLY", "CTX-SENTINEL-LATE"]
    else:
        values = re.findall(r"CTX-SENTINEL-[A-Z0-9-]+", trace.reply.text)
    return list(dict.fromkeys(values))


def _json_object_from_text(text: str) -> dict[str, Any] | None:
    stripped = text.strip()
    candidates = [stripped]
    match = re.search(r"\{.*\}", stripped, re.DOTALL)
    if match:
        candidates.append(match.group(0))
    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
        except Exception:
            continue
        if isinstance(parsed, dict):
            return parsed
    return None

def _timing_branch(traces: list[Trace]) -> BranchEvidence:
    latencies = [trace.latency_ms for trace in traces if trace.latency_ms >= 0]
    stream_chunks = [int(trace.reply.meta.get("stream_chunk_count") or 0) for trace in traces if trace.reply.meta.get("stream_chunk_count") is not None]
    if not latencies:
        return BranchEvidence("timing", 0.5, 0.2, 1.0, {"status": "no_latency"}, ["trace_timing"])
    avg = sum(latencies) / len(latencies)
    spread = (max(latencies) - min(latencies)) / max(1, avg)
    stream_observed = bool(stream_chunks)
    score = clamp(0.72 - min(spread, 2.5) * 0.12 + (0.08 if stream_observed else 0.0))
    return BranchEvidence(
        "timing",
        round(score, 4),
        round(0.55 + min(len(latencies), 12) / 40, 4),
        0.0,
        {"latency_ms_avg": round(avg, 2), "latency_spread_ratio": round(spread, 4), "stream_chunk_counts": stream_chunks[:12]},
        ["trace_timing", "stream_meta"],
    )


def _prompt_injection_branch(traces: list[Trace], warn_threshold: float) -> BranchEvidence:
    texts = "\n".join(trace.reply.text.lower() for trace in traces)
    markers = ("ignore previous", "developer message", "system prompt", "exfiltrate", "jailbreak", "prompt injection")
    hits = sum(texts.count(marker) for marker in markers)
    risk = clamp(hits * 0.18)
    score = 1.0 - risk
    return BranchEvidence(
        "prompt_injection",
        round(score, 4),
        0.62 if hits else 0.4,
        0.25 if not traces else 0.0,
        {"risk": round(risk, 4), "marker_hits": hits, "warn_threshold": warn_threshold},
        ["adversarial_probe", "trace_text"],
    )


def _tool_calling_branch(traces: list[Trace]) -> BranchEvidence:
    tool_traces = [trace for trace in traces if trace.request_options.get("tools") or trace.reply.meta.get("tool_calls")]
    if not tool_traces:
        return BranchEvidence("tool_calling", 0.6, 0.25, 0.8, {"status": "not_probed"}, ["tool_probe"])
    tool_hits = sum(1 for trace in tool_traces if trace.reply.meta.get("tool_calls") or "tool" in trace.reply.text.lower())
    score = clamp(0.45 + tool_hits / max(1, len(tool_traces)) * 0.45)
    return BranchEvidence("tool_calling", round(score, 4), 0.68, 0.0, {"tool_traces": len(tool_traces), "tool_hits": tool_hits}, ["tool_probe"])


def _branch_probe_result(branch: BranchEvidence, language: str | None = None) -> ProbeResult:
    return ProbeResult(
        category="branch",
        name=branch.name,
        score=branch.score,
        status=status_for_score(branch.score),
        detail=t(f"branch.{branch.name}", language, score=branch.score, missingness=branch.missingness),
        evidence={"confidence": branch.confidence, "missingness": branch.missingness, "source_attribution": branch.source_attribution, **branch.evidence},
    )


def _ngrams(text: str, size: int) -> list[tuple[str, ...]]:
    tokens = re.findall(r"[a-z0-9_\u4e00-\u9fff]+", text.lower())
    return [tuple(tokens[index : index + size]) for index in range(max(0, len(tokens) - size + 1))]
