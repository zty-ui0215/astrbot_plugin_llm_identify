from __future__ import annotations

import unittest

from llm_identify.probes import FingerprintProbePack
from llm_identify.rules import load_rules


class FingerprintRuleTests(unittest.TestCase):
    def test_rule_database_covers_documented_methods(self) -> None:
        rules = load_rules()
        methods = {rule.method for rule in rules.probe_rules} | set(rules.feature_rules)
        expected = {
            "llmmap_behavior",
            "prompt_probe",
            "refusal_style",
            "embedding_fingerprint",
            "knowledge_boundary",
            "reasoning_structure",
            "tokenizer_unicode",
            "sampling_distribution",
            "api_sidechannel",
            "mixed_routing",
            "context_truth",
            "adversarial_robustness",
            "inference_stack",
        }
        self.assertTrue(expected.issubset(methods))

    def test_public_fingerprint_database_is_loadable(self) -> None:
        rules = load_rules()
        self.assertIn("fingerprint", rules.databases)
        models = rules.databases["fingerprint"]["models"]
        sources = {item.get("id") for item in rules.databases["fingerprint"].get("sources", [])}
        self.assertGreaterEqual(len(models), 50)
        self.assertIn("llmmap_default_supported_models", sources)
        self.assertIn("lmsys_chat_1m", sources)
        self.assertEqual(rules.databases["embedding"]["vectors"], [])
        self.assertEqual(rules.databases["knowledge_boundary"]["facts"], [])

    def test_profile_selection_is_executable(self) -> None:
        light = FingerprintProbePack(profile="light", repeats=1).build_cases()
        standard = FingerprintProbePack(profile="standard", repeats=1).build_cases()
        exhaustive = FingerprintProbePack(profile="exhaustive", repeats=1).build_cases()
        self.assertLess(len(light), len(standard))
        self.assertLess(len(standard), len(exhaustive))


if __name__ == "__main__":
    unittest.main()
