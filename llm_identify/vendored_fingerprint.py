from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any


DATA_DIR = Path(__file__).resolve().parent / "data"
PACKS_PATH = DATA_DIR / "bundled_fingerprint_packs.json"


@dataclass(frozen=True)
class BundledFingerprintPack:
    pack_id: str
    module: str
    display_name: str
    upstream_url: str
    license: str
    description: str
    artifact_path: Path
    probe_rules: tuple[dict[str, Any], ...]
    feature_rules: tuple[dict[str, Any], ...]
    database_sources: tuple[dict[str, Any], ...]


@lru_cache(maxsize=1)
def load_bundled_fingerprint_packs() -> tuple[BundledFingerprintPack, ...]:
    if not PACKS_PATH.exists():
        return ()
    raw = json.loads(PACKS_PATH.read_text(encoding="utf-8-sig"))
    packs: list[BundledFingerprintPack] = []
    for item in raw.get("packs", []):
        packs.append(
            BundledFingerprintPack(
                pack_id=str(item.get("id") or item.get("module") or "bundled"),
                module=str(item.get("module") or ""),
                display_name=str(item.get("display_name") or item.get("id") or "Bundled fingerprint pack"),
                upstream_url=str(item.get("upstream_url") or ""),
                license=str(item.get("license") or ""),
                description=str(item.get("description") or ""),
                artifact_path=PACKS_PATH,
                probe_rules=tuple(dict(rule) for rule in item.get("probe_rules") or []),
                feature_rules=tuple(dict(rule) for rule in item.get("feature_rules") or []),
                database_sources=tuple(dict(source) for source in item.get("database_sources") or []),
            )
        )
    return tuple(pack for pack in packs if pack.module)


def get_bundled_fingerprint_pack(module: str) -> BundledFingerprintPack | None:
    return next((pack for pack in load_bundled_fingerprint_packs() if pack.module == module), None)


def bundled_fingerprint_modules() -> tuple[str, ...]:
    return tuple(pack.module for pack in load_bundled_fingerprint_packs())