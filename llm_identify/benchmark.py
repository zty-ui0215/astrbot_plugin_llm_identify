from __future__ import annotations

import csv
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

from .features.fingerprint import FAMILIES
from .utils import clamp


@dataclass(frozen=True)
class BenchmarkCase:
    case_id: str
    expected_family: str
    probabilities: dict[str, float]
    scenario: str = "official_endpoint"
    endpoint_class: str = "official"
    weight: float = 1.0
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def confidence(self) -> float:
        return clamp(float(self.probabilities.get(self.expected_family, 0.0)))

    @property
    def predicted_family(self) -> str:
        return max(self.probabilities.items(), key=lambda item: item[1])[0] if self.probabilities else "unknown"


@dataclass
class BenchmarkMetrics:
    total_cases: int
    accuracy: float
    top1_accuracy: float
    macro_f1: float
    macro_auroc: float | None
    brier_score: float
    expected_calibration_error: float
    threshold_curve: list[dict[str, float]]
    reliability_bins: list[dict[str, float]]
    confusion_matrix: dict[str, dict[str, int]]
    scenario_metrics: dict[str, dict[str, float]]
    temperature_calibration: dict[str, float]

    def as_dict(self) -> dict[str, Any]:
        return {
            "total_cases": self.total_cases,
            "accuracy": self.accuracy,
            "top1_accuracy": self.top1_accuracy,
            "macro_f1": self.macro_f1,
            "macro_auroc": self.macro_auroc,
            "brier_score": self.brier_score,
            "expected_calibration_error": self.expected_calibration_error,
            "threshold_curve": self.threshold_curve,
            "reliability_bins": self.reliability_bins,
            "confusion_matrix": self.confusion_matrix,
            "scenario_metrics": self.scenario_metrics,
            "temperature_calibration": self.temperature_calibration,
        }


def load_benchmark_cases(path: str | Path) -> list[BenchmarkCase]:
    source = Path(path)
    if source.suffix.lower() == ".jsonl":
        return [parse_benchmark_case(json.loads(line)) for line in source.read_text(encoding="utf-8").splitlines() if line.strip()]
    if source.suffix.lower() == ".csv":
        with source.open("r", encoding="utf-8-sig", newline="") as handle:
            return [parse_benchmark_case(row) for row in csv.DictReader(handle)]
    data = json.loads(source.read_text(encoding="utf-8-sig"))
    rows = data.get("cases", data) if isinstance(data, dict) else data
    if not isinstance(rows, list):
        raise ValueError("benchmark file must contain a list of cases")
    return [parse_benchmark_case(row) for row in rows]


def parse_benchmark_case(row: dict[str, Any]) -> BenchmarkCase:
    expected = str(row.get("expected_family") or row.get("label") or "").strip()
    if expected not in FAMILIES:
        raise ValueError(f"unknown expected family {expected!r}")
    probabilities = _extract_probabilities(row)
    if not probabilities:
        raise ValueError("benchmark case requires probabilities")
    total = sum(max(0.0, value) for value in probabilities.values())
    if total <= 0:
        raise ValueError("benchmark probabilities must contain positive mass")
    normalized = {family: round(max(0.0, probabilities.get(family, 0.0)) / total, 6) for family in FAMILIES}
    return BenchmarkCase(
        case_id=str(row.get("case_id") or row.get("id") or f"case-{abs(hash(json.dumps(row, sort_keys=True))) % 10**10}"),
        expected_family=expected,
        probabilities=normalized,
        scenario=str(row.get("scenario") or "official_endpoint"),
        endpoint_class=str(row.get("endpoint_class") or "official"),
        weight=float(row.get("weight") or 1.0),
        metadata={key: value for key, value in row.items() if key not in {"case_id", "id", "expected_family", "label", "probabilities", "scenario", "endpoint_class", "weight"}},
    )


def evaluate_benchmark(cases: Iterable[BenchmarkCase], *, bins: int = 10) -> BenchmarkMetrics:
    case_list = list(cases)
    if not case_list:
        raise ValueError("benchmark requires at least one case")
    total_weight = sum(max(0.0, case.weight) for case in case_list) or 1.0
    correct_weight = sum(case.weight for case in case_list if case.predicted_family == case.expected_family)
    accuracy = round(correct_weight / total_weight, 6)
    brier = _brier_score(case_list, total_weight)
    reliability = _reliability_bins(case_list, bins=bins)
    ece = _ece_from_bins(reliability)
    threshold_curve = _threshold_curve(case_list)
    temperature_calibration = fit_temperature_calibration(case_list, bins=bins)
    return BenchmarkMetrics(
        total_cases=len(case_list),
        accuracy=accuracy,
        top1_accuracy=accuracy,
        macro_f1=_macro_f1(case_list),
        macro_auroc=_macro_auroc(case_list),
        brier_score=brier,
        expected_calibration_error=ece,
        threshold_curve=threshold_curve,
        reliability_bins=reliability,
        confusion_matrix=_confusion_matrix(case_list),
        scenario_metrics=_scenario_metrics(case_list),
        temperature_calibration=temperature_calibration,
    )


def write_benchmark_artifacts(cases: Iterable[BenchmarkCase], output_dir: str | Path) -> list[Path]:
    metrics = evaluate_benchmark(cases)
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    metrics_path = out / "benchmark_metrics.json"
    metrics_path.write_text(json.dumps(metrics.as_dict(), ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
    curve_path = out / "threshold_curve.csv"
    _write_rows(curve_path, metrics.threshold_curve, ["threshold", "accepted", "coverage", "accuracy", "error_rate"])
    reliability_path = out / "reliability_bins.csv"
    _write_rows(reliability_path, metrics.reliability_bins, ["bin", "count", "weight_fraction", "confidence", "accuracy"])
    manifest_path = out / "benchmark_manifest.json"
    calibration_path = out / "temperature_calibration.json"
    calibration_path.write_text(json.dumps(metrics.temperature_calibration, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
    manifest_path.write_text(
        json.dumps(
            {
                "status": "complete",
                "metrics": metrics_path.name,
                "threshold_curve": curve_path.name,
                "reliability_bins": reliability_path.name,
                "temperature_calibration": calibration_path.name,
                "total_cases": metrics.total_cases,
            },
            ensure_ascii=True,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return [metrics_path, curve_path, reliability_path, calibration_path, manifest_path]

def fit_temperature_calibration(cases: Iterable[BenchmarkCase], *, bins: int = 10) -> dict[str, float]:
    case_list = list(cases)
    if not case_list:
        raise ValueError("temperature calibration requires at least one case")
    candidates = [round(0.5 + index * 0.05, 2) for index in range(61)]
    scored = [(temperature, _nll(_temperature_cases(case_list, temperature))) for temperature in candidates]
    best_temperature, best_nll = min(scored, key=lambda item: item[1])
    calibrated = _temperature_cases(case_list, best_temperature)
    reliability = _reliability_bins(calibrated, bins=bins)
    return {
        "mode": "temperature_grid_search/v1",
        "temperature": round(best_temperature, 4),
        "nll": round(best_nll, 6),
        "brier_score": _brier_score(calibrated, sum(case.weight for case in calibrated) or 1.0),
        "expected_calibration_error": _ece_from_bins(reliability),
        "uncalibrated_brier_score": _brier_score(case_list, sum(case.weight for case in case_list) or 1.0),
        "uncalibrated_expected_calibration_error": _ece_from_bins(_reliability_bins(case_list, bins=bins)),
    }

def default_regression_cases() -> list[BenchmarkCase]:
    rows = [
        ("official-openai", "openai_like", {"openai_like": 0.86, "anthropic_like": 0.04, "google_like": 0.04, "open_source_or_relay": 0.03, "unknown": 0.03}, "official_endpoint"),
        ("official-anthropic", "anthropic_like", {"openai_like": 0.06, "anthropic_like": 0.82, "google_like": 0.04, "open_source_or_relay": 0.04, "unknown": 0.04}, "official_endpoint"),
        ("official-google", "google_like", {"openai_like": 0.05, "anthropic_like": 0.04, "google_like": 0.84, "open_source_or_relay": 0.04, "unknown": 0.03}, "official_endpoint"),
        ("relay-open-source", "open_source_or_relay", {"openai_like": 0.12, "anthropic_like": 0.06, "google_like": 0.05, "open_source_or_relay": 0.72, "unknown": 0.05}, "relay"),
        ("spoofed-openai-claim", "open_source_or_relay", {"openai_like": 0.38, "anthropic_like": 0.08, "google_like": 0.06, "open_source_or_relay": 0.43, "unknown": 0.05}, "spoofed_endpoint"),
        ("mixed-routing", "unknown", {"openai_like": 0.28, "anthropic_like": 0.26, "google_like": 0.08, "open_source_or_relay": 0.25, "unknown": 0.13}, "mixed_routing"),
    ]
    return [BenchmarkCase(case_id=case_id, expected_family=family, probabilities=probs, scenario=scenario) for case_id, family, probs, scenario in rows]

def _temperature_cases(cases: list[BenchmarkCase], temperature: float) -> list[BenchmarkCase]:
    calibrated: list[BenchmarkCase] = []
    for case in cases:
        probs = _temperature_distribution(case.probabilities, temperature)
        calibrated.append(BenchmarkCase(case.case_id, case.expected_family, probs, case.scenario, case.endpoint_class, case.weight, case.metadata))
    return calibrated


def _temperature_distribution(probabilities: dict[str, float], temperature: float) -> dict[str, float]:
    powered = {family: clamp(float(probabilities.get(family, 0.0)), 1e-9, 1.0) ** (1.0 / max(temperature, 1e-9)) for family in FAMILIES}
    total = sum(powered.values()) or 1.0
    return {family: round(powered[family] / total, 6) for family in FAMILIES}


def _nll(cases: list[BenchmarkCase]) -> float:
    import math

    total_weight = sum(case.weight for case in cases) or 1.0
    return sum(case.weight * -math.log(clamp(case.probabilities.get(case.expected_family, 0.0), 1e-9, 1.0)) for case in cases) / total_weight


def _ece_from_bins(rows: list[dict[str, float]]) -> float:
    return round(sum(row["weight_fraction"] * abs(row["accuracy"] - row["confidence"]) for row in rows), 6)


def _macro_f1(cases: list[BenchmarkCase]) -> float:
    values: list[float] = []
    for family in FAMILIES:
        tp = sum(1 for case in cases if case.expected_family == family and case.predicted_family == family)
        fp = sum(1 for case in cases if case.expected_family != family and case.predicted_family == family)
        fn = sum(1 for case in cases if case.expected_family == family and case.predicted_family != family)
        if tp == 0 and fp == 0 and fn == 0:
            continue
        precision = tp / max(1, tp + fp)
        recall = tp / max(1, tp + fn)
        values.append(0.0 if precision + recall == 0 else 2 * precision * recall / (precision + recall))
    return round(sum(values) / len(values), 6) if values else 0.0

def _extract_probabilities(row: dict[str, Any]) -> dict[str, float]:
    raw = row.get("probabilities")
    if isinstance(raw, str):
        raw = json.loads(raw)
    if isinstance(raw, dict):
        return {family: float(raw.get(family, 0.0)) for family in FAMILIES}
    return {family: float(row.get(family, 0.0) or 0.0) for family in FAMILIES}


def _brier_score(cases: list[BenchmarkCase], total_weight: float) -> float:
    error = 0.0
    for case in cases:
        for family in FAMILIES:
            target = 1.0 if family == case.expected_family else 0.0
            error += case.weight * (case.probabilities.get(family, 0.0) - target) ** 2
    return round(error / total_weight, 6)


def _reliability_bins(cases: list[BenchmarkCase], *, bins: int) -> list[dict[str, float]]:
    total_weight = sum(case.weight for case in cases) or 1.0
    rows: list[dict[str, float]] = []
    for index in range(bins):
        low = index / bins
        high = (index + 1) / bins
        members = [case for case in cases if low <= max(case.probabilities.values()) < high or (index == bins - 1 and max(case.probabilities.values()) == 1.0)]
        if not members:
            rows.append({"bin": index, "count": 0, "weight_fraction": 0.0, "confidence": round((low + high) / 2, 6), "accuracy": 0.0})
            continue
        weight = sum(case.weight for case in members)
        confidence = sum(case.weight * max(case.probabilities.values()) for case in members) / weight
        accuracy = sum(case.weight for case in members if case.predicted_family == case.expected_family) / weight
        rows.append({"bin": index, "count": len(members), "weight_fraction": round(weight / total_weight, 6), "confidence": round(confidence, 6), "accuracy": round(accuracy, 6)})
    return rows


def _threshold_curve(cases: list[BenchmarkCase]) -> list[dict[str, float]]:
    rows: list[dict[str, float]] = []
    total = len(cases)
    for index in range(0, 21):
        threshold = round(index / 20, 2)
        accepted = [case for case in cases if max(case.probabilities.values()) >= threshold]
        correct = sum(1 for case in accepted if case.predicted_family == case.expected_family)
        rows.append(
            {
                "threshold": threshold,
                "accepted": len(accepted),
                "coverage": round(len(accepted) / total, 6),
                "accuracy": round(correct / len(accepted), 6) if accepted else 0.0,
                "error_rate": round(1.0 - (correct / len(accepted)), 6) if accepted else 0.0,
            }
        )
    return rows


def _macro_auroc(cases: list[BenchmarkCase]) -> float | None:
    aucs: list[float] = []
    for family in FAMILIES:
        positives = [(case.probabilities.get(family, 0.0), 1) for case in cases if case.expected_family == family]
        negatives = [(case.probabilities.get(family, 0.0), 0) for case in cases if case.expected_family != family]
        if not positives or not negatives:
            continue
        wins = 0.0
        for pos_score, _ in positives:
            for neg_score, _ in negatives:
                if pos_score > neg_score:
                    wins += 1.0
                elif pos_score == neg_score:
                    wins += 0.5
        aucs.append(wins / (len(positives) * len(negatives)))
    if not aucs:
        return None
    return round(sum(aucs) / len(aucs), 6)


def _confusion_matrix(cases: list[BenchmarkCase]) -> dict[str, dict[str, int]]:
    matrix = {family: {predicted: 0 for predicted in FAMILIES} for family in FAMILIES}
    for case in cases:
        matrix[case.expected_family][case.predicted_family] += 1
    return matrix


def _scenario_metrics(cases: list[BenchmarkCase]) -> dict[str, dict[str, float]]:
    grouped: dict[str, list[BenchmarkCase]] = {}
    for case in cases:
        grouped.setdefault(case.scenario, []).append(case)
    return {
        scenario: {
            "cases": len(members),
            "accuracy": round(sum(1 for case in members if case.predicted_family == case.expected_family) / len(members), 6),
            "mean_confidence": round(sum(max(case.probabilities.values()) for case in members) / len(members), 6),
        }
        for scenario, members in sorted(grouped.items())
    }


def _write_rows(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({name: row.get(name, "") for name in fieldnames})
