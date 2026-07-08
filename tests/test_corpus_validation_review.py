from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from llm_identify.contribution.evidence_schema import build_evidence_package
from llm_identify.contribution.official_endpoint_detector import detect_official_endpoint
from llm_identify.contribution.review import MAINTAINER_REVIEW, PROMOTE, QUARANTINE, REJECT, review_contribution_candidate
from llm_identify.corpus import TrustedCorpusLoader, TrustedCorpusSource, default_trusted_corpus_sources
from llm_identify.corpus_validation import validate_trusted_corpus


class CorpusValidationAndReviewTests(unittest.TestCase):
    def test_embedded_corpus_exposes_validation_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = TrustedCorpusLoader(default_trusted_corpus_sources()[0], tmp).load(provider_id="openai", claimed_model="gpt-4o")
        self.assertEqual(result.status, "ok")
        self.assertTrue(result.metadata["validation"]["ok"])
        self.assertEqual(result.metadata["validation"]["schema_version"], "1.0.0")

    def test_validator_rejects_alias_family_conflicts_unofficial_high_trust_and_secrets(self) -> None:
        report = validate_trusted_corpus(
            {
                "schema_version": "1.0.0",
                "corpus_version": "bad-v1",
                "source_attribution": [{"id": "seed", "kind": "test"}],
                "model_profiles": [
                    {"id": "a", "provider_family_id": "openai_like", "aliases": ["same"], "trust_tier": "T2"},
                    {"id": "b", "provider_family_id": "anthropic_like", "aliases": ["same"], "trust_tier": "T2"},
                ],
                "accepted_references": [
                    {
                        "record_id": "x",
                        "provider": "openai",
                        "trust_tier": "T1",
                        "endpoint_class": {"host": "proxy.example", "official_match": False},
                        "model_claim": "gpt",
                        "probe_pack_version": "pack",
                        "sanitizer_version": "1",
                        "authorization": "Bearer secret-token-value",
                    }
                ],
            }
        )
        codes = {issue.code for issue in report.errors}
        self.assertIn("alias_family_conflict", codes)
        self.assertIn("reference_tier_official", codes)
        self.assertIn("sensitive_key", codes)
        self.assertIn("sensitive_value", codes)

    def test_loader_degrades_invalid_optional_corpus_without_scoring_it(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "invalid.json"
            path.write_text(
                json.dumps({"schema_version": "1.0.0", "corpus_version": "bad", "model_profiles": "not-a-list"}),
                encoding="utf-8",
            )
            result = TrustedCorpusLoader(TrustedCorpusSource(source_id="invalid", path=str(path)), tmp).load(provider_id="openai", claimed_model="gpt")
        self.assertEqual(result.status, "unavailable")
        self.assertEqual(result.models, [])
        self.assertIsNone(result.method)
        self.assertIn("validation failed", result.degraded_reason or "")

    def test_contribution_review_rejects_sensitive_candidate(self) -> None:
        package = _candidate_package()
        package["headers"] = {"authorization": "Bearer leaked-secret-value"}
        decision = review_contribution_candidate(package, official_endpoint=detect_official_endpoint("https://api.openai.com/v1"))
        self.assertEqual(decision.status, REJECT)
        self.assertIn("sensitive_content_detected", decision.reasons)

    def test_contribution_review_quarantines_corpus_contradictions(self) -> None:
        package = _candidate_package(model="claude-family")
        decision = review_contribution_candidate(
            package,
            official_endpoint=detect_official_endpoint("https://api.openai.com/v1"),
            existing_corpus_models=[{"id": "claude-family", "provider_cluster": "anthropic", "family": "anthropic_like"}],
        )
        self.assertEqual(decision.status, QUARANTINE)
        self.assertIn("corpus_contradiction", decision.reasons)

    def test_contribution_review_keeps_duplicates_for_manual_review(self) -> None:
        package = _candidate_package(model="gpt-family")
        decision = review_contribution_candidate(
            package,
            official_endpoint=detect_official_endpoint("https://api.openai.com/v1"),
            existing_corpus_models=[{"id": "gpt-family", "provider_cluster": "openai", "family": "openai_like"}],
        )
        self.assertEqual(decision.status, MAINTAINER_REVIEW)
        self.assertIn("duplicate_reference", decision.reasons)

    def test_contribution_review_promotes_clean_high_evidence_candidate(self) -> None:
        decision = review_contribution_candidate(_candidate_package(), official_endpoint=detect_official_endpoint("https://api.openai.com/v1"))
        self.assertEqual(decision.status, PROMOTE)
        self.assertTrue(decision.promotable)


def _candidate_package(model: str = "gpt-4o") -> dict:
    endpoint = detect_official_endpoint("https://api.openai.com/v1")
    assert endpoint is not None
    report = {
        "claimed_model": model,
        "created_at": 1783512000,
        "protocol_score": 0.91,
        "token_truth_score": 0.88,
        "context_truth_score": 0.83,
        "fingerprint_confidence": 0.86,
        "trace_summary": {"usage_trace_count": 8},
        "probe_results": [{"name": "usage_availability", "score": 1.0}],
    }
    return build_evidence_package(task_id="task-a", report=report, feature_vector={"token_truth_score": 0.88}, official_endpoint=endpoint, plugin_version="test")


if __name__ == "__main__":
    unittest.main()
