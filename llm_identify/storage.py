from __future__ import annotations

import csv
import json
import sqlite3
import gc
import time
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any

from .capture import Trace
from .models import AuditReport
from .privacy import RedactionPolicy, redact_value
from .pdf_export import write_pdf_report
from .scoring import format_text_report
from .tasks import AuditEvent, AuditTask


def default_data_dir() -> Path:
    return Path.cwd() / "data" / "llm_identify"


class AuditStorage:
    def __init__(self, root: str | Path | None = None, policy: RedactionPolicy | None = None) -> None:
        self.root = Path(root) if root else default_data_dir()
        self.objects = self.root / "objects"
        self.exports = self.root / "exports"
        self.db_path = self.root / "audit.db"
        self.policy = policy or RedactionPolicy()
        self.root.mkdir(parents=True, exist_ok=True)
        self.objects.mkdir(parents=True, exist_ok=True)
        self.exports.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def create_task(self, task: AuditTask) -> AuditTask:
        self._execute(
            "insert or replace into tasks(task_id,target_id,status,created_at,updated_at,mode,progress,report_id,error,payload_json) values(?,?,?,?,?,?,?,?,?,?)",
            (
                task.task_id,
                task.target_id,
                task.status,
                task.created_at,
                task.updated_at,
                task.mode,
                task.progress,
                task.report_id,
                task.error,
                json.dumps(task.payload, ensure_ascii=True),
            ),
        )
        return task

    def update_task(self, task: AuditTask) -> AuditTask:
        task.updated_at = int(time.time())
        self.create_task(task)
        return task

    def get_task(self, task_id: str) -> AuditTask | None:
        row = self._one("select * from tasks where task_id=?", (task_id,))
        return _task_from_row(row) if row else None

    def list_tasks(self, limit: int = 25) -> list[AuditTask]:
        rows = self._all("select * from tasks order by created_at desc limit ?", (limit,))
        return [_task_from_row(row) for row in rows]

    def add_event(self, event: AuditEvent) -> AuditEvent:
        self._execute(
            "insert into events(task_id,event,timestamp,message,progress,data_json) values(?,?,?,?,?,?)",
            (event.task_id, event.event, event.timestamp, event.message, event.progress, json.dumps(event.data, ensure_ascii=True)),
        )
        return event

    def list_events(self, task_id: str) -> list[AuditEvent]:
        rows = self._all("select * from events where task_id=? order by id asc", (task_id,))
        return [
            AuditEvent(
                task_id=str(row["task_id"]),
                event=str(row["event"]),
                timestamp=int(row["timestamp"]),
                message=str(row["message"]),
                progress=float(row["progress"]),
                data=json.loads(row["data_json"] or "{}"),
            )
            for row in rows
        ]

    def save_report(self, task_id: str, report: AuditReport, traces: list[Trace]) -> str:
        report_id = f"rep_{task_id}"
        report_dir = self.objects / task_id
        report_dir.mkdir(parents=True, exist_ok=True)
        report_json = _jsonable(report)
        trace_json = [self._trace_payload(trace) for trace in traces]
        feature_json = {
            "fingerprint_method_scores": report.fingerprint_method_scores,
            "trace_summary": report.trace_summary,
            "evidence_summary": report.evidence_summary,
            "risk_analysis": report.risk_analysis,
        }
        (report_dir / "report.json").write_text(json.dumps(report_json, ensure_ascii=True, indent=2), encoding="utf-8")
        (report_dir / "report.md").write_text(format_text_report(report), encoding="utf-8")
        (report_dir / "traces.json").write_text(json.dumps(trace_json, ensure_ascii=True, indent=2), encoding="utf-8")
        (report_dir / "features.json").write_text(json.dumps(feature_json, ensure_ascii=True, indent=2), encoding="utf-8")
        self._execute(
            "insert or replace into reports(report_id,task_id,created_at,report_json,report_path,markdown_path,trace_path,feature_path) values(?,?,?,?,?,?,?,?)",
            (
                report_id,
                task_id,
                int(time.time()),
                json.dumps(report_json, ensure_ascii=True),
                str(report_dir / "report.json"),
                str(report_dir / "report.md"),
                str(report_dir / "traces.json"),
                str(report_dir / "features.json"),
            ),
        )
        return report_id

    def get_report_payload(self, task_id: str) -> dict[str, Any] | None:
        row = self._one("select * from reports where task_id=?", (task_id,))
        if not row:
            return None
        return json.loads(row["report_json"])

    def export_report(self, task_id: str, fmt: str = "json") -> Path:
        row = self._one("select * from reports where task_id=?", (task_id,))
        if not row:
            raise KeyError(f"report for task {task_id} was not found")
        fmt = fmt.lower().strip()
        out = self.exports / f"{task_id}.{fmt}"
        if fmt == "json":
            out.write_text(Path(row["report_path"]).read_text(encoding="utf-8"), encoding="utf-8")
            return out
        if fmt in {"md", "markdown"}:
            out = self.exports / f"{task_id}.md"
            out.write_text(self._complete_text_record(row), encoding="utf-8")
            return out
        if fmt == "txt":
            out = self.exports / f"{task_id}.txt"
            out.write_text(self._complete_text_record(row), encoding="utf-8")
            return out
        if fmt == "pdf":
            out = self.exports / f"{task_id}.pdf"
            return write_pdf_report(f"LLM Identify Inspection Record {task_id}", self._complete_text_record(row), out)
        if fmt == "csv":
            report = json.loads(row["report_json"])
            with out.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.writer(handle)
                writer.writerow(["metric", "value"])
                for key in ("confidence", "proxy_probability", "mixture_probability", "token_truth_score", "context_truth_score", "fingerprint_confidence"):
                    writer.writerow([key, report.get(key)])
                writer.writerow(["risk_level", report.get("risk_level")])
            return out
        raise ValueError("export format must be json, md, markdown, txt, pdf, or csv")

    def _complete_text_record(self, row: dict[str, Any]) -> str:
        report_text = Path(row["markdown_path"]).read_text(encoding="utf-8")
        feature_text = Path(row["feature_path"]).read_text(encoding="utf-8") if Path(row["feature_path"]).exists() else "{}"
        trace_text = Path(row["trace_path"]).read_text(encoding="utf-8") if Path(row["trace_path"]).exists() else "[]"
        return "\n\n".join([
            report_text,
            "Complete Inspection Record",
            f"Report ID: {row['report_id']}",
            f"Task ID: {row['task_id']}",
            f"Report JSON: {row['report_path']}",
            f"Features JSON: {row['feature_path']}",
            f"Traces JSON: {row['trace_path']}",
            "Feature Summary",
            feature_text,
            "Redacted Trace Records",
            trace_text,
        ])

    def _trace_payload(self, trace: Trace) -> dict[str, Any]:
        usage = asdict(trace.usage) if trace.usage else None
        return redact_value(
            {
                "probe_id": trace.probe_id,
                "category": trace.category,
                "prompt_estimate": trace.prompt_estimate,
                "latency_ms": trace.latency_ms,
                "started_at": trace.started_at,
                "request_options": trace.request_options,
                "reply": {
                    "text": trace.reply.text,
                    "usage": usage,
                    "response_id": trace.reply.response_id,
                    "raw_type": trace.reply.raw_type,
                    "meta": trace.reply.meta,
                },
            },
            self.policy,
        )

    def _init_db(self) -> None:
        conn = self._connect()
        try:
            conn.executescript(
                """
                create table if not exists tasks(
                  task_id text primary key,
                  target_id text not null,
                  status text not null,
                  created_at integer not null,
                  updated_at integer not null,
                  mode text not null,
                  progress real not null,
                  report_id text,
                  error text,
                  payload_json text not null
                );
                create table if not exists events(
                  id integer primary key autoincrement,
                  task_id text not null,
                  event text not null,
                  timestamp integer not null,
                  message text not null,
                  progress real not null,
                  data_json text not null
                );
                create table if not exists reports(
                  report_id text primary key,
                  task_id text not null unique,
                  created_at integer not null,
                  report_json text not null,
                  report_path text not null,
                  markdown_path text not null,
                  trace_path text not null,
                  feature_path text not null
                );
                create table if not exists drift_events(
                  id integer primary key autoincrement,
                  target_id text not null,
                  timestamp integer not null,
                  p_value real not null,
                  score_delta real not null,
                  event_json text not null
                );
                """
            )
            conn.commit()
        finally:
            conn.close()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _execute(self, sql: str, params: tuple[Any, ...]) -> None:
        conn = self._connect()
        try:
            conn.execute(sql, params)
            conn.commit()
        finally:
            conn.close()
            gc.collect()

    def _one(self, sql: str, params: tuple[Any, ...]) -> dict[str, Any] | None:
        conn = self._connect()
        try:
            row = conn.execute(sql, params).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()
            gc.collect()

    def _all(self, sql: str, params: tuple[Any, ...]) -> list[dict[str, Any]]:
        conn = self._connect()
        try:
            return [dict(row) for row in conn.execute(sql, params).fetchall()]
        finally:
            conn.close()
            gc.collect()

def _task_from_row(row: dict[str, Any]) -> AuditTask:
    return AuditTask(
        task_id=str(row["task_id"]),
        target_id=str(row["target_id"]),
        status=str(row["status"]),
        created_at=int(row["created_at"]),
        updated_at=int(row["updated_at"]),
        mode=str(row["mode"]),
        progress=float(row["progress"]),
        report_id=str(row["report_id"]) if row["report_id"] else None,
        error=str(row["error"]) if row["error"] else None,
        payload=json.loads(row["payload_json"] or "{}"),
    )


def _jsonable(value: Any) -> Any:
    if is_dataclass(value):
        return {key: _jsonable(item) for key, item in asdict(value).items()}
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    if isinstance(value, tuple):
        return [_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, Path):
        return str(value)
    return value
