from __future__ import annotations

import json
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any


DATA_DIR = Path(__file__).resolve().parent / "data"


@dataclass(frozen=True)
class ProbeRule:
    rule_id: str
    method: str
    prompt: str
    profiles: tuple[str, ...] = ("standard", "exhaustive")
    options: dict[str, Any] = field(default_factory=dict)

    def enabled_for(self, profile: str) -> bool:
        return profile in self.profiles


@dataclass(frozen=True)
class FeatureRule:
    method: str
    family_markers: dict[str, tuple[str, ...]]
    quality_divisor: int = 6
    evidence_markers: tuple[str, ...] = ()


@dataclass(frozen=True)
class RuleSet:
    probe_rules: tuple[ProbeRule, ...]
    feature_rules: dict[str, FeatureRule]
    databases: dict[str, Any]


@lru_cache(maxsize=1)
def load_rules() -> RuleSet:
    raw = _read_json(DATA_DIR / "fingerprint_rules.json")
    probe_rules = tuple(
        ProbeRule(
            rule_id=str(item["id"]),
            method=str(item["method"]),
            prompt=str(item["prompt"]),
            profiles=tuple(item.get("profiles") or ("standard", "exhaustive")),
            options=dict(item.get("options") or {}),
        )
        for item in raw.get("probe_rules", [])
    )
    feature_rules = {
        str(item["method"]): FeatureRule(
            method=str(item["method"]),
            family_markers={str(family): tuple(str(marker).lower() for marker in markers) for family, markers in dict(item.get("family_markers") or {}).items()},
            quality_divisor=int(item.get("quality_divisor") or 6),
            evidence_markers=tuple(str(marker).lower() for marker in item.get("evidence_markers") or ()),
        )
        for item in raw.get("feature_rules", [])
    }
    databases = {
        "fingerprint": _read_json(DATA_DIR / "fingerprint_database.json"),
        "knowledge_boundary": _read_json(DATA_DIR / "knowledge_boundary_database.json"),
        "embedding": _read_json(DATA_DIR / "embedding_fingerprint_database.json"),
        "drift": _read_json(DATA_DIR / "drift_database.json"),
        "static_scan": _read_json(DATA_DIR / "static_scan_database.json"),
        "inference_stack": _read_json(DATA_DIR / "inference_stack_database.json"),
        "adversarial": _read_json(DATA_DIR / "adversarial_database.json"),
    }
    return RuleSet(probe_rules=probe_rules, feature_rules=feature_rules, databases=databases)


def _read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"{path.name} must contain a JSON object")
    return data
