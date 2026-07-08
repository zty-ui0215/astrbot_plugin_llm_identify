from __future__ import annotations

import json
import unittest
from pathlib import Path

from llm_identify.contribution.evidence_schema import build_evidence_package
from llm_identify.contribution.official_endpoint_detector import detect_official_endpoint
from tests.test_task_storage_privacy_cli import minimal_report


ROOT = Path(__file__).resolve().parents[1]


class SchemaArtifactTests(unittest.TestCase):
    def test_schema_and_governance_artifacts_exist(self) -> None:
        for path in [
            "schemas/evidence-package.schema.json",
            "schemas/corpus-row.schema.json",
            "schemas/sanitizer-report.schema.json",
            "docs/trusted_corpus_governance.md",
            "CODEOWNERS",
            ".github/ISSUE_TEMPLATE/trusted-reference-candidate.yml",
            ".github/workflows/validate-trusted-corpus.yml",
        ]:
            self.assertTrue((ROOT / path).exists(), path)

    def test_generated_evidence_package_satisfies_committed_schema_required_fields(self) -> None:
        schema = _schema("evidence-package.schema.json")
        endpoint = detect_official_endpoint("https://api.openai.com/v1")
        self.assertIsNotNone(endpoint)
        report = minimal_report().__dict__.copy()
        package = build_evidence_package(task_id="task-schema", report=report, feature_vector={"x": 0.4}, official_endpoint=endpoint, plugin_version="test")
        _assert_required(self, schema, package)
        self.assertEqual(package["schema_version"], schema["properties"]["schema_version"]["const"])
        self.assertEqual(package["sample_type"], "trusted_reference_candidate")
        self.assertIn(package["verification_status"], schema["properties"]["verification_status"]["enum"])
        self.assertIn(package["endpoint"]["provider"], schema["properties"]["endpoint"]["properties"]["provider"]["enum"])

    def test_embedded_accepted_references_satisfy_corpus_row_schema_required_fields(self) -> None:
        schema = _schema("corpus-row.schema.json")
        corpus = json.loads((ROOT / "llm_identify/data/trusted_reference_corpus.json").read_text(encoding="utf-8"))
        rows = corpus.get("accepted_references") or []
        self.assertTrue(rows)
        for row in rows:
            _assert_required(self, schema, row)
            _assert_required(self, schema["properties"]["endpoint_class"], row["endpoint_class"])
            self.assertIn(row["provider"], schema["properties"]["provider"]["enum"])
            self.assertIn(row["trust_tier"], schema["properties"]["trust_tier"]["enum"])
            self.assertTrue(row["endpoint_class"]["official_match"])

    def test_sanitizer_report_schema_requires_forbidden_field_scan(self) -> None:
        schema = _schema("sanitizer-report.schema.json")
        report = {
            "schema_version": "1.0.0",
            "sanitizer_version": "1.0.0",
            "raw_text_uploaded": False,
            "forbidden_fields_found": [],
            "rules_applied": ["drop_sensitive_keys", "bucket_timestamps"],
        }
        _assert_required(self, schema, report)
        self.assertFalse(report["raw_text_uploaded"])

    def test_governance_doc_names_review_states_and_trust_tiers(self) -> None:
        text = (ROOT / "docs/trusted_corpus_governance.md").read_text(encoding="utf-8")
        for token in ["intake", "needs-sanitization-proof", "schema-failed", "quarantine", "accepted", "T0", "T1", "T2", "T3"]:
            self.assertIn(token, text)


def _schema(name: str) -> dict:
    return json.loads((ROOT / "schemas" / name).read_text(encoding="utf-8"))


def _assert_required(testcase: unittest.TestCase, schema: dict, payload: dict) -> None:
    for key in schema.get("required", []):
        testcase.assertIn(key, payload)


if __name__ == "__main__":
    unittest.main()
