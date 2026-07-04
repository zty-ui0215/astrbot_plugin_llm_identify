from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Awaitable, Callable, TypeVar


T = TypeVar("T")
ProgressFn = Callable[[str, str, float], None]


@dataclass
class ProbeOrchestrator:
    retries: int = 1
    timeout_seconds: float = 60.0
    rate_limit_seconds: float = 0.0
    nonce: bool = True
    anti_cache_suffix: bool = True
    temperatures: tuple[float, ...] = (0.0,)
    progress_fn: ProgressFn | None = None
    events: list[dict[str, object]] = field(default_factory=list)

    async def run_step(self, name: str, progress: float, fn: Callable[[], Awaitable[T]]) -> T:
        self._emit("probe_started", name, progress)
        last_error: Exception | None = None
        for attempt in range(max(1, self.retries + 1)):
            try:
                result = await asyncio.wait_for(fn(), timeout=self.timeout_seconds)
                self._emit("probe_completed", name, progress)
                if self.rate_limit_seconds > 0:
                    await asyncio.sleep(self.rate_limit_seconds)
                return result
            except Exception as exc:
                last_error = exc
                if attempt >= self.retries:
                    break
                await asyncio.sleep(min(2.0, 0.25 * (attempt + 1)))
        self._emit("failed", name, progress)
        raise last_error or RuntimeError(f"{name} failed")

    def prompt_suffix(self, task_id: str | None = None) -> str:
        parts: list[str] = []
        if self.nonce and task_id:
            parts.append(f"Audit nonce: {task_id[-12:]}.")
        if self.anti_cache_suffix:
            parts.append("Do not reuse cached prior answers; answer this exact request.")
        return "\n".join(parts)

    def _emit(self, event: str, name: str, progress: float) -> None:
        item = {"event": event, "name": name, "progress": progress}
        self.events.append(item)
        if self.progress_fn:
            self.progress_fn(event, name, progress)
