"""Independent static identities and saved-path checks for Corollary 1."""
import csv
import hashlib
import json
import math
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'.python-packages'),str(ROOT/'scripts')]
import numpy as np
from simulate_monopoly_growth_reversal import make_design
from solve_competitive_ai_transition import static_block, limiting_return


class CompetitiveTransitionIdentities(unittest.TestCase):
    def test_competitive_static_choice_and_envelope(self):
        d=make_design(7.5); p=d.parameters; B=d.initial_capability; sigma=1.5
        phi=(sigma-1)/sigma
        for log_k in (0.,5.,10.,20.):
            with self.subTest(log_k=log_k):
                a=static_block(log_k,B,sigma,p)
                k,x=math.exp(log_k),math.exp(a['log_x'])
                z=(p.omega_l+p.omega_x*x**phi)**(1/phi)
                y=k**p.alpha*z**(1-p.alpha)
                fx=(1-p.alpha)*k**p.alpha*z**(1-p.alpha-phi)*p.omega_x*x**(phi-1)
                self.assertAlmostEqual(math.log(y),float(a['log_y']),places=11)
                self.assertAlmostEqual(fx*B,1.,places=11)
                h=1e-4
                up,down=[static_block(log_k+s*h,B,sigma,p) for s in (1,-1)]
                fp=(math.exp(log_k+h)*up['net_over_k']-math.exp(log_k-h)*down['net_over_k'])/(k*(math.exp(h)-math.exp(-h)))
                self.assertAlmostEqual(float(fp),p.alpha*y/k,places=7)
                self.assertLess(float(a['y_log_gradient']),1.)
                self.assertGreater(float(a['y_log_gradient']),p.alpha)
                self.assertAlmostEqual(float((up['log_y']-down['log_y'])/(2*h)),float(a['y_log_gradient']),places=8)
                self.assertAlmostEqual(float((up['log_w']-down['log_w'])/(2*h)),float(a['w_log_gradient']),places=8)

    def test_same_initial_stocks_and_threshold_region(self):
        high,low=make_design(7.5),make_design(1.5)
        self.assertEqual(high.initial_capital,low.initial_capital)
        self.assertEqual(high.initial_capability,low.initial_capability)
        self.assertEqual(high.frontier,low.frontier)
        bmon=high.frontier/.9
        self.assertLess((1-high.parameters.alpha)*bmon,high.initial_capability)
        self.assertLess(high.initial_capability,high.frontier)
        self.assertLess(high.frontier,bmon)
        self.assertGreater(limiting_return(high.initial_capability,1.5,high.parameters),
                           high.parameters.discount+high.parameters.labor_productivity_growth)

    def test_saved_paths_admitted_and_unchanged(self):
        directory=ROOT/'numerical_rewrite'/'monopoly_growth_reversal'
        summary=json.loads((directory/'summary.json').read_text())
        manifest=json.loads((directory/'figure_manifest.json').read_text())
        self.assertTrue(summary['competitive_audit']['passes'])
        for filename,digest in manifest['files_sha256'].items():
            self.assertNotIn('\\',filename, 'Manifest paths must also work on Linux.')
            self.assertEqual(hashlib.sha256((ROOT/filename).read_bytes()).hexdigest(),digest)
        for chi in (7.5,1.5):
            d=make_design(chi)
            report=json.loads((d.output_directory/'sigma_1_50_audit.json').read_text())
            self.assertTrue(report['equilibrium_certified'])
            self.assertTrue(report['early_window_checks']['passes'])
            self.assertEqual(hashlib.sha256((d.output_directory/'equilibrium_paths.csv').read_bytes()).hexdigest(),
                             manifest['monopoly_input_csv_sha256'][str(chi)])
        self.assertAlmostEqual(summary['monopoly_limits']['output_per_person_growth'],.01)
        self.assertGreater(summary['competitive_limits']['output_per_person_growth'],.01)
        with (directory/'comparison_paths.csv').open(newline='') as f:
            data=list(csv.DictReader(f))
        for name in ('Competition','Monopoly, chi = 7.5','Monopoly, chi = 1.5'):
            series=[{k:float(v) for k,v in r.items() if k!='scenario'} for r in data if r['scenario']==name]
            self.assertEqual(series[0]['time'],0.)
            self.assertEqual(series[-1]['time'],500.)
            self.assertTrue(all(np.isfinite(v) for r in series for v in r.values()))
            self.assertTrue(all(a['time']<b['time'] for a,b in zip(series,series[1:])))
            if name!='Competition':
                self.assertLess(series[0]['output_counterfactual_ratio'],1.)
                self.assertLess(series[0]['ai_services_counterfactual_ratio'],1.)
                self.assertGreater(series[-1]['capability_frontier_ratio'],series[0]['capability_frontier_ratio'])


if __name__=='__main__':
    unittest.main()
