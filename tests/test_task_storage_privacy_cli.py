from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from llm_identify.cli import build_parser
from llm_identify.drift import detect_drift
from llm_identify.exporting import write_curve_placeholders
from llm_identify.models import AuditReport
from llm_identify.privacy import RedactionPolicy, redact_value
from llm_identify.storage import AuditStorage
from llm_identify.tasks import AuditEvent, AuditTask, sse_payload


def minimal_report() -> AuditReport:
    return AuditReport(
        provider_id="provider",
        claimed_model="model",
        adapter_type="fake",
        model_family_guess="openai",
        provider_probabilities={"openai_like": 0.7, "unknown": 0.3},
        protocol_score=0.8,
        token_truth_score=0.7,
        context_truth_score=0.65,
        fingerprint_score=None,
        fingerprint_confidence=None,
        prompt_injection_risk=0.1,
        drift_risk=0.05,
        identity_posterior={"openai_like": 0.7, "unknown": 0.3},
        authenticity_posterior={"authentic": 0.8, "degraded_or_wrapped": 0.2},
        security_posterior={"low": 0.8, "medium": 0.15, "high": 0.05},
        branch_evidence=[],
        thresholds={"family_confidence": 0.65},
        fingerprint_candidates=[],
        fingerprint_method_scores={},
        fingerprint_database_status={},
        fingerprint_disagreement=None,
        spoofing_risk=None,
        proxy_probability=0.2,
        mixture_probability=0.1,
        confidence=0.75,
        risk_level="medium",
        risk_analysis={},
        evidence_summary={},
        findings=[],
        probe_results=[],
        evidence_sources=[],
        judge_invocations=[],
        degraded_modes=[],
        execution_trace={},
        trace_summary={},
        created_at=1,
    )


class TaskStoragePrivacyCliTests(unittest.TestCase):
    def test_redaction_masks_common_sensitive_values(self) -> None:
        redacted = redact_value({"email": "a@example.com", "api_key": "sk_test_abcdefghijklmnopqrstuvwxyz"}, RedactionPolicy())
        self.assertIn("[REDACTED:email:", redacted["email"])
        self.assertIn("[REDACTED:field:", redacted["api_key"])

    def test_storage_persists_task_events_report_and_exports(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            storage = AuditStorage(tmp)
            task = AuditTask.create(target_id="target", mode="test")
            storage.create_task(task)
            storage.add_event(AuditEvent.create(task.task_id, "queued", "queued", 0.1))
            report_id = storage.save_report(task.task_id, minimal_report(), [])
            task.report_id = report_id
            task.status = "completed"
            storage.update_task(task)
            self.assertEqual(storage.get_task(task.task_id).status, "completed")
            self.assertEqual(storage.get_report_payload(task.task_id)["confidence"], 0.75)
            self.assertTrue(storage.export_report(task.task_id, "json").exists())
            self.assertTrue(storage.export_report(task.task_id, "csv").exists())

    def test_sse_payload_contains_event_name(self) -> None:
        event = AuditEvent.create("task", "report_ready", "done", 1.0)
        self.assertIn("event: report_ready", sse_payload([event]))

    def test_cli_parser_accepts_required_commands(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["report", "plot", "--out", "tmp/figures"])
        self.assertEqual(args.command, "report")
        self.assertEqual(args.report_command, "plot")

    def test_curve_and_drift_helpers_are_executable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            paths = write_curve_placeholders(Path(tmp))
            self.assertTrue(paths[0].exists())
        event = detect_drift("target", [0.8, 0.82, 0.81], [0.4, 0.42, 0.41])
        self.assertGreater(event.score_delta, 0.2)


if __name__ == "__main__":
    unittest.main()
