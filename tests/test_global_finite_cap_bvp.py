"""Tests for the global finite-cap coordinate system and equilibrium gates."""

from __future__ import annotations

import math
import sys
import unittest
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
LOCAL_DEPS = ROOT / ".python-packages"
TMP_DEPS = ROOT / "tmp" / "pydeps"
if TMP_DEPS.exists():
    sys.path.insert(0, str(TMP_DEPS))
elif LOCAL_DEPS.exists():
    sys.path.insert(0, str(LOCAL_DEPS))
sys.path.insert(0, str(ROOT / "scripts"))

from analyze_axm_finite_cap_bvp import (  # noqa: E402
    critical_capability_frontier,
    labor_supported_dynamics,
    solve_local_terminal_bvp,
    terminal_point,
)
from define_positive_ai_branch import (  # noqa: E402
    PositiveAIBenchmarkParameters,
    balanced_growth_seed,
)
from solve_axm_global_finite_cap_bvp import (  # noqa: E402
    _LocalRawSeed,
    _capability_logs,
    _developer_concavity_margin,
    dated_bounded_dynamics,
    initial_raw_coordinates,
    normalized_to_raw_coordinates,
    raw_to_terminal_coordinates,
)


class GlobalFiniteCapCoordinateTests(unittest.TestCase):
    """Verify exact mappings before running the expensive global continuation."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.parameters = PositiveAIBenchmarkParameters()
        cls.seed = balanced_growth_seed(cls.parameters)
        cls.sigma = 1.10
        cls.critical = critical_capability_frontier(
            cls.sigma, cls.parameters
        )
        cls.terminal = terminal_point(
            cls.sigma, 1e-6 * cls.critical, cls.parameters
        )

    def test_logit_mapping_keeps_capability_strictly_inside_frontier(self) -> None:
        for logit in (-100.0, -10.0, 0.0, 10.0, 100.0):
            log_capability, log_gap, log_psi = _capability_logs(
                logit, self.terminal.frontier
            )
            self.assertLessEqual(log_capability, math.log(self.terminal.frontier))
            self.assertLessEqual(log_gap, math.log(self.terminal.frontier))
            self.assertLessEqual(log_psi, 0.0)
            self.assertAlmostEqual(log_capability - log_gap, logit)

    def test_initial_raw_coordinates_recover_paper_stocks(self) -> None:
        raw = initial_raw_coordinates(
            self.terminal, self.seed.capital, self.seed.capability
        )
        self.assertAlmostEqual(math.exp(raw[0]), self.seed.capital)
        ratio = 1.0 / (1.0 + math.exp(-raw[1]))
        self.assertAlmostEqual(
            ratio * self.terminal.frontier, self.seed.capability
        )

    def test_local_normalized_path_maps_to_same_terminal_coordinates(self) -> None:
        deviations = np.asarray([0.01, -0.01, 1e-5])
        local = solve_local_terminal_bvp(
            self.terminal,
            self.parameters,
            deviations,
            horizon=200.0,
            nodes=81,
            tolerance=1e-8,
        )
        local_scale = (
            self.terminal.auxiliary["gap_scale"]
            / self.terminal.frontier
            / deviations[2]
        )
        time = 37.0
        normalized = np.asarray(local.raw.sol(time), dtype=float)
        raw = normalized_to_raw_coordinates(
            np.asarray([time]),
            normalized[:, None],
            self.terminal,
            self.parameters,
            local_scale,
        )[:, 0]
        recovered = raw_to_terminal_coordinates(
            time,
            raw,
            self.terminal,
            self.parameters,
            local_scale,
        )
        np.testing.assert_allclose(recovered, normalized, atol=2e-10, rtol=2e-10)

    def test_bounded_dynamics_are_the_exact_transformed_local_system(self) -> None:
        deviations = np.asarray([0.01, -0.01, 1e-5])
        local = solve_local_terminal_bvp(
            self.terminal,
            self.parameters,
            deviations,
            horizon=200.0,
            nodes=81,
            tolerance=1e-8,
        )
        local_scale = (
            self.terminal.auxiliary["gap_scale"]
            / self.terminal.frontier
            / deviations[2]
        )
        adapter = _LocalRawSeed(
            local.raw, self.terminal, self.parameters, local_scale
        )
        time = 25.0
        bounded = np.asarray(adapter.sol(time), dtype=float)
        exact = dated_bounded_dynamics(
            time,
            bounded,
            self.terminal,
            self.parameters,
            local_scale,
        )
        step = 1e-5
        numerical = (adapter.sol(time + step) - adapter.sol(time - step)) / (
            2.0 * step
        )
        np.testing.assert_allclose(exact, numerical, atol=2e-7, rtol=2e-6)

    def test_moderate_cap_initial_developer_gate_is_strict(self) -> None:
        margin, share, elasticity = _developer_concavity_margin(
            math.log(self.seed.capital),
            0.0,
            self.seed.capability,
            self.terminal,
            self.parameters,
        )
        self.assertGreater(margin, 0.5)
        self.assertTrue(0.0 < share < 1.0)
        self.assertGreater(elasticity, 0.0)


if __name__ == "__main__":
    unittest.main()
