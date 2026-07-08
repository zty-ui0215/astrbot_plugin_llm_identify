from __future__ import annotations

import unittest

from llm_identify.capture import Trace
from llm_identify.features.fingerprint import FingerprintFeatureBundle, MethodFingerprint
from llm_identify.mixture import detect_mixture_or_provider_switching
from llm_identify.models import ModelReply, ProbeResult, TokenSnapshot
from llm_identify.scoring.fingerprint import fuse_fingerprint_features
from llm_identify.scoring.report import build_report


def trace(probe_id: str, text: str, *, latency: int = 100, provider: str = "openai_like", model: str = "gpt-a", usage_shape: str = "openai_chat") -> Trace:
    return Trace(
        probe_id=probe_id,
        category="fingerprint",
        prompt_estimate=20,
        reply=ModelReply(
            text=text,
            usage=TokenSnapshot(input=10, output=3, total=13),
            raw_type="fake",
            meta={
                "provider_trace": {"provider_hint": provider, "model": model, "usage_shape": usage_shape},
                "normalized_usage": {"provider_shape": usage_shape},
                "normalized_headers": {"signals": {"provider_hint": provider, "request_id": f"{provider}-{model}-{latency}"}},
            },
        ),
        latency_ms=latency,
        started_at=1,
    )


def fp_result():
    bundle = FingerprintFeatureBundle(
        methods=[
            MethodFingerprint("api_sidechannel", {"openai_like": 0.72, "anthropic_like": 0.07, "google_like": 0.07, "open_source_or_relay": 0.07, "unknown": 0.07}, 0.8),
            MethodFingerprint("mixed_routing", {"openai_like": 0.08, "anthropic_like": 0.08, "google_like": 0.08, "open_source_or_relay": 0.68, "unknown": 0.08}, 0.8),
        ],
        probe_count=2,
    )
    return fuse_fingerprint_features(bundle)


class MixtureDetectionTests(unittest.TestCase):
    def test_stable_single_provider_repeated_traces_score_low(self) -> None:
        traces = [
            trace("mixed_routing_stability__r0", "same answer", latency=100),
            trace("mixed_routing_stability__r1", "same answer", latency=110),
            trace("mixed_routing_stability__r2", "same answer", latency=105),
            trace("mixed_routing_stability__r3", "same answer", latency=115),
        ]
        result = detect_mixture_or_provider_switching(probe_results=[], traces=traces)
        self.assertLess(result.probability, 0.25)
        self.assertEqual(result.signals["response_clusters"]["max_instability"], 0.25)

    def test_provider_switching_response_clusters_usage_and_latency_raise_probability(self) -> None:
        traces = [
            trace("mixed_routing_stability__r0", "OpenAI-shaped answer", latency=90, provider="openai_like", model="gpt-a", usage_shape="openai_chat"),
            trace("mixed_routing_stability__r1", "Claude-shaped answer", latency=620, provider="anthropic_like", model="claude-a", usage_shape="openai_responses_or_anthropic"),
            trace("mixed_routing_stability__r2", "Gemini-shaped answer", latency=760, provider="google_like", model="gemini-a", usage_shape="gemini"),
            trace("mixed_routing_stability__r3", "Relay answer", latency=95, provider="open_source_or_relay", model="llama-a", usage_shape="generic_camel"),
        ]
        result = detect_mixture_or_provider_switching(probe_results=[ProbeResult("fingerprint", "mixed", 0.4, "warning", "")], traces=traces, fingerprint_result=fp_result())
        self.assertGreaterEqual(result.probability, 0.55)
        self.assertGreaterEqual(result.signals["provider_switching"]["score"], 0.45)
        self.assertGreaterEqual(result.signals["usage_shape_switching"]["score"], 0.45)
        self.assertTrue(result.findings)

    def test_report_risk_analysis_contains_mixture_signals(self) -> None:
        traces = [
            trace("mixed_routing_stability__r0", "A", latency=80, provider="openai_like", model="gpt-a"),
            trace("mixed_routing_stability__r1", "B", latency=600, provider="anthropic_like", model="claude-a", usage_shape="openai_responses_or_anthropic"),
            trace("mixed_routing_stability__r2", "C", latency=650, provider="google_like", model="gemini-a", usage_shape="gemini"),
            trace("mixed_routing_stability__r3", "D", latency=85, provider="open_source_or_relay", model="llama-a", usage_shape="generic_camel"),
        ]
        report = build_report(
            provider_id="provider",
            claimed_model="model",
            adapter_type="fake",
            probe_results=[ProbeResult("fingerprint", "mixed", 0.4, "warning", "")],
            traces=traces,
            token_features=None,
            fingerprint_result=fp_result(),
        )
        self.assertGreaterEqual(report.mixture_probability, 0.5)
        self.assertIn("mixture_signals", report.risk_analysis)
        self.assertIn("provider_switching", report.risk_analysis["mixture_signals"])
        self.assertTrue(any("Repeated probes" in finding or "Provider trace" in finding for finding in report.findings))


if __name__ == "__main__":
    unittest.main()
