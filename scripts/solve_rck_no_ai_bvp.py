"""Independent Ramsey--Cass--Koopmans boundary-value solver.

This module starts a new numerical architecture for the no-AI economy
(``omega_x = 0``).  It deliberately does not import or modify the existing AI
simulation code.  The economic problem is written in capital and consumption
per unit of effective labor and solved with SciPy's tested fourth-order
collocation BVP solver.

Specifically, ``k = K / (A N)`` and ``c = C / (A N)`` obey

``k_dot = k**alpha - c - (delta + n + gamma_A) * k``

``c_dot / c = alpha * k**(alpha - 1) - delta - rho - gamma_A``.

These are transformations of the paper's aggregate equations, not changes in
their timing, parameter definitions, or the convention that ``r`` is net of
depreciation.

The implementation has four safeguards:

1. log states enforce positive capital and consumption;
2. a linearized stable-direction condition closes the finite-horizon BVP;
3. analytic ODE and boundary-condition Jacobians are supplied to ``solve_bvp``;
4. backward integration, with separately coded equations, supplies an
   independent value for initial consumption.

Running this file prints a validation summary.  It does not write numerical
results, figures, or paper artifacts.
"""

from __future__ import annotations

import argparse
import json
import math
from dataclasses import asdict, dataclass
from typing import Any

import numpy as np
from scipy.integrate import solve_bvp, solve_ivp


@dataclass(frozen=True)
class RCKParameters:
    """Annual parameters for the no-AI Ramsey economy."""

    alpha: float = 0.33
    population_growth: float = 0.003
    labor_productivity_growth: float = 0.01
    depreciation: float = 0.05
    discount: float = 0.04

    def __post_init__(self) -> None:
        if not 0.0 < self.alpha < 1.0:
            raise ValueError("alpha must lie strictly between zero and one.")
        if self.population_growth < 0.0:
            raise ValueError("Population growth must be nonnegative.")
        if self.labor_productivity_growth < 0.0:
            raise ValueError("Labor-productivity growth must be nonnegative.")
        if self.depreciation < 0.0:
            raise ValueError("Depreciation must be nonnegative.")
        if self.discount <= self.population_growth:
            raise ValueError(
                "The maintained household condition requires discount > "
                "population growth."
            )


@dataclass(frozen=True)
class RCKSteadyState:
    """Balanced-growth values per unit of effective labor."""

    capital: float
    consumption: float
    output: float
    net_interest_rate: float
    wage_per_efficiency_unit: float


@dataclass
class RCKTransitionSolution:
    """Solved no-AI transition and metadata used to audit it."""

    raw: Any
    parameters: RCKParameters
    steady_state: RCKSteadyState
    initial_capital: float
    horizon: float
    stable_eigenvalue: float
    stable_log_slope: float
    continuation_capital: tuple[float, ...]
    continuation_iterations: tuple[int, ...]

    @property
    def initial_consumption(self) -> float:
        return float(math.exp(float(self.raw.y[1, 0])))

    def evaluate(self, times: np.ndarray | float) -> tuple[np.ndarray, np.ndarray]:
        logs = np.asarray(self.raw.sol(times))
        return np.exp(logs[0]), np.exp(logs[1])


def steady_state(parameters: RCKParameters) -> RCKSteadyState:
    """Return the exact balanced-growth allocation in effective units."""

    user_cost = (
        parameters.discount
        + parameters.depreciation
        + parameters.labor_productivity_growth
    )
    capital = (parameters.alpha / user_cost) ** (1.0 / (1.0 - parameters.alpha))
    output = capital**parameters.alpha
    effective_labor_growth = (
        parameters.population_growth + parameters.labor_productivity_growth
    )
    consumption = output - (
        parameters.depreciation + effective_labor_growth
    ) * capital
    if consumption <= 0.0:
        raise ValueError(
            "The parameterization implies nonpositive steady-state consumption."
        )
    return RCKSteadyState(
        capital=capital,
        consumption=consumption,
        output=output,
        net_interest_rate=parameters.discount
        + parameters.labor_productivity_growth,
        wage_per_efficiency_unit=(1.0 - parameters.alpha) * output,
    )


def log_dynamics(
    times: np.ndarray | float,
    log_states: np.ndarray,
    parameters: RCKParameters,
) -> np.ndarray:
    """Dynamics of log capital and log consumption in effective units."""

    del times
    log_capital = log_states[0]
    log_consumption = log_states[1]
    capital_product = np.exp((parameters.alpha - 1.0) * log_capital)
    consumption_capital_ratio = np.exp(log_consumption - log_capital)
    effective_cost = (
        parameters.depreciation
        + parameters.population_growth
        + parameters.labor_productivity_growth
    )
    return np.vstack(
        (
            capital_product - consumption_capital_ratio - effective_cost,
            parameters.alpha * capital_product
            - parameters.depreciation
            - parameters.discount
            - parameters.labor_productivity_growth,
        )
    )


def log_dynamics_jacobian(
    times: np.ndarray,
    log_states: np.ndarray,
    parameters: RCKParameters,
) -> np.ndarray:
    """Analytic Jacobian of :func:`log_dynamics` at all mesh nodes."""

    del times
    log_capital = log_states[0]
    log_consumption = log_states[1]
    capital_product = np.exp((parameters.alpha - 1.0) * log_capital)
    consumption_capital_ratio = np.exp(log_consumption - log_capital)
    jacobian = np.zeros((2, 2, log_states.shape[1]))
    jacobian[0, 0] = (
        (parameters.alpha - 1.0) * capital_product
        + consumption_capital_ratio
    )
    jacobian[0, 1] = -consumption_capital_ratio
    jacobian[1, 0] = (
        parameters.alpha * (parameters.alpha - 1.0) * capital_product
    )
    return jacobian


def stable_log_direction(
    parameters: RCKParameters,
    equilibrium: RCKSteadyState | None = None,
) -> tuple[float, float]:
    """Return the stable eigenvalue and dz/dx in log coordinates."""

    equilibrium = equilibrium or steady_state(parameters)
    logs = np.asarray(
        [[math.log(equilibrium.capital)], [math.log(equilibrium.consumption)]]
    )
    jacobian = log_dynamics_jacobian(
        np.asarray([0.0]), logs, parameters
    )[:, :, 0]
    eigenvalues, eigenvectors = np.linalg.eig(jacobian)
    stable_indices = [
        index
        for index, value in enumerate(eigenvalues)
        if value.real < 0.0 and abs(value.imag) < 1e-10
    ]
    if len(stable_indices) != 1:
        raise RuntimeError(
            "The detrended Ramsey system does not have exactly one real stable "
            "eigenvalue."
        )
    index = stable_indices[0]
    vector = np.real(eigenvectors[:, index])
    if abs(vector[0]) < 1e-12:
        raise RuntimeError("The stable direction has a zero capital component.")
    return float(eigenvalues[index].real), float(vector[1] / vector[0])


def _initial_guess(
    mesh: np.ndarray,
    initial_capital: float,
    equilibrium: RCKSteadyState,
    stable_eigenvalue: float,
    stable_log_slope: float,
) -> np.ndarray:
    log_capital_star = math.log(equilibrium.capital)
    log_consumption_star = math.log(equilibrium.consumption)
    displacement = math.log(initial_capital) - log_capital_star
    decay = np.exp(stable_eigenvalue * mesh)
    log_capital = log_capital_star + displacement * decay
    log_consumption = (
        log_consumption_star + stable_log_slope * displacement * decay
    )
    return np.vstack((log_capital, log_consumption))


def solve_transition(
    parameters: RCKParameters,
    initial_capital: float,
    *,
    horizon: float = 300.0,
    continuation_steps: int = 8,
    initial_nodes: int = 121,
    tolerance: float = 1e-8,
    boundary_tolerance: float = 1e-10,
    maximum_nodes: int = 10_000,
) -> RCKTransitionSolution:
    """Solve an off-balanced-growth no-AI transition with continuation."""

    if initial_capital <= 0.0:
        raise ValueError("Initial capital must be strictly positive.")
    if horizon <= 0.0:
        raise ValueError("The solution horizon must be strictly positive.")
    if continuation_steps < 1:
        raise ValueError("continuation_steps must be at least one.")
    if initial_nodes < 5:
        raise ValueError("initial_nodes must be at least five.")

    equilibrium = steady_state(parameters)
    stable_eigenvalue, stable_log_slope = stable_log_direction(
        parameters, equilibrium
    )
    log_capital_star = math.log(equilibrium.capital)
    log_consumption_star = math.log(equilibrium.consumption)
    target_displacement = math.log(initial_capital) - log_capital_star
    if abs(target_displacement) < 1e-14:
        continuation_logs = np.asarray([log_capital_star])
    else:
        continuation_logs = log_capital_star + target_displacement * np.linspace(
            1.0 / continuation_steps, 1.0, continuation_steps
        )
    continuation_capital = tuple(float(math.exp(value)) for value in continuation_logs)

    mesh = np.linspace(0.0, horizon, initial_nodes)
    guess = _initial_guess(
        mesh,
        continuation_capital[0],
        equilibrium,
        stable_eigenvalue,
        stable_log_slope,
    )
    previous_initial_log_capital = float(guess[0, 0])
    iterations: list[int] = []
    result: Any | None = None

    for stage, stage_initial_capital in enumerate(continuation_capital, start=1):
        stage_initial_log_capital = math.log(stage_initial_capital)
        if stage > 1:
            shift = stage_initial_log_capital - previous_initial_log_capital
            decay = np.exp(stable_eigenvalue * mesh)
            guess = guess.copy()
            guess[0] += shift * decay
            guess[1] += stable_log_slope * shift * decay

        def ode(times: np.ndarray, states: np.ndarray) -> np.ndarray:
            return log_dynamics(times, states, parameters)

        def ode_jacobian(times: np.ndarray, states: np.ndarray) -> np.ndarray:
            return log_dynamics_jacobian(times, states, parameters)

        def boundary(left: np.ndarray, right: np.ndarray) -> np.ndarray:
            return np.asarray(
                [
                    left[0] - stage_initial_log_capital,
                    right[1]
                    - log_consumption_star
                    - stable_log_slope * (right[0] - log_capital_star),
                ]
            )

        def boundary_jacobian(
            left: np.ndarray, right: np.ndarray
        ) -> tuple[np.ndarray, np.ndarray]:
            del left, right
            derivative_left = np.asarray([[1.0, 0.0], [0.0, 0.0]])
            derivative_right = np.asarray(
                [[0.0, 0.0], [-stable_log_slope, 1.0]]
            )
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
                f"BVP continuation stage {stage}/{len(continuation_capital)} "
                f"failed: {result.message}"
            )
        iterations.append(int(result.niter))
        mesh = np.asarray(result.x)
        guess = np.asarray(result.y)
        previous_initial_log_capital = stage_initial_log_capital

    if result is None:
        raise RuntimeError("The BVP continuation produced no solution.")
    return RCKTransitionSolution(
        raw=result,
        parameters=parameters,
        steady_state=equilibrium,
        initial_capital=initial_capital,
        horizon=horizon,
        stable_eigenvalue=stable_eigenvalue,
        stable_log_slope=stable_log_slope,
        continuation_capital=continuation_capital,
        continuation_iterations=tuple(iterations),
    )


def backward_initial_consumption(
    parameters: RCKParameters,
    initial_capital: float,
    *,
    relative_tolerance: float = 1e-11,
    absolute_tolerance: float = 1e-13,
) -> float:
    """Audit c(0) by integrating the stable path backward from steady state."""

    if initial_capital <= 0.0:
        raise ValueError("Initial capital must be strictly positive.")
    equilibrium = steady_state(parameters)
    target_log_capital = math.log(initial_capital)
    log_capital_star = math.log(equilibrium.capital)
    log_consumption_star = math.log(equilibrium.consumption)
    displacement = target_log_capital - log_capital_star
    if abs(displacement) < 1e-13:
        return equilibrium.consumption

    stable_eigenvalue, stable_log_slope = stable_log_direction(
        parameters, equilibrium
    )
    direction = math.copysign(1.0, displacement)
    initial_step = direction * min(1e-6, abs(displacement) / 100.0)
    initial_logs = np.asarray(
        [
            log_capital_star + initial_step,
            log_consumption_star + stable_log_slope * initial_step,
        ]
    )

    def reverse_dynamics(time: float, states: np.ndarray) -> np.ndarray:
        del time
        log_capital, log_consumption = states
        capital_product = math.exp(
            (parameters.alpha - 1.0) * log_capital
        )
        consumption_capital_ratio = math.exp(
            log_consumption - log_capital
        )
        effective_cost = (
            parameters.depreciation
            + parameters.population_growth
            + parameters.labor_productivity_growth
        )
        forward_values = np.asarray(
            [
                capital_product
                - consumption_capital_ratio
                - effective_cost,
                parameters.alpha * capital_product
                - parameters.depreciation
                - parameters.discount
                - parameters.labor_productivity_growth,
            ]
        )
        return -forward_values

    def hit_initial_capital(time: float, states: np.ndarray) -> float:
        del time
        return float(states[0] - target_log_capital)

    hit_initial_capital.terminal = True  # type: ignore[attr-defined]
    hit_initial_capital.direction = direction  # type: ignore[attr-defined]
    growth_time = math.log(max(abs(displacement / initial_step), 1.0)) / (
        -stable_eigenvalue
    )
    reverse_horizon = max(100.0, 2.0 * growth_time + 20.0)
    result = solve_ivp(
        reverse_dynamics,
        (0.0, reverse_horizon),
        initial_logs,
        method="DOP853",
        events=hit_initial_capital,
        rtol=relative_tolerance,
        atol=absolute_tolerance,
        max_step=1.0,
    )
    if not result.success:
        raise RuntimeError(f"Backward integration failed: {result.message}")
    if not result.y_events or len(result.y_events[0]) == 0:
        raise RuntimeError(
            "Backward integration did not reach the requested initial capital."
        )
    return float(math.exp(float(result.y_events[0][0, 1])))


def audit_solution(
    solution: RCKTransitionSolution,
    *,
    evaluation_points: int = 1001,
) -> dict[str, float | int | bool]:
    """Return numerical and economic residuals for a solved transition."""

    if evaluation_points < 5:
        raise ValueError("evaluation_points must be at least five.")
    parameters = solution.parameters
    equilibrium = solution.steady_state
    times = np.linspace(0.0, solution.horizon, evaluation_points)
    logs = np.asarray(solution.raw.sol(times))
    log_derivatives = np.asarray(solution.raw.sol(times, 1))
    model_derivatives = log_dynamics(times, logs, parameters)
    capital = np.exp(logs[0])
    consumption = np.exp(logs[1])

    capital_rhs = (
        capital**parameters.alpha
        - consumption
        - (
            parameters.depreciation
            + parameters.population_growth
            + parameters.labor_productivity_growth
        )
        * capital
    )
    capital_lhs = capital * log_derivatives[0]
    euler_rhs = (
        parameters.alpha * capital ** (parameters.alpha - 1.0)
        - parameters.depreciation
        - parameters.discount
        - parameters.labor_productivity_growth
    )

    log_capital_star = math.log(equilibrium.capital)
    log_consumption_star = math.log(equilibrium.consumption)
    terminal_stable_residual = (
        logs[1, -1]
        - log_consumption_star
        - solution.stable_log_slope * (logs[0, -1] - log_capital_star)
    )
    boundary_residual = max(
        abs(logs[0, 0] - math.log(solution.initial_capital)),
        abs(terminal_stable_residual),
    )
    tvc_proxy = math.exp(
        (parameters.population_growth - parameters.discount) * solution.horizon
        + logs[0, -1]
        - logs[1, -1]
    )
    backward_consumption = backward_initial_consumption(
        parameters, solution.initial_capital
    )
    backward_relative_gap = abs(
        solution.initial_consumption / backward_consumption - 1.0
    )

    return {
        "success": bool(solution.raw.success),
        "nodes": int(len(solution.raw.x)),
        "iterations_last_stage": int(solution.raw.niter),
        "continuation_stages": int(len(solution.continuation_capital)),
        "max_collocation_rms_residual": float(
            np.max(solution.raw.rms_residuals)
        ),
        "max_log_ode_residual": float(
            np.max(np.abs(log_derivatives - model_derivatives))
        ),
        "max_capital_equation_residual": float(
            np.max(np.abs(capital_lhs - capital_rhs))
        ),
        "max_euler_equation_residual": float(
            np.max(np.abs(log_derivatives[1] - euler_rhs))
        ),
        "boundary_residual": float(boundary_residual),
        "terminal_log_distance_to_steady_state": float(
            math.hypot(
                logs[0, -1] - log_capital_star,
                logs[1, -1] - log_consumption_star,
            )
        ),
        "finite_horizon_tvc_proxy": float(tvc_proxy),
        "initial_consumption": float(solution.initial_consumption),
        "backward_initial_consumption": float(backward_consumption),
        "backward_initial_consumption_relative_gap": float(
            backward_relative_gap
        ),
    }


def _parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--initial-capital-ratio",
        type=float,
        default=0.5,
        help="Initial effective capital divided by its balanced-growth value.",
    )
    parser.add_argument("--horizon", type=float, default=300.0)
    parser.add_argument("--continuation-steps", type=int, default=8)
    parser.add_argument("--nodes", type=int, default=121)
    parser.add_argument("--tolerance", type=float, default=1e-8)
    return parser.parse_args()


def main() -> None:
    arguments = _parse_arguments()
    parameters = RCKParameters()
    equilibrium = steady_state(parameters)
    solution = solve_transition(
        parameters,
        arguments.initial_capital_ratio * equilibrium.capital,
        horizon=arguments.horizon,
        continuation_steps=arguments.continuation_steps,
        initial_nodes=arguments.nodes,
        tolerance=arguments.tolerance,
    )
    summary = {
        "parameters": asdict(parameters),
        "steady_state": asdict(equilibrium),
        "initial_capital_ratio": arguments.initial_capital_ratio,
        "stable_eigenvalue": solution.stable_eigenvalue,
        "stable_log_slope": solution.stable_log_slope,
        "continuation_iterations": solution.continuation_iterations,
        "audit": audit_solution(solution),
    }
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
