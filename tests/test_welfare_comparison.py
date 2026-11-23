"""Welfare identities, tail handling, and the two admitted numerical cases."""
import importlib.util
import math
from pathlib import Path
import unittest

import numpy as np
from scipy.interpolate import PPoly

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('welfare', ROOT / 'scripts/report_rewrite_welfare.py')
welfare = importlib.util.module_from_spec(spec)
spec.loader.exec_module(welfare)


class WelfareIdentityTests(unittest.TestCase):
    def compare_affine(self, level, slope, beta, end):
        spline = PPoly(np.array([[0.], [0.], [slope], [level]]), np.array([0., end]))
        value = welfare.weighted_integral(spline, beta, end)
        value += welfare.affine_tail(float(spline(end)), slope, beta, end)
        self.assertAlmostEqual(value, level / beta + slope / beta ** 2, places=10)
        self.assertAlmostEqual(welfare.ce_from_integral(value, beta),
                               math.expm1(level + slope / beta), places=10)
        return value

    def test_identical_paths_have_zero_gain(self):
        self.assertEqual(self.compare_affine(0., 0., .037, 500.), 0.)

    def test_constant_consumption_premium(self):
        value = self.compare_affine(math.log(1.05), 0., .037, 50.)
        self.assertAlmostEqual(welfare.ce_from_integral(value, .037), .05)

    def test_growth_difference_and_tail(self):
        for end in (10., 50., 500.):
            with self.subTest(end=end):
                self.compare_affine(-.2, .02, .037, end)

    def test_reversing_comparison_is_not_negating_percentage(self):
        positive = welfare.ce_from_integral(2., .037)
        negative = welfare.ce_from_integral(-2., .037)
        self.assertAlmostEqual((1 + positive) * (1 + negative), 1.)

    def test_nonpositive_discount_is_rejected(self):
        with self.assertRaises(ValueError):
            welfare.affine_tail(1., .01, 0., 500.)


class PublishedWelfareTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = welfare.build_report()

    def test_published_numbers_and_effective_discount(self):
        for case, expected in zip(self.report['cases'], (1.303463501597463, .11094849249348833)):
            with self.subTest(chi=case['chi']):
                self.assertTrue(case['numerically_verified'])
                self.assertAlmostEqual(case['effective_discount'], .037)
                self.assertAlmostEqual(case['stages']['long']['consumption_equivalent'], expected, places=9)
                self.assertGreater(case['stages']['long']['horizon'], 4000.)
                self.assertLess(abs(case['horizon_checks']['500']['ce_change_from_full_solution']), 1e-8)

    def test_table_is_generated_from_current_report(self):
        table = (ROOT / 'sections_rewrite/welfare_table.tex').read_text(encoding='utf-8')
        self.assertEqual(table, welfare.render_table(self.report))


if __name__ == '__main__':
    unittest.main()
