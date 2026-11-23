"""Approved-grid coverage, counterfactual identity, and figure reproducibility."""
from collections import Counter
import copy
import csv
import sys
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import numpy as np
import simulate_welfare_grid as grid
import report_welfare_grid as plot
from report_rewrite_welfare import read_json,digest


class GridSpecificationTests(unittest.TestCase):
    def test_approved_grid_is_exactly_35_unique_combinations(self):
        ids = [grid.cell_id(s,c) for s in grid.SIGMAS for c in grid.CHIS]
        self.assertEqual(len(ids),35)
        self.assertEqual(len(set(ids)),35)
        self.assertEqual(sum(grid.is_original(s,c) for s in grid.SIGMAS for c in grid.CHIS),8)
        with self.assertRaises(ValueError):
            grid.cell_id(1.25,3.)

    def test_new_designs_leave_the_baseline_untouched(self):
        original = grid.baseline_design(7.5)
        for sigma in grid.SIGMAS:
            for chi in grid.CHIS:
                design = grid.make_design(sigma,chi)
                self.assertEqual(design.frontier,original.frontier)
                self.assertEqual(design.initial_capability,original.initial_capability)
                self.assertEqual(design.parameters.chi,chi)
                self.assertEqual(design.sigmas,(sigma,))
                self.assertNotEqual(design.output_directory,original.output_directory)
                self.assertNotEqual(design.cache_directory,original.cache_directory)
                self.assertEqual(grid.asdict(grid.replace(design.parameters,chi=7.5)),grid.asdict(original.parameters))
                self.assertGreater(min(design.parameters.alpha,1/sigma)-design.parameters.eta*.99,0)


class AdmittedGridTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report=grid.build_report()

    def test_all_cases_are_admitted_without_dropping_failures(self):
        report=self.report
        self.assertEqual(report['admitted'],35)
        self.assertEqual(report['attempted'],35)
        self.assertEqual(report['reused'],8)
        self.assertEqual(report['new'],27)
        self.assertFalse(report['unresolved'])
        self.assertEqual(Counter(c['chi'] for c in report['cases']),{c:7 for c in grid.CHIS})
        self.assertEqual(Counter(c['sigma'] for c in report['cases']),{s:5 for s in grid.SIGMAS})
        for case in report['cases']:
            self.assertTrue(case['numerically_verified'])
            self.assertAlmostEqual(case['effective_discount'],.037)
            self.assertEqual(case['competitive_growth'],.01)

    def test_the_eight_original_numbers_are_identical(self):
        baseline=read_json(ROOT/'numerical_rewrite/welfare_comparison/welfare_results.json')
        original={(c['sigma'],c['chi']):c for c in baseline['cases']}
        count=0
        for case in self.report['cases']:
            pair=case['sigma'],case['chi']
            if pair in original:
                count+=1
                self.assertEqual(case['source_sha256'],original[pair]['source_sha256'])
                self.assertEqual(case['stages'],original[pair]['stages'])
        self.assertEqual(count,8)

    def test_initial_stocks_are_common_within_each_elasticity(self):
        for sigma in grid.SIGMAS:
            cases=[c for c in self.report['cases'] if c['sigma']==sigma]
            for field in ('initial_capital','initial_capability','frontier','competitive_initial_consumption'):
                self.assertEqual(len({c[field] for c in cases}),1)

    def test_new_text_about_level_gains_without_growth_acceleration(self):
        for sigma in (1.2,1.3,1.4):
            cases=[c for c in self.report['cases'] if c['sigma']==sigma]
            self.assertEqual(len(cases),5)
            for case in cases:
                self.assertGreater(case['stages']['long']['consumption_equivalent'],0)
                self.assertEqual(case['monopoly_growth'],case['competitive_growth'])
                self.assertEqual(case['monopoly_growth'],.01)

    def test_matrix_orientation_matches_both_axes(self):
        values=plot.grid_values(self.report)
        self.assertEqual(values.shape,(5,7))
        self.assertAlmostEqual(values[0,0],-31.852735039122898)
        self.assertAlmostEqual(values[-1,-1],130.3463501597463)
        self.assertAlmostEqual(values[-1,1],1.0039496479290169)

    def test_partial_duplicate_and_unverified_grids_are_rejected(self):
        for change in ('missing','duplicate','unverified'):
            report=copy.deepcopy(self.report)
            if change=='missing':
                report['cases'].pop()
            elif change=='duplicate':
                report['cases'][-1]=report['cases'][0]
            else:
                report['cases'][0]['numerically_verified']=False
            with self.subTest(change=change),self.assertRaises(ValueError):
                plot.grid_values(report)

    def test_zero_contour_does_not_replace_computed_cells(self):
        manifest=read_json(plot.FIGURES/'welfare_heatmap_manifest.json')
        self.assertEqual(len(manifest['cells']),35)
        self.assertIn('interpolation',manifest['zero_contour'])
        self.assertIn('not interpolated',manifest['cell_values'])
        self.assertEqual(manifest['source_sha256'],digest(grid.OUT/'grid_results.json'))
        values=plot.grid_values(self.report)
        for cell in manifest['cells']:
            value=values[grid.CHIS.index(cell['chi']),grid.SIGMAS.index(cell['sigma'])]
            self.assertEqual(cell['label'],plot.cell_label(value))
            self.assertEqual(cell['welfare_percent'],value)
        with (grid.OUT/'heatmap_cells.csv').open(newline='',encoding='utf-8') as stream:
            rows=list(csv.DictReader(stream))
        self.assertEqual(len(rows),35)
        for cell,row in zip(manifest['cells'],rows):
            self.assertEqual(cell['id'],row['id'])
            self.assertEqual(cell['label'],row['label'])
            self.assertEqual(cell['welfare_percent'],float(row['welfare_percent']))

    def test_numerical_precision_and_tail_checks_hold_in_every_cell(self):
        for case in self.report['cases']:
            self.assertLess(case['checks']['refined_to_long_ce_change'],2e-7)
            self.assertLess(case['checks']['independent_quad_difference'],1e-9)
            self.assertLess(abs(case['horizon_checks']['500']['ce_change_from_full_solution']),1e-6)
            self.assertGreater(case['stages']['long']['horizon'],3000.)


if __name__=='__main__':
    unittest.main()
