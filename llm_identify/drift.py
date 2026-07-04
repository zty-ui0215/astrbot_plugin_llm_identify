from __future__ import annotations

import math
import time
from dataclasses import dataclass
from typing import Any


@dataclass
class DriftEvent:
    target_id: str
    timestamp: int
    p_value: float
    score_delta: float
    drift_detected: bool
    evidence: dict[str, Any]


def detect_drift(target_id: str, baseline_scores: list[float], current_scores: list[float], *, p_threshold: float = 0.01) -> DriftEvent:
    baseline = [float(value) for value in baseline_scores if value is not None]
    current = [float(value) for value in current_scores if value is not None]
    if not baseline or not current:
        return DriftEvent(target_id, int(time.time()), 1.0, 0.0, False, {"status": "insufficient_samples"})
    delta = abs(sum(current) / len(current) - sum(baseline) / len(baseline))
    spread = _stddev(baseline + current) or 0.001
    z = delta / spread
    p_value = max(0.0001, min(1.0, math.exp(-z * z / 2)))
    return DriftEvent(
        target_id=target_id,
        timestamp=int(time.time()),
        p_value=round(p_value, 6),
        score_delta=round(delta, 4),
        drift_detected=p_value < p_threshold and delta >= 0.12,
        evidence={"baseline_count": len(baseline), "current_count": len(current), "z_approx": round(z, 4), "p_threshold": p_threshold},
    )


def baseline_refresh_plan(providers: list[str]) -> dict[str, Any]:
    return {
        "status": "scheduled",
        "providers": providers,
        "next_steps": ["run official direct probes", "update cached public baselines", "recompute calibration summaries"],
        "created_at": int(time.time()),
    }


def _stddev(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    mean = sum(values) / len(values)
    return math.sqrt(sum((value - mean) ** 2 for value in values) / (len(values) - 1))
