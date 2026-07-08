from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path

from llm_identify.benchmark import default_regression_cases, evaluate_benchmark, load_benchmark_cases, parse_benchmark_case, write_benchmark_artifacts
from llm_identify.exporting import default_curve_rows, write_curve_placeholders


class BenchmarkHarnessTests(unittest.TestCase):
    def test_default_regression_metrics_include_calibration_and_scenarios(self) -> None:
        metrics = evaluate_benchmark(default_regression_cases())
        self.assertEqual(metrics.total_cases, 6)
        self.assertIsNotNone(metrics.macro_auroc)
        self.assertGreater(metrics.top1_accuracy, 0.0)
        self.assertGreater(metrics.macro_f1, 0.0)
        self.assertIn("temperature", metrics.temperature_calibration)
        self.assertGreater(metrics.brier_score, 0.0)
        self.assertGreaterEqual(metrics.expected_calibration_error, 0.0)
        self.assertEqual(len(metrics.reliability_bins), 10)
        self.assertEqual(len(metrics.threshold_curve), 21)
        self.assertIn("mixed_routing", metrics.scenario_metrics)
        self.assertIn("openai_like", metrics.confusion_matrix)

    def test_benchmark_case_parser_normalizes_probability_mass(self) -> None:
        case = parse_benchmark_case(
            {
                "case_id": "x",
                "expected_family": "openai_like",
                "probabilities": {"openai_like": 8, "anthropic_like": 1, "google_like": 1},
                "scenario": "compatibility_layer",
            }
        )
        self.assertAlmostEqual(sum(case.probabilities.values()), 1.0)
        self.assertEqual(case.predicted_family, "openai_like")
        self.assertEqual(case.scenario, "compatibility_layer")

    def test_benchmark_loader_accepts_json_csv_and_jsonl(self) -> None:
        rows = [
            {"case_id": "a", "expected_family": "openai_like", "openai_like": 0.9, "anthropic_like": 0.1},
            {"case_id": "b", "expected_family": "anthropic_like", "probabilities": {"anthropic_like": 0.8, "unknown": 0.2}},
        ]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            json_path = root / "cases.json"
            json_path.write_text(json.dumps({"cases": rows}), encoding="utf-8")
            jsonl_path = root / "cases.jsonl"
            jsonl_path.write_text("\n".join(json.dumps(row) for row in rows), encoding="utf-8")
            csv_path = root / "cases.csv"
            with csv_path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=["case_id", "expected_family", "openai_like", "anthropic_like", "unknown"])
                writer.writeheader()
                writer.writerow({"case_id": "a", "expected_family": "openai_like", "openai_like": 0.9, "anthropic_like": 0.1, "unknown": 0.0})
                writer.writerow({"case_id": "b", "expected_family": "anthropic_like", "openai_like": 0.1, "anthropic_like": 0.8, "unknown": 0.1})
            self.assertEqual(len(load_benchmark_cases(json_path)), 2)
            self.assertEqual(len(load_benchmark_cases(jsonl_path)), 2)
            self.assertEqual(len(load_benchmark_cases(csv_path)), 2)

    def test_benchmark_rejects_unknown_expected_family(self) -> None:
        with self.assertRaises(ValueError):
            parse_benchmark_case({"expected_family": "not-a-family", "probabilities": {"unknown": 1.0}})

    def test_benchmark_artifacts_are_written_and_cli_compat_wrapper_is_real(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            paths = write_benchmark_artifacts(default_regression_cases(), tmp)
            names = {path.name for path in paths}
            self.assertIn("benchmark_metrics.json", names)
            self.assertIn("threshold_curve.csv", names)
            self.assertIn("reliability_bins.csv", names)
            self.assertIn("temperature_calibration.json", names)
            metrics = json.loads((Path(tmp) / "benchmark_metrics.json").read_text(encoding="utf-8"))
            self.assertEqual(metrics["total_cases"], 6)
            self.assertIn("macro_f1", metrics)
            self.assertIn("temperature_calibration", metrics)
        with tempfile.TemporaryDirectory() as tmp:
            wrapper_paths = write_curve_placeholders(tmp)
            self.assertTrue((Path(tmp) / "benchmark_metrics.json").exists())
            self.assertTrue(any(path.name == "benchmark_manifest.json" for path in wrapper_paths))
        self.assertIn("accepted", default_curve_rows()[0])


if __name__ == "__main__":
    unittest.main()
