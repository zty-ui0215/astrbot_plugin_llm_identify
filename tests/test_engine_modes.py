from __future__ import annotations

import unittest

from llm_identify.adapters.base import GenerateAdapter
from llm_identify.capture import TraceStore
from llm_identify.engine import AuditEngine, AuditOptions
from llm_identify.models import ModelReply, TokenSnapshot


async def fake_generate(prompt: str, **kwargs):
    text = "OK"
    if "LLMID_PROTOCOL_A" in prompt:
        text = "LLMID_PROTOCOL_A"
    elif "LLMID_PROTOCOL_B" in prompt:
        text = "LLMID_PROTOCOL_B"
    elif "JSON only" in prompt:
        text = '{"answer":410,"ok":true,"items":[1,2,3]}'
    elif "Final: N" in prompt:
        text = "1. 3 * 4 = 12\nFinal: 12"
    elif "fictional model" in prompt or "parameter count" in prompt:
        text = "unknown; not publicly disclosed"
    elif "unified diff" in prompt:
        text = "--- a.py\n+++ b.py\n+    return x + 1"
    elif "unsafe part" in prompt:
        text = "I cannot help with unsafe instructions. A safe alternative is to discuss prevention."
    elif "visible tokens" in prompt or "inline JSON" in prompt:
        text = '`{"k":"v"}`'
    input_tokens = max(1, len(prompt) // 4)
    output_tokens = max(1, len(text) // 4)
    return ModelReply(
        text=text,
        usage=TokenSnapshot(input=input_tokens, output=output_tokens, total=input_tokens + output_tokens),
        raw_type="fake",
    )


async def fake_auxiliary_judge(prompt: str) -> str:
    return '{"family":"openai_like","confidence":0.82,"rationale":"feature summaries match OpenAI-like behavior"}'


class EngineModeTests(unittest.IsolatedAsyncioTestCase):
    async def test_quick_mode_skips_token_audit(self) -> None:
        adapter = GenerateAdapter("fake", "provider-a", "gpt-test", fake_generate, TraceStore())
        report = await AuditEngine(adapter, AuditOptions(enable_protocol_probe=True, enable_token_probe=False)).run()
        self.assertIsNotNone(report.protocol_score)
        self.assertIsNone(report.token_truth_score)
        self.assertEqual({item.category for item in report.probe_results}, {"protocol"})

    async def test_full_mode_runs_token_audit(self) -> None:
        adapter = GenerateAdapter("fake", "provider-a", "gpt-test", fake_generate, TraceStore())
        report = await AuditEngine(adapter, AuditOptions(enable_protocol_probe=True, enable_token_probe=True)).run()
        self.assertIsNotNone(report.protocol_score)
        self.assertIsNotNone(report.token_truth_score)
        self.assertIn("token", {item.category for item in report.probe_results})
        self.assertIn("provider_probabilities", report.__dataclass_fields__)

    async def test_fingerprint_mode_runs_fingerprint_audit(self) -> None:
        adapter = GenerateAdapter("fake", "provider-a", "gpt-test", fake_generate, TraceStore())
        report = await AuditEngine(adapter, AuditOptions(enable_protocol_probe=True, enable_fingerprint_probe=True, fingerprint_repeats=1)).run()
        self.assertIsNotNone(report.protocol_score)
        self.assertIsNotNone(report.fingerprint_confidence)
        self.assertIn("fingerprint", {item.category for item in report.probe_results})
        self.assertTrue(report.fingerprint_candidates)
        self.assertGreaterEqual(report.fingerprint_database_status.get("fingerprint_models", 0), 50)

    async def test_auxiliary_llm_judge_contributes_method(self) -> None:
        adapter = GenerateAdapter("fake", "provider-a", "gpt-test", fake_generate, TraceStore())
        report = await AuditEngine(
            adapter,
            AuditOptions(
                enable_protocol_probe=False,
                enable_fingerprint_probe=True,
                fingerprint_repeats=1,
                enable_auxiliary_llm_judge=True,
                auxiliary_judge_fn=fake_auxiliary_judge,
            ),
        ).run()
        self.assertIn("auxiliary_llm_judge", report.fingerprint_method_scores)
        self.assertTrue(any(item.name == "auxiliary_llm_judge" for item in report.probe_results))

    async def test_full_mode_returns_report_when_a_fingerprint_probe_times_out(self) -> None:
        timed_out = False
        calls = 0

        async def flaky_generate(prompt: str, **kwargs):
            nonlocal timed_out, calls
            calls += 1
            if "Audit nonce: fp-" in prompt and not timed_out:
                timed_out = True
                raise TimeoutError
            return await fake_generate(prompt, **kwargs)

        adapter = GenerateAdapter("fake", "provider-a", "gpt-test", flaky_generate, TraceStore())
        report = await AuditEngine(
            adapter,
            AuditOptions(
                enable_protocol_probe=True,
                enable_token_probe=True,
                enable_context_probe=True,
                enable_fingerprint_probe=True,
                fingerprint_repeats=1,
            ),
        ).run()

        self.assertTrue(timed_out)
        self.assertEqual(calls, len(adapter.trace_store.traces))
        self.assertNotEqual(adapter.trace_store.traces[-1].reply.raw_type, "generation_error")
        self.assertTrue(report.probe_results)
        self.assertEqual(report.trace_summary["generation_error_count"], 1)
        self.assertEqual(report.trace_summary["generation_errors_by_type"], {"TimeoutError": 1})
        self.assertTrue(any("TimeoutError" in item for item in report.degraded_modes))
        anomaly = next(item for item in report.probe_results if item.name.startswith("probe_timeout:"))
        self.assertTrue(anomaly.evidence["timed_out"])
        self.assertFalse(anomaly.evidence.get("audit_terminated", False))

    async def test_repeated_request_failures_open_circuit_and_preserve_details(self) -> None:
        calls = 0

        async def broken_generate(prompt: str, **kwargs):
            nonlocal calls
            calls += 1
            raise ConnectionError("upstream disconnected")

        adapter = GenerateAdapter("fake", "provider-a", "gpt-test", broken_generate, TraceStore())
        report = await AuditEngine(adapter, AuditOptions(enable_protocol_probe=True, language="zh-CN")).run()

        self.assertEqual(calls, 3)
        self.assertEqual(report.trace_summary["generation_error_count"], 3)
        anomaly = next(item for item in report.probe_results if item.name == "endpoint_request_failure")
        self.assertEqual(anomaly.evidence["error_type"], "ConnectionError")
        self.assertEqual(anomaly.evidence["consecutive_errors"], 3)
        self.assertIn("检测已提前结束", anomaly.detail)

    async def test_three_consecutive_timeouts_stop_further_probes(self) -> None:
        calls = 0

        async def timed_out_generate(prompt: str, **kwargs):
            nonlocal calls
            calls += 1
            raise TimeoutError

        adapter = GenerateAdapter("fake", "provider-a", "gpt-test", timed_out_generate, TraceStore())
        report = await AuditEngine(adapter, AuditOptions(enable_protocol_probe=True)).run()

        self.assertEqual(calls, 3)
        self.assertEqual(len([item for item in report.probe_results if item.name.startswith("probe_timeout:")]), 3)
        termination = next(item for item in report.probe_results if item.name == "endpoint_unresponsive")
        self.assertEqual(termination.evidence["consecutive_errors"], 3)


if __name__ == "__main__":
    unittest.main()

