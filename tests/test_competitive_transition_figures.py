"""Presentation changes must select stored paths, not alter the experiment."""
import hashlib
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import report_competitive_to_monopoly as report


class CompetitiveTransitionFigures(unittest.TestCase):
    def test_main_figures_have_intermediate_window_and_honest_scales(self):
        for chi in (7.5, 1.5):
            design = report.make_design(chi)
            rows, references = report.write_report(design)
            fig = report.figure(design, rows, references, report.LEVEL_PANELS,
                                'Levels relative to competition', levels=True)
            try:
                self.assertEqual(len(fig.axes), 9)
                for view, window in enumerate(report.LEVEL_WINDOWS):
                    for axis in fig.axes[3*view:3*(view+1)]:
                        self.assertEqual(tuple(axis.get_xlim()), window)
                        self.assertEqual(axis.get_yscale(), 'linear' if view == 0 else 'log')
                        # The first four lines of each post-event panel are
                        # the four elasticities, all within the stated window.
                        if view:
                            for line in axis.lines[:4]:
                                x = line.get_xdata()
                                self.assertGreaterEqual(min(x), window[0])
                                self.assertLessEqual(max(x), window[1])
                self.assertIn('100.0', fig.axes[0].yaxis.get_major_formatter()(1))
            finally:
                report.plt.close(fig)

    def test_manuscript_figures_and_provenance_exist(self):
        manifest = json.loads((report.FIGDIR / 'manifest.json').read_text())
        self.assertEqual(manifest['levels_windows'], [[-2, 10], [10, 100], [10, 500]])
        self.assertEqual(manifest['detail_windows'], [[-2, 10], [10, 500]])
        self.assertEqual(manifest['percent_decimals'], 1)
        self.assertEqual(len(manifest['individual_pdfs']), 8)
        for name in manifest['individual_pdfs']:
            self.assertTrue((ROOT / name).read_bytes().startswith(b'%PDF-'))
        for name, expected in manifest['source_sha256'].items():
            actual = hashlib.sha256((ROOT / 'numerical_rewrite' / name /
                                     'comparison_paths.csv').read_bytes()).hexdigest()
            self.assertEqual(actual, expected)
        main = (ROOT / 'main_rewrite.tex').read_text()
        self.assertIn(r'\input{sections_rewrite/14_competitive_to_monopoly}', main)
        self.assertIn(r'\input{sections_rewrite/appendix_competitive_transition}', main)


if __name__ == '__main__':
    unittest.main()
