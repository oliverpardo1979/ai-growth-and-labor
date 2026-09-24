"""Independent checks for the competitive-to-monopoly experiment."""
import math
from pathlib import Path
import sys
import unittest
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
from simulate_competitive_to_monopoly import make_design, SIGMAS
from competitive_ai_bgp import competitive_fixed_efficiency_bgp
from simulate_rewrite_finite_frontier import design_initial_stocks
from solve_near_unit_ai_bvp import solve_monopoly_static_block


class CompetitiveInitialConditions(unittest.TestCase):
    def test_all_eight_bgps_and_event_static_direction(self):
        for chi in (7.5,1.5):
            d = make_design(chi)
            p = d.parameters
            for sigma in SIGMAS:
                with self.subTest(chi=chi, sigma=sigma):
                    v = competitive_fixed_efficiency_bgp(sigma, d.initial_capability, p)
                    x, k, y = v['ai_services'], v['capital'], v['output']
                    power = (sigma-1)/sigma
                    z = x**p.omega_x if sigma == 1 else (p.omega_l+p.omega_x*x**power)**(1/power)
                    self.assertAlmostEqual(y, k**p.alpha*z**(1-p.alpha), places=10)
                    self.assertAlmostEqual(v['capital_output_ratio'], 3.3, places=10)
                    self.assertAlmostEqual(v['ai_service_price']*x, v['inference_compute'], places=10)
                    self.assertAlmostEqual(y-v['consumption']-v['inference_compute']-p.depreciation*k,
                                           (p.population_growth+p.labor_productivity_growth)*k, places=10)
                    self.assertGreater(v['consumption'], 0)
                    self.assertTrue(v['pre_event_research_available'])
                    self.assertEqual(v['research_compute'], 0)
                    self.assertEqual(design_initial_stocks(d,sigma), (k,d.initial_capability))
                    monopoly = solve_monopoly_static_block(math.log(k), math.log(d.initial_capability), 0., sigma,p)
                    self.assertLess(math.exp(monopoly.log_output), y)
                    self.assertLess(math.exp(monopoly.log_ai_services), x)
                    monopoly_wage=(1-p.alpha)*(1-monopoly.ai_ces_share)*math.exp(monopoly.log_output)
                    self.assertLess(monopoly_wage,v['wage'])

    def test_chi_does_not_change_competitive_reference(self):
        high, low = make_design(7.5), make_design(1.5)
        for sigma in SIGMAS:
            self.assertEqual(design_initial_stocks(high,sigma), design_initial_stocks(low,sigma))

    def test_no_labor_bgp_above_substitute_threshold(self):
        d=make_design(7.5)
        with self.assertRaises(ValueError):
            competitive_fixed_efficiency_bgp(1.5, d.frontier, d.parameters)


if __name__ == '__main__':
    unittest.main()
