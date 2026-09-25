"""The focused presentation must preserve and faithfully select existing data."""
import csv
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import report_competitive_main_comparison as report


class CompetitiveMainComparison(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.datasets, cls.sources = report.load_comparison()

    def test_ratios_match_every_stored_observation_without_changing_sources(self):
        self.assertEqual(set(self.datasets), {7.5, 1.5})
        for chi, series in self.datasets.items():
            folder = report.make_design(chi).output_directory
            with (folder / "comparison_paths.csv").open(newline="") as stream:
                expected = {float(row["time"]): row for row in csv.DictReader(stream)
                            if float(row["sigma"]) == 1.5}
            self.assertEqual(len(series), len(expected))
            for row in series:
                self.assertEqual(row["sigma"], 1.5)
                for field in report.RATIO_FIELDS:
                    self.assertAlmostEqual(row[field], float(expected[row["time"]][field]),
                                           delta=abs(row[field]) * 1e-12)
            for path, digest in self.sources[str(chi)]["files"].items():
                self.assertEqual(report.sha256(ROOT / path), digest)

    def test_recoveries_and_level_jumps_match_the_published_evidence(self):
        for chi in report.CHIS:
            folder = report.make_design(chi).output_directory
            summary = json.loads((folder / "comparison_summary.json").read_text())["sigma_1_50"]
            event = json.loads((folder / "policy_event.json").read_text())["jumps"]["sigma_1_50"]
            self.assertEqual(self.sources[str(chi)]["first_recovery_year"],
                             summary["first_recovery_year"])
            for ratio, jump in (
                ("output_counterfactual_ratio", "output"),
                ("wage_counterfactual_ratio", "wage"),
                ("consumption_counterfactual_ratio", "consumption"),
            ):
                self.assertAlmostEqual(
                    self.sources[str(chi)]["initial_change_percent"][ratio], 100 * event[jump])

    def test_shared_axes_and_discontinuous_event_are_honest(self):
        fig = report.make_figure(self.datasets)
        try:
            self.assertEqual(len(fig.axes), 9)
            for view, window in enumerate(report.LEVEL_WINDOWS):
                for col, (field, _, _) in enumerate(report.LEVEL_PANELS):
                    axis = fig.axes[view * 3 + col]
                    self.assertEqual(tuple(axis.get_xlim()), window)
                    self.assertEqual(axis.get_yscale(), "linear" if view == 0 else "log")
                    for chi in report.CHIS:
                        line = next(line for line in axis.lines if line.get_gid() == f"chi_{chi}_post")
                        series = [r for r in self.datasets[chi] if window[0] <= r["time"] <= window[1]]
                        self.assertEqual(list(line.get_xdata()), [r["time"] for r in series])
                        self.assertEqual(list(line.get_ydata()), [r[field] for r in series])
                        self.assertGreaterEqual(min(line.get_xdata()), max(window[0], 0))
                    benchmark = next(line for line in axis.lines if line.get_gid() == "continued_competition")
                    self.assertEqual(list(benchmark.get_ydata()), [1, 1])
                    if view == 0:
                        self.assertIn("100.0", axis.yaxis.get_major_formatter()(1))
            self.assertEqual([t.get_text() for t in fig.legends[0].get_texts()],
                             ["Continued competition", r"Monopoly, $\chi=7.5$", r"Monopoly, $\chi=1.5$"])
        finally:
            report.plt.close(fig)

    def test_figure_provenance_and_appendix_preservation(self):
        manifest = json.loads((report.FIGDIR / f"{report.STEM}_manifest.json").read_text())
        self.assertEqual(manifest["sigma"], 1.5)
        self.assertEqual(manifest["chis"], [7.5, 1.5])
        self.assertEqual(manifest["windows"], [[-2, 10], [10, 100], [10, 500]])
        for entry in manifest["sources"].values():
            for path, digest in entry["files"].items():
                self.assertEqual(report.sha256(ROOT / path), digest)
        for name in manifest["files"]:
            self.assertTrue((ROOT / name).is_file())
        main = (ROOT / "sections_rewrite/14_competitive_to_monopoly.tex").read_text()
        appendix = (ROOT / "sections_rewrite/appendix_competitive_transition.tex").read_text()
        self.assertIn(f"{report.STEM}.pdf", main)
        for chi in ("7_5", "1_5"):
            filename = f"competitive_to_monopoly_chi_{chi}_levels.pdf"
            self.assertNotIn(filename, main)
            self.assertIn(filename, appendix)
        self.assertTrue((ROOT / "sections_rewrite/archive/14_competitive_to_monopoly_four_sigmas.tex").is_file())


if __name__ == "__main__":
    unittest.main()
