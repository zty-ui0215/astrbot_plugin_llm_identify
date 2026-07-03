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


if __name__ == "__main__":
    unittest.main()

