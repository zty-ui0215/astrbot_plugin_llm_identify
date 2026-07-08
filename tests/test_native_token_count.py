from __future__ import annotations

import unittest

from llm_identify.adapters.base import GenerateAdapter
from llm_identify.capture import Trace, TraceStore
from llm_identify.features.token import analyze_token_traces
from llm_identify.models import ModelReply, TokenSnapshot


def token_trace(probe_id: str, reported: int, native: int | None = None, status: str = "ok") -> Trace:
    meta = {}
    if native is not None or status != "ok":
        meta["native_token_count"] = {"status": status, "input_tokens": native, "total_tokens": native, "endpoint": "/responses/input_tokens"}
    return Trace(
        probe_id=probe_id,
        category="token",
        prompt_estimate=max(1, reported - 2),
        reply=ModelReply(text="OK", usage=TokenSnapshot(input=reported, output=1, total=reported + 1), raw_type="fake", meta=meta),
        latency_ms=10,
        started_at=1,
    )


def monotonic_traces(native_delta: int = 0) -> list[Trace]:
    values = {
        "usage_ascii_short": 20,
        "usage_cjk_mixed": 32,
        "usage_unicode_edge": 42,
        "usage_long_1": 220,
        "usage_long_2": 420,
        "output_short": 18,
        "output_long": 60,
        "cache_prefix_plain": 260,
        "cache_prefix_nonce": 262,
    }
    return [token_trace(probe_id, reported, reported + native_delta) for probe_id, reported in values.items()]


class NativeTokenCountTests(unittest.IsolatedAsyncioTestCase):
    async def test_generate_adapter_records_native_count_success(self) -> None:
        async def generate(prompt: str, **kwargs):
            return ModelReply(text="OK", usage=TokenSnapshot(input=12, output=1, total=13), raw_type="fake")

        async def count(prompt: str):
            return {"provider": "openai_compatible", "endpoint": "/responses/input_tokens", "input_tokens": 12, "total_tokens": 12}

        store = TraceStore()
        adapter = GenerateAdapter("fake", "provider", "model", generate, store, count_tokens_fn=count)
        reply = await adapter.generate("hello world", probe_id="usage_ascii_short", category="token")
        self.assertEqual(reply.meta["native_token_count"]["status"], "ok")
        self.assertEqual(store.traces[0].reply.meta["native_token_count"]["input_tokens"], 12)

    async def test_generate_adapter_records_native_count_degraded_without_failing(self) -> None:
        async def generate(prompt: str, **kwargs):
            return ModelReply(text="OK", usage=TokenSnapshot(input=12, output=1, total=13), raw_type="fake")

        async def count(prompt: str):
            raise RuntimeError("count endpoint unavailable")

        store = TraceStore()
        adapter = GenerateAdapter("fake", "provider", "model", generate, store, count_tokens_fn=count)
        reply = await adapter.generate("hello world", probe_id="usage_ascii_short", category="token")
        self.assertEqual(reply.text, "OK")
        self.assertEqual(reply.meta["native_token_count"]["status"], "error")
        self.assertIn("unavailable", reply.meta["native_token_count"]["error"])

    def test_native_count_consistency_adds_positive_probe_result(self) -> None:
        features, results = analyze_token_traces(monotonic_traces(native_delta=1))
        self.assertTrue(features.native_count_consistency)
        self.assertNotIn("native_count_disagrees_with_usage", features.anomaly_flags)
        self.assertTrue(any(item.name == "native_count_consistency" and item.status == "pass" for item in results))

    def test_native_count_disagreement_penalizes_token_truth(self) -> None:
        features, results = analyze_token_traces(monotonic_traces(native_delta=100))
        self.assertFalse(features.native_count_consistency)
        self.assertIn("native_count_disagrees_with_usage", features.anomaly_flags)
        self.assertLess(features.token_truth_score, 0.9)
        self.assertTrue(any(item.name == "native_count_consistency" and item.status == "fail" for item in results))


if __name__ == "__main__":
    unittest.main()
