"""Read-only checks for the web export; no numerical solver is imported."""
import copy
import csv
import hashlib
import json
import math
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import build_web_data as web


class WebDataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = web.build_data(ROOT)

    def test_only_eight_scenarios_and_actual_shared_dates(self):
        self.assertEqual(set(self.data["datasets"]), {"7.5", "1.5"})
        self.assertEqual(self.data["windows"], {"short": [-2, 10], "long": [10, 500]})
        times = self.data["times"]
        self.assertEqual(len(times), 4961)
        self.assertEqual((times[0], times[-1]), (0, 500))
        self.assertTrue(all(left < right for left, right in zip(times, times[1:])))
        for dataset in self.data["datasets"].values():
            self.assertEqual(set(dataset["scenarios"]), {"0.9", "1", "1.1", "1.5"})
            for scenario in dataset["scenarios"].values():
                self.assertEqual(set(scenario["columns"]), set(web.FIELD_KEYS))
                self.assertTrue(all(len(column) == len(times) for column in scenario["columns"].values()))

    def test_all_original_samples_preserved_without_rounding(self):
        alpha = self.data["parameters"]["alpha"]
        for dataset in self.data["datasets"].values():
            path = ROOT / dataset["provenance"]["csv_path"]
            indices = {f"{sigma:g}": 0 for sigma in web.SIGMAS}
            with path.open(encoding="utf-8", newline="") as stream:
                for row in csv.DictReader(stream):
                    sigma = f"{float(row['sigma']):g}"
                    index = indices[sigma]
                    self.assertEqual(self.data["times"][index], float(row["time"]))
                    columns = dataset["scenarios"][sigma]["columns"]
                    for key in web.FIELD_KEYS:
                        expected = (1 - alpha - float(row["labor_income_share"])
                                    if key == "ai_revenue_output_share" else float(row[key]))
                        self.assertEqual(columns[key][index], expected)
                    indices[sigma] += 1
            self.assertEqual(set(indices.values()), {len(self.data["times"])})

    def test_source_hashes_and_admission_provenance(self):
        for dataset in self.data["datasets"].values():
            provenance = dataset["provenance"]
            self.assertEqual(hashlib.sha256((ROOT / provenance["csv_path"]).read_bytes()).hexdigest(),
                             provenance["csv_sha256"])
            self.assertEqual(provenance["raw_csv_url"], web.RAW_BASE + provenance["csv_path"])
            self.assertTrue(provenance["all_recorded_checks_pass"])
            folder = ROOT / "numerical_rewrite" / dataset["design"]
            for name, digest in provenance["manifest_sha256"].items():
                self.assertEqual(web.sha256(folder / f"{name}.json"), digest)
            for key, digest in provenance["audit_sha256"].items():
                self.assertEqual(web.sha256(folder / f"{key}_audit.json"), digest)

    def test_units_normalization_and_income_identity(self):
        metadata = {item["key"]: item for item in self.data["fields"]}
        self.assertEqual(len(metadata), 13)
        self.assertEqual(metadata["ai_service_price"]["display_scale"], 1)
        self.assertEqual(metadata["ai_service_price"]["axis_scale"], "log")
        self.assertEqual(metadata["output_per_person_growth"]["unit"], "instantaneous_percent_per_year")
        self.assertEqual(metadata["research_output_share"]["unit"], "percent_of_output")
        gamma = self.data["parameters"]["labor_productivity_growth"]
        for dataset in self.data["datasets"].values():
            for scenario in dataset["scenarios"].values():
                columns = scenario["columns"]
                for index in range(len(self.data["times"])):
                    self.assertAlmostEqual(columns["output_per_person_growth"][index],
                                           columns["output_effective_labor_growth"][index] + gamma, places=12)
                    self.assertAlmostEqual(columns["ai_revenue_output_share"][index],
                                           sum(columns[key][index] for key in
                                               ("profit_output_share", "inference_output_share", "research_output_share")),
                                           places=12)
                self.assertTrue(all(math.isfinite(value) for column in columns.values() for value in column))

    def test_pre_event_and_only_documented_analytical_limits(self):
        for dataset in self.data["datasets"].values():
            figures = web.load_json(ROOT / "numerical_rewrite" / dataset["design"] / "figure_manifest.json")
            for sigma, scenario in dataset["scenarios"].items():
                pre = scenario["pre_event"]
                self.assertEqual(set(pre), set(web.FIELD_KEYS))
                self.assertEqual(pre["research_output_share"], 0)
                self.assertEqual(pre["output_effective_labor_growth"], 0)
                self.assertEqual(pre["output_per_person_growth"], self.data["parameters"]["labor_productivity_growth"])
                if sigma == "1.5":
                    self.assertEqual(scenario["analytical_limits"], figures["analytical_limits"]["sigma_1_50"])
                    self.assertNotIn("output_per_person_growth", scenario["analytical_limits"])
                else:
                    self.assertIsNone(scenario["analytical_limits"])
                self.assertGreater(scenario["columns"]["research_output_share"][0], pre["research_output_share"])

    def test_hash_mismatch_rejected(self):
        with self.assertRaisesRegex(ValueError, "CSV hash"):
            web.validate_csv_hash("actual", {"csv_sha256": "stale"},
                                  {"data_sha256": "actual"}, {"data_sha256": "actual"})

    def test_unadmitted_or_changed_source_manifest_rejected(self):
        original_loader = web.load_json
        for target, change in (
            ("scenario.json", lambda item: item.update(status="not_admitted")),
            ("figure_manifest.json", lambda item: item["analytical_limits"].update(sigma_1_00={})),
            ("activation_audit.json", lambda item: item.update(passes=False)),
        ):
            def tampered(path):
                item = original_loader(path)
                if path.name == target:
                    item = copy.deepcopy(item)
                    change(item)
                return item
            with self.subTest(target=target), patch.object(web, "load_json", side_effect=tampered):
                with self.assertRaises(ValueError):
                    web.load_dataset(ROOT, 7.5, "rsi_chi_7_5")

    def test_generated_file_is_current(self):
        expected = (json.dumps(self.data, ensure_ascii=False, allow_nan=False, separators=(",", ":")) + "\n").encode("utf-8")
        self.assertEqual((ROOT / web.OUTPUT).read_bytes(), expected)


if __name__ == "__main__":
    unittest.main()
