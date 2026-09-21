"""Focused tests for the independent no-AI Ramsey solver."""

from __future__ import annotations

import math
import sys
import unittest
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / ".python-packages"))
sys.path.insert(0, str(ROOT / "scripts"))

from solve_rck_no_ai_bvp import (  # noqa: E402
    RCKParameters,
    audit_solution,
    log_dynamics,
    solve_transition,
    stable_log_direction,
    steady_state,
)


class RCKNoAIBVPSolverTests(unittest.TestCase):
    """Check economics, numerical residuals, and independent agreement."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.parameters = RCKParameters()
        cls.equilibrium = steady_state(cls.parameters)

    def test_balanced_growth_values_satisfy_the_detrended_system(self) -> None:
        logs = np.asarray(
            [
                [math.log(self.equilibrium.capital)],
                [math.log(self.equilibrium.consumption)],
            ]
        )
        residual = log_dynamics(
            np.asarray([0.0]), logs, self.parameters
        )
        self.assertLess(float(np.max(np.abs(residual))), 1e-13)
        self.assertAlmostEqual(
            self.equilibrium.net_interest_rate,
            self.parameters.discount
            + self.parameters.labor_productivity_growth,
        )

        stable_eigenvalue, stable_slope = stable_log_direction(
            self.parameters, self.equilibrium
        )
        self.assertLess(stable_eigenvalue, 0.0)
        self.assertGreater(stable_slope, 0.0)

    def test_off_bgp_paths_pass_residual_and_backward_checks(self) -> None:
        for ratio in (0.7, 1.3):
            with self.subTest(initial_capital_ratio=ratio):
                solution = solve_transition(
                    self.parameters,
                    ratio * self.equilibrium.capital,
                    horizon=250.0,
                    continuation_steps=6,
                    initial_nodes=81,
                    tolerance=1e-8,
                )
                audit = audit_solution(solution)
                self.assertTrue(audit["success"])
                self.assertLess(audit["max_log_ode_residual"], 2e-7)
                self.assertLess(audit["max_capital_equation_residual"], 2e-7)
                self.assertLess(audit["max_euler_equation_residual"], 2e-7)
                self.assertLess(audit["boundary_residual"], 1e-9)
                self.assertLess(
                    audit["backward_initial_consumption_relative_gap"], 1e-8
                )

    def test_initial_consumption_is_stable_across_terminal_horizons(self) -> None:
        initial_capital = 0.7 * self.equilibrium.capital
        shorter = solve_transition(
            self.parameters,
            initial_capital,
            horizon=150.0,
            continuation_steps=5,
            initial_nodes=61,
            tolerance=1e-7,
        )
        longer = solve_transition(
            self.parameters,
            initial_capital,
            horizon=250.0,
            continuation_steps=5,
            initial_nodes=61,
            tolerance=1e-7,
        )
        relative_gap = abs(
            shorter.initial_consumption / longer.initial_consumption - 1.0
        )
        self.assertLess(relative_gap, 1e-8)


if __name__ == "__main__":
    unittest.main()
