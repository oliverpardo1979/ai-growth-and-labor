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
            self.assertEqual(len(fig.axes), 6)
            self.assertEqual([panel[0] for panel in report.MAIN_PANELS],
                             ["output_counterfactual_ratio", "wage_counterfactual_ratio",
                              "consumption_counterfactual_ratio"])
            for view, window in enumerate(report.MAIN_WINDOWS):
                for col, (field, _, unit) in enumerate(report.MAIN_PANELS):
                    axis = fig.axes[view * 3 + col]
                    self.assertEqual(tuple(axis.get_xlim()), window)
                    self.assertEqual(unit, "ratio")
                    self.assertEqual(axis.get_yscale(), "linear" if view == 0 else "log")
                    for chi in report.CHIS:
                        line = next(line for line in axis.lines if line.get_gid() == f"chi_{chi}_post")
                        series = [r for r in self.datasets[chi] if window[0] <= r["time"] <= window[1]]
                        self.assertEqual(list(line.get_xdata()), [r["time"] for r in series])
                        self.assertEqual(list(line.get_ydata()), [r[field] for r in series])
                        self.assertGreaterEqual(min(line.get_xdata()), max(window[0], 0))
                    benchmark = next(line for line in axis.lines if line.get_gid() == "continued_competition")
                    value = report.competitive_benchmark(self.datasets, field)
                    self.assertEqual(value, 1.)
                    self.assertEqual(list(benchmark.get_ydata()), [value, value])
                    if view == 0 and unit == "ratio":
                        self.assertIn("100.0", axis.yaxis.get_major_formatter()(1))
                    if view == 0:
                        for chi in report.CHIS:
                            before = next(line for line in axis.lines if line.get_gid() == f"chi_{chi}_before")
                            after = next(line for line in axis.lines if line.get_gid() == f"chi_{chi}_after")
                            self.assertEqual(list(before.get_ydata()), [value])
                            self.assertEqual(list(after.get_ydata()), [self.datasets[chi][0][field]])
            self.assertEqual([t.get_text() for t in fig.legends[0].get_texts()],
                             ["Continued competition", r"Monopoly, $\chi=7.5$", r"Monopoly, $\chi=1.5$"])
        finally:
            report.plt.close(fig)

    def test_main_consumption_panels_plot_the_stored_consumption_series(self):
        fig = report.make_figure(self.datasets)
        try:
            for chi in report.CHIS:
                folder = report.make_design(chi).output_directory
                reference = json.loads((folder / "competitive_reference.json").read_text())["sigma_1_50"]
                with (folder / "equilibrium_paths.csv").open(newline="") as stream:
                    raw = {float(row["time"]): float(row["consumption_effective_labor"])
                           for row in csv.DictReader(stream) if float(row["sigma"]) == 1.5}
                for view in (0, 1):
                    axis = fig.axes[3 * view + 2]
                    self.assertIn("Consumption per person", " ".join(axis.get_title(loc="left").split()))
                    line = next(line for line in axis.lines if line.get_gid() == f"chi_{chi}_post")
                    for time, value in zip(line.get_xdata(), line.get_ydata()):
                        self.assertEqual(value, raw[time] / reference["consumption"])
        finally:
            report.plt.close(fig)

    def test_supplementary_revenue_uses_own_output_and_two_linear_windows(self):
        fig = report.make_revenue_figure(self.datasets)
        try:
            self.assertEqual(len(fig.axes), 2)
            self.assertEqual(fig.axes[0].get_ylim(), fig.axes[1].get_ylim())
            benchmark_value = report.competitive_benchmark(self.datasets, "ai_revenue_output_share")
            self.assertGreater(benchmark_value, 0)
            self.assertLess(benchmark_value, 1)
            for axis, window in zip(fig.axes, report.MAIN_WINDOWS):
                self.assertEqual(tuple(axis.get_xlim()), window)
                self.assertEqual(axis.get_yscale(), "linear")
                self.assertIn("50.0", axis.yaxis.get_major_formatter()(.5))
                benchmark = next(line for line in axis.lines if line.get_gid() == "continued_competition")
                self.assertEqual(list(benchmark.get_ydata()), [benchmark_value, benchmark_value])
                self.assertEqual(benchmark.get_color(), report.COMPETITION_STYLE[0])
                for chi in report.CHIS:
                    line = next(line for line in axis.lines if line.get_gid() == f"chi_{chi}_post")
                    series = [row for row in self.datasets[chi] if window[0] <= row["time"] <= window[1]]
                    self.assertEqual(list(line.get_xdata()), [row["time"] for row in series])
                    self.assertEqual(list(line.get_ydata()), [row["ai_revenue_output_share"] for row in series])
                    self.assertEqual(line.get_color(), report.STYLES[chi][0])
                    self.assertGreaterEqual(min(line.get_xdata()), max(window[0], 0))
                    if window[0] < 0:
                        before = next(line for line in axis.lines if line.get_gid() == f"chi_{chi}_before")
                        after = next(line for line in axis.lines if line.get_gid() == f"chi_{chi}_after")
                        pre = next(line for line in axis.lines if line.get_gid() == f"chi_{chi}_pre")
                        self.assertEqual(list(pre.get_xdata()), [window[0], 0])
                        self.assertEqual(list(before.get_ydata()), [benchmark_value])
                        self.assertEqual(list(after.get_ydata()), [series[0]["ai_revenue_output_share"]])
            self.assertEqual([text.get_text() for text in fig.legends[0].get_texts()],
                             ["Continued competition", r"Monopoly, $\chi=7.5$", r"Monopoly, $\chi=1.5$"])
        finally:
            report.plt.close(fig)

    def test_revenue_is_not_net_profit_or_a_ratio_to_competitive_revenue(self):
        for chi, series in self.datasets.items():
            folder = report.make_design(chi).output_directory
            parameters = json.loads((folder / "scenario.json").read_text())["parameters"]
            reference = json.loads((folder / "competitive_reference.json").read_text())["sigma_1_50"]
            with (folder / "equilibrium_paths.csv").open(newline="") as stream:
                expected = {float(row["time"]): row for row in csv.DictReader(stream)
                            if float(row["sigma"]) == 1.5}
            self.assertGreater(reference["ai_revenue_output_share"], 0)
            self.assertEqual(reference["profit_output_share"], 0)
            for row in series:
                revenue = row["ai_revenue_output_share"]
                self.assertEqual(revenue, float(expected[row["time"]]["ai_revenue_output_share"]))
                self.assertAlmostEqual(revenue, 1 - parameters["alpha"] - row["labor_income_share"])
                self.assertAlmostEqual(revenue, sum(row[field] for field in
                                      ("profit_output_share", "inference_output_share", "research_output_share")))
                self.assertEqual(row["competitive_ai_revenue_output_share"],
                                 reference["ai_revenue_output_share"])

    def test_figure_provenance_and_appendix_preservation(self):
        manifest = json.loads((report.FIGDIR / f"{report.STEM}_manifest.json").read_text())
        self.assertEqual(manifest["sigma"], 1.5)
        self.assertEqual(manifest["chis"], [7.5, 1.5])
        self.assertEqual(manifest["windows"], [[-2, 10], [10, 50]])
        self.assertEqual([panel["field"] for panel in manifest["panels"]],
                         ["output_counterfactual_ratio", "wage_counterfactual_ratio", "consumption_counterfactual_ratio"])
        for panel in manifest["panels"]:
            self.assertEqual(panel["scales_by_window"], ["linear_percent", "log_multiple"])
            self.assertEqual(panel["competitive_benchmark"], 1.)
        revenue = manifest["supplementary_revenue"]
        self.assertEqual(revenue["stem"], report.REVENUE_STEM)
        self.assertEqual(revenue["field"], "ai_revenue_output_share")
        self.assertEqual(revenue["windows"], [[-2, 10], [10, 50]])
        self.assertEqual(revenue["scales_by_window"], ["linear_percent", "linear_percent"])
        self.assertEqual(revenue["competitive_benchmark"],
                         report.competitive_benchmark(self.datasets, "ai_revenue_output_share"))
        self.assertEqual(len(manifest["files"]), 4)
        self.assertTrue(set(revenue["files"]) <= set(manifest["files"]))
        for path, digest in manifest["preserved_supplemental_files"].items():
            self.assertEqual(report.sha256(ROOT / path), digest)
        for entry in manifest["sources"].values():
            for path, digest in entry["files"].items():
                self.assertEqual(report.sha256(ROOT / path), digest)
        for name in manifest["files"]:
            self.assertTrue((ROOT / name).is_file())
        main = (ROOT / "sections_rewrite/14_competitive_to_monopoly.tex").read_text()
        appendix = (ROOT / "sections_rewrite/appendix_competitive_transition.tex").read_text()
        self.assertIn(f"{report.STEM}.pdf", main)
        self.assertNotIn(f"{report.REVENUE_STEM}.pdf", main)
        self.assertIn(f"{report.REVENUE_STEM}.pdf", appendix)
        for chi in ("7_5", "1_5"):
            filename = f"competitive_to_monopoly_chi_{chi}_levels.pdf"
            self.assertNotIn(filename, main)
            self.assertIn(filename, appendix)
        self.assertTrue((ROOT / "sections_rewrite/archive/14_competitive_to_monopoly_four_sigmas.tex").is_file())


if __name__ == "__main__":
    unittest.main()
