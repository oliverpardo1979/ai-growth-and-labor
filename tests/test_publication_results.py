"""Check published evidence without claiming to recompute equilibrium paths."""
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import re
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
from simulate_rewrite_illustrative_rsi import make_design, SIGMAS, key, design_initial_stocks
from report_rewrite_illustrative_rsi import admitted_data


class PublicationResults(unittest.TestCase):
    def test_only_research_productivity_changes_between_comparisons(self):
        high, low = make_design(7.5), make_design(1.5)
        p, q = asdict(high.parameters), asdict(low.parameters)
        self.assertEqual(p.pop('chi') / q.pop('chi'), 5)
        self.assertEqual(p, q)
        self.assertEqual(p['omega_x'], .1)
        self.assertEqual(p['eta'], .2)
        self.assertEqual(high.frontier, low.frontier)
        self.assertEqual(high.initial_capability, .01*high.frontier)
        for sigma in SIGMAS:
            self.assertEqual(design_initial_stocks(high, sigma), design_initial_stocks(low, sigma))

    def test_all_eight_saved_paths_pass_recorded_admission_checks(self):
        for chi in (7.5, 1.5):
            data = admitted_data(make_design(chi).name)
            self.assertIsNone(data['spec']['empirical_target'])
            for report in data['reports']:
                with self.subTest(chi=chi, sigma=report['sigma_xl']):
                    self.assertTrue(report['equilibrium_certified'])
                    self.assertLess(report['horizon_comparison']['maximum_common_window_coordinate_change'], 1e-5)
                    for check in report['independent_dated_checks'] + report['early_window_checks']['independent_residuals']:
                        self.assertLess(check['maximum_ode_residual'], 1e-6)
                        self.assertLess(check['maximum_monopoly_foc_residual'], 1e-9)
                        self.assertLess(check['maximum_research_foc_residual'], 1e-9)
                    self.assertLess(report['audit']['asymptotic_household_tvc_growth'], 0)
                    self.assertLess(report['audit']['asymptotic_developer_tvc_growth'], 0)
                    if report['sigma_xl'] == 1.5:
                        self.assertTrue(all(g['support_diagnostic_passes'] for g in report['global_hamiltonian_support']))
                        self.assertGreater(report['analytical_support_continuation']['analytical_limiting_margin'], 0)
                    else:
                        self.assertTrue(report['counterfactual_developer_sufficiency']['developer_sufficiency_gate_passes'])

    def test_initial_bgp_and_activation_continuity(self):
        for chi in (7.5, 1.5):
            data = admitted_data(make_design(chi).name)
            for sigma in SIGMAS:
                event = data['event']['scenarios'][key(sigma)]
                self.assertTrue(event['passes'])
                self.assertEqual(event['pre']['research_compute'], 0)
                self.assertGreater(event['pre']['inference_compute'], 0)
                self.assertAlmostEqual(event['pre']['capital_output_ratio'], 3.3)
                self.assertLess(max(abs(v) for v in event['level_log_gaps'].values()), 1e-9)
                self.assertLess(data['annual']['scenarios'][key(sigma)]['maximum_horizon_log_change'], 2e-5)

    def test_solver_dependencies_are_unchanged_from_migration(self):
        manifest = json.loads((ROOT/'PUBLICATION_MANIFEST.json').read_text())
        for item in manifest['files']:
            if item['path'].startswith('scripts/'):
                self.assertEqual(hashlib.sha256((ROOT/item['path']).read_bytes()).hexdigest(),
                                 item['source_sha256'], item['path'])

    def test_all_active_tex_inputs_and_graphics_are_present(self):
        seen = set()
        def visit(path):
            if path in seen:
                return
            seen.add(path)
            text = re.sub(r'(?<!\\)%[^\n]*', '', (ROOT/path).read_text(encoding='utf-8'))
            for name in re.findall(r'\\input\{([^}]+)\}', text):
                visit(name + '.tex')
            for name in re.findall(r'\\includegraphics(?:\[[^]]*\])?\{([^}]+)\}', text):
                self.assertTrue((ROOT/name).is_file(), name)
        visit('main_rewrite.tex')
        self.assertFalse((ROOT/'main_companion.tex').exists())
        self.assertFalse((ROOT/'main_axm.tex').exists())


if __name__ == '__main__':
    unittest.main()
