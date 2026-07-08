from __future__ import annotations

import json
import unittest

from llm_identify.adapters.base import GenerateAdapter
from llm_identify.capture import TraceStore
from llm_identify.engine import AuditEngine, AuditOptions
from llm_identify.models import ModelReply, TokenSnapshot
from llm_identify.probes.context import ContextWindowProbePack


async def faithful_context_generate(prompt: str, **kwargs):
    sentinels = [value for value in ("CTX-SENTINEL-SHORT", "CTX-SENTINEL-EARLY", "CTX-SENTINEL-MIDDLE", "CTX-SENTINEL-LATE") if value in prompt]
    text = json.dumps({"sentinels": sentinels, "missing": []})
    return ModelReply(text=text, usage=TokenSnapshot(input=max(1, len(prompt) // 4), output=max(1, len(text) // 4), total=max(1, len(prompt) // 4) + max(1, len(text) // 4)), raw_type="fake")


async def degraded_context_generate(prompt: str, **kwargs):
    if "CTX-SENTINEL-SHORT" in prompt:
        text = '{"sentinels":["CTX-SENTINEL-SHORT"],"missing":[]}'
    else:
        text = "I cannot reliably inspect the full context; it may be too long or truncated."
    return ModelReply(
        text=text,
        usage=TokenSnapshot(input=42, output=max(1, len(text) // 4), total=42 + max(1, len(text) // 4)),
        raw_type="fake",
        meta={"finish_reason": "length"} if "cannot" in text else {},
    )


class ContextWindowTests(unittest.IsolatedAsyncioTestCase):
    def test_context_probe_pack_builds_multi_position_sentinels(self) -> None:
        cases = ContextWindowProbePack(target_tokens=768).build_cases()
        self.assertEqual(len(cases), 3)
        self.assertTrue(any(case.expected_sentinels == ("CTX-SENTINEL-EARLY", "CTX-SENTINEL-MIDDLE", "CTX-SENTINEL-LATE") for case in cases))
        self.assertGreater(len(cases[-1].prompt), len(cases[0].prompt))

    async def test_context_probe_success_scores_high_and_records_recall(self) -> None:
        adapter = GenerateAdapter("fake", "provider-a", "model-a", faithful_context_generate, TraceStore())
        report = await AuditEngine(
            adapter,
            AuditOptions(enable_protocol_probe=False, enable_context_probe=True, context_probe_target_tokens=768),
        ).run()
        self.assertIsNotNone(report.context_truth_score)
        self.assertGreaterEqual(report.context_truth_score or 0.0, 0.9)
        context_branch = next(item for item in report.branch_evidence if item["name"] == "context_truth")
        self.assertEqual(context_branch["evidence"]["sentinel_recall"], 1.0)
        self.assertEqual(context_branch["evidence"]["truncation_hits"], 0)
        self.assertEqual(report.trace_summary["by_category"]["context"], 3)

    async def test_context_probe_degraded_window_scores_low_with_truncation_evidence(self) -> None:
        adapter = GenerateAdapter("fake", "provider-a", "model-a", degraded_context_generate, TraceStore())
        report = await AuditEngine(
            adapter,
            AuditOptions(enable_protocol_probe=False, enable_context_probe=True, context_probe_target_tokens=768),
        ).run()
        self.assertIsNotNone(report.context_truth_score)
        self.assertLess(float(report.context_truth_score), 0.55)
        context_branch = next(item for item in report.branch_evidence if item["name"] == "context_truth")
        self.assertLess(context_branch["evidence"]["sentinel_recall"], 0.5)
        self.assertGreaterEqual(context_branch["evidence"]["truncation_hits"], 1)


if __name__ == "__main__":
    unittest.main()
