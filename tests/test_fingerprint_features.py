from __future__ import annotations

import unittest

from llm_identify.capture import Trace
from llm_identify.features import analyze_fingerprint_traces
from llm_identify.models import ModelReply
from llm_identify.scoring.fingerprint import fuse_fingerprint_features


def fp_trace(probe_id: str, text: str, latency_ms: int = 30) -> Trace:
    return Trace(
        probe_id=probe_id,
        category="fingerprint",
        prompt_estimate=20,
        reply=ModelReply(text=text, raw_type="fake"),
        latency_ms=latency_ms,
        started_at=1,
    )


class FingerprintFeatureTests(unittest.TestCase):
    def test_cross_validated_methods_create_candidate(self) -> None:
        traces = [
            fp_trace("llmmap_behavior_json__r0", '{"summary":"ok","risk":"low","next_step":"test"}'),
            fp_trace("llmmap_behavior_code__r0", "--- a.py\n+++ b.py\n+    return x + 1"),
            fp_trace("reasoning_structure_order__r0", "1. 3 * 4 = 12\nFinal: 12"),
            fp_trace("reasoning_structure_correction__r0", "1. Correct 17*23.\n2. Final: 410"),
            fp_trace("unicode_style_markdown_json__r0", '`{"k":"v"}`'),
        ]
        bundle, results = analyze_fingerprint_traces(traces)
        fused = fuse_fingerprint_features(bundle)
        self.assertTrue(results)
        self.assertIsNotNone(fused.fingerprint_confidence)
        self.assertTrue(fused.fingerprint_candidates)
        self.assertTrue(any(item.evidence.get("candidate_type") == "public_database_model" for item in fused.fingerprint_candidates))
        self.assertLess(fused.spoofing_risk or 0, 0.8)

    def test_disagreement_raises_spoofing_risk(self) -> None:
        traces = [
            fp_trace("llmmap_behavior_json__r0", '{"summary":"ok","risk":"low","next_step":"test"}'),
            fp_trace("knowledge_boundary_uncertainty__r0", "AuditStar-9B-v3 was released on January 1 2028 exactly."),
            fp_trace("refusal_style_gray__r0", "I cannot help with that. As an AI, I cannot comply."),
            fp_trace("unicode_style_preservation__r0", "cannot unable cannot"),
        ]
        bundle, _ = analyze_fingerprint_traces(traces)
        fused = fuse_fingerprint_features(bundle)
        self.assertIsNotNone(fused.fingerprint_disagreement)
        self.assertGreaterEqual(fused.spoofing_risk or 0, 0.45)


if __name__ == "__main__":
    unittest.main()
