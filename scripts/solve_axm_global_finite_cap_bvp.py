"""Continue the finite-cap stable manifold to the paper's initial stocks.

The local terminal analysis uses five autonomous coordinates.  The fifth,
``tau=(AN)^(-1)``, is exogenous rather than an additional economic state.  A
global equilibrium BVP can therefore be written in the first four coordinates,
with ``tau`` evaluated from calendar time.  This leaves exactly four boundary
conditions: the two predetermined stocks at date zero and the two terminal
conditions that eliminate the unstable components.

The solver starts from the already verified local BVP and moves the initial
effective-labor scale and the two initial normalized states to their requested
values by continuation.  A converged collocation path is still only a
candidate equilibrium until feasibility, both transversality conditions, and
the finite-cap developer sufficiency gate have been audited.
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

from scipy.integrate import cumulative_trapezoid  # noqa: E402
from scipy.integrate import solve_bvp  # noqa: E402
from scipy.optimize import minimize_scalar  # noqa: E402

from analyze_axm_finite_cap_bvp import (  # noqa: E402
    FiniteCapTerminalPoint,
    TerminalLinearization,
    ai_dominated_dynamics,
    critical_capability_frontier,
    labor_supported_dynamics,
    solve_local_terminal_bvp,
    terminal_linearization,
    terminal_point,
)
from define_positive_ai_branch import (  # noqa: E402
    PositiveAIBenchmarkParameters,
    balanced_growth_seed,
)
from solve_near_unit_ai_bvp import solve_monopoly_static_block  # noqa: E402


@dataclass(frozen=True)
class GlobalContinuationStage:
    """One successful step from the terminal neighborhood to date zero."""

    fraction: float
    horizon: float
    initial_effective_labor_scale: float
    iterations: int
    nodes: int
    maximum_rms_residual: float
    maximum_boundary_residual: float


@dataclass
class GlobalFiniteCapBVP:
    """A finite-cap BVP reaching specified predetermined date-zero stocks."""

    raw: Any
    terminal: FiniteCapTerminalPoint
    linearization: TerminalLinearization
    parameters: PositiveAIBenchmarkParameters
    initial_capital: float
    initial_capability: float
    initial_effective_labor_scale: float
    horizon: float
    stages: tuple[GlobalContinuationStage, ...]


@dataclass(frozen=True)
class _LocalRawSeed:
    """Adapter exposing the local normalized spline in raw coordinates."""

    local_raw: Any
    terminal: FiniteCapTerminalPoint
    parameters: PositiveAIBenchmarkParameters
    initial_effective_labor_scale: float

    def sol(self, times: np.ndarray | float) -> np.ndarray:
        values = np.atleast_1d(np.asarray(times, dtype=float))
        normalized = np.asarray(self.local_raw.sol(values), dtype=float)
        raw = normalized_to_raw_coordinates(
            values,
            normalized,
            self.terminal,
            self.parameters,
            self.initial_effective_labor_scale,
        )
        raw -= self.terminal.terminal_growth * values[None, :]
        if np.asarray(times).ndim == 0:
            return raw[:, 0]
        return raw


def effective_labor_growth(parameters: PositiveAIBenchmarkParameters) -> float:
    return parameters.population_growth + parameters.labor_productivity_growth


def _softplus(value: float) -> float:
    """Evaluate log(1+exp(value)) without overflow."""

    if value >= 0.0:
        return value + math.log1p(math.exp(-value))
    return math.log1p(math.exp(value))


def _exponential(value: float, *, newton_safeguard: bool) -> float:
    """Evaluate an exponential, bounding only off-path Newton trial values."""

    if newton_safeguard:
        value = min(100.0, max(-100.0, value))
    return math.exp(value)


def _capability_logs(
    capability_logit: float,
    frontier: float,
) -> tuple[float, float, float]:
    """Return log B, log(Bbar-B), and log psi from an unrestricted logit."""

    log_frontier = math.log(frontier)
    log_capability = log_frontier - _softplus(-capability_logit)
    log_gap = log_frontier - _softplus(capability_logit)
    return log_capability, log_gap, log_gap - log_frontier


def initial_raw_coordinates(
    terminal: FiniteCapTerminalPoint,
    initial_capital: float,
    initial_capability: float,
) -> np.ndarray:
    """Map physical date-zero stocks into positivity-preserving raw logs."""

    if initial_capital <= 0.0:
        raise ValueError("Initial capital must be strictly positive.")
    if not 0.0 < initial_capability < terminal.frontier:
        raise ValueError("Initial capability must lie in (0,Bbar).")
    return np.asarray(
        [
            math.log(initial_capital),
            math.log(initial_capability / (terminal.frontier - initial_capability)),
            math.nan,
            math.nan,
        ]
    )


def scaled_tau_path(
    times: np.ndarray | float,
    terminal: FiniteCapTerminalPoint,
    parameters: PositiveAIBenchmarkParameters,
    initial_effective_labor_scale: float,
) -> np.ndarray:
    """Return the autonomous system's scaled version of (AN)^(-1)."""

    values = np.asarray(times, dtype=float)
    actual_tau = np.exp(-effective_labor_growth(parameters) * values) / (
        initial_effective_labor_scale
    )
    return (
        terminal.auxiliary["gap_scale"]
        / terminal.frontier
        * actual_tau
    )


def raw_to_terminal_coordinates(
    time: float,
    raw_coordinates: np.ndarray,
    terminal: FiniteCapTerminalPoint,
    parameters: PositiveAIBenchmarkParameters,
    initial_effective_labor_scale: float,
    *,
    newton_safeguard: bool = False,
) -> np.ndarray:
    """Map raw logs into the five coordinates used by the terminal proof."""

    log_capital, capability_logit, log_consumption, log_shadow = np.asarray(
        raw_coordinates, dtype=float
    )
    _, log_gap, _ = _capability_logs(
        float(capability_logit), terminal.frontier
    )
    log_effective_labor = (
        math.log(initial_effective_labor_scale)
        + effective_labor_growth(parameters) * float(time)
    )
    scaled_tau = (
        terminal.auxiliary["gap_scale"]
        / terminal.frontier
        * math.exp(-log_effective_labor)
    )
    if terminal.regime == "labor_supported":
        return np.asarray(
            [
                log_capital - log_effective_labor,
                log_consumption - log_effective_labor,
                log_gap + log_effective_labor,
                log_shadow - log_effective_labor,
                scaled_tau,
            ]
        )
    varphi = (terminal.sigma_xl - 1.0) / terminal.sigma_xl
    return np.asarray(
        [
            _exponential(
                varphi * (log_effective_labor - log_capital),
                newton_safeguard=newton_safeguard,
            ),
            log_gap + log_capital,
            log_consumption - log_capital,
            log_shadow - log_capital,
            scaled_tau,
        ]
    )


def normalized_to_raw_coordinates(
    times: np.ndarray,
    normalized_coordinates: np.ndarray,
    terminal: FiniteCapTerminalPoint,
    parameters: PositiveAIBenchmarkParameters,
    initial_effective_labor_scale: float,
) -> np.ndarray:
    """Convert the verified local normalized path into raw solver variables."""

    time_values = np.atleast_1d(np.asarray(times, dtype=float))
    values = np.asarray(normalized_coordinates, dtype=float)
    if values.shape[0] < 4 or values.shape[1] != time_values.size:
        raise ValueError("The local path has incompatible dimensions.")
    result = np.empty((4, time_values.size))
    growth = effective_labor_growth(parameters)
    log_frontier = math.log(terminal.frontier)
    for index, time in enumerate(time_values):
        log_effective_labor = (
            math.log(initial_effective_labor_scale) + growth * float(time)
        )
        if terminal.regime == "labor_supported":
            log_capital = values[0, index] + log_effective_labor
            log_consumption = values[1, index] + log_effective_labor
            log_gap = values[2, index] - log_effective_labor
            log_shadow = values[3, index] + log_effective_labor
        else:
            varphi = (terminal.sigma_xl - 1.0) / terminal.sigma_xl
            h_value = values[0, index]
            if h_value <= 0.0:
                raise FloatingPointError("The local h coordinate is nonpositive.")
            log_capital = log_effective_labor - math.log(h_value) / varphi
            log_gap = values[1, index] - log_capital
            log_consumption = values[2, index] + log_capital
            log_shadow = values[3, index] + log_capital
        if log_gap >= log_frontier:
            raise FloatingPointError("The local seed implies nonpositive capability.")
        log_capability = log_frontier + math.log1p(
            -math.exp(log_gap - log_frontier)
        )
        result[:, index] = (
            log_capital,
            log_capability - log_gap,
            log_consumption,
            log_shadow,
        )
    return result


def dated_raw_dynamics(
    times: np.ndarray | float,
    raw_coordinates: np.ndarray,
    terminal: FiniteCapTerminalPoint,
    parameters: PositiveAIBenchmarkParameters,
    initial_effective_labor_scale: float,
    *,
    newton_safeguard: bool = False,
) -> np.ndarray:
    """Evaluate the exact capped system in positivity-preserving raw logs."""

    time_values = np.atleast_1d(np.asarray(times, dtype=float))
    values = np.asarray(raw_coordinates, dtype=float)
    scalar = values.ndim == 1
    if scalar:
        values = values[:, None]
    if values.shape != (4, time_values.size):
        raise ValueError("Expected four raw coordinates at every supplied date.")
    result = np.empty_like(values)
    log_chi = math.log(parameters.chi)
    log_eta = math.log(parameters.eta)
    growth = effective_labor_growth(parameters)
    for index in range(time_values.size):
        log_capital, capability_logit, log_consumption, log_shadow = values[
            :, index
        ]
        log_capability, _, log_psi = _capability_logs(
            float(capability_logit), terminal.frontier
        )
        log_effective_labor = (
            math.log(initial_effective_labor_scale)
            + growth * float(time_values[index])
        )
        static = solve_monopoly_static_block(
            float(log_capital),
            float(log_capability),
            log_effective_labor,
            terminal.sigma_xl,
            parameters,
        )
        log_bm = (
            log_shadow
            + log_chi
            + log_eta
            + log_capability
            + log_psi
        ) / (1.0 - parameters.eta)
        log_research = log_bm - log_capability
        output_capital = _exponential(
            static.log_output - log_capital,
            newton_safeguard=newton_safeguard,
        )
        consumption_capital = _exponential(
            log_consumption - log_capital,
            newton_safeguard=newton_safeguard,
        )
        inference_capital = _exponential(
            static.log_inference_compute - log_capital,
            newton_safeguard=newton_safeguard,
        )
        research_capital = _exponential(
            log_research - log_capital,
            newton_safeguard=newton_safeguard,
        )
        capability_growth = _exponential(
            log_chi
            + parameters.eta * log_bm
            + log_psi
            - log_capability,
            newton_safeguard=newton_safeguard,
        )
        approach_rate = _exponential(
            log_chi
            + parameters.eta * log_bm
            - math.log(terminal.frontier),
            newton_safeguard=newton_safeguard,
        )
        capital_growth = (
            output_capital
            - consumption_capital
            - inference_capital
            - research_capital
            - parameters.depreciation
        )
        net_interest = parameters.alpha * output_capital - parameters.depreciation
        service_shadow_return = _exponential(
            static.log_ai_services - log_shadow - 2.0 * log_capability,
            newton_safeguard=newton_safeguard,
        )
        result[:, index] = (
            capital_growth,
            capability_growth + approach_rate,
            parameters.population_growth + net_interest - parameters.discount,
            net_interest
            - service_shadow_return
            - parameters.eta * capability_growth
            + approach_rate,
        )
    return result[:, 0] if scalar else result


def dated_bounded_dynamics(
    times: np.ndarray | float,
    bounded_coordinates: np.ndarray,
    terminal: FiniteCapTerminalPoint,
    parameters: PositiveAIBenchmarkParameters,
    initial_effective_labor_scale: float,
    *,
    newton_safeguard: bool = False,
) -> np.ndarray:
    """Evaluate raw dynamics after removing terminal common growth."""

    time_values = np.atleast_1d(np.asarray(times, dtype=float))
    values = np.asarray(bounded_coordinates, dtype=float)
    scalar = values.ndim == 1
    if scalar:
        values = values[:, None]
    evaluation_values = (
        np.clip(values, -150.0, 150.0) if newton_safeguard else values
    )
    raw = evaluation_values + terminal.terminal_growth * time_values[None, :]
    result = dated_raw_dynamics(
        time_values,
        raw,
        terminal,
        parameters,
        initial_effective_labor_scale,
        newton_safeguard=newton_safeguard,
    ) - terminal.terminal_growth
    return result[:, 0] if scalar else result


def global_boundary_residual(
    left: np.ndarray,
    right: np.ndarray,
    initial_targets: np.ndarray,
    horizon: float,
    initial_effective_labor_scale: float,
    terminal: FiniteCapTerminalPoint,
    linearization: TerminalLinearization,
    parameters: PositiveAIBenchmarkParameters,
    *,
    newton_safeguard: bool = False,
) -> np.ndarray:
    """Impose the two initial stocks and the two terminal projections."""

    terminal_raw = right + terminal.terminal_growth * horizon
    terminal_deviation = (
        raw_to_terminal_coordinates(
            horizon,
            terminal_raw,
            terminal,
            parameters,
            initial_effective_labor_scale,
            newton_safeguard=newton_safeguard,
        )
        - terminal.coordinates
    )
    return np.concatenate(
        (
            left[:2] - initial_targets[:2],
            linearization.terminal_matrix @ terminal_deviation,
        )
    )


def _extended_guess(
    previous: Any,
    previous_horizon: float,
    mesh: np.ndarray,
    terminal: FiniteCapTerminalPoint,
) -> np.ndarray:
    """Extend a previous collocation spline by its terminal value."""

    clipped = np.minimum(mesh, previous_horizon)
    guess = np.asarray(previous.sol(clipped), dtype=float)
    beyond = mesh > previous_horizon
    if np.any(beyond):
        end_value = np.asarray(previous.sol(previous_horizon), dtype=float)
        guess[:, beyond] = end_value[:, None]
    return guess


def _solve_stage(
    previous: Any,
    previous_horizon: float,
    horizon: float,
    initial_targets: np.ndarray,
    initial_effective_labor_scale: float,
    terminal: FiniteCapTerminalPoint,
    linearization: TerminalLinearization,
    parameters: PositiveAIBenchmarkParameters,
    *,
    nodes: int,
    tolerance: float,
    boundary_tolerance: float,
    maximum_nodes: int,
) -> tuple[Any, float]:
    mesh = np.linspace(0.0, horizon, nodes)
    guess = _extended_guess(previous, previous_horizon, mesh, terminal)
    def ode(times: np.ndarray, values: np.ndarray) -> np.ndarray:
        return dated_bounded_dynamics(
            times,
            values,
            terminal,
            parameters,
            initial_effective_labor_scale,
            newton_safeguard=True,
        )

    def boundary(left: np.ndarray, right: np.ndarray) -> np.ndarray:
        return global_boundary_residual(
            left,
            right,
            initial_targets,
            horizon,
            initial_effective_labor_scale,
            terminal,
            linearization,
            parameters,
            newton_safeguard=True,
        )

    result = solve_bvp(
        ode,
        boundary,
        mesh,
        guess,
        tol=tolerance,
        bc_tol=boundary_tolerance,
        max_nodes=maximum_nodes,
        verbose=0,
    )
    if not result.success:
        raise RuntimeError(result.message)
    boundary_value = boundary(result.y[:, 0], result.y[:, -1])
    return result, float(np.max(np.abs(boundary_value)))


def recommended_global_horizon(
    terminal: FiniteCapTerminalPoint,
    parameters: PositiveAIBenchmarkParameters,
    initial_effective_labor_scale: float,
    *,
    terminal_decay_multiples: float = 11.0,
) -> float:
    """Choose a horizon from the exogenous scale and slow stable root."""

    linearization = terminal_linearization(terminal, parameters)
    initial_scaled_tau = float(
        scaled_tau_path(
            0.0,
            terminal,
            parameters,
            initial_effective_labor_scale,
        )
    )
    scale_time = max(0.0, math.log(max(1.0, initial_scaled_tau))) / (
        effective_labor_growth(parameters)
    )
    slow_root = float(np.min(np.abs(linearization.stable_eigenvalues)))
    return scale_time + terminal_decay_multiples / slow_root


def solve_global_finite_cap_bvp(
    terminal: FiniteCapTerminalPoint,
    parameters: PositiveAIBenchmarkParameters,
    initial_capital: float,
    initial_capability: float,
    *,
    initial_effective_labor_scale: float | None = None,
    horizon: float | None = None,
    continuation_steps: int = 48,
    local_horizon: float = 400.0,
    nodes: int = 401,
    tolerance: float = 2e-7,
    boundary_tolerance: float = 1e-9,
    maximum_nodes: int = 30_000,
) -> GlobalFiniteCapBVP:
    """Continue the local stable path to requested physical initial stocks."""

    if continuation_steps < 2:
        raise ValueError("continuation_steps must be at least two.")
    initial_effective_labor_scale = (
        parameters.initial_labor_productivity
        * parameters.initial_population
        if initial_effective_labor_scale is None
        else initial_effective_labor_scale
    )
    final_targets = initial_raw_coordinates(
        terminal,
        initial_capital,
        initial_capability,
    )
    final_horizon = float(
        horizon
        if horizon is not None
        else recommended_global_horizon(
            terminal, parameters, initial_effective_labor_scale
        )
    )
    if final_horizon <= local_horizon:
        raise ValueError("The global horizon must exceed the local seed horizon.")

    local_deviations = (
        np.asarray([0.01, -0.01, 1e-5])
        if terminal.regime == "labor_supported"
        else np.asarray([1e-5, -0.01, 1e-5])
    )
    local = solve_local_terminal_bvp(
        terminal,
        parameters,
        local_deviations,
        horizon=local_horizon,
        nodes=161,
        tolerance=min(tolerance, 1e-8),
        boundary_tolerance=boundary_tolerance,
        maximum_nodes=maximum_nodes,
    )
    local_scale = (
        terminal.auxiliary["gap_scale"]
        / terminal.frontier
        / local_deviations[2]
    )
    previous = _LocalRawSeed(
        local.raw,
        terminal,
        parameters,
        local_scale,
    )
    previous_horizon = local_horizon
    local_targets = np.asarray(previous.sol(0.0), dtype=float)
    log_local_scale = math.log(local_scale)
    log_final_scale = math.log(initial_effective_labor_scale)
    linearization = terminal_linearization(terminal, parameters)
    stages: list[GlobalContinuationStage] = []

    base_step = 1.0 / continuation_steps
    step = base_step
    fraction = 0.0
    minimum_step = base_step / 64.0
    while fraction < 1.0 - 1e-14:
        proposed_fraction = min(1.0, fraction + step)
        scale = math.exp(
            (1.0 - proposed_fraction) * log_local_scale
            + proposed_fraction * log_final_scale
        )
        targets = local_targets.copy()
        targets[:2] = (
            (1.0 - proposed_fraction) * local_targets[:2]
            + proposed_fraction * final_targets[:2]
        )
        stage_horizon = (
            (1.0 - proposed_fraction) * local_horizon
            + proposed_fraction * final_horizon
        )
        stage_nodes = max(
            nodes,
            int(math.ceil(nodes * stage_horizon / final_horizon)),
        )
        try:
            result, boundary_residual = _solve_stage(
                previous,
                previous_horizon,
                stage_horizon,
                targets,
                scale,
                terminal,
                linearization,
                parameters,
                nodes=stage_nodes,
                tolerance=tolerance,
                boundary_tolerance=boundary_tolerance,
                maximum_nodes=maximum_nodes,
            )
        except (FloatingPointError, OverflowError, RuntimeError) as error:
            step *= 0.5
            if step < minimum_step:
                raise RuntimeError(
                    "Global finite-cap continuation failed near fraction "
                    f"{proposed_fraction:.6f}, after adaptive step "
                    f"refinement: {error}"
                ) from error
            continue
        rms = np.asarray(result.rms_residuals, dtype=float)
        stages.append(
            GlobalContinuationStage(
                fraction=float(proposed_fraction),
                horizon=float(stage_horizon),
                initial_effective_labor_scale=float(scale),
                iterations=int(result.niter),
                nodes=int(result.x.size),
                maximum_rms_residual=float(np.max(rms)),
                maximum_boundary_residual=boundary_residual,
            )
        )
        previous = result
        previous_horizon = stage_horizon
        fraction = proposed_fraction
        step = min(base_step, 1.25 * step)

    return GlobalFiniteCapBVP(
        raw=previous,
        terminal=terminal,
        linearization=linearization,
        parameters=parameters,
        initial_capital=initial_capital,
        initial_capability=initial_capability,
        initial_effective_labor_scale=initial_effective_labor_scale,
        horizon=final_horizon,
        stages=tuple(stages),
    )


def refine_global_horizon(
    solution: GlobalFiniteCapBVP,
    horizon: float,
    *,
    nodes: int = 501,
    tolerance: float = 1e-8,
    boundary_tolerance: float = 1e-10,
    maximum_nodes: int = 40_000,
) -> GlobalFiniteCapBVP:
    """Re-solve an admitted candidate at a longer horizon."""

    if horizon <= solution.horizon:
        raise ValueError("The refined horizon must be longer.")
    targets = initial_raw_coordinates(
        solution.terminal,
        solution.initial_capital,
        solution.initial_capability,
    )
    result, boundary_value = _solve_stage(
        solution.raw,
        solution.horizon,
        horizon,
        targets,
        solution.initial_effective_labor_scale,
        solution.terminal,
        solution.linearization,
        solution.parameters,
        nodes=nodes,
        tolerance=tolerance,
        boundary_tolerance=boundary_tolerance,
        maximum_nodes=maximum_nodes,
    )
    stage = GlobalContinuationStage(
        fraction=1.0,
        horizon=float(horizon),
        initial_effective_labor_scale=solution.initial_effective_labor_scale,
        iterations=int(result.niter),
        nodes=int(result.x.size),
        maximum_rms_residual=float(np.max(result.rms_residuals)),
        maximum_boundary_residual=boundary_value,
    )
    return GlobalFiniteCapBVP(
        raw=result,
        terminal=solution.terminal,
        linearization=solution.linearization,
        parameters=solution.parameters,
        initial_capital=solution.initial_capital,
        initial_capability=solution.initial_capability,
        initial_effective_labor_scale=solution.initial_effective_labor_scale,
        horizon=float(horizon),
        stages=solution.stages + (stage,),
    )


def reconstruct_levels(
    times: np.ndarray,
    coordinates: np.ndarray,
    solution: GlobalFiniteCapBVP,
) -> dict[str, np.ndarray]:
    """Recover dated levels and static allocations from raw solver paths."""

    times = np.asarray(times, dtype=float)
    values = np.asarray(coordinates, dtype=float)
    if values.shape != (4, times.size):
        raise ValueError("Expected four raw coordinates at every supplied date.")
    p = solution.parameters
    terminal = solution.terminal
    effective_labor = (
        solution.initial_effective_labor_scale
        * np.exp(effective_labor_growth(p) * times)
    )
    raw_values = values + terminal.terminal_growth * times[None, :]
    log_capital = raw_values[0]
    capability_logit = raw_values[1]
    log_consumption = raw_values[2]
    log_shadow = raw_values[3]
    capability = np.empty(times.size)
    log_capability = np.empty(times.size)
    log_psi = np.empty(times.size)
    for index in range(times.size):
        log_capability[index], _, log_psi[index] = _capability_logs(
            float(capability_logit[index]), terminal.frontier
        )
        capability[index] = math.exp(log_capability[index])

    log_output = np.empty(times.size)
    log_ai_services = np.empty(times.size)
    log_inference = np.empty(times.size)
    log_research = np.empty(times.size)
    interest = np.empty(times.size)
    ai_share = np.empty(times.size)
    soc_margin = np.empty(times.size)
    concavity_margin = np.empty(times.size)
    for index in range(times.size):
        static = solve_monopoly_static_block(
            float(log_capital[index]),
            float(log_capability[index]),
            math.log(float(effective_labor[index])),
            terminal.sigma_xl,
            p,
        )
        log_output[index] = static.log_output
        log_ai_services[index] = static.log_ai_services
        log_inference[index] = static.log_inference_compute
        ai_share[index] = static.ai_ces_share
        soc_margin[index] = static.monopoly_soc_margin
        log_bm = (
            float(log_shadow[index])
            + math.log(p.chi)
            + math.log(p.eta)
            + float(log_capability[index])
            + float(log_psi[index])
        ) / (1.0 - p.eta)
        log_research[index] = log_bm - log_capability[index]
        interest[index] = (
            p.alpha * math.exp(static.log_output - log_capital[index])
            - p.depreciation
        )
        e_x = (1.0 - ai_share[index]) / terminal.sigma_xl + p.alpha * ai_share[index]
        denominator = (
            e_x * (1.0 - e_x)
            + (p.alpha - 1.0 / terminal.sigma_xl)
            * (1.0 - 1.0 / terminal.sigma_xl)
            * ai_share[index]
            * (1.0 - ai_share[index])
        )
        epsilon_b = (1.0 - e_x) / denominator
        capability_ratio = capability[index] / terminal.frontier
        concavity_margin[index] = (
            capability_ratio
            - math.exp(log_psi[index]) * (epsilon_b - 2.0)
        )
    return {
        "effective_labor": effective_labor,
        "log_capital": log_capital,
        "capability": capability,
        "log_capability": log_capability,
        "log_remaining_frontier_share": log_psi,
        "log_consumption": log_consumption,
        "log_shadow_value": log_shadow,
        "log_output": log_output,
        "log_ai_services": log_ai_services,
        "log_inference_compute": log_inference,
        "log_research_compute": log_research,
        "net_interest_rate": interest,
        "ai_ces_share": ai_share,
        "monopoly_soc_margin": soc_margin,
        "actual_path_concavity_margin": concavity_margin,
    }


def _developer_concavity_margin(
    log_capital: float,
    log_effective_labor: float,
    capability: float,
    terminal: FiniteCapTerminalPoint,
    parameters: PositiveAIBenchmarkParameters,
) -> tuple[float, float, float]:
    """Evaluate the exact finite-cap concavity gate at one counterfactual B."""

    static = solve_monopoly_static_block(
        log_capital,
        math.log(capability),
        log_effective_labor,
        terminal.sigma_xl,
        parameters,
    )
    share = static.ai_ces_share
    inverse_elasticity = (
        (1.0 - share) / terminal.sigma_xl + parameters.alpha * share
    )
    denominator = (
        inverse_elasticity * (1.0 - inverse_elasticity)
        + (parameters.alpha - 1.0 / terminal.sigma_xl)
        * (1.0 - 1.0 / terminal.sigma_xl)
        * share
        * (1.0 - share)
    )
    service_elasticity = (1.0 - inverse_elasticity) / denominator
    ratio = capability / terminal.frontier
    margin = ratio - (1.0 - ratio) * (service_elasticity - 2.0)
    return margin, share, service_elasticity


def audit_counterfactual_developer_sufficiency(
    solution: GlobalFiniteCapBVP,
    *,
    time_points: int = 81,
    capability_points: int = 81,
    sample_times: np.ndarray | None = None,
) -> dict[str, float | bool | int]:
    """Numerically minimize the developer gate over dates and reachable B."""

    if time_points < 11 or capability_points < 21:
        raise ValueError("The counterfactual audit grids are too small.")
    lower_ratio = solution.initial_capability / solution.terminal.frontier
    if not 0.0 < lower_ratio < 1.0:
        raise ValueError("The initial capability is outside the capped domain.")
    lower_logit = math.log(lower_ratio / (1.0 - lower_ratio))
    upper_logit = 30.0
    logit_grid = np.linspace(lower_logit, upper_logit, capability_points)
    times = (np.linspace(0.0, solution.horizon, time_points) if sample_times is None
             else np.asarray(sample_times, dtype=float))
    if (times.ndim != 1 or times.size < 11 or not np.all(np.isfinite(times))
            or np.min(times) < 0 or np.max(times) > solution.horizon):
        raise ValueError('Counterfactual sample times must stay inside the solved horizon.')
    minimum = math.inf
    minimum_time = math.nan
    minimum_capability = math.nan
    minimum_share = math.nan
    minimum_elasticity = math.nan
    evaluations = 0
    for time in times:
        bounded = np.asarray(solution.raw.sol(float(time)), dtype=float)
        raw = bounded + solution.terminal.terminal_growth * float(time)
        log_capital = float(raw[0])
        log_effective_labor = (
            math.log(solution.initial_effective_labor_scale)
            + effective_labor_growth(solution.parameters) * float(time)
        )

        def objective(logit_value: float) -> float:
            nonlocal evaluations
            evaluations += 1
            if logit_value >= 0.0:
                ratio = 1.0 / (1.0 + math.exp(-logit_value))
            else:
                exponential = math.exp(logit_value)
                ratio = exponential / (1.0 + exponential)
            capability = ratio * solution.terminal.frontier
            return _developer_concavity_margin(
                log_capital,
                log_effective_labor,
                capability,
                solution.terminal,
                solution.parameters,
            )[0]

        grid_values = np.asarray([objective(value) for value in logit_grid])
        grid_index = int(np.argmin(grid_values))
        left = logit_grid[max(0, grid_index - 1)]
        right = logit_grid[min(capability_points - 1, grid_index + 1)]
        if right > left:
            refined = minimize_scalar(
                objective,
                bounds=(float(left), float(right)),
                method="bounded",
                options={"xatol": 1e-10},
            )
            best_logit = float(refined.x)
            best_margin = float(refined.fun)
        else:
            best_logit = float(logit_grid[grid_index])
            best_margin = float(grid_values[grid_index])
        ratio = (
            1.0 / (1.0 + math.exp(-best_logit))
            if best_logit >= 0.0
            else math.exp(best_logit) / (1.0 + math.exp(best_logit))
        )
        capability = ratio * solution.terminal.frontier
        margin, share, elasticity = _developer_concavity_margin(
            log_capital,
            log_effective_labor,
            capability,
            solution.terminal,
            solution.parameters,
        )
        evaluations += 1
        if margin < minimum:
            minimum = margin
            minimum_time = float(time)
            minimum_capability = capability
            minimum_share = share
            minimum_elasticity = elasticity
    return {
        "time_points": len(times),
        "capability_points_per_date": capability_points,
        "function_evaluations": evaluations,
        "minimum_counterfactual_concavity_margin": minimum,
        "date_of_minimum_margin": minimum_time,
        "capability_at_minimum_margin": minimum_capability,
        "capability_frontier_ratio_at_minimum": (
            minimum_capability / solution.terminal.frontier
        ),
        "ai_share_at_minimum_margin": minimum_share,
        "service_capability_elasticity_at_minimum": minimum_elasticity,
        "developer_sufficiency_gate_passes": minimum > 0.0,
    }


def audit_global_solution(
    solution: GlobalFiniteCapBVP,
    *,
    sample_points: int = 801,
) -> dict[str, float | bool | int]:
    """Audit equations, feasibility, boundary conditions, and TVC tails."""

    times = np.linspace(0.0, solution.horizon, sample_points)
    values = np.asarray(solution.raw.sol(times), dtype=float)
    derivative = np.asarray(solution.raw.sol(times, 1), dtype=float)
    reconstructed_rhs = dated_bounded_dynamics(
        times,
        values,
        solution.terminal,
        solution.parameters,
        solution.initial_effective_labor_scale,
    )
    levels = reconstruct_levels(times, values, solution)
    p = solution.parameters
    initial_targets = initial_raw_coordinates(
        solution.terminal,
        solution.initial_capital,
        solution.initial_capability,
    )
    boundary = global_boundary_residual(
        values[:, 0],
        values[:, -1],
        initial_targets,
        solution.horizon,
        solution.initial_effective_labor_scale,
        solution.terminal,
        solution.linearization,
        p,
    )
    population = p.initial_population * np.exp(p.population_growth * times)
    household_tvc_log = (
        -p.discount * times
        + np.log(population)
        + levels["log_capital"]
        - levels["log_consumption"]
    )
    discount_integral = cumulative_trapezoid(
        levels["net_interest_rate"], times, initial=0.0
    )
    developer_tvc_log = (
        -discount_integral
        + levels["log_shadow_value"]
        + levels["log_capability"]
    )
    minimum_log_level = min(
        float(np.min(levels[name]))
        for name in (
            "log_capital",
            "log_capability",
            "log_consumption",
            "log_shadow_value",
            "log_inference_compute",
            "log_research_compute",
        )
    )
    maximum_capability_ratio = float(
        np.max(levels["capability"] / solution.terminal.frontier)
    )
    maximum_capability_log_ratio = float(
        np.max(
            levels["log_capability"] - math.log(solution.terminal.frontier)
        )
    )
    maximum_absolute_bounded_coordinate = float(np.max(np.abs(values)))
    maximum_absolute_capability_logit = float(np.max(np.abs(
        values[1] + solution.terminal.terminal_growth * times
    )))
    maximum_equation_residual = float(
        np.max(np.abs(derivative - reconstructed_rhs))
    )
    return {
        "success": bool(solution.raw.success),
        "horizon": solution.horizon,
        "nodes": int(solution.raw.x.size),
        "iterations": int(solution.raw.niter),
        "maximum_rms_residual": float(np.max(solution.raw.rms_residuals)),
        "maximum_equation_residual": maximum_equation_residual,
        "maximum_boundary_residual": float(np.max(np.abs(boundary))),
        "initial_capital_error": float(
            abs(math.exp(levels["log_capital"][0]) - solution.initial_capital)
        ),
        "initial_capability_error": float(
            abs(levels["capability"][0] - solution.initial_capability)
        ),
        "minimum_log_positive_level": minimum_log_level,
        "maximum_capability_frontier_ratio": maximum_capability_ratio,
        "maximum_capability_log_ratio": maximum_capability_log_ratio,
        "minimum_log_remaining_frontier_share": float(
            np.min(levels["log_remaining_frontier_share"])
        ),
        "maximum_absolute_bounded_coordinate": (
            maximum_absolute_bounded_coordinate
        ),
        "maximum_absolute_capability_logit": (
            maximum_absolute_capability_logit
        ),
        "newton_safeguard_not_binding": (
            maximum_absolute_bounded_coordinate < 140.0
        ),
        "minimum_monopoly_soc_margin": float(
            np.min(levels["monopoly_soc_margin"])
        ),
        "minimum_actual_path_concavity_margin": float(
            np.min(levels["actual_path_concavity_margin"])
        ),
        "terminal_household_tvc_log": float(household_tvc_log[-1]),
        "terminal_developer_tvc_log": float(developer_tvc_log[-1]),
        "asymptotic_household_tvc_growth": p.population_growth - p.discount,
        "asymptotic_developer_tvc_growth": p.population_growth - p.discount,
        "dated_candidate_accepted": bool(
            solution.raw.success
            and maximum_equation_residual < 5e-5
            and float(np.max(np.abs(boundary))) < 5e-7
            and math.isfinite(minimum_log_level)
            and maximum_capability_log_ratio <= 0.0
            and math.isfinite(maximum_absolute_capability_logit)
            and maximum_absolute_bounded_coordinate < 140.0
            and float(np.min(levels["monopoly_soc_margin"])) > 0.0
            and p.population_growth - p.discount < 0.0
        ),
    }


def compare_global_solutions(
    shorter: GlobalFiniteCapBVP,
    longer: GlobalFiniteCapBVP,
    *,
    common_window: float = 2_500.0,
    points: int = 501,
) -> dict[str, float]:
    """Compare paths and initial jumps after a terminal-horizon extension."""

    if shorter.terminal is not longer.terminal:
        raise ValueError("The two solutions use different terminal regimes.")
    window = min(common_window, shorter.horizon, longer.horizon)
    times = np.linspace(0.0, window, points)
    shorter_values = np.asarray(shorter.raw.sol(times), dtype=float)
    longer_values = np.asarray(longer.raw.sol(times), dtype=float)
    initial_jump_change = np.max(
        np.abs(shorter_values[2:, 0] - longer_values[2:, 0])
    )
    return {
        "common_window": float(window),
        "maximum_common_window_coordinate_change": float(
            np.max(np.abs(shorter_values - longer_values))
        ),
        "maximum_initial_jump_change": float(initial_jump_change),
    }


def _solution_payload(
    solution: GlobalFiniteCapBVP,
    audit: dict[str, float | bool | int],
    *,
    horizon_comparison: dict[str, float] | None = None,
    counterfactual_sufficiency: dict[str, float | bool | int] | None = None,
) -> dict[str, Any]:
    payload = {
        "sigma_xl": solution.terminal.sigma_xl,
        "frontier": solution.terminal.frontier,
        "critical_frontier": solution.terminal.critical_frontier,
        "frontier_ratio": solution.terminal.frontier_ratio,
        "terminal_regime": solution.terminal.regime,
        "initial_capital": solution.initial_capital,
        "initial_capability": solution.initial_capability,
        "log_initial_consumption": float(solution.raw.sol(0.0)[2]),
        "log_initial_shadow_value": float(solution.raw.sol(0.0)[3]),
        "continuation_stages": [asdict(item) for item in solution.stages],
        "audit": audit,
    }
    if horizon_comparison is not None:
        payload["horizon_comparison"] = horizon_comparison
    if counterfactual_sufficiency is not None:
        payload["counterfactual_developer_sufficiency"] = (
            counterfactual_sufficiency
        )
    payload["equilibrium_certified"] = bool(
        audit["dated_candidate_accepted"]
        and audit["minimum_actual_path_concavity_margin"] > 0.0
        and (
            counterfactual_sufficiency is not None
            and counterfactual_sufficiency[
                "developer_sufficiency_gate_passes"
            ]
        )
        and (
            horizon_comparison is not None
            and horizon_comparison["maximum_initial_jump_change"] < 2e-5
            and horizon_comparison[
                "maximum_common_window_coordinate_change"
            ] < 2e-5
        )
    )
    return payload


def build_global_analysis() -> dict[str, Any]:
    """Audit global continuation as the finite frontier is enlarged."""

    parameters = PositiveAIBenchmarkParameters()
    seed = balanced_growth_seed(parameters)
    sigma_xl = 1.10
    critical = critical_capability_frontier(sigma_xl, parameters)
    payloads = []
    cases = (
        ("moderate_certification", 1e-6, 32),
        ("large_subcritical_diagnostic", 0.5, 48),
    )
    for label, ratio, continuation_steps in cases:
        terminal = terminal_point(sigma_xl, ratio * critical, parameters)
        base = solve_global_finite_cap_bvp(
            terminal,
            parameters,
            seed.capital,
            seed.capability,
            continuation_steps=continuation_steps,
            nodes=221,
            tolerance=2e-6,
            maximum_nodes=20_000,
        )
        solution = refine_global_horizon(
            base,
            base.horizon + 500.0,
            nodes=401,
            tolerance=1e-8,
            boundary_tolerance=1e-10,
            maximum_nodes=40_000,
        )
        audit = audit_global_solution(solution)
        comparison = compare_global_solutions(base, solution)
        counterfactual = (
            audit_counterfactual_developer_sufficiency(
                solution,
                time_points=61,
                capability_points=81,
            )
            if label == "moderate_certification"
            else None
        )
        payload = _solution_payload(
            solution,
            audit,
            horizon_comparison=comparison,
            counterfactual_sufficiency=counterfactual,
        )
        payload["case"] = label
        payloads.append(payload)
    return {
        "parameters": asdict(parameters),
        "initial_stocks": {
            "capital": seed.capital,
            "capability": seed.capability,
            "source": "unit-elastic positive-AI balanced-growth equilibrium",
        },
        "solutions": payloads,
        "scope": (
            "Global finite-cap BVPs from the paper's common unit-elastic "
            "initial stocks. The moderate cap is subjected to the full "
            "counterfactual developer sufficiency audit. The large-cap path "
            "is retained as a rejected canonical-path diagnostic because the "
            "sufficiency gate fails on the path itself."
        ),
    }


def _parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "numerical_axm" / "global_finite_cap_bvp_analysis.json",
    )
    return parser.parse_args()


def main() -> None:
    arguments = _parse_arguments()
    analysis = build_global_analysis()
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(
        json.dumps(analysis, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(analysis, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
