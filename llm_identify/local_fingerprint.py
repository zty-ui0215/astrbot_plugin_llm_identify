from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .vendored_fingerprint import get_bundled_fingerprint_pack, load_bundled_fingerprint_packs


DEFAULT_FINGERPRINT_LIBRARIES = ("bundled:llmmap", "llmmap", "rofl", "model_fingerprint")


@dataclass(frozen=True)
class FingerprintLibraryCandidate:
    module: str
    package: str | None = None
    install_source: str | None = None
    description: str = ""


@dataclass
class FingerprintLibraryStatus:
    module: str
    available: bool
    path: str | None = None
    package: str | None = None
    install_source: str | None = None
    install_command: list[str] = field(default_factory=list)
    checked_at: int = field(default_factory=lambda: int(time.time()))
    error: str | None = None
    bundled: bool = False
    license: str | None = None
    upstream_url: str | None = None


class LocalFingerprintLibraryManager:
    def __init__(self, candidates: list[FingerprintLibraryCandidate] | None = None, install_root: str | Path | None = None) -> None:
        self.candidates = candidates or [_default_candidate(name) for name in DEFAULT_FINGERPRINT_LIBRARIES]
        self.install_root = Path(install_root) if install_root else None

    @classmethod
    def from_config(cls, raw: Any, install_root: str | Path | None = None) -> "LocalFingerprintLibraryManager":
        candidates: list[FingerprintLibraryCandidate] = []
        if isinstance(raw, str):
            raw = [item.strip() for item in raw.split(",") if item.strip()]
        for item in raw or []:
            if isinstance(item, str):
                candidates.append(_default_candidate(item))
            elif isinstance(item, dict):
                module = str(item.get("module") or item.get("name") or "").strip()
                if not module:
                    continue
                candidates.append(
                    FingerprintLibraryCandidate(
                        module=module,
                        package=str(item.get("package") or module),
                        install_source=str(item.get("install_source") or item.get("source") or item.get("package") or module),
                        description=str(item.get("description") or ""),
                    )
                )
        return cls(candidates or None, install_root)

    def statuses(self) -> list[FingerprintLibraryStatus]:
        return [self.status(candidate) for candidate in self.candidates]

    def status(self, candidate: FingerprintLibraryCandidate) -> FingerprintLibraryStatus:
        if candidate.module.startswith("bundled:"):
            return self._bundled_status(candidate)
        try:
            spec = importlib.util.find_spec(candidate.module)
            available = spec is not None
            path = str(spec.origin) if spec and spec.origin else None
            return FingerprintLibraryStatus(
                module=candidate.module,
                available=available,
                path=path,
                package=candidate.package,
                install_source=candidate.install_source,
                install_command=self.install_command(candidate),
            )
        except Exception as exc:
            return FingerprintLibraryStatus(
                module=candidate.module,
                available=False,
                package=candidate.package,
                install_source=candidate.install_source,
                install_command=self.install_command(candidate),
                error=str(exc),
            )

    def install_command(self, candidate: FingerprintLibraryCandidate) -> list[str]:
        if candidate.module.startswith("bundled:"):
            return []
        command = [sys.executable, "-m", "pip", "install"]
        if self.install_root:
            command.extend(["--target", str(self.install_root)])
        command.append(candidate.install_source or candidate.package or candidate.module)
        return command

    def install(self, module: str, *, timeout_seconds: int = 300) -> FingerprintLibraryStatus:
        candidate = next((item for item in self.candidates if item.module == module), None)
        if candidate is None:
            candidate = _default_candidate(module)
        if candidate.module.startswith("bundled:"):
            return self._bundled_status(candidate)
        command = self.install_command(candidate)
        try:
            completed = subprocess.run(command, capture_output=True, text=True, timeout=timeout_seconds, check=False)
            status = self.status(candidate)
            if completed.returncode != 0:
                status.error = (completed.stderr or completed.stdout or "install failed").strip()[:1000]
            return status
        except Exception as exc:
            status = self.status(candidate)
            status.error = str(exc)
            return status

    def payload(self) -> dict[str, Any]:
        statuses = self.statuses()
        return {
            "libraries": [_status_payload(status) for status in statuses],
            "bundled_libraries": [_status_payload(status) for status in statuses if status.bundled],
            "local_operation_available": any(status.available for status in statuses),
            "install_required": not any(status.available and status.bundled for status in statuses),
        }

    def _bundled_status(self, candidate: FingerprintLibraryCandidate) -> FingerprintLibraryStatus:
        pack = get_bundled_fingerprint_pack(candidate.module)
        if pack is None:
            return FingerprintLibraryStatus(
                module=candidate.module,
                available=False,
                package=candidate.package,
                install_source=candidate.install_source,
                install_command=[],
                bundled=True,
                error="bundled fingerprint pack was not found",
            )
        return FingerprintLibraryStatus(
            module=candidate.module,
            available=True,
            path=str(pack.artifact_path),
            package="bundled",
            install_source=None,
            install_command=[],
            bundled=True,
            license=pack.license,
            upstream_url=pack.upstream_url,
        )


def write_status_report(manager: LocalFingerprintLibraryManager, path: str | Path) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(manager.payload(), ensure_ascii=True, indent=2), encoding="utf-8")
    return target


def _default_candidate(name: str) -> FingerprintLibraryCandidate:
    pack = get_bundled_fingerprint_pack(name)
    if pack is not None:
        return FingerprintLibraryCandidate(module=name, package="bundled", install_source=None, description=pack.description)
    return FingerprintLibraryCandidate(module=name, package=name, install_source=name, description="Optional local model fingerprint library")


def _status_payload(status: FingerprintLibraryStatus) -> dict[str, Any]:
    return {
        "module": status.module,
        "available": status.available,
        "path": status.path,
        "package": status.package,
        "install_source": status.install_source,
        "install_command": status.install_command,
        "checked_at": status.checked_at,
        "error": status.error,
        "bundled": status.bundled,
        "license": status.license,
        "upstream_url": status.upstream_url,
    }