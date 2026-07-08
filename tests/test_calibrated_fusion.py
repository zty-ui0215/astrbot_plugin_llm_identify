from __future__ import annotations

import unittest

from llm_identify.features.fingerprint import FingerprintFeatureBundle, MethodFingerprint
from llm_identify.scoring.fingerprint import fuse_fingerprint_features


def method(name: str, winner: str, confidence: float, quality: float = 0.8, **evidence):
    other = (1.0 - confidence) / 4.0
    scores = {family: other for family in ("openai_like", "anthropic_like", "google_like", "open_source_or_relay", "unknown")}
    scores[winner] = confidence
    return MethodFingerprint(method=name, family_scores=scores, quality=quality, evidence=evidence)


class CalibratedFusionTests(unittest.TestCase):
    def test_cross_validated_reliable_methods_keep_high_confidence_with_diagnostics(self) -> None:
        bundle = FingerprintFeatureBundle(
            methods=[
                method("api_sidechannel", "openai_like", 0.86, 0.9),
                method("tokenizer_unicode", "openai_like", 0.78, 0.85),
                method("trusted_corpus:local", "openai_like", 0.82, 0.8),
            ],
            probe_count=3,
        )
        fused = fuse_fingerprint_features(bundle)
        self.assertEqual(fused.fingerprint_candidates[0].family, "openai_like")
        self.assertGreater(fused.fingerprint_confidence or 0.0, 0.6)
        self.assertLess(fused.spoofing_risk or 1.0, 0.45)
        calibration = fused.database_status["fusion_calibration"]
        self.assertEqual(calibration["mode"], "tempered_log_opinion_pool/v1")
        self.assertEqual(len(calibration["method_diagnostics"]), 3)
        self.assertIn("calibration", fused.fingerprint_candidates[0].evidence)

    def test_single_method_is_tempered_and_mixed_with_unknown(self) -> None:
        bundle = FingerprintFeatureBundle(methods=[method("trusted_corpus:local", "google_like", 0.96, 0.9)], probe_count=1)
        fused = fuse_fingerprint_features(bundle)
        self.assertEqual(fused.fingerprint_candidates[0].family, "google_like")
        self.assertLess(fused.fingerprint_score or 1.0, 0.96)
        self.assertLess(fused.fingerprint_confidence or 1.0, 0.6)
        self.assertGreaterEqual(fused.spoofing_risk or 0.0, 0.35)

    def test_low_reliability_judge_is_tempered_by_physical_evidence(self) -> None:
        bundle = FingerprintFeatureBundle(
            methods=[
                method("external_llm_judge:cheap", "anthropic_like", 0.94, 0.9),
                method("api_sidechannel", "openai_like", 0.72, 0.85),
                method("trusted_corpus:embedded", "openai_like", 0.74, 0.7, source="embedded_trusted_reference"),
            ],
            probe_count=3,
        )
        fused = fuse_fingerprint_features(bundle)
        self.assertEqual(fused.fingerprint_candidates[0].family, "openai_like")
        diag = fused.database_status["fusion_calibration"]["method_diagnostics"]
        judge_diag = next(item for item in diag if item["method"].startswith("external_llm_judge"))
        sidechannel_diag = next(item for item in diag if item["method"] == "api_sidechannel")
        self.assertLess(judge_diag["reliability"], sidechannel_diag["reliability"])

    def test_conflicting_methods_raise_entropy_disagreement_and_spoofing_risk(self) -> None:
        bundle = FingerprintFeatureBundle(
            methods=[
                method("api_sidechannel", "openai_like", 0.72, 0.8),
                method("mixed_routing", "open_source_or_relay", 0.70, 0.8),
                method("knowledge_boundary", "anthropic_like", 0.68, 0.75),
            ],
            probe_count=3,
        )
        fused = fuse_fingerprint_features(bundle)
        calibration = fused.database_status["fusion_calibration"]
        self.assertGreater(calibration["entropy"], 0.65)
        self.assertGreaterEqual(fused.fingerprint_disagreement or 0.0, 0.55)
        self.assertGreaterEqual(fused.spoofing_risk or 0.0, 0.55)


if __name__ == "__main__":
    unittest.main()
