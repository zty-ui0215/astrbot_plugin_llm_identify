from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any


TASK_STATUSES = ("queued", "running", "completed", "failed")


@dataclass
class AuditTask:
    task_id: str
    target_id: str
    status: str
    created_at: int
    updated_at: int
    mode: str
    progress: float = 0.0
    report_id: str | None = None
    error: str | None = None
    payload: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def create(cls, *, target_id: str, mode: str, payload: dict[str, Any] | None = None) -> "AuditTask":
        now = int(time.time())
        return cls(
            task_id=f"aud_{time.strftime('%Y%m%d_%H%M%S', time.gmtime(now))}_{uuid.uuid4().hex[:8]}",
            target_id=target_id or "unknown",
            status="queued",
            created_at=now,
            updated_at=now,
            mode=mode or "audit",
            payload=payload or {},
        )


@dataclass
class AuditEvent:
    task_id: str
    event: str
    timestamp: int
    message: str
    progress: float
    data: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def create(cls, task_id: str, event: str, message: str, progress: float, data: dict[str, Any] | None = None) -> "AuditEvent":
        return cls(task_id=task_id, event=event, timestamp=int(time.time()), message=message, progress=progress, data=data or {})


class EventRecorder:
    def __init__(self) -> None:
        self.events: list[AuditEvent] = []

    def emit(self, task_id: str, event: str, message: str, progress: float, data: dict[str, Any] | None = None) -> AuditEvent:
        item = AuditEvent.create(task_id, event, message, progress, data)
        self.events.append(item)
        return item


def sse_payload(events: list[AuditEvent]) -> str:
    import json
    from dataclasses import asdict

    lines: list[str] = []
    for event in events:
        lines.append(f"event: {event.event}")
        lines.append(f"data: {json.dumps(asdict(event), ensure_ascii=True)}")
        lines.append("")
    return "\n".join(lines)
