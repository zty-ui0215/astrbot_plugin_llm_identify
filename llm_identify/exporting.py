from __future__ import annotations

import csv
from pathlib import Path
from typing import Iterable


def write_curve_csv(rows: Iterable[dict[str, float]], output: str | Path) -> Path:
    path = Path(output)
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ["threshold", "fpr", "tpr", "precision", "recall", "fnr"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({name: row.get(name, "") for name in fieldnames})
    return path


def default_curve_rows() -> list[dict[str, float]]:
    rows: list[dict[str, float]] = []
    for index in range(1, 10):
        threshold = index / 10
        fpr = max(0.01, (1.0 - threshold) ** 2 * 0.75)
        fnr = min(0.95, threshold ** 2 * 0.8)
        tpr = 1.0 - fnr
        precision = 1.0 - fpr * 0.55
        rows.append({"threshold": threshold, "fpr": fpr, "tpr": tpr, "precision": precision, "recall": tpr, "fnr": fnr})
    return rows


def write_curve_placeholders(output_dir: str | Path) -> list[Path]:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    csv_path = write_curve_csv(default_curve_rows(), out / "metrics.csv")
    manifest = out / "figures_manifest.json"
    manifest.write_text('{"metrics":"metrics.csv","figures":["roc.png","pr.png","threshold.png"],"status":"csv_ready"}\n', encoding="utf-8")
    return [csv_path, manifest]
