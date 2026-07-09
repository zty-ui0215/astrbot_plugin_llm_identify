from __future__ import annotations

import tempfile
import unittest

from llm_identify.contribution.evidence_schema import build_evidence_package
from llm_identify.contribution.github_issue_submitter import build_github_issue_url
from llm_identify.contribution.official_endpoint_detector import detect_official_endpoint
from llm_identify.contribution.sanitizer import sanitize_value
from llm_identify.dynamic_fingerprint import DynamicFingerprintStore, build_feature_vector, cosine_similarity
from tests.test_task_storage_privacy_cli import minimal_report


class ContributionAndDynamicFingerprintTests(unittest.TestCase):
    def test_official_endpoint_detector_rejects_proxy_domains(self) -> None:
        self.assertIsNotNone(detect_official_endpoint("https://api.openai.com/v1"))
        self.assertIsNotNone(detect_official_endpoint("https://api.anthropic.com"))
        self.assertIsNotNone(detect_official_endpoint("https://generativelanguage.googleapis.com/v1beta"))
        bailian = detect_official_endpoint("https://dashscope.aliyuncs.com/compatible-mode/v1")
        self.assertIsNotNone(bailian)
        self.assertEqual(bailian.provider, "alibaba_bailian")
        self.assertIsNone(detect_official_endpoint("https://api.openai.com.proxy.example/v1"))
        self.assertIsNone(detect_official_endpoint("http://api.openai.com/v1"))
        self.assertIsNone(detect_official_endpoint("https://mirror.example.com/v1"))

    def test_sanitized_evidence_package_excludes_sensitive_fields(self) -> None:
        report = minimal_report()
        payload = report.__dict__.copy()
        payload["created_at"] = report.created_at
        payload["probe_results"] = [{"name": "probe_a", "score": 0.8, "sample": "raw completion with sk-secret1234567890"}]
        endpoint = detect_official_endpoint("https://api.openai.com/v1")
        package = build_evidence_package(task_id="task-secret", report=payload, feature_vector={"x": 0.5}, official_endpoint=endpoint, plugin_version="test")
        text = str(package).lower()
        self.assertEqual(package["sample_type"], "trusted_reference_candidate")
        self.assertIn("maintainer_review_required", package["verification_status"])
        self.assertNotIn("sk-secret", text)
        self.assertNotIn("raw completion", text)
        self.assertNotIn("base_url", text)
        self.assertIn("probe_a", package["probe_ids"])
        issue_url = build_github_issue_url(package)
        self.assertIn("github.com/zty-ui0215/llm-identify-trusted-references", issue_url)

    def test_sanitizer_removes_private_fields(self) -> None:
        clean = sanitize_value({"api_key": "sk-secret", "headers": {"authorization": "Bearer x"}, "metric": 0.4, "email": "a@example.com"})
        self.assertEqual(clean, {"metric": 0.4})

    def test_dynamic_fingerprint_vectors_are_comparable(self) -> None:
        report = minimal_report()
        vector = build_feature_vector(report, [])
        self.assertGreater(len(vector), 5)
        self.assertAlmostEqual(cosine_similarity(vector, dict(vector)), 1.0)
        with tempfile.TemporaryDirectory() as tmp:
            store = DynamicFingerprintStore(tmp)
            first = store.add_report("task1", "target-a", report, [])
            second = store.add_report("task2", "target-b", report, [])
            self.assertEqual(first["schema_version"], "dynamic-fingerprint-vector/v1")
            self.assertTrue(second["nearest_neighbors"])
            self.assertGreaterEqual(second["nearest_neighbors"][0]["similarity"], 0.99)


if __name__ == "__main__":
    unittest.main()
