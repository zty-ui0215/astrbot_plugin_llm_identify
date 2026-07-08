from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
from typing import Any

from .adapters.base import GenerateAdapter
from .adapters.direct_openai import DirectOpenAICompatibleAdapter
from .capture import TraceStore
from .drift import baseline_refresh_plan
from .engine import AuditEngine, AuditOptions
from .exporting import write_curve_placeholders
from .storage import AuditStorage
from .tasks import AuditTask


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="llm-audit")
    sub = parser.add_subparsers(dest="command", required=True)
    scan = sub.add_parser("scan")
    scan.add_argument("--target-id", default="direct")
    scan.add_argument("--base-url", required=True)
    scan.add_argument("--api-key", required=True)
    scan.add_argument("--model", required=True)
    scan.add_argument("--output", default="reports/run")
    scan.add_argument("--full", action="store_true", default=True)
    baselines = sub.add_parser("baselines")
    baselines_sub = baselines.add_subparsers(dest="baselines_command", required=True)
    refresh = baselines_sub.add_parser("refresh")
    refresh.add_argument("--providers", nargs="+", default=["openai", "anthropic", "gemini"])
    report = sub.add_parser("report")
    report_sub = report.add_subparsers(dest="report_command", required=True)
    export = report_sub.add_parser("export")
    export.add_argument("--task-id", required=True)
    export.add_argument("--format", default="json", choices=["json", "csv", "md", "markdown", "txt", "pdf"])
    export.add_argument("--data-dir", default=None)
    plot = report_sub.add_parser("plot")
    plot.add_argument("--out", required=True)
    return parser


async def run_scan(args: argparse.Namespace) -> dict[str, Any]:
    storage = AuditStorage(args.output)
    task = AuditTask.create(target_id=args.target_id, mode="cli_scan", payload=vars(args))
    storage.create_task(task)
    client = DirectOpenAICompatibleAdapter(base_url=args.base_url, api_key=args.api_key, model=args.model)

    async def generate(prompt: str, **kwargs: Any):
        return await client.generate(prompt, **kwargs)

    trace_store = TraceStore()
    adapter = GenerateAdapter("direct_openai_compatible", args.target_id, args.model, generate, trace_store, count_tokens_fn=client.count_tokens)
    report = await AuditEngine(adapter, AuditOptions(enable_protocol_probe=True, enable_token_probe=True, enable_fingerprint_probe=True)).run()
    task.status = "completed"
    task.progress = 1.0
    task.report_id = storage.save_report(task.task_id, report, trace_store.traces)
    storage.update_task(task)
    return {"task": task.task_id, "report_id": task.report_id, "report": storage.get_report_payload(task.task_id)}


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "scan":
        print(json.dumps(asyncio.run(run_scan(args)), ensure_ascii=True, indent=2))
        return 0
    if args.command == "baselines" and args.baselines_command == "refresh":
        print(json.dumps(baseline_refresh_plan(args.providers), ensure_ascii=True, indent=2))
        return 0
    if args.command == "report" and args.report_command == "export":
        path = AuditStorage(args.data_dir).export_report(args.task_id, args.format)
        print(str(path))
        return 0
    if args.command == "report" and args.report_command == "plot":
        paths = write_curve_placeholders(Path(args.out))
        print(json.dumps([str(path) for path in paths], ensure_ascii=True))
        return 0
    parser.error("unknown command")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
