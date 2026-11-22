"""Analytical sensitivity report stays tied to the saved design."""
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    'growth_sensitivity', ROOT / 'scripts/report_rewrite_growth_sensitivity.py')
reporter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(reporter)


class GrowthSensitivityTests(unittest.TestCase):
    def test_rates_and_generated_table(self):
        report = reporter.build()
        rows = report['rows']
        self.assertEqual(len(rows), 5)
        self.assertEqual(sum(len(row['cells']) for row in rows), 20)
        self.assertTrue(all(cell['growth'] == 0.01 for cell in rows[0]['cells']))
        self.assertAlmostEqual(rows[1]['cells'][1]['growth'], 0.03134997581384653)
        self.assertAlmostEqual(rows[3]['cells'][1]['growth'], 0.48651069826735055)
        self.assertAlmostEqual(rows[4]['cells'][1]['growth'], 12.921960145693298)
        for row in rows:
            rates = [cell['growth'] for cell in row['cells']]
            self.assertEqual(rates, sorted(rates))
        self.assertEqual((ROOT / 'sections_rewrite/growth_sensitivity.tex').read_text(
            encoding='utf-8'), reporter.render(report))


if __name__ == '__main__':
    unittest.main()
