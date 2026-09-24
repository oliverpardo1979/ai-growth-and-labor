"""Inherited stocks, time-origin invariance, and revised-experiment admission."""
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
from simulate_monopoly_growth_reversal_burnin import make_design, OUT, RATE_TOLERANCE
from solve_competitive_ai_transition import solve, rows, static_block


def read(name):
    return json.loads((OUT/name).read_text())


class CompetitivePrehistory(unittest.TestCase):
    def test_selection_and_all_inherited_stocks(self):
        init=read('initialization.json'); stocks=init['stocks']; p=init['seed_parameters']
        t=init['burnin_years']
        self.assertEqual(t,190)
        self.assertLess(init['selection_rate_error'],RATE_TOLERANCE)
        self.assertGreaterEqual(init['previous_year_rate_error'],RATE_TOLERANCE)
        self.assertAlmostEqual(stocks['A0'],p['initial_labor_productivity']*math.exp(p['labor_productivity_growth']*t))
        self.assertAlmostEqual(stocks['N0'],p['initial_population']*math.exp(p['population_growth']*t))
        self.assertAlmostEqual(stocks['K0']/(stocks['A0']*stocks['N0'])/init['pre_event']['capital_effective_labor'],1.,places=12)
        high,low=make_design(7.5),make_design(1.5)
        self.assertEqual(high.initial_capital,low.initial_capital)
        self.assertEqual(high.initial_capability,low.initial_capability)
        self.assertEqual(high.parameters.initial_population,low.parameters.initial_population)
        self.assertEqual(high.parameters.initial_labor_productivity,low.parameters.initial_labor_productivity)
        for d in (high,low):
            self.assertEqual(d.initial_capital,stocks['K0'])
            self.assertAlmostEqual(d.initial_capability,stocks['B0'])
        self.assertEqual(high.parameters.chi,7.5)
        self.assertEqual(low.parameters.chi,1.5)

    def test_rebased_solution_starts_at_physical_capital(self):
        d=make_design(7.5)
        path=solve(d.initial_capability,1.5,d.parameters,d.initial_capital)
        r=rows(path,np.array([0.]))[0]
        scale=d.parameters.initial_labor_productivity*d.parameters.initial_population
        self.assertAlmostEqual(r['capital_effective_labor']*scale/d.initial_capital,1.,places=12)
        init=read('initialization.json')
        for field in ('capital_effective_labor','output_effective_labor','consumption_effective_labor','wage_productivity'):
            self.assertLess(abs(math.log(r[field]/init['pre_event'][field])),2e-7)
        self.assertLess(init['maximum_rebase_log_error'],2e-7)
        # Independently reconstruct CES output and competitive marginal cost
        # at the new large inherited capital/effective-labor ratio.
        k=r['capital_effective_labor']; x=r['ai_services_effective_labor']
        p=d.parameters; phi=1/3
        z=(p.omega_l+p.omega_x*x**phi)**(1/phi)
        y=k**p.alpha*z**(1-p.alpha)
        fx=(1-p.alpha)*k**p.alpha*z**(1-p.alpha-phi)*p.omega_x*x**(phi-1)
        self.assertAlmostEqual(y/r['output_effective_labor'],1.,places=10)
        self.assertAlmostEqual(fx*d.initial_capability,1.,places=10)

    def test_admission_continuity_provenance_and_windows(self):
        manifest=read('figure_manifest.json'); summary=read('summary.json')
        self.assertTrue(summary['competitive_audit']['passes'])
        for f,h in manifest['files_sha256'].items():
            self.assertNotIn('\\',f)
            self.assertEqual(hashlib.sha256((ROOT/f).read_bytes()).hexdigest(),h)
        for chi in (7.5,1.5):
            d=make_design(chi)
            a=json.loads((d.output_directory/'sigma_1_50_audit.json').read_text())
            self.assertTrue(a['equilibrium_certified'])
            self.assertTrue(a['early_window_checks']['passes'])
            self.assertEqual(hashlib.sha256((d.output_directory/'equilibrium_paths.csv').read_bytes()).hexdigest(),manifest['monopoly_input_csv_sha256'][str(chi)])
            initial=summary['observations'][f'Monopoly, chi = {chi}']['0']
            scale=d.parameters.initial_labor_productivity*d.parameters.initial_population
            self.assertAlmostEqual(initial['capital_effective_labor']*scale/d.initial_capital,1.,places=10)
            self.assertAlmostEqual(initial['capability']/d.initial_capability,1.,places=10)
            self.assertLess(initial['output_counterfactual_ratio'],1.)
        with (OUT/'competitive_prehistory.csv').open(newline='') as f:
            pre=[{k:float(v) for k,v in r.items()} for r in csv.DictReader(f)]
        self.assertEqual(pre[0]['time'],-10.)
        self.assertEqual(pre[-1]['time'],0.)
        post=summary['observations']['Competition']['0']
        for field in ('output_per_person_growth','wage_growth','net_interest','labor_income_share'):
            self.assertAlmostEqual(pre[-1][field],post[field],places=9)
        with (OUT/'comparison_paths.csv').open(newline='') as f:
            data=list(csv.DictReader(f))
        for name in summary['observations']:
            points=[r for r in data if r['scenario']==name]
            times=[float(r['time']) for r in points]
            self.assertEqual(times[0],0.)
            self.assertEqual(times[-1],500.)
            self.assertTrue(all(a<b for a,b in zip(times,times[1:])))
            self.assertTrue(all(math.isfinite(float(v)) for r in points for k,v in r.items() if k!='scenario'))


if __name__=='__main__':
    unittest.main()
