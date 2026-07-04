from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from llm_identify.adapters.base import GenerateAdapter
from llm_identify.capture import TraceStore
from llm_identify.engine import AuditEngine, AuditOptions
from llm_identify.evidence import ExternalJudge, PublicKnowledgeSource
from llm_identify.models import ModelReply, TokenSnapshot


async def fake_generate(prompt: str, **kwargs):
    text = "OK"
    if "JSON only" in prompt:
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
    return ModelReply(text=text, usage=TokenSnapshot(input=input_tokens, output=output_tokens, total=input_tokens + output_tokens), raw_type="fake")


async def openai_judge(prompt: str) -> str:
    return '{"family":"openai_like","confidence":0.81,"rationale":"OpenAI-like feature cluster"}'


async def relay_judge(prompt: str) -> str:
    return '{"family":"open_source_or_relay","confidence":0.62,"rationale":"Relay risk remains plausible"}'


class EvidenceSourceTests(unittest.IsolatedAsyncioTestCase):
    async def test_multiple_external_judges_are_logged(self) -> None:
        adapter = GenerateAdapter("fake", "provider-a", "gpt-test", fake_generate, TraceStore())
        report = await AuditEngine(
            adapter,
            AuditOptions(
                enable_protocol_probe=False,
                enable_fingerprint_probe=True,
                fingerprint_repeats=1,
                external_judges=[
                    ExternalJudge("judge-openai", openai_judge),
                    ExternalJudge("judge-relay", relay_judge),
                ],
            ),
        ).run()
        self.assertEqual([item.model for item in report.judge_invocations], ["judge-openai", "judge-relay"])
        self.assertIn("external_llm_judge:judge-openai", report.fingerprint_method_scores)
        self.assertEqual(report.execution_trace["judge_invocation_count"], 2)

    async def test_public_fingerprint_source_contributes_candidate_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source_path = Path(tmp) / "public.json"
            source_path.write_text(
                json.dumps({"models": [{"id": "gpt-test", "family": "openai_like", "provider_cluster": "provider-a"}]}),
                encoding="utf-8",
            )
            adapter = GenerateAdapter("fake", "provider-a", "gpt-test", fake_generate, TraceStore())
            report = await AuditEngine(
                adapter,
                AuditOptions(
                    enable_protocol_probe=False,
                    enable_fingerprint_probe=True,
                    fingerprint_repeats=1,
                    public_knowledge_sources=[PublicKnowledgeSource("local-public", path=str(source_path))],
                    public_cache_dir=tmp,
                ),
            ).run()
            public_source = next(item for item in report.evidence_sources if item.source_id == "local-public")
            self.assertEqual(public_source.status, "ok")
            self.assertIn("public_knowledge:local-public", report.fingerprint_method_scores)
            public_probe = next(item for item in report.probe_results if item.name == "public_knowledge:local-public")
            self.assertIn("gpt-test", public_probe.evidence.get("matched_models", []))

    async def test_unavailable_public_source_degrades_without_failing_audit(self) -> None:
        adapter = GenerateAdapter("fake", "provider-a", "gpt-test", fake_generate, TraceStore())
        report = await AuditEngine(
            adapter,
            AuditOptions(
                enable_protocol_probe=False,
                enable_fingerprint_probe=True,
                fingerprint_repeats=1,
                public_knowledge_sources=[PublicKnowledgeSource("missing", path="Z:/missing/fingerprints.json")],
            ),
        ).run()
        missing_source = next(item for item in report.evidence_sources if item.source_id == "missing")
        self.assertEqual(missing_source.status, "unavailable")
        self.assertTrue(any(item.startswith("missing:") for item in report.degraded_modes))
        self.assertGreater(report.confidence, 0.0)


if __name__ == "__main__":
    unittest.main()



