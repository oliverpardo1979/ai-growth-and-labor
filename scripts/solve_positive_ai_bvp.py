"""Solve positive-AI transitions away from the analytic balanced-growth path.

The solver applies only to the automated-research benchmark with
``sigma_XL = 1`` and a strictly positive ``omega_X``.  It starts from the
exact balanced-growth equilibrium constructed in ``define_positive_ai_branch``
and continues the two predetermined initial stocks ``(K_0, B_0)`` to their
requested values.  At every continuation stage, SciPy's collocation solver
selects the two jump variables ``(C_0, q_0)`` so that the terminal point has no
unstable component.

This module never continues through ``omega_X = 0``.  The no-AI economy has a
different state dimension and is solved by ``solve_rck_no_ai_bvp.py``.
Running this file prints diagnostics and does not write paper artifacts.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
LOCAL_DEPS = ROOT / ".python-packages"
TMP_DEPS = ROOT / "tmp" / "pydeps"
if LOCAL_DEPS.exists():
    sys.path.insert(0, str(LOCAL_DEPS))
elif TMP_DEPS.exists():
    sys.path.insert(0, str(TMP_DEPS))
sys.path.insert(0, str(ROOT / "scripts"))

from scipy.integrate import solve_bvp, solve_ivp  # noqa: E402
from scipy.linalg import expm  # noqa: E402

from define_positive_ai_branch import (  # noqa: E402
    PositiveAIBalancedGrowth,
    PositiveAIBenchmarkParameters,
    PositiveAIInitialStocks,
    StableSubspace,
    balanced_growth_seed,
    boundary_jacobians,
    boundary_residual,
    initial_stocks_matching_bgp_capital_output_ratio,
    normalized_dynamics,
    normalized_jacobian,
    stable_subspace,
    state_continuation_schedule,
)


@dataclass(frozen=True)
class ContinuationStage:
    """One accepted stock- or horizon-continuation solve."""

    kind: str
    horizon: float
    initial_capital_deviation: float
    initial_capability_deviation: float
    initial_consumption_deviation: float
    initial_shadow_value_deviation: float
    iterations: int
    nodes: int
    maximum_rms_residual: float


@dataclass
class PositiveAITransitionSolution:
    """A collocation solution and the objects needed to audit it."""

    raw: Any
    parameters: PositiveAIBenchmarkParameters
    seed: PositiveAIBalancedGrowth
    subspace: StableSubspace
    initial_stocks: PositiveAIInitialStocks
    horizon: float
    stock_schedule: tuple[np.ndarray, ...]
    horizon_schedule: tuple[float, ...]
    stages: tuple[ContinuationStage, ...]

    @property
    def initial_deviations(self) -> np.ndarray:
        """Return the four stationary log deviations at date zero."""

        return np.asarray(self.raw.sol(0.0), dtype=float)

    @property
    def initial_consumption(self) -> float:
        return float(
            self.seed.consumption * math.exp(self.initial_deviations[2])
        )

    @property
    def initial_shadow_value(self) -> float:
        return float(
            self.seed.shadow_value * math.exp(self.initial_deviations[3])
        )

    def evaluate_deviations(
        self, times: np.ndarray | float
    ) -> np.ndarray:
        return np.asarray(self.raw.sol(times), dtype=float)


def _validate_horizons(horizons: tuple[float, ...]) -> tuple[float, ...]:
    if not horizons:
        raise ValueError("At least one terminal horizon is required.")
    values = tuple(float(value) for value in horizons)
    if any(value <= 0.0 for value in values):
        raise ValueError("Every terminal horizon must be strictly positive.")
    if any(right <= left for left, right in zip(values, values[1:])):
        raise ValueError("Terminal horizons must be strictly increasing.")
    return values


def subdivide_horizon_schedule(
    horizons: tuple[float, ...],
) -> tuple[float, ...]:
    """Insert continuation horizons so no step exceeds the first horizon.

    Extending a finite-horizon solution with the BGP linearization is a local
    predictor.  A very large horizon jump can extrapolate that predictor far
    outside its useful range and overflow the exponential terms before the
    collocation corrector can recover.  The first solved horizon provides a
    conservative, scale-aware maximum continuation step.
    """

    values = _validate_horizons(horizons)
    maximum_step = values[0]
    expanded = [values[0]]
    for target in values[1:]:
        start = expanded[-1]
        step_count = max(1, int(math.ceil((target - start) / maximum_step)))
        increment = (target - start) / step_count
        expanded.extend(
            start + increment * step
            for step in range(1, step_count + 1)
        )
    return tuple(float(value) for value in expanded)


def _linear_stable_correction(
    mesh: np.ndarray,
    state_deviation: np.ndarray,
    jacobian: np.ndarray,
    subspace: StableSubspace,
) -> np.ndarray:
    """Return a linear stable-path guess with requested initial states."""

    state = np.asarray(state_deviation, dtype=float)
    if state.shape != (2,):
        raise ValueError("The initial state deviation must have shape (2,).")
    state_block = subspace.stable_basis[[0, 1], :]
    coefficients = np.linalg.solve(state_block, state)
    initial = subspace.stable_basis @ coefficients
    return np.column_stack(
        [expm(jacobian * float(time)) @ initial for time in mesh]
    )


def _extend_guess(
    previous: Any,
    old_horizon: float,
    new_mesh: np.ndarray,
    jacobian: np.ndarray,
) -> np.ndarray:
    """Extend an accepted solution with its linear stable tail."""

    values = np.empty((4, new_mesh.size))
    old_terminal = np.asarray(previous.sol(old_horizon), dtype=float)
    for index, time in enumerate(new_mesh):
        if time <= old_horizon:
            values[:, index] = previous.sol(float(time))
        else:
            values[:, index] = (
                expm(jacobian * float(time - old_horizon)) @ old_terminal
            )
    return values


def _stage_record(
    kind: str,
    horizon: float,
    target_states: np.ndarray,
    result: Any,
) -> ContinuationStage:
    initial = np.asarray(result.sol(0.0), dtype=float)
    rms = np.asarray(getattr(result, "rms_residuals", [math.nan]))
    maximum_rms = float(np.nanmax(rms)) if rms.size else math.nan
    return ContinuationStage(
        kind=kind,
        horizon=float(horizon),
        initial_capital_deviation=float(target_states[0]),
        initial_capability_deviation=float(target_states[1]),
        initial_consumption_deviation=float(initial[2]),
        initial_shadow_value_deviation=float(initial[3]),
        iterations=int(result.niter),
        nodes=int(result.x.size),
        maximum_rms_residual=maximum_rms,
    )


def solve_transition(
    parameters: PositiveAIBenchmarkParameters,
    initial_capital: float,
    initial_capability: float,
    *,
    horizons: tuple[float, ...] = (100.0, 150.0, 200.0, 250.0),
    continuation_steps: int = 10,
    initial_nodes: int = 121,
    tolerance: float = 1e-8,
    boundary_tolerance: float = 1e-10,
    maximum_nodes: int = 20_000,
) -> PositiveAITransitionSolution:
    """Solve a transition from off-BGP predetermined stocks.

    The first continuation holds the shortest horizon fixed and moves the
    initial state from the exact BGP to ``(initial_capital,
    initial_capability)``.  The second continuation lengthens the horizon while
    preserving those initial stocks.  The terminal conditions eliminate the
    two unstable components of the normalized four-dimensional system.
    """

    if initial_capital <= 0.0 or initial_capability <= 0.0:
        raise ValueError("Initial capital and capability must be positive.")
    if continuation_steps < 1:
        raise ValueError("continuation_steps must be at least one.")
    if initial_nodes < 9:
        raise ValueError("initial_nodes must be at least nine.")
    if tolerance <= 0.0 or boundary_tolerance <= 0.0:
        raise ValueError("Solver tolerances must be strictly positive.")

    horizon_values = subdivide_horizon_schedule(horizons)
    seed = balanced_growth_seed(parameters)
    subspace = stable_subspace(parameters, seed)
    jacobian = normalized_jacobian(np.zeros(4), parameters, seed)
    target_states = np.asarray(
        [
            math.log(initial_capital / seed.capital),
            math.log(initial_capability / seed.capability),
        ]
    )
    schedule = state_continuation_schedule(
        target_states, continuation_steps
    )
    first_horizon = horizon_values[0]
    mesh = np.linspace(0.0, first_horizon, initial_nodes)
    guess = np.zeros((4, mesh.size))
    previous_state = np.zeros(2)
    result: Any | None = None
    records: list[ContinuationStage] = []

    def ode(times: np.ndarray, states: np.ndarray) -> np.ndarray:
        del times
        return normalized_dynamics(states, parameters, seed)

    def ode_jacobian(
        times: np.ndarray, states: np.ndarray
    ) -> np.ndarray:
        del times
        return normalized_jacobian(states, parameters, seed)

    derivative_left, derivative_right = boundary_jacobians(subspace)

    for stage_index, stage_states in enumerate(schedule[1:], start=1):
        delta = np.asarray(stage_states) - previous_state
        if result is not None:
            mesh = np.asarray(result.x)
            guess = np.asarray(result.y)
        guess = guess + _linear_stable_correction(
            mesh, delta, jacobian, subspace
        )

        def boundary(left: np.ndarray, right: np.ndarray) -> np.ndarray:
            return boundary_residual(
                left, right, np.asarray(stage_states), subspace
            )

        def boundary_jacobian(
            left: np.ndarray, right: np.ndarray
        ) -> tuple[np.ndarray, np.ndarray]:
            del left, right
            return derivative_left, derivative_right

        result = solve_bvp(
            ode,
            boundary,
            mesh,
            guess,
            fun_jac=ode_jacobian,
            bc_jac=boundary_jacobian,
            tol=tolerance,
            bc_tol=boundary_tolerance,
            max_nodes=maximum_nodes,
            verbose=0,
        )
        if not result.success:
            raise RuntimeError(
                "Positive-AI stock continuation failed at stage "
                f"{stage_index}/{continuation_steps}: {result.message}"
            )
        records.append(
            _stage_record(
                "stocks", first_horizon, np.asarray(stage_states), result
            )
        )
        previous_state = np.asarray(stage_states).copy()

    if result is None:
        # The exact BGP is also a valid solve and keeps the public function
        # defined when the requested stocks coincide with the seed.
        zero_states = np.zeros(2)

        def zero_boundary(left: np.ndarray, right: np.ndarray) -> np.ndarray:
            return boundary_residual(left, right, zero_states, subspace)

        def zero_boundary_jacobian(
            left: np.ndarray, right: np.ndarray
        ) -> tuple[np.ndarray, np.ndarray]:
            del left, right
            return derivative_left, derivative_right

        result = solve_bvp(
            ode,
            zero_boundary,
            mesh,
            guess,
            fun_jac=ode_jacobian,
            bc_jac=zero_boundary_jacobian,
            tol=tolerance,
            bc_tol=boundary_tolerance,
            max_nodes=maximum_nodes,
            verbose=0,
        )
        if not result.success:
            raise RuntimeError(f"Exact BGP solve failed: {result.message}")
        records.append(
            _stage_record("stocks", first_horizon, zero_states, result)
        )

    old_horizon = first_horizon
    for new_horizon in horizon_values[1:]:
        tail_nodes = max(
            21,
            int(math.ceil(initial_nodes * (new_horizon - old_horizon)
                          / first_horizon)),
        )
        tail = np.linspace(old_horizon, new_horizon, tail_nodes + 1)[1:]
        new_mesh = np.unique(np.concatenate((np.asarray(result.x), tail)))
        new_guess = _extend_guess(
            result, old_horizon, new_mesh, jacobian
        )

        def target_boundary(left: np.ndarray, right: np.ndarray) -> np.ndarray:
            return boundary_residual(left, right, target_states, subspace)

        def target_boundary_jacobian(
            left: np.ndarray, right: np.ndarray
        ) -> tuple[np.ndarray, np.ndarray]:
            del left, right
            return derivative_left, derivative_right

        result = solve_bvp(
            ode,
            target_boundary,
            new_mesh,
            new_guess,
            fun_jac=ode_jacobian,
            bc_jac=target_boundary_jacobian,
            tol=tolerance,
            bc_tol=boundary_tolerance,
            max_nodes=maximum_nodes,
            verbose=0,
        )
        if not result.success:
            raise RuntimeError(
                f"Positive-AI horizon continuation failed at T={new_horizon:g}: "
                f"{result.message}"
            )
        records.append(
            _stage_record("horizon", new_horizon, target_states, result)
        )
        old_horizon = new_horizon

    a_k = parameters.alpha / (1.0 - seed.beta)
    a_b = seed.beta / (1.0 - seed.beta)
    implied_output = seed.output * math.exp(
        a_k * target_states[0] + a_b * target_states[1]
    )
    initial_stocks = PositiveAIInitialStocks(
        capital=float(initial_capital),
        capability=float(initial_capability),
        implied_output=float(implied_output),
        capital_output_ratio=float(
            initial_capital / implied_output
        ),
        log_capital_deviation_from_bgp=float(target_states[0]),
        log_capability_deviation_from_bgp=float(target_states[1]),
    )
    return PositiveAITransitionSolution(
        raw=result,
        parameters=parameters,
        seed=seed,
        subspace=subspace,
        initial_stocks=initial_stocks,
        horizon=horizon_values[-1],
        stock_schedule=schedule,
        horizon_schedule=horizon_values,
        stages=tuple(records),
    )


def _independent_normalized_dynamics(
    deviations: np.ndarray,
    parameters: PositiveAIBenchmarkParameters,
    seed: PositiveAIBalancedGrowth,
) -> np.ndarray:
    """Reconstruct the four equilibrium laws without calling the solver RHS."""

    values = np.asarray(deviations, dtype=float)
    xi_k, xi_b, xi_c, xi_q = values
    output_deviation = (
        parameters.alpha / (1.0 - seed.beta) * xi_k
        + seed.beta / (1.0 - seed.beta) * xi_b
    )
    research_deviation = (
        xi_q + parameters.eta * xi_b
    ) / (1.0 - parameters.eta)
    capability_growth_deviation = (
        (2.0 * parameters.eta - 1.0) * xi_b
        + parameters.eta * xi_q
    ) / (1.0 - parameters.eta)
    output_capital_ratio = np.exp(output_deviation - xi_k)
    consumption_capital_ratio = np.exp(xi_c - xi_k)
    research_capital_ratio = np.exp(research_deviation - xi_k)
    profit_shadow_ratio = np.exp(output_deviation - xi_q - xi_b)
    capability_growth_ratio = np.exp(capability_growth_deviation)

    capital_rate = (
        (1.0 - seed.inference_share)
        / seed.capital_output_ratio
        * output_capital_ratio
        - seed.consumption_share
        / seed.capital_output_ratio
        * consumption_capital_ratio
        - seed.research_share
        / seed.capital_output_ratio
        * research_capital_ratio
        - parameters.depreciation
        - seed.output_growth
    )
    capability_rate = seed.capability_growth * (
        capability_growth_ratio - 1.0
    )
    consumption_rate = (
        parameters.population_growth
        + parameters.alpha
        / seed.capital_output_ratio
        * output_capital_ratio
        - parameters.depreciation
        - parameters.discount
        - seed.output_growth
    )
    shadow_rate = (
        parameters.alpha
        / seed.capital_output_ratio
        * output_capital_ratio
        - parameters.depreciation
        - seed.profit_shadow_ratio * profit_shadow_ratio
        - parameters.eta
        * seed.capability_growth
        * capability_growth_ratio
        - seed.shadow_value_growth
    )
    return np.stack(
        (capital_rate, capability_rate, consumption_rate, shadow_rate),
        axis=0,
    )


def segmented_backward_reconstruction_gap(
    solution: PositiveAITransitionSolution,
    *,
    segment_length: float = 10.0,
    points_per_segment: int = 21,
) -> tuple[float, int]:
    """Reintegrate short path segments backward with an independent RHS.

    A single backward integration over centuries is itself ill-conditioned:
    errors in the fast stable mode are magnified exponentially.  Short,
    overlapping reconstructions test the differential equations over the full
    path without confusing that known conditioning problem with model error.
    """

    if segment_length <= 0.0:
        raise ValueError("segment_length must be strictly positive.")
    if points_per_segment < 3:
        raise ValueError("points_per_segment must be at least three.")
    boundaries = list(
        np.arange(0.0, solution.horizon, segment_length, dtype=float)
    )
    if not boundaries or boundaries[0] != 0.0:
        boundaries.insert(0, 0.0)
    if boundaries[-1] < solution.horizon:
        boundaries.append(float(solution.horizon))
    else:
        boundaries[-1] = float(solution.horizon)

    maximum_gap = 0.0
    total_evaluations = 0
    for left, right in zip(boundaries[:-1], boundaries[1:]):
        length = float(right - left)
        terminal = np.asarray(solution.raw.sol(right), dtype=float)
        reverse = solve_ivp(
            lambda reverse_time, state: -_independent_normalized_dynamics(
                state, solution.parameters, solution.seed
            ),
            (0.0, length),
            terminal,
            method="DOP853",
            rtol=1e-10,
            atol=1e-13,
            max_step=min(0.5, length),
            dense_output=True,
        )
        if not reverse.success:
            raise RuntimeError(
                "Segmented backward reconstruction failed on "
                f"[{left:g},{right:g}]: {reverse.message}"
            )
        times = np.linspace(left, right, points_per_segment)
        reconstructed = reverse.sol(right - times)
        collocation = solution.raw.sol(times)
        maximum_gap = max(
            maximum_gap,
            float(np.max(np.abs(reconstructed - collocation))),
        )
        total_evaluations += int(reverse.nfev)
    return maximum_gap, total_evaluations


def audit_solution(
    solution: PositiveAITransitionSolution,
    *,
    sample_points: int = 2001,
) -> dict[str, float | bool | int]:
    """Independently reconstruct the normalized equilibrium equations."""

    if sample_points < 101:
        raise ValueError("sample_points must be at least 101.")
    parameters = solution.parameters
    seed = solution.seed
    times = np.linspace(0.0, solution.horizon, sample_points)
    deviations = np.asarray(solution.raw.sol(times))
    derivatives = np.asarray(solution.raw.sol(times, 1))
    reconstructed = _independent_normalized_dynamics(
        deviations, parameters, seed
    )
    ode_residual = derivatives - reconstructed

    xi_k, xi_b, xi_c, xi_q = deviations
    dxi_k, dxi_b, dxi_c, dxi_q = derivatives
    a_k = parameters.alpha / (1.0 - seed.beta)
    a_b = seed.beta / (1.0 - seed.beta)
    output_deviation = a_k * xi_k + a_b * xi_b
    research_deviation = (
        xi_q + parameters.eta * xi_b
    ) / (1.0 - parameters.eta)
    capability_growth_log_ratio = (
        (2.0 * parameters.eta - 1.0) * xi_b
        + parameters.eta * xi_q
    ) / (1.0 - parameters.eta)

    capital_share = seed.capital_output_ratio * np.exp(
        xi_k - output_deviation
    )
    consumption_share = seed.consumption_share * np.exp(
        xi_c - output_deviation
    )
    research_share = seed.research_share * np.exp(
        research_deviation - output_deviation
    )
    net_interest = parameters.alpha / capital_share - parameters.depreciation
    calendar_capability_growth = seed.capability_growth + dxi_b

    resource_residual = (
        (seed.output_growth + dxi_k + parameters.depreciation)
        * capital_share
        + consumption_share
        + seed.inference_share
        + research_share
        - 1.0
    )
    euler_residual = (
        seed.output_growth + dxi_c
        - parameters.population_growth
        - net_interest
        + parameters.discount
    )
    capability_residual = (
        calendar_capability_growth
        - seed.capability_growth * np.exp(capability_growth_log_ratio)
    )
    costate_residual = (
        seed.shadow_value_growth + dxi_q
        - net_interest
        + seed.profit_shadow_ratio
        * np.exp(output_deviation - xi_q - xi_b)
        + parameters.eta * calendar_capability_growth
    )
    research_foc_log_residual = (
        xi_q
        + parameters.eta * xi_b
        + (parameters.eta - 1.0) * research_deviation
    )

    target_states = np.asarray(
        [
            solution.initial_stocks.log_capital_deviation_from_bgp,
            solution.initial_stocks.log_capability_deviation_from_bgp,
        ]
    )
    boundary = boundary_residual(
        deviations[:, 0], deviations[:, -1], target_states,
        solution.subspace,
    )

    interest_deviation = (
        net_interest - seed.net_interest_rate
    )
    increments = np.diff(times)
    interest_integral = np.concatenate(
        (
            np.asarray([0.0]),
            np.cumsum(
                0.5
                * (interest_deviation[:-1] + interest_deviation[1:])
                * increments
            ),
        )
    )
    household_log_tvc = (
        math.log(seed.population * seed.capital / seed.consumption)
        - (parameters.discount - parameters.population_growth) * times
        + xi_k
        - xi_c
    )
    developer_log_tvc = (
        math.log(seed.shadow_value * seed.capability)
        - (parameters.discount - parameters.population_growth) * times
        + xi_q
        + xi_b
        - interest_integral
    )

    horizon_records = [
        record for record in solution.stages if record.kind == "horizon"
    ]
    if horizon_records:
        penultimate = (
            horizon_records[-2]
            if len(horizon_records) >= 2
            else solution.stages[-len(horizon_records) - 1]
        )
        latest = horizon_records[-1]
        horizon_jump_change = max(
            abs(latest.initial_consumption_deviation
                - penultimate.initial_consumption_deviation),
            abs(latest.initial_shadow_value_deviation
                - penultimate.initial_shadow_value_deviation),
        )
    else:
        horizon_jump_change = math.nan

    backward_gap, backward_evaluations = (
        segmented_backward_reconstruction_gap(solution)
    )

    return {
        "success": bool(solution.raw.success),
        "maximum_rms_residual": float(
            max(record.maximum_rms_residual for record in solution.stages)
        ),
        "max_normalized_ode_residual": float(
            np.max(np.abs(ode_residual))
        ),
        "max_resource_residual": float(np.max(np.abs(resource_residual))),
        "max_euler_residual": float(np.max(np.abs(euler_residual))),
        "max_capability_residual": float(
            np.max(np.abs(capability_residual))
        ),
        "max_costate_residual": float(np.max(np.abs(costate_residual))),
        "max_research_foc_log_residual": float(
            np.max(np.abs(research_foc_log_residual))
        ),
        "max_boundary_residual": float(np.max(np.abs(boundary))),
        "terminal_deviation_norm": float(
            np.linalg.norm(deviations[:, -1])
        ),
        "minimum_consumption_share": float(np.min(consumption_share)),
        "minimum_research_share": float(np.min(research_share)),
        "household_log_tvc_change": float(
            household_log_tvc[-1] - household_log_tvc[0]
        ),
        "developer_log_tvc_change": float(
            developer_log_tvc[-1] - developer_log_tvc[0]
        ),
        "last_horizon_initial_jump_change": float(horizon_jump_change),
        "segmented_backward_reconstruction_gap": float(backward_gap),
        "segmented_backward_function_evaluations": int(
            backward_evaluations
        ),
        "continuation_stages": int(len(solution.stages)),
        "final_nodes": int(solution.raw.x.size),
    }


def _parse_horizons(value: str) -> tuple[float, ...]:
    try:
        horizons = tuple(float(item.strip()) for item in value.split(","))
    except ValueError as error:
        raise argparse.ArgumentTypeError(str(error)) from error
    try:
        return _validate_horizons(horizons)
    except ValueError as error:
        raise argparse.ArgumentTypeError(str(error)) from error


def _parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target-capability", type=float, default=1.0)
    parser.add_argument(
        "--horizons",
        type=_parse_horizons,
        default=(100.0, 150.0, 200.0, 250.0),
        help="Comma-separated increasing terminal horizons.",
    )
    parser.add_argument("--continuation-steps", type=int, default=10)
    parser.add_argument("--nodes", type=int, default=121)
    parser.add_argument("--tolerance", type=float, default=1e-8)
    return parser.parse_args()


def main() -> None:
    arguments = _parse_arguments()
    parameters = PositiveAIBenchmarkParameters()
    seed = balanced_growth_seed(parameters)
    target = initial_stocks_matching_bgp_capital_output_ratio(
        parameters, arguments.target_capability, seed
    )
    solution = solve_transition(
        parameters,
        target.capital,
        target.capability,
        horizons=arguments.horizons,
        continuation_steps=arguments.continuation_steps,
        initial_nodes=arguments.nodes,
        tolerance=arguments.tolerance,
    )
    summary = {
        "parameters": asdict(parameters),
        "balanced_growth_capability": seed.capability,
        "initial_stocks": asdict(solution.initial_stocks),
        "initial_consumption": solution.initial_consumption,
        "initial_shadow_value": solution.initial_shadow_value,
        "horizons": solution.horizon_schedule,
        "stages": [asdict(stage) for stage in solution.stages],
        "audit": audit_solution(solution),
        "transition_solved": True,
    }
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
