from __future__ import annotations

from typing import Any


def create_app(storage_root: str | None = None):
    try:
        from fastapi import FastAPI, HTTPException
    except Exception as exc:  # pragma: no cover - optional dependency.
        raise RuntimeError("FastAPI is required to run the standalone REST service") from exc

    from .storage import AuditStorage

    app = FastAPI(title="LLM Identify Audit API")
    storage = AuditStorage(storage_root)

    @app.post("/v1/audits")
    async def create_audit(payload: dict[str, Any]) -> dict[str, Any]:
        from .tasks import AuditTask

        task = AuditTask.create(target_id=str(payload.get("target_id") or "unknown"), mode=str(payload.get("suite") or "default"), payload=payload)
        storage.create_task(task)
        return {"task_id": task.task_id, "status": task.status}

    @app.get("/v1/audits/{task_id}")
    async def get_audit(task_id: str) -> dict[str, Any]:
        task = storage.get_task(task_id)
        if task is None:
            raise HTTPException(status_code=404, detail="task not found")
        return {"task": task}

    @app.get("/v1/audits/{task_id}/report")
    async def get_report(task_id: str) -> dict[str, Any]:
        report = storage.get_report_payload(task_id)
        if report is None:
            raise HTTPException(status_code=404, detail="report not found")
        return report

    return app
