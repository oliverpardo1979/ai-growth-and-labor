"""Checks of stored evidence for all eight new simulations, without re-solving."""
import csv
import hashlib
import json
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


class CompetitiveTransitionResults(unittest.TestCase):
    def test_eight_paths_have_full_admission_and_unaltered_tolerances(self):
        for chi in ('7_5','1_5'):
            folder=ROOT/'numerical_rewrite'/f'competitive_to_monopoly_chi_{chi}'
            manifest=read(folder/'paths_manifest.json')
            self.assertEqual(manifest['csv_sha256'],hashlib.sha256((folder/'equilibrium_paths.csv').read_bytes()).hexdigest())
            for sigma in ('0_90','1_00','1_10','1_50'):
                report=read(folder/f'sigma_{sigma}_audit.json')
                with self.subTest(chi=chi,sigma=sigma):
                    self.assertTrue(report['equilibrium_certified'])
                    self.assertTrue(report['early_window_checks']['passes'])
                    self.assertEqual(report['checkpoint_sha256'],manifest['checkpoint_sha256'][f'sigma_{sigma}'])
                    self.assertLess(report['maximum_terminal_coordinate_gap'],1e-4)
                    for gap in ('maximum_initial_jump_change','maximum_common_window_coordinate_change'):
                        self.assertLess(report['horizon_comparison'][gap],2e-5)
                    for check in report['independent_dated_checks']+report['early_window_checks']['independent_residuals']:
                        self.assertLess(check['maximum_ode_residual'],1e-6)
                        self.assertLess(check['maximum_research_foc_residual'],1e-9)
                        self.assertLess(check['maximum_monopoly_foc_residual'],1e-9)
                    self.assertLess(report['audit']['asymptotic_household_tvc_growth'],0)
                    self.assertLess(report['audit']['asymptotic_developer_tvc_growth'],0)
                    if sigma=='1_50':
                        self.assertTrue(all(s['support_diagnostic_passes'] for s in report['global_hamiltonian_support']))
                        self.assertGreater(report['analytical_support_continuation']['terminal_margin'],0)
                    else:
                        self.assertTrue(report['counterfactual_developer_sufficiency']['developer_sufficiency_gate_passes'])

    def test_same_stocks_and_static_jumps_for_both_chis(self):
        high=ROOT/'numerical_rewrite'/'competitive_to_monopoly_chi_7_5'
        low=ROOT/'numerical_rewrite'/'competitive_to_monopoly_chi_1_5'
        self.assertEqual(read(high/'competitive_reference.json'),read(low/'competitive_reference.json'))
        h,l=read(high/'scenario.json'),read(low/'scenario.json')
        self.assertEqual(h['parameters'].pop('chi'),7.5)
        self.assertEqual(l['parameters'].pop('chi'),1.5)
        self.assertEqual(h['parameters'],l['parameters'])
        high_jump,low_jump=read(high/'policy_event.json')['jumps'],read(low/'policy_event.json')['jumps']
        for sigma in high_jump:
            for field in ('output','wage','ai_service_price','ai_services','interest_rate_pp'):
                self.assertAlmostEqual(high_jump[sigma][field],low_jump[sigma][field],places=10)

    def test_comparison_ratios_use_competitive_not_old_monopoly_reference(self):
        for chi in ('7_5','1_5'):
            folder=ROOT/'numerical_rewrite'/f'competitive_to_monopoly_chi_{chi}'
            pre={v['sigma']:v for v in read(folder/'competitive_reference.json').values()}
            with (folder/'comparison_paths.csv').open(newline='') as stream:
                comparison={(float(r['sigma']),float(r['time'])):r for r in csv.DictReader(stream)}
            with (folder/'equilibrium_paths.csv').open(newline='') as stream:
                for row in csv.DictReader(stream):
                    sigma,time=float(row['sigma']),float(row['time'])
                    comp=comparison[(sigma,time)]
                    for ratio,field,base in (
                        ('output_counterfactual_ratio','output_effective_labor','output'),
                        ('wage_counterfactual_ratio','wage_productivity','wage'),
                        ('consumption_counterfactual_ratio','consumption_effective_labor','consumption')):
                        self.assertAlmostEqual(float(comp[ratio])/(float(row[field])/pre[sigma][base]),1,places=12)


if __name__=='__main__':
    unittest.main()
