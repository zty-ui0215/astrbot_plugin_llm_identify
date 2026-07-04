from __future__ import annotations

import tempfile
import unittest

from llm_identify.local_fingerprint import FingerprintLibraryCandidate, LocalFingerprintLibraryManager
from llm_identify.probes.fingerprint import FingerprintProbePack
from llm_identify.rules import load_rules
from llm_identify.storage import AuditStorage
from llm_identify.tasks import AuditTask
from llm_identify.vendored_fingerprint import load_bundled_fingerprint_packs
from tests.test_task_storage_privacy_cli import minimal_report


class GoalFeatureTests(unittest.TestCase):
    def test_local_fingerprint_library_status_reports_available_module(self) -> None:
        manager = LocalFingerprintLibraryManager([FingerprintLibraryCandidate(module="json", package="json")])
        payload = manager.payload()
        self.assertTrue(payload["local_operation_available"])
        self.assertTrue(payload["libraries"][0]["available"])

    def test_bundled_fingerprint_pack_is_available_without_install(self) -> None:
        manager = LocalFingerprintLibraryManager.from_config("bundled:llmmap")
        payload = manager.payload()
        self.assertTrue(payload["local_operation_available"])
        self.assertFalse(payload["install_required"])
        self.assertTrue(payload["bundled_libraries"][0]["available"])
        self.assertEqual(payload["bundled_libraries"][0]["license"], "MIT")

    def test_bundled_fingerprint_pack_contributes_probe_rules(self) -> None:
        load_rules.cache_clear()
        load_bundled_fingerprint_packs.cache_clear()
        rules = load_rules()
        self.assertTrue(any(rule.rule_id == "bundled_llmmap_nonce_contract" for rule in rules.probe_rules))
        self.assertIn("bundled_llmmap_behavior", rules.feature_rules)

    def test_fingerprint_probe_pack_samples_redundant_cases_per_method(self) -> None:
        full = FingerprintProbePack(profile="standard", repeats=1, randomize=False).build_cases()
        sampled = FingerprintProbePack(profile="standard", repeats=1, randomize=True, probes_per_method=1, seed=7).build_cases()
        full_methods = {case.method for case in full}
        sampled_methods = {case.method for case in sampled}
        self.assertEqual(full_methods, sampled_methods)
        self.assertLessEqual(len(sampled), len(full))

    def test_storage_exports_complete_records_as_txt_and_pdf(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            storage = AuditStorage(tmp)
            task = AuditTask.create(target_id="target", mode="test")
            storage.create_task(task)
            storage.save_report(task.task_id, minimal_report(), [])
            txt = storage.export_report(task.task_id, "txt")
            pdf = storage.export_report(task.task_id, "pdf")
            self.assertTrue(txt.exists())
            self.assertTrue(pdf.exists())
            self.assertIn("Complete Inspection Record", txt.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()