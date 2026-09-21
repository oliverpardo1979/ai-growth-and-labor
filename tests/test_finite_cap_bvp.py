"""Tests for the finite-cap terminal systems and their local BVPs."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
LOCAL_DEPS = ROOT / ".python-packages"
TMP_DEPS = ROOT / "tmp" / "pydeps"
if LOCAL_DEPS.exists():
    sys.path.insert(0, str(LOCAL_DEPS))
elif TMP_DEPS.exists():
    sys.path.insert(0, str(TMP_DEPS))
sys.path.insert(0, str(ROOT / "scripts"))

from analyze_axm_finite_cap_bvp import (  # noqa: E402
    ai_dominated_dynamics,
    ai_dominated_jacobian,
    critical_capability_frontier,
    labor_supported_dynamics,
    labor_supported_jacobian,
    solve_local_terminal_bvp,
    terminal_linearization,
    terminal_point,
    terminal_residual,
)
from define_positive_ai_branch import (  # noqa: E402
    PositiveAIBenchmarkParameters,
)


class FiniteCapBVPTests(unittest.TestCase):
    """Verify the threshold, terminal systems, and local saddle selection."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.parameters = PositiveAIBenchmarkParameters()
        cls.sigma = 1.10
        cls.critical = critical_capability_frontier(
            cls.sigma, cls.parameters
        )
        cls.subcritical = terminal_point(
            cls.sigma, 0.5 * cls.critical, cls.parameters
        )
        cls.supercritical = terminal_point(
            cls.sigma, 2.0 * cls.critical, cls.parameters
        )

    def test_critical_frontier_values_and_near_unit_growth(self) -> None:
        expected = {
            1.01: 4.8801522316e70,
            1.05: 5.8997430365e14,
            1.10: 6.0413358454e7,
            1.50: 1.5465820e2,
            2.00: 3.09316395e1,
        }
        values = []
        for sigma, target in expected.items():
            actual = critical_capability_frontier(sigma, self.parameters)
            self.assertLess(abs(actual / target - 1.0), 3e-7)
            values.append(actual)
        self.assertTrue(all(np.diff(values) < 0.0))

    def test_threshold_selects_distinct_terminal_regimes(self) -> None:
        self.assertEqual(self.subcritical.regime, "labor_supported")
        self.assertEqual(self.supercritical.regime, "ai_dominated")
        self.assertGreater(self.subcritical.labor_income_share, 0.0)
        self.assertEqual(self.supercritical.labor_income_share, 0.0)
        self.assertAlmostEqual(
            self.subcritical.terminal_growth,
            self.parameters.population_growth
            + self.parameters.labor_productivity_growth,
        )
        self.assertGreater(
            self.supercritical.terminal_growth,
            self.subcritical.terminal_growth,
        )

    def test_terminal_points_satisfy_exact_normalized_systems(self) -> None:
        for terminal in (self.subcritical, self.supercritical):
            with self.subTest(regime=terminal.regime):
                self.assertLess(
                    float(np.max(np.abs(terminal_residual(
                        terminal, self.parameters
                    )))),
                    3e-11,
                )

    def test_analytic_jacobians_match_finite_differences(self) -> None:
        cases = (
            (
                self.subcritical,
                labor_supported_dynamics,
                labor_supported_jacobian,
            ),
            (
                self.supercritical,
                ai_dominated_dynamics,
                ai_dominated_jacobian,
            ),
        )
        step = 2e-6
        for terminal, dynamics, jacobian_function in cases:
            with self.subTest(regime=terminal.regime):
                analytic = jacobian_function(terminal, self.parameters)
                numerical = np.empty((5, 5))
                origin = terminal.coordinates
                for column in range(5):
                    change = np.zeros(5)
                    column_step = (
                        2e-8
                        if terminal.regime == "ai_dominated" and column == 0
                        else step
                    )
                    change[column] = column_step
                    if terminal.regime == "ai_dominated" and column == 0:
                        numerical[:, column] = (
                            dynamics(
                                origin + change, terminal, self.parameters
                            )
                            - dynamics(origin, terminal, self.parameters)
                        ) / column_step
                    else:
                        numerical[:, column] = (
                            dynamics(
                                origin + change, terminal, self.parameters
                            )
                            - dynamics(
                                origin - change, terminal, self.parameters
                            )
                        ) / (2.0 * column_step)
                np.testing.assert_allclose(
                    analytic, numerical, atol=3e-7, rtol=3e-6
                )

    def test_each_regime_has_three_stable_and_two_unstable_roots(self) -> None:
        for terminal in (self.subcritical, self.supercritical):
            with self.subTest(regime=terminal.regime):
                linearization = terminal_linearization(
                    terminal, self.parameters
                )
                self.assertEqual(linearization.stable_eigenvalues.size, 3)
                self.assertEqual(linearization.unstable_eigenvalues.size, 2)
                self.assertTrue(
                    np.all(linearization.stable_eigenvalues < 0.0)
                )
                self.assertTrue(
                    np.all(linearization.unstable_eigenvalues > 0.0)
                )
                self.assertLess(
                    float(np.max(np.abs(
                        linearization.terminal_matrix
                        @ linearization.stable_basis
                    ))),
                    2e-14,
                )
                self.assertTrue(
                    np.isfinite(
                        linearization.state_projection_condition_number
                    )
                )

    def test_local_nonlinear_bvp_converges_in_both_regimes(self) -> None:
        deviations = {
            "labor_supported": np.asarray([0.01, -0.01, 1e-5]),
            "ai_dominated": np.asarray([1e-5, -0.01, 1e-5]),
        }
        for terminal in (self.subcritical, self.supercritical):
            with self.subTest(regime=terminal.regime):
                solution = solve_local_terminal_bvp(
                    terminal,
                    self.parameters,
                    deviations[terminal.regime],
                    horizon=300.0,
                    nodes=121,
                    tolerance=1e-8,
                )
                self.assertTrue(solution.raw.success)
                self.assertLess(
                    float(np.max(solution.raw.rms_residuals)), 3e-8
                )
                self.assertLess(solution.maximum_boundary_residual, 2e-9)


if __name__ == "__main__":
    unittest.main()
