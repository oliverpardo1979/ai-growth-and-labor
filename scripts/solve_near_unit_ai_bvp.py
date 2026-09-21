"""Continue the positive-AI equilibrium BVP locally in ``sigma_XL``.

The strictly positive-AI branch is first solved at ``sigma_XL = 1`` by
``solve_positive_ai_bvp``.  This module preserves that four-dimensional
collocation problem and then continues the accepted finite-horizon solution in

``varphi = (sigma_XL - 1) / sigma_XL``.

For nonunit elasticities the unit-elastic balanced-growth path is only a dated
reference used to scale ``(K, B, C, q)``.  It is not imposed as an asymptotic
equilibrium.  The two terminal restrictions are the same finite-horizon
linear projection used at the unit-elastic solution, as in the paper's local
continuation proposition.  Consequently, this module establishes and audits a
nearby branch on a fixed finite window; it does not transfer the unit-elastic
infinite-horizon tail to ``sigma_XL != 1``.
"""

from __future__ import annotations

import math
import sys
from dataclasses import dataclass
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
from scipy.optimize import brentq  # noqa: E402

from define_positive_ai_branch import (  # noqa: E402
    PositiveAIBalancedGrowth,
    PositiveAIBenchmarkParameters,
    StableSubspace,
    balanced_growth_seed,
    boundary_jacobians,
    boundary_residual,
)
from solve_positive_ai_bvp import (  # noqa: E402
    PositiveAITransitionSolution,
    solve_transition,
)


@dataclass(frozen=True)
class NearUnitStaticBlock:
    """Dated intratemporal equilibrium conditional on ``K``, ``B``, and ``AL``."""

    log_effective_labor: float
    log_ai_labor_ratio: float
    log_ai_services: float
    log_service_composite: float
    log_output: float
    ai_ces_share: float
    inverse_demand_elasticity: float
    log_inference_compute: float
    monopoly_foc_log_residual: float
    monopoly_soc_margin: float
    monopoly_derivative: float
    output_log_gradient: np.ndarray
    ai_services_log_gradient: np.ndarray
    inference_log_gradient: np.ndarray


@dataclass(frozen=True)
class ElasticityContinuationStage:
    """One accepted continuation step in the regular CES coordinate."""

    sigma_xl: float
    varphi: float
    iterations: int
    nodes: int
    maximum_rms_residual: float
    maximum_boundary_residual: float


@dataclass
class NearUnitAITransitionSolution:
    """A finite-window positive-AI BVP continued away from unit elasticity."""

    raw: Any
    parameters: PositiveAIBenchmarkParameters
    seed: PositiveAIBalancedGrowth
    subspace: StableSubspace
    unit_solution: PositiveAITransitionSolution
    sigma_xl: float
    varphi_schedule: tuple[float, ...]
    stages: tuple[ElasticityContinuationStage, ...]

    @property
    def horizon(self) -> float:
        return float(self.unit_solution.horizon)

    @property
    def initial_deviations(self) -> np.ndarray:
        return np.asarray(self.raw.sol(0.0), dtype=float)

    def evaluate_deviations(self, times: np.ndarray | float) -> np.ndarray:
        return np.asarray(self.raw.sol(times), dtype=float)


def elasticity_coordinate(sigma_xl: float) -> float:
    """Return the CES coordinate with a removable singularity at one."""

    if not math.isfinite(sigma_xl) or sigma_xl <= 0.0:
        raise ValueError("sigma_xl must be finite and strictly positive.")
    return (float(sigma_xl) - 1.0) / float(sigma_xl)


def sigma_from_coordinate(varphi: float) -> float:
    """Invert ``varphi=(sigma-1)/sigma`` on its economic domain."""

    if not math.isfinite(varphi) or varphi >= 1.0:
        raise ValueError("varphi must be finite and strictly smaller than one.")
    return 1.0 / (1.0 - float(varphi))


def elasticity_continuation_schedule(
    target_sigma_xl: float,
    *,
    steps: int,
) -> tuple[float, ...]:
    """Move linearly in the regular CES coordinate from one to the target."""

    if steps < 1:
        raise ValueError("Elasticity continuation requires at least one step.")
    target = elasticity_coordinate(target_sigma_xl)
    if target == 0.0:
        return (0.0,)
    return tuple(float(value) for value in np.linspace(0.0, target, steps + 1))


def _log_ces_adjustment(varphi: float, log_ratio: float, omega_x: float) -> float:
    """Return ``log(omega_L+omega_X exp(varphi*d))/varphi`` stably.

    The two numerical branches evaluate the same exact expression.  ``expm1``
    and ``log1p`` preserve relative precision when ``varphi*d`` is near zero;
    log-sum-exp avoids overflow farther from zero.  No Taylor approximation or
    tolerance-based replacement of the CES is used.
    """

    if varphi == 0.0:
        return omega_x * log_ratio
    h_value = varphi * log_ratio
    if abs(h_value) <= 0.5:
        log_sum = math.log1p(omega_x * math.expm1(h_value))
    else:
        log_sum = float(
            np.logaddexp(math.log1p(-omega_x), math.log(omega_x) + h_value)
        )
    return log_sum / varphi


def _logistic(value: float) -> float:
    if value >= 0.0:
        exponent = math.exp(-value)
        return 1.0 / (1.0 + exponent)
    exponent = math.exp(value)
    return exponent / (1.0 + exponent)


def _unit_log_ai_labor_ratio(
    log_capital: float,
    log_capability: float,
    log_effective_labor: float,
    parameters: PositiveAIBenchmarkParameters,
) -> float:
    beta = (1.0 - parameters.alpha) * parameters.omega_x
    labor_exponent = (1.0 - parameters.alpha) * parameters.omega_l
    log_ai_services = (
        2.0 * math.log(beta)
        + log_capability
        + parameters.alpha * log_capital
        + labor_exponent * log_effective_labor
    ) / (1.0 - beta)
    return log_ai_services - log_effective_labor


def _static_quantities_from_ratio(
    log_capital: float,
    log_capability: float,
    log_effective_labor: float,
    log_ai_labor_ratio: float,
    sigma_xl: float,
    parameters: PositiveAIBenchmarkParameters,
) -> dict[str, float]:
    varphi = elasticity_coordinate(sigma_xl)
    log_service_composite = (
        log_effective_labor
        + _log_ces_adjustment(
            varphi, log_ai_labor_ratio, parameters.omega_x
        )
    )
    log_ai_services = log_effective_labor + log_ai_labor_ratio
    log_output = (
        parameters.alpha * log_capital
        + (1.0 - parameters.alpha) * log_service_composite
    )
    log_share_odds = (
        math.log(parameters.omega_x / parameters.omega_l)
        + varphi * log_ai_labor_ratio
    )
    ai_share = _logistic(log_share_odds)
    # Compute 1-e directly. Subtracting e from one loses significant digits
    # near the zero-marginal-revenue boundary under complementarity.
    revenue_fraction = varphi + (1.0 / sigma_xl - parameters.alpha) * ai_share
    inverse_elasticity = 1.0 - revenue_fraction
    if not 0.0 < revenue_fraction < 1.0:
        raise FloatingPointError(
            "The monopoly markup is not interior at the trial point."
        )
    log_price = (
        math.log1p(-parameters.alpha)
        + math.log(ai_share)
        + log_output
        - log_ai_services
    )
    foc = (
        log_price
        + math.log(revenue_fraction)
        + log_capability
    )
    share_derivative = varphi * ai_share * (1.0 - ai_share)
    inverse_elasticity_derivative = (
        parameters.alpha - 1.0 / sigma_xl
    ) * share_derivative
    foc_derivative = (
        varphi * (1.0 - ai_share)
        + (1.0 - parameters.alpha) * ai_share
        - 1.0
        - inverse_elasticity_derivative / revenue_fraction
    )
    soc_margin = (
        inverse_elasticity * revenue_fraction
        + (parameters.alpha - 1.0 / sigma_xl)
        * (1.0 - 1.0 / sigma_xl)
        * ai_share
        * (1.0 - ai_share)
    )
    return {
        "log_ai_services": log_ai_services,
        "log_service_composite": log_service_composite,
        "log_output": log_output,
        "ai_share": ai_share,
        "inverse_elasticity": inverse_elasticity,
        "log_price": log_price,
        "foc": foc,
        "foc_derivative": foc_derivative,
        "soc_margin": soc_margin,
    }


def solve_monopoly_static_block(
    log_capital: float,
    log_capability: float,
    log_effective_labor: float,
    sigma_xl: float,
    parameters: PositiveAIBenchmarkParameters,
) -> NearUnitStaticBlock:
    """Solve the unique pointwise monopoly choice and its exact derivatives."""

    varphi = elasticity_coordinate(sigma_xl)
    unit_ratio = _unit_log_ai_labor_ratio(
        log_capital, log_capability, log_effective_labor, parameters
    )

    def residual(log_ratio: float) -> float:
        if varphi < 0:
            # With complementary inputs, large X makes marginal revenue
            # nonpositive. This is outside the root's domain, not a missing
            # monopoly optimum. Its limiting log-FOC residual is -infinity.
            # Keep this analytical boundary while expanding the root bracket.
            share = _logistic(math.log(parameters.omega_x/parameters.omega_l)
                              + varphi*log_ratio)
            if varphi + (1/sigma_xl-parameters.alpha)*share <= 0:
                return -math.inf
        return _static_quantities_from_ratio(
            log_capital,
            log_capability,
            log_effective_labor,
            log_ratio,
            sigma_xl,
            parameters,
        )["foc"]

    if varphi == 0.0:
        log_ratio = unit_ratio
    else:
        width = 1.0
        lower = unit_ratio - width
        upper = unit_ratio + width
        lower_value = residual(lower)
        upper_value = residual(upper)
        for _ in range(60):
            if lower_value * upper_value <= 0.0:
                break
            width *= 2.0
            lower = unit_ratio - width
            upper = unit_ratio + width
            lower_value = residual(lower)
            upper_value = residual(upper)
        else:
            raise RuntimeError(
                "Could not bracket the unique monopoly service choice."
            )
        log_ratio = float(
            brentq(
                residual,
                lower,
                upper,
                xtol=1e-12,
                rtol=4.0 * np.finfo(float).eps,
                maxiter=100,
            )
        )

    block = _static_quantities_from_ratio(
        log_capital,
        log_capability,
        log_effective_labor,
        log_ratio,
        sigma_xl,
        parameters,
    )
    if varphi < 0.0:
        # Brent's tolerance is in log(X/AL), not the log first-order condition.
        # Near zero marginal revenue, polish in residual units and inspect
        # adjacent floating-point choices. This tightens the solution without
        # altering the FOC or any equilibrium-admission tolerance.
        for _ in range(6):
            if abs(block["foc"]) <= 1e-11:
                break
            proposal = log_ratio - block["foc"] / block["foc_derivative"]
            candidates = [proposal, np.nextafter(proposal, -math.inf),
                          np.nextafter(proposal, math.inf)]
            best_ratio, best_block = log_ratio, block
            for candidate in candidates:
                try:
                    trial = _static_quantities_from_ratio(
                        log_capital, log_capability, log_effective_labor,
                        float(candidate), sigma_xl, parameters)
                except FloatingPointError:
                    continue
                if abs(trial["foc"]) < abs(best_block["foc"]):
                    best_ratio, best_block = float(candidate), trial
            if best_ratio == log_ratio:
                break
            log_ratio, block = best_ratio, best_block
    derivative = float(block["foc_derivative"])
    if derivative >= 0.0:
        raise FloatingPointError(
            "The solved monopoly FOC does not have the required negative slope."
        )

    # Implicit derivatives of d=log(X/AL) with respect to (log K, log B).
    ratio_gradient = np.asarray(
        [
            -parameters.alpha / derivative,
            -1.0 / derivative,
            0.0,
            0.0,
        ]
    )
    ai_share = float(block["ai_share"])
    output_gradient = np.asarray(
        [parameters.alpha, 0.0, 0.0, 0.0]
    ) + (1.0 - parameters.alpha) * ai_share * ratio_gradient
    ai_services_gradient = ratio_gradient.copy()
    inference_gradient = ai_services_gradient - np.asarray(
        [0.0, 1.0, 0.0, 0.0]
    )

    return NearUnitStaticBlock(
        log_effective_labor=float(log_effective_labor),
        log_ai_labor_ratio=float(log_ratio),
        log_ai_services=float(block["log_ai_services"]),
        log_service_composite=float(block["log_service_composite"]),
        log_output=float(block["log_output"]),
        ai_ces_share=ai_share,
        inverse_demand_elasticity=float(block["inverse_elasticity"]),
        log_inference_compute=float(
            block["log_ai_services"] - log_capability
        ),
        monopoly_foc_log_residual=float(block["foc"]),
        monopoly_soc_margin=float(block["soc_margin"]),
        monopoly_derivative=derivative,
        output_log_gradient=output_gradient,
        ai_services_log_gradient=ai_services_gradient,
        inference_log_gradient=inference_gradient,
    )


def _reference_logs(
    times: np.ndarray,
    seed: PositiveAIBalancedGrowth,
) -> np.ndarray:
    rates = np.asarray(
        [
            seed.output_growth,
            seed.capability_growth,
            seed.output_growth,
            seed.shadow_value_growth,
        ]
    )
    initial = np.log(
        np.asarray(
            [seed.capital, seed.capability, seed.consumption, seed.shadow_value]
        )
    )
    return initial[:, None] + rates[:, None] * times[None, :]


def dated_normalized_dynamics(
    times: np.ndarray | float,
    deviations: np.ndarray,
    sigma_xl: float,
    parameters: PositiveAIBenchmarkParameters,
    seed: PositiveAIBalancedGrowth | None = None,
) -> np.ndarray:
    """Evaluate the dated four-equation system around the unit BGP reference."""

    seed = seed or balanced_growth_seed(parameters)
    time_values = np.atleast_1d(np.asarray(times, dtype=float))
    values = np.asarray(deviations, dtype=float)
    scalar_input = values.ndim == 1
    if scalar_input:
        values = values[:, None]
    if values.shape != (4, time_values.size):
        raise ValueError("Expected four deviations at every supplied time.")

    raw_logs = _reference_logs(time_values, seed) + values
    derivatives = np.empty_like(values)
    reference_rates = np.asarray(
        [
            seed.output_growth,
            seed.capability_growth,
            seed.output_growth,
            seed.shadow_value_growth,
        ]
    )
    for index, time in enumerate(time_values):
        log_capital, log_capability, log_consumption, log_shadow = raw_logs[
            :, index
        ]
        log_effective_labor = (
            math.log(parameters.initial_labor_productivity)
            + math.log(parameters.initial_population)
            + (parameters.labor_productivity_growth
               + parameters.population_growth)
            * float(time)
        )
        static = solve_monopoly_static_block(
            float(log_capital),
            float(log_capability),
            log_effective_labor,
            sigma_xl,
            parameters,
        )
        log_research = (
            log_shadow
            + math.log(parameters.chi)
            + math.log(parameters.eta)
            + parameters.eta * log_capability
        ) / (1.0 - parameters.eta)
        capability_growth = math.exp(
            math.log(parameters.chi)
            + parameters.eta * (log_capability + log_research)
            - log_capability
        )
        output_capital = math.exp(static.log_output - log_capital)
        consumption_capital = math.exp(log_consumption - log_capital)
        inference_capital = math.exp(
            static.log_inference_compute - log_capital
        )
        research_capital = math.exp(log_research - log_capital)
        inference_shadow_capability = math.exp(
            static.log_ai_services - log_shadow - 2.0 * log_capability
        )
        raw_rates = np.asarray(
            [
                output_capital
                - consumption_capital
                - inference_capital
                - research_capital
                - parameters.depreciation,
                capability_growth,
                parameters.population_growth
                + parameters.alpha * output_capital
                - parameters.depreciation
                - parameters.discount,
                parameters.alpha * output_capital
                - parameters.depreciation
                - inference_shadow_capability
                - parameters.eta * capability_growth,
            ]
        )
        derivatives[:, index] = raw_rates - reference_rates
    return derivatives[:, 0] if scalar_input else derivatives


def dated_normalized_jacobian(
    times: np.ndarray | float,
    deviations: np.ndarray,
    sigma_xl: float,
    parameters: PositiveAIBenchmarkParameters,
    seed: PositiveAIBalancedGrowth | None = None,
) -> np.ndarray:
    """Analytic state Jacobian, including the monopoly implicit derivative."""

    seed = seed or balanced_growth_seed(parameters)
    time_values = np.atleast_1d(np.asarray(times, dtype=float))
    values = np.asarray(deviations, dtype=float)
    scalar_input = values.ndim == 1
    if scalar_input:
        values = values[:, None]
    if values.shape != (4, time_values.size):
        raise ValueError("Expected four deviations at every supplied time.")

    raw_logs = _reference_logs(time_values, seed) + values
    jacobians = np.empty((4, 4, time_values.size))
    unit_capital = np.asarray([1.0, 0.0, 0.0, 0.0])
    unit_capability = np.asarray([0.0, 1.0, 0.0, 0.0])
    unit_consumption = np.asarray([0.0, 0.0, 1.0, 0.0])
    research_gradient = np.asarray(
        [
            0.0,
            parameters.eta / (1.0 - parameters.eta),
            0.0,
            1.0 / (1.0 - parameters.eta),
        ]
    )
    capability_growth_gradient = np.asarray(
        [
            0.0,
            (2.0 * parameters.eta - 1.0) / (1.0 - parameters.eta),
            0.0,
            parameters.eta / (1.0 - parameters.eta),
        ]
    )

    for index, time in enumerate(time_values):
        log_capital, log_capability, log_consumption, log_shadow = raw_logs[
            :, index
        ]
        log_effective_labor = (
            math.log(parameters.initial_labor_productivity)
            + math.log(parameters.initial_population)
            + (parameters.labor_productivity_growth
               + parameters.population_growth)
            * float(time)
        )
        static = solve_monopoly_static_block(
            float(log_capital),
            float(log_capability),
            log_effective_labor,
            sigma_xl,
            parameters,
        )
        log_research = (
            log_shadow
            + math.log(parameters.chi)
            + math.log(parameters.eta)
            + parameters.eta * log_capability
        ) / (1.0 - parameters.eta)
        output_capital = math.exp(static.log_output - log_capital)
        consumption_capital = math.exp(log_consumption - log_capital)
        inference_capital = math.exp(
            static.log_inference_compute - log_capital
        )
        research_capital = math.exp(log_research - log_capital)
        capability_growth = math.exp(
            math.log(parameters.chi)
            + parameters.eta * (log_capability + log_research)
            - log_capability
        )
        inference_shadow_capability = math.exp(
            static.log_ai_services - log_shadow - 2.0 * log_capability
        )

        output_capital_gradient = static.output_log_gradient - unit_capital
        consumption_capital_gradient = unit_consumption - unit_capital
        inference_capital_gradient = (
            static.inference_log_gradient - unit_capital
        )
        research_capital_gradient = research_gradient - unit_capital
        inference_shadow_gradient = (
            static.ai_services_log_gradient
            - np.asarray([0.0, 2.0, 0.0, 1.0])
        )

        jacobians[0, :, index] = (
            output_capital * output_capital_gradient
            - consumption_capital * consumption_capital_gradient
            - inference_capital * inference_capital_gradient
            - research_capital * research_capital_gradient
        )
        jacobians[1, :, index] = (
            capability_growth * capability_growth_gradient
        )
        jacobians[2, :, index] = (
            parameters.alpha
            * output_capital
            * output_capital_gradient
        )
        jacobians[3, :, index] = (
            parameters.alpha
            * output_capital
            * output_capital_gradient
            - inference_shadow_capability * inference_shadow_gradient
            - parameters.eta
            * capability_growth
            * capability_growth_gradient
        )
    return jacobians[:, :, 0] if scalar_input else jacobians


def solve_near_unit_transition(
    parameters: PositiveAIBenchmarkParameters,
    initial_capital: float,
    initial_capability: float,
    target_sigma_xl: float,
    *,
    accepted_unit_solution: PositiveAITransitionSolution | None = None,
    horizons: tuple[float, ...] = (100.0, 150.0, 200.0, 250.0),
    stock_continuation_steps: int = 10,
    elasticity_continuation_steps: int = 4,
    initial_nodes: int = 121,
    tolerance: float = 1e-8,
    boundary_tolerance: float = 1e-10,
    maximum_nodes: int = 20_000,
) -> NearUnitAITransitionSolution:
    """Solve at one, then continue the same finite-window BVP in elasticity."""

    varphi_schedule = elasticity_continuation_schedule(
        target_sigma_xl, steps=elasticity_continuation_steps
    )
    if accepted_unit_solution is None:
        unit_solution = solve_transition(
            parameters,
            initial_capital,
            initial_capability,
            horizons=horizons,
            continuation_steps=stock_continuation_steps,
            initial_nodes=initial_nodes,
            tolerance=tolerance,
            boundary_tolerance=boundary_tolerance,
            maximum_nodes=maximum_nodes,
        )
    else:
        unit_solution = accepted_unit_solution
        if unit_solution.parameters != parameters:
            raise ValueError(
                "The accepted unit solution uses different parameters."
            )
        if not math.isclose(
            unit_solution.initial_stocks.capital,
            initial_capital,
            rel_tol=0.0,
            abs_tol=1e-12,
        ) or not math.isclose(
            unit_solution.initial_stocks.capability,
            initial_capability,
            rel_tol=0.0,
            abs_tol=1e-12,
        ):
            raise ValueError(
                "The accepted unit solution uses different initial stocks."
            )
        if not math.isclose(
            unit_solution.horizon,
            float(horizons[-1]),
            rel_tol=0.0,
            abs_tol=1e-12,
        ):
            raise ValueError(
                "The accepted unit solution has a different terminal horizon."
            )
    seed = unit_solution.seed
    subspace = unit_solution.subspace
    target_states = np.asarray(
        [
            math.log(initial_capital / seed.capital),
            math.log(initial_capability / seed.capability),
        ]
    )
    derivative_left, derivative_right = boundary_jacobians(subspace)
    result = unit_solution.raw
    records: list[ElasticityContinuationStage] = []

    for varphi in varphi_schedule[1:]:
        sigma_xl = sigma_from_coordinate(varphi)
        mesh = np.asarray(result.x, dtype=float)
        guess = np.asarray(result.y, dtype=float)

        def ode(times: np.ndarray, states: np.ndarray) -> np.ndarray:
            return dated_normalized_dynamics(
                times, states, sigma_xl, parameters, seed
            )

        def ode_jacobian(
            times: np.ndarray, states: np.ndarray
        ) -> np.ndarray:
            return dated_normalized_jacobian(
                times, states, sigma_xl, parameters, seed
            )

        def boundary(left: np.ndarray, right: np.ndarray) -> np.ndarray:
            return boundary_residual(left, right, target_states, subspace)

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
                "Near-unit elasticity continuation failed at "
                f"sigma_XL={sigma_xl:.12g}: {result.message}"
            )
        rms = np.asarray(getattr(result, "rms_residuals", [math.nan]))
        boundary_value = boundary(result.y[:, 0], result.y[:, -1])
        records.append(
            ElasticityContinuationStage(
                sigma_xl=float(sigma_xl),
                varphi=float(varphi),
                iterations=int(result.niter),
                nodes=int(result.x.size),
                maximum_rms_residual=float(np.nanmax(rms)),
                maximum_boundary_residual=float(
                    np.max(np.abs(boundary_value))
                ),
            )
        )

    return NearUnitAITransitionSolution(
        raw=result,
        parameters=parameters,
        seed=seed,
        subspace=subspace,
        unit_solution=unit_solution,
        sigma_xl=float(target_sigma_xl),
        varphi_schedule=varphi_schedule,
        stages=tuple(records),
    )


def _reconstructed_dynamics(
    time: float,
    deviations: np.ndarray,
    solution: NearUnitAITransitionSolution,
) -> np.ndarray:
    """Reconstruct the dated laws for an independent IVP integration."""

    # This scalar route is deliberately separate from the collocation wrapper.
    # The static root is common, and its equation is audited independently.
    return dated_normalized_dynamics(
        float(time),
        np.asarray(deviations, dtype=float),
        solution.sigma_xl,
        solution.parameters,
        solution.seed,
    )


def segmented_backward_reconstruction_gap(
    solution: NearUnitAITransitionSolution,
    *,
    segment_length: float = 10.0,
    points_per_segment: int = 21,
) -> tuple[float, int]:
    """Reintegrate short segments with a different integrator."""

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
        boundaries.append(solution.horizon)
    else:
        boundaries[-1] = solution.horizon

    maximum_gap = 0.0
    evaluations = 0
    for left, right in zip(boundaries[:-1], boundaries[1:]):
        terminal = np.asarray(solution.raw.sol(right), dtype=float)
        reverse = solve_ivp(
            lambda reverse_time, state: -_reconstructed_dynamics(
                right - reverse_time, state, solution
            ),
            (0.0, right - left),
            terminal,
            method="DOP853",
            rtol=1e-10,
            atol=1e-13,
            max_step=min(0.5, right - left),
            dense_output=True,
        )
        if not reverse.success:
            raise RuntimeError(
                "Near-unit backward reconstruction failed on "
                f"[{left:g},{right:g}]: {reverse.message}"
            )
        times = np.linspace(left, right, points_per_segment)
        reconstructed = reverse.sol(right - times)
        collocation = solution.raw.sol(times)
        maximum_gap = max(
            maximum_gap,
            float(np.max(np.abs(reconstructed - collocation))),
        )
        evaluations += int(reverse.nfev)
    return maximum_gap, evaluations


def audit_near_unit_solution(
    solution: NearUnitAITransitionSolution,
    *,
    sample_points: int = 501,
) -> dict[str, float | bool | int]:
    """Audit static equations, dynamic equations, feasibility, and boundary data."""

    if sample_points < 11:
        raise ValueError("sample_points must be at least eleven.")
    times = np.linspace(0.0, solution.horizon, sample_points)
    deviations = np.asarray(solution.raw.sol(times), dtype=float)
    collocation_derivative = np.asarray(
        solution.raw.sol(times, 1), dtype=float
    )
    reconstructed = dated_normalized_dynamics(
        times,
        deviations,
        solution.sigma_xl,
        solution.parameters,
        solution.seed,
    )
    raw_logs = _reference_logs(times, solution.seed) + deviations

    resource_residuals: list[float] = []
    euler_residuals: list[float] = []
    capability_residuals: list[float] = []
    costate_residuals: list[float] = []
    monopoly_residuals: list[float] = []
    research_foc_residuals: list[float] = []
    minimum_consumption_share = math.inf
    minimum_research_share = math.inf
    minimum_inference_share = math.inf
    minimum_soc_margin = math.inf
    interest_rates: list[float] = []

    reference_rates = np.asarray(
        [
            solution.seed.output_growth,
            solution.seed.capability_growth,
            solution.seed.output_growth,
            solution.seed.shadow_value_growth,
        ]
    )
    for index, time in enumerate(times):
        log_capital, log_capability, log_consumption, log_shadow = raw_logs[
            :, index
        ]
        log_effective_labor = (
            math.log(solution.parameters.initial_labor_productivity)
            + math.log(solution.parameters.initial_population)
            + (solution.parameters.labor_productivity_growth
               + solution.parameters.population_growth)
            * float(time)
        )
        static = solve_monopoly_static_block(
            float(log_capital),
            float(log_capability),
            log_effective_labor,
            solution.sigma_xl,
            solution.parameters,
        )
        log_research = (
            log_shadow
            + math.log(solution.parameters.chi)
            + math.log(solution.parameters.eta)
            + solution.parameters.eta * log_capability
        ) / (1.0 - solution.parameters.eta)
        capability_growth = math.exp(
            math.log(solution.parameters.chi)
            + solution.parameters.eta * (log_capability + log_research)
            - log_capability
        )
        output_capital = math.exp(static.log_output - log_capital)
        consumption_capital = math.exp(log_consumption - log_capital)
        inference_capital = math.exp(
            static.log_inference_compute - log_capital
        )
        research_capital = math.exp(log_research - log_capital)
        inference_shadow = math.exp(
            static.log_ai_services - log_shadow - 2.0 * log_capability
        )
        raw_growth = collocation_derivative[:, index] + reference_rates
        resource_residuals.append(
            raw_growth[0]
            - (
                output_capital
                - consumption_capital
                - inference_capital
                - research_capital
                - solution.parameters.depreciation
            )
        )
        capability_residuals.append(raw_growth[1] - capability_growth)
        euler_residuals.append(
            raw_growth[2]
            - (
                solution.parameters.population_growth
                + solution.parameters.alpha * output_capital
                - solution.parameters.depreciation
                - solution.parameters.discount
            )
        )
        costate_residuals.append(
            raw_growth[3]
            - (
                solution.parameters.alpha * output_capital
                - solution.parameters.depreciation
                - inference_shadow
                - solution.parameters.eta * capability_growth
            )
        )
        monopoly_residuals.append(static.monopoly_foc_log_residual)
        research_foc_residuals.append(
            log_shadow
            + math.log(solution.parameters.chi)
            + math.log(solution.parameters.eta)
            + solution.parameters.eta * log_capability
            + (solution.parameters.eta - 1.0) * log_research
        )
        output = math.exp(static.log_output)
        minimum_consumption_share = min(
            minimum_consumption_share, math.exp(log_consumption) / output
        )
        minimum_research_share = min(
            minimum_research_share, math.exp(log_research) / output
        )
        minimum_inference_share = min(
            minimum_inference_share,
            math.exp(static.log_inference_compute) / output,
        )
        minimum_soc_margin = min(
            minimum_soc_margin, static.monopoly_soc_margin
        )
        interest_rates.append(
            solution.parameters.alpha * output_capital
            - solution.parameters.depreciation
        )

    target_states = solution.unit_solution.initial_deviations[:2]
    boundary = boundary_residual(
        deviations[:, 0], deviations[:, -1], target_states, solution.subspace
    )
    backward_gap, backward_evaluations = (
        segmented_backward_reconstruction_gap(solution)
    )
    household_log_tvc = (
        -solution.parameters.discount * times
        + math.log(solution.parameters.initial_population)
        + solution.parameters.population_growth * times
        + raw_logs[0]
        - raw_logs[2]
    )
    interest_array = np.asarray(interest_rates)
    developer_log_tvc_change = float(
        raw_logs[3, -1]
        + raw_logs[1, -1]
        - raw_logs[3, 0]
        - raw_logs[1, 0]
        - np.trapezoid(interest_array, times)
    )
    rms = np.asarray(getattr(solution.raw, "rms_residuals", [math.nan]))
    return {
        "success": bool(solution.raw.success),
        "sigma_xl": float(solution.sigma_xl),
        "maximum_rms_residual": float(np.nanmax(rms)),
        "max_normalized_ode_residual": float(
            np.max(np.abs(collocation_derivative - reconstructed))
        ),
        "max_resource_residual": float(np.max(np.abs(resource_residuals))),
        "max_euler_residual": float(np.max(np.abs(euler_residuals))),
        "max_capability_residual": float(
            np.max(np.abs(capability_residuals))
        ),
        "max_costate_residual": float(np.max(np.abs(costate_residuals))),
        "max_monopoly_foc_log_residual": float(
            np.max(np.abs(monopoly_residuals))
        ),
        "max_research_foc_log_residual": float(
            np.max(np.abs(research_foc_residuals))
        ),
        "max_boundary_residual": float(np.max(np.abs(boundary))),
        "minimum_consumption_share": float(minimum_consumption_share),
        "minimum_research_share": float(minimum_research_share),
        "minimum_inference_share": float(minimum_inference_share),
        "minimum_monopoly_soc_margin": float(minimum_soc_margin),
        "household_log_tvc_change": float(
            household_log_tvc[-1] - household_log_tvc[0]
        ),
        "developer_log_tvc_change": developer_log_tvc_change,
        "segmented_backward_reconstruction_gap": float(backward_gap),
        "segmented_backward_function_evaluations": int(backward_evaluations),
        "elasticity_continuation_stages": int(len(solution.stages)),
        "final_nodes": int(solution.raw.x.size),
    }
