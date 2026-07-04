from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .sanitizer import stable_hash


class ConsentStore:
    def __init__(self, root: str | Path) -> None:
        self.path = Path(root) / "contribution_consent.json"
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def is_declined(self, endpoint_host: str) -> bool:
        data = self._read()
        return stable_hash(endpoint_host, "endpoint") in set(data.get("declined_endpoints", []))

    def decline(self, endpoint_host: str) -> dict[str, Any]:
        data = self._read()
        declined = set(data.get("declined_endpoints", []))
        declined.add(stable_hash(endpoint_host, "endpoint"))
        data["declined_endpoints"] = sorted(declined)
        self.path.write_text(json.dumps(data, ensure_ascii=True, indent=2), encoding="utf-8")
        return {"declined": True, "endpoint_ref": stable_hash(endpoint_host, "endpoint")}

    def _read(self) -> dict[str, Any]:
        if not self.path.exists():
            return {"declined_endpoints": []}
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {"declined_endpoints": []}
        except Exception:
            return {"declined_endpoints": []}