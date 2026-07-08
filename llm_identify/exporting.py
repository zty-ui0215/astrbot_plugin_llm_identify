from __future__ import annotations

import csv
from pathlib import Path
from typing import Iterable

from .benchmark import default_regression_cases, evaluate_benchmark, write_benchmark_artifacts


def write_curve_csv(rows: Iterable[dict[str, float]], output: str | Path) -> Path:
    path = Path(output)
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ["threshold", "accepted", "coverage", "accuracy", "error_rate"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({name: row.get(name, "") for name in fieldnames})
    return path


def default_curve_rows() -> list[dict[str, float]]:
    return evaluate_benchmark(default_regression_cases()).threshold_curve


def write_curve_placeholders(output_dir: str | Path) -> list[Path]:
    """Write offline benchmark artifacts for CLI compatibility.

    The historical function name is retained because the CLI and older callers use it,
    but the output is now a real regression metric bundle rather than synthetic curves.
    """
    return write_benchmark_artifacts(default_regression_cases(), output_dir)