from __future__ import annotations

import json
import math
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .capture import Trace
from .models import AuditReport
from .utils import clamp

VECTOR_SCHEMA_VERSION = "dynamic-fingerprint-vector/v1"


@dataclass
class SimilarityMatch:
    vector_id: str
    task_id: str
    target_id: str
    similarity: float
    created_at: int


class DynamicFingerprintStore:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.db_path = self.root / "dynamic_fingerprints.db"
        self.root.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def add_report(self, task_id: str, target_id: str, report: AuditReport, traces: list[Trace]) -> dict[str, Any]:
        vector = build_feature_vector(report, traces)
        vector_id = f"vec_{task_id}"
        matches = self.find_similar(vector, exclude_task_id=task_id, limit=5)
        self._execute(
            "insert or replace into fingerprint_vectors(vector_id,task_id,target_id,created_at,schema_version,vector_json) values(?,?,?,?,?,?)",
            (vector_id, task_id, target_id or "unknown", int(time.time()), VECTOR_SCHEMA_VERSION, json.dumps(vector, ensure_ascii=True)),
        )
        return {"vector_id": vector_id, "schema_version": VECTOR_SCHEMA_VERSION, "dimensions": len(vector), "nearest_neighbors": [match.__dict__ for match in matches]}

    def get_vector(self, task_id: str) -> dict[str, Any] | None:
        row = self._one("select vector_json from fingerprint_vectors where task_id=?", (task_id,))
        return json.loads(row["vector_json"]) if row else None

    def find_similar(self, vector: dict[str, Any], *, exclude_task_id: str | None = None, limit: int = 5) -> list[SimilarityMatch]:
        rows = self._all("select vector_id,task_id,target_id,created_at,vector_json from fingerprint_vectors order by created_at desc limit 500", ())
        matches: list[SimilarityMatch] = []
        for row in rows:
            if exclude_task_id and row["task_id"] == exclude_task_id:
                continue
            other = json.loads(row["vector_json"])
            score = cosine_similarity(vector, other)
            matches.append(SimilarityMatch(str(row["vector_id"]), str(row["task_id"]), str(row["target_id"]), round(score, 4), int(row["created_at"])))
        return sorted(matches, key=lambda item: item.similarity, reverse=True)[:limit]

    def _init_db(self) -> None:
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute(
                "create table if not exists fingerprint_vectors(vector_id text primary key, task_id text not null unique, target_id text not null, created_at integer not null, schema_version text not null, vector_json text not null)"
            )
            conn.commit()
        finally:
            conn.close()

    def _execute(self, sql: str, params: tuple[Any, ...]) -> None:
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute(sql, params)
            conn.commit()
        finally:
            conn.close()

    def _one(self, sql: str, params: tuple[Any, ...]) -> dict[str, Any] | None:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            row = conn.execute(sql, params).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def _all(self, sql: str, params: tuple[Any, ...]) -> list[dict[str, Any]]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            return [dict(row) for row in conn.execute(sql, params).fetchall()]
        finally:
            conn.close()


def build_feature_vector(report: AuditReport, traces: list[Trace]) -> dict[str, float]:
    vector: dict[str, float] = {
        "score.protocol": _num(report.protocol_score),
        "score.token_truth": _num(report.token_truth_score),
        "score.context_truth": _num(report.context_truth_score),
        "score.fingerprint": _num(report.fingerprint_score),
        "score.fingerprint_confidence": _num(report.fingerprint_confidence),
        "score.proxy_probability": _num(report.proxy_probability),
        "score.mixture_probability": _num(report.mixture_probability),
        "score.prompt_injection_risk": _num(report.prompt_injection_risk),
        "score.drift_risk": _num(report.drift_risk),
    }
    for name, value in (report.identity_posterior or {}).items():
        vector[f"identity.{name}"] = _num(value)
    for name, value in (report.authenticity_posterior or {}).items():
        vector[f"authenticity.{name}"] = _num(value)
    for name, value in (report.security_posterior or {}).items():
        vector[f"security.{name}"] = _num(value)
    for method, scores in (report.fingerprint_method_scores or {}).items():
        if isinstance(scores, dict):
            for family, value in scores.items():
                vector[f"method.{method}.{family}"] = _num(value)
    for result in report.probe_results or []:
        vector[f"probe.{result.category}.{result.name}"] = _num(result.score)
    latencies = [trace.latency_ms for trace in traces if trace.latency_ms >= 0]
    totals = [trace.usage.total for trace in traces if trace.usage and trace.usage.total is not None]
    outputs = [trace.usage.output for trace in traces if trace.usage and trace.usage.output is not None]
    vector.update(_stats("latency", latencies, scale=10000.0))
    vector.update(_stats("tokens.total", totals, scale=4000.0))
    vector.update(_stats("tokens.output", outputs, scale=2000.0))
    categories: dict[str, int] = {}
    for trace in traces:
        categories[trace.category] = categories.get(trace.category, 0) + 1
        if trace.reply.meta.get("stream_chunk_count"):
            vector["stream.chunk_count.avg"] = vector.get("stream.chunk_count.avg", 0.0) + _num(trace.reply.meta.get("stream_chunk_count"))
    for category, count in categories.items():
        vector[f"trace.category.{category}"] = min(1.0, count / 50.0)
    if categories and "stream.chunk_count.avg" in vector:
        vector["stream.chunk_count.avg"] = clamp(vector["stream.chunk_count.avg"] / max(1, sum(categories.values())) / 100.0)
    return {key: round(clamp(value), 6) for key, value in sorted(vector.items())}


def cosine_similarity(left: dict[str, Any], right: dict[str, Any]) -> float:
    keys = set(left) | set(right)
    dot = 0.0
    left_norm = 0.0
    right_norm = 0.0
    for key in keys:
        a = _num(left.get(key))
        b = _num(right.get(key))
        dot += a * b
        left_norm += a * a
        right_norm += b * b
    if left_norm <= 0 or right_norm <= 0:
        return 0.0
    return clamp(dot / math.sqrt(left_norm * right_norm))


def _stats(prefix: str, values: list[int | float], *, scale: float) -> dict[str, float]:
    if not values:
        return {f"{prefix}.count": 0.0}
    values = [float(value) for value in values]
    avg = sum(values) / len(values)
    variance = sum((value - avg) ** 2 for value in values) / len(values)
    return {
        f"{prefix}.count": min(1.0, len(values) / 100.0),
        f"{prefix}.min": min(values) / scale,
        f"{prefix}.max": max(values) / scale,
        f"{prefix}.avg": avg / scale,
        f"{prefix}.std": math.sqrt(variance) / scale,
    }


def _num(value: Any) -> float:
    try:
        if value is None:
            return 0.0
        return float(value)
    except (TypeError, ValueError):
        return 0.0