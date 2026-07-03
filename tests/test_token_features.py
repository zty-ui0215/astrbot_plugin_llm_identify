from __future__ import annotations

import unittest

from llm_identify.capture import Trace
from llm_identify.features import analyze_token_traces
from llm_identify.models import ModelReply, TokenSnapshot


def trace(probe_id: str, prompt_estimate: int, input_tokens: int | None, output_tokens: int | None = 1, text: str = "OK") -> Trace:
    usage = None if input_tokens is None else TokenSnapshot(input=input_tokens, output=output_tokens, total=input_tokens + (output_tokens or 0))
    return Trace(
        probe_id=probe_id,
        category="token",
        prompt_estimate=prompt_estimate,
        reply=ModelReply(text=text, usage=usage, raw_type="fake"),
        latency_ms=20,
        started_at=1,
    )


def valid_traces() -> list[Trace]:
    return [
        trace("usage_ascii_short", 16, 20),
        trace("usage_cjk_mixed", 28, 38),
        trace("usage_unicode_edge", 36, 52),
        trace("usage_long_1", 280, 330),
        trace("usage_long_2", 540, 650),
        trace("cache_prefix_plain", 260, 310),
        trace("cache_prefix_nonce", 262, 312),
        trace("output_short", 10, 18, output_tokens=1, text="short"),
        trace("output_long", 18, 28, output_tokens=35, text="one two three four " * 8),
    ]


class TokenFeatureTests(unittest.TestCase):
    def test_valid_usage_scores_high(self) -> None:
        features, results = analyze_token_traces(valid_traces())
        self.assertGreaterEqual(features.token_truth_score, 0.8)
        self.assertTrue(features.usage_available)
        self.assertTrue(features.input_token_monotonic)
        self.assertFalse(features.constant_count_detected)
        self.assertEqual(features.anomaly_flags, [])
        self.assertTrue(any(item.name == "token_truth_score" for item in results))

    def test_missing_usage_scores_low(self) -> None:
        traces = [trace(probe_id, 20, None) for probe_id in ["usage_ascii_short", "usage_cjk_mixed", "usage_unicode_edge", "usage_long_1", "usage_long_2"]]
        features, _ = analyze_token_traces(traces)
        self.assertFalse(features.usage_available)
        self.assertIn("usage_missing", features.anomaly_flags)
        self.assertLess(features.token_truth_score, 0.7)

    def test_constant_counts_are_flagged(self) -> None:
        traces = valid_traces()
        for item in traces:
            if item.usage:
                item.usage.input = 42
                item.usage.total = 43
        features, _ = analyze_token_traces(traces)
        self.assertTrue(features.constant_count_detected)
        self.assertIn("constant_or_nearly_constant_input_counts", features.anomaly_flags)
        self.assertLess(features.token_truth_score, 0.75)

    def test_decreasing_counts_fail_monotonicity(self) -> None:
        traces = valid_traces()
        values = {
            "usage_ascii_short": 100,
            "usage_cjk_mixed": 90,
            "usage_unicode_edge": 80,
            "usage_long_1": 70,
            "usage_long_2": 60,
        }
        for item in traces:
            if item.probe_id in values and item.usage:
                item.usage.input = values[item.probe_id]
        features, _ = analyze_token_traces(traces)
        self.assertFalse(features.input_token_monotonic)
        self.assertIn("input_tokens_not_monotonic", features.anomaly_flags)

    def test_implausible_slope_is_flagged(self) -> None:
        traces = valid_traces()
        for item in traces:
            if item.probe_id == "usage_long_2" and item.usage:
                item.usage.input = 9000
        features, _ = analyze_token_traces(traces)
        self.assertFalse(features.slope_consistency)
        self.assertIn("implausible_input_token_slope", features.anomaly_flags)

    def test_unicode_instability_is_flagged(self) -> None:
        traces = valid_traces()
        for item in traces:
            if item.probe_id == "usage_unicode_edge" and item.usage:
                item.usage.input = 3
        features, _ = analyze_token_traces(traces)
        self.assertFalse(features.unicode_count_stability)
        self.assertIn("unicode_count_unstable_or_implausible", features.anomaly_flags)


if __name__ == "__main__":
    unittest.main()
