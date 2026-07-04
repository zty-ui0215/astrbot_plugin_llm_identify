from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class ContributionExporter:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def export_json(self, task_id: str, package: dict[str, Any]) -> Path:
        path = self.root / f"{task_id}.trusted_reference_candidate.json"
        path.write_text(json.dumps(package, ensure_ascii=True, indent=2), encoding="utf-8")
        return path

    def export_jsonl(self, task_id: str, package: dict[str, Any]) -> Path:
        path = self.root / f"{task_id}.trusted_reference_candidate.jsonl"
        path.write_text(json.dumps(package, ensure_ascii=True) + "\n", encoding="utf-8")
        return path