"""Terminal analysis and local BVPs for the finite-cap AI economy.

The finite capability frontier does not turn a dated solution into an
equilibrium by itself.  It does, however, create finite terminal regimes that
can close an infinite-horizon boundary-value problem.  This module implements
the two normalizations derived in the paper for all positive ``sigma_XL``:

* in a positive-labor-share regime, quantities are scaled by effective labor
  ``AN`` and the capability gap is represented by ``d=(Bbar-B)AN``;
* above the critical frontier, capital is the growing scale and the regular
  CES coordinate is ``h=(AN/K)**varphi`` together with
  ``d=(Bbar-B)K``.

For each regime the code constructs the terminal point, its analytic
Jacobian, the stable subspace, and the two terminal projection conditions.
It can also solve a small nonlinear BVP near the terminal point.  That local
calculation verifies the saddle-path architecture; it is not presented as a
transition from the paper's date-zero stocks.
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

from scipy.integrate import solve_bvp  # noqa: E402
from scipy.optimize import brentq  # noqa: E402

from define_positive_ai_branch import (  # noqa: E402
    PositiveAIBenchmarkParameters,
)
from solve_near_unit_ai_bvp import (  # noqa: E402
    _log_ces_adjustment, _logistic, solve_monopoly_static_block,
)


@dataclass(frozen=True)
class FiniteCapTerminalPoint:
    """Terminal ratios and coordinates for one side of the critical frontier."""

    sigma_xl: float
    frontier: float
    critical_frontier: float | None
    frontier_ratio: float | None
    regime: str
    terminal_growth: float
    net_interest_rate: float
    ai_ces_share: float
    labor_income_share: float
    inference_output_share: float
    consumption_output_share: float
    research_compute: float
    coordinate_names: tuple[str, ...]
    predetermined_indices: tuple[int, ...]
    jump_indices: tuple[int, ...]
    coordinates: np.ndarray
    auxiliary: dict[str, float]


@dataclass(frozen=True)
class TerminalLinearization:
    """Analytic terminal Jacobian and the associated saddle-path objects."""

    jacobian: np.ndarray
    eigenvalues: np.ndarray
    stable_eigenvalues: np.ndarray
    unstable_eigenvalues: np.ndarray
    stable_basis: np.ndarray
    terminal_matrix: np.ndarray
    state_projection_determinant: float
    state_projection_condition_number: float


@dataclass(frozen=True)
class LocalFiniteCapBVP:
    """One nonlinear BVP solved in a neighborhood of a terminal regime."""

    raw: Any
    terminal: FiniteCapTerminalPoint
    linearization: TerminalLinearization
    horizon: float
    initial_predetermined_deviations: np.ndarray
    maximum_boundary_residual: float


def elasticity_coordinate(sigma_xl: float) -> float:
    """Return the regular CES coordinate varphi=(sigma-1)/sigma."""

    if not math.isfinite(sigma_xl) or sigma_xl <= 0.0:
        raise ValueError("sigma_XL must be finite and strictly positive.")
    return (sigma_xl - 1.0) / sigma_xl


def effective_labor_growth(parameters: PositiveAIBenchmarkParameters) -> float:
    """Growth rate of A N in the paper's continuous-time convention."""

    return parameters.population_growth + parameters.labor_productivity_growth


def capability_exponent(parameters: PositiveAIBenchmarkParameters) -> float:
    """Return theta=(1-alpha)/alpha without changing the paper's notation."""

    return (1.0 - parameters.alpha) / parameters.alpha


def ai_only_scale(
    sigma_xl: float,
    parameters: PositiveAIBenchmarkParameters,
) -> float:
    """Return D_sigma in the AI-dominated output-capital ratio."""

    if sigma_xl <= 1.0:
        raise ValueError("The AI-dominated terminal regime requires sigma_XL > 1.")
    theta = capability_exponent(parameters)
    exponent = sigma_xl / (sigma_xl - 1.0)
    return (
        (1.0 - parameters.alpha) ** 2
        * parameters.omega_x**exponent
    ) ** theta


def log_critical_capability_frontier(
    sigma_xl: float,
    parameters: PositiveAIBenchmarkParameters,
) -> float:
    """Return log Bbar_c; the threshold is not defined at unit elasticity."""

    elasticity_coordinate(sigma_xl)
    if sigma_xl == 1.0:
        raise ValueError("No critical frontier is defined at sigma_XL=1.")
    theta = capability_exponent(parameters)
    required_output_capital = (
        parameters.discount
        + parameters.labor_productivity_growth
        + parameters.depreciation
    ) / parameters.alpha
    log_scale = theta * (
        2.0 * math.log1p(-parameters.alpha)
        + sigma_xl / (sigma_xl - 1.0) * math.log(parameters.omega_x)
    )
    return (math.log(required_output_capital) - log_scale) / theta


def critical_capability_frontier(sigma_xl, parameters):
    """Report the threshold; overflow/underflow is metadata only.

    Regime decisions use logarithms, so neither infinity nor a rounded zero
    here is substituted into the model's equations.
    """
    value = log_critical_capability_frontier(sigma_xl, parameters)
    return math.exp(value) if value <= math.log(sys.float_info.max) else math.inf


def _labor_log_ai_labor_ratio(sigma_xl, frontier, parameters, iterations=160):
    """Solve the terminal service ratio without dividing by sigma-1.

    At Y/K=R, K=Z*R**(-1/(1-alpha)). Substitution in the monopoly
    condition determines X/(AL). The CES evaluator uses exact log1p/expm1
    identities, including its analytical Cobb-Douglas value at sigma=1.
    """
    phi = elasticity_coordinate(sigma_xl)
    if not math.isfinite(frontier) or frontier <= 0:
        raise ValueError("The frontier must be positive and finite.")
    if sigma_xl != 1:
        distance = math.log(frontier) - log_critical_capability_frontier(sigma_xl, parameters)
        if distance * (1 - sigma_xl) <= 0:
            raise ValueError("The frontier does not support a positive labor-share terminal point.")
    p = parameters
    required = (p.discount + p.labor_productivity_growth + p.depreciation) / p.alpha
    beta = (1-p.alpha)*p.omega_x
    log_k_unit = (beta*math.log(beta*beta*frontier)
                  + (beta-1)*math.log(required))/(1-p.alpha-beta)
    center = math.log(frontier*beta*beta*required) + log_k_unit
    if sigma_xl == 1:
        return center

    def residual(log_x):
        share = _logistic(math.log(p.omega_x/p.omega_l) + phi*log_x)
        margin = phi + (1/sigma_xl-p.alpha)*share
        if margin <= 0 or share == 0:
            return math.inf
        log_z = _log_ces_adjustment(phi, log_x, p.omega_x)
        return (log_x-log_z + p.alpha/(1-p.alpha)*math.log(required)
                - math.log((1-p.alpha)*share*margin) - math.log(frontier))

    width = 1.0
    for _ in range(iterations):
        lower, upper = center-width, center+width
        if residual(lower) < 0 < residual(upper):
            # Roundoff-level root tolerance, unrelated to economic admission.
            return brentq(residual, lower, upper, xtol=2e-13,
                          rtol=4*np.finfo(float).eps, maxiter=iterations)
        width *= 2
    raise RuntimeError("Failed to bracket the positive-labor-share terminal ratio.")


def _inverse_demand_elasticity(
    share: float,
    sigma_xl: float,
    parameters: PositiveAIBenchmarkParameters,
) -> float:
    return (1.0 - share) / sigma_xl + parameters.alpha * share


def log_share_map(
    share: float,
    sigma_xl: float,
    parameters: PositiveAIBenchmarkParameters,
) -> float:
    """Evaluate log H_sigma(s) without overflowing near unit elasticity."""

    if not 0.0 < share <= 1.0:
        raise ValueError("The AI CES share must lie in (0,1].")
    theta = capability_exponent(parameters)
    inverse_elasticity = _inverse_demand_elasticity(
        share, sigma_xl, parameters
    )
    return theta * (
        math.log1p(-parameters.alpha)
        + math.log(share)
        + math.log1p(-inverse_elasticity)
        + sigma_xl
        / (sigma_xl - 1.0)
        * (math.log(parameters.omega_x) - math.log(share))
    )


def labor_supported_share(
    sigma_xl: float,
    frontier: float,
    parameters: PositiveAIBenchmarkParameters,
    *,
    iterations: int = 160,
) -> float:
    """Solve the terminal share in any positive-labor-share regime."""
    log_x = _labor_log_ai_labor_ratio(sigma_xl, frontier, parameters, iterations)
    return _logistic(math.log(parameters.omega_x/parameters.omega_l)
                     + elasticity_coordinate(sigma_xl)*log_x)


def _terminal_research_compute(
    growth: float,
    frontier: float,
    parameters: PositiveAIBenchmarkParameters,
) -> float:
    return (
        growth
        * frontier ** (1.0 - parameters.eta)
        / parameters.chi
    ) ** (1.0 / parameters.eta)


def labor_supported_terminal(
    sigma_xl: float,
    frontier: float,
    parameters: PositiveAIBenchmarkParameters,
) -> FiniteCapTerminalPoint:
    """Construct the effective-labor-normalized point in all three regimes."""

    critical = (critical_capability_frontier(sigma_xl, parameters)
                if sigma_xl != 1 else None)
    log_ai_labor_ratio = _labor_log_ai_labor_ratio(sigma_xl, frontier, parameters)
    varphi = elasticity_coordinate(sigma_xl)
    omega_l = 1.0 - parameters.omega_x
    share = _logistic(math.log(parameters.omega_x/omega_l) + varphi*log_ai_labor_ratio)
    inverse_elasticity = _inverse_demand_elasticity(
        share, sigma_xl, parameters
    )
    ai_services = math.exp(log_ai_labor_ratio)
    inference_compute = ai_services / frontier
    inference_share = (
        (1.0 - parameters.alpha)
        * share
        * (1.0 - inverse_elasticity)
    )
    output = inference_compute / inference_share
    required_output_capital = (
        parameters.discount
        + parameters.labor_productivity_growth
        + parameters.depreciation
    ) / parameters.alpha
    capital = output / required_output_capital
    growth = effective_labor_growth(parameters)
    net_interest = parameters.discount + parameters.labor_productivity_growth
    consumption = (
        output
        - inference_compute
        - (parameters.depreciation + growth) * capital
    )
    if consumption <= 0.0:
        raise ValueError("The labor-supported terminal consumption ratio is not positive.")
    research_compute = _terminal_research_compute(
        growth, frontier, parameters
    )
    shadow_value = ai_services / (net_interest * frontier**2)
    gap_scale = research_compute ** (1.0 - parameters.eta) / (
        shadow_value
        * parameters.chi
        * parameters.eta
        * frontier ** (parameters.eta - 1.0)
    )
    return FiniteCapTerminalPoint(
        sigma_xl=sigma_xl,
        frontier=frontier,
        critical_frontier=critical,
        frontier_ratio=(None if critical is None else
                        frontier/critical if critical > 0 else math.inf),
        regime="labor_supported",
        terminal_growth=growth,
        net_interest_rate=net_interest,
        ai_ces_share=share,
        labor_income_share=(1.0 - parameters.alpha) * (1.0 - share),
        inference_output_share=inference_share,
        consumption_output_share=consumption / output,
        research_compute=research_compute,
        coordinate_names=(
            "log_k",
            "log_c",
            "log_d",
            "log_q_tilde",
            "scaled_tau",
        ),
        predetermined_indices=(0, 2, 4),
        jump_indices=(1, 3),
        coordinates=np.asarray(
            [
                math.log(capital),
                math.log(consumption),
                math.log(gap_scale),
                math.log(shadow_value),
                0.0,
            ]
        ),
        auxiliary={
            "effective_labor_growth": growth,
            "capital_effective_labor_ratio": capital,
            "output_effective_labor_ratio": output,
            "consumption_effective_labor_ratio": consumption,
            "ai_services_effective_labor_ratio": ai_services,
            "inference_effective_labor_ratio": inference_compute,
            "gap_scale": gap_scale,
            "shadow_effective_labor_ratio": shadow_value,
        },
    )


def ai_dominated_terminal(
    sigma_xl: float,
    frontier: float,
    parameters: PositiveAIBenchmarkParameters,
) -> FiniteCapTerminalPoint:
    """Construct the capital-normalized terminal point above Bbar_c."""

    critical = critical_capability_frontier(sigma_xl, parameters)
    if not frontier > critical:
        raise ValueError("An AI-dominated terminal point requires Bbar > Bbar_c.")
    scale = ai_only_scale(sigma_xl, parameters)
    theta = capability_exponent(parameters)
    output_capital = scale * frontier**theta
    net_interest = parameters.alpha * output_capital - parameters.depreciation
    growth = parameters.population_growth + net_interest - parameters.discount
    if growth <= effective_labor_growth(parameters):
        raise ValueError("The supplied frontier does not imply AI domination.")
    inference_output_share = (1.0 - parameters.alpha) ** 2
    inference_capital = inference_output_share * output_capital
    ai_services_capital = frontier * inference_capital
    consumption_capital = (
        parameters.alpha * (1.0 - parameters.alpha) * output_capital
        + parameters.discount
        - parameters.population_growth
    )
    research_compute = _terminal_research_compute(
        growth, frontier, parameters
    )
    shadow_capital = ai_services_capital / (
        net_interest * frontier**2
    )
    gap_scale = research_compute ** (1.0 - parameters.eta) / (
        shadow_capital
        * parameters.chi
        * parameters.eta
        * frontier ** (parameters.eta - 1.0)
    )
    return FiniteCapTerminalPoint(
        sigma_xl=sigma_xl,
        frontier=frontier,
        critical_frontier=critical,
        frontier_ratio=frontier / critical,
        regime="ai_dominated",
        terminal_growth=growth,
        net_interest_rate=net_interest,
        ai_ces_share=1.0,
        labor_income_share=0.0,
        inference_output_share=inference_output_share,
        consumption_output_share=consumption_capital / output_capital,
        research_compute=research_compute,
        coordinate_names=("h", "log_d", "log_c", "log_v", "scaled_tau"),
        predetermined_indices=(0, 1, 4),
        jump_indices=(2, 3),
        coordinates=np.asarray(
            [
                0.0,
                math.log(gap_scale),
                math.log(consumption_capital),
                math.log(shadow_capital),
                0.0,
            ]
        ),
        auxiliary={
            "effective_labor_growth": effective_labor_growth(parameters),
            "output_capital_ratio": output_capital,
            "consumption_capital_ratio": consumption_capital,
            "inference_capital_ratio": inference_capital,
            "ai_services_capital_ratio": ai_services_capital,
            "gap_scale": gap_scale,
            "shadow_capital_ratio": shadow_capital,
        },
    )


def terminal_point(
    sigma_xl: float,
    frontier: float,
    parameters: PositiveAIBenchmarkParameters,
) -> FiniteCapTerminalPoint:
    """Dispatch to the normalization selected by the exact threshold."""

    elasticity_coordinate(sigma_xl)
    if not math.isfinite(frontier) or frontier <= 0:
        raise ValueError("The frontier must be positive and finite.")
    if sigma_xl <= 1:
        return labor_supported_terminal(sigma_xl, frontier, parameters)
    distance = math.log(frontier) - log_critical_capability_frontier(sigma_xl, parameters)
    if distance < 0:
        return labor_supported_terminal(sigma_xl, frontier, parameters)
    if distance > 0:
        return ai_dominated_terminal(sigma_xl, frontier, parameters)
    raise ValueError("The knife-edge Bbar=Bbar_c requires a separate normalization.")


def labor_supported_dynamics(
    coordinates: np.ndarray,
    terminal: FiniteCapTerminalPoint,
    parameters: PositiveAIBenchmarkParameters,
) -> np.ndarray:
    """Exact autonomous dynamics below the threshold in terminal coordinates."""

    log_k, log_c, log_d, log_q, scaled_tau = np.asarray(
        coordinates, dtype=float
    )
    capital = math.exp(log_k)
    consumption = math.exp(log_c)
    gap_scale = math.exp(log_d)
    shadow_value = math.exp(log_q)
    frontier = terminal.frontier
    terminal_gap_scale = terminal.auxiliary["gap_scale"]
    tau = scaled_tau * frontier / terminal_gap_scale
    capability = frontier - gap_scale * tau
    if capability <= 0.0:
        raise FloatingPointError("The normalized state implies nonpositive capability.")
    static = solve_monopoly_static_block(
        log_k,
        math.log(capability),
        0.0,
        terminal.sigma_xl,
        parameters,
    )
    output = math.exp(static.log_output)
    ai_services = math.exp(static.log_ai_services)
    inference_compute = math.exp(static.log_inference_compute)
    research_compute = (
        shadow_value
        * gap_scale
        * parameters.chi
        * parameters.eta
        * capability**parameters.eta
        / frontier
    ) ** (1.0 / (1.0 - parameters.eta))
    approach_rate = (
        parameters.chi
        * capability**parameters.eta
        * research_compute**parameters.eta
        / frontier
    )
    capability_growth = approach_rate * gap_scale * tau / capability
    net_interest = parameters.alpha * output / capital - parameters.depreciation
    service_shadow_return = ai_services / (shadow_value * capability**2)
    growth = effective_labor_growth(parameters)
    return np.asarray(
        [
            (
                output
                - consumption
                - inference_compute
                - research_compute * tau
            )
            / capital
            - parameters.depreciation
            - growth,
            net_interest
            - parameters.discount
            - parameters.labor_productivity_growth,
            growth - approach_rate,
            net_interest
            - service_shadow_return
            - parameters.eta * capability_growth
            + approach_rate
            - growth,
            -growth * scaled_tau,
        ]
    )


def _ai_dominated_static_ratios(
    h_value: float,
    capability: float,
    terminal: FiniteCapTerminalPoint,
    parameters: PositiveAIBenchmarkParameters,
) -> tuple[float, float, float]:
    """Return (Y/K, X/K, U/K), including the regular h=0 limit."""

    if h_value < 0.0:
        raise FloatingPointError("The regular CES coordinate h cannot be negative.")
    if h_value == 0.0:
        output = ai_only_scale(
            terminal.sigma_xl, parameters
        ) * capability ** capability_exponent(parameters)
        log_ai_services = (
            math.log(capability)
            + 2.0 * math.log1p(-parameters.alpha)
            + (1.0 - parameters.alpha)
            / elasticity_coordinate(terminal.sigma_xl)
            * math.log(parameters.omega_x)
        ) / parameters.alpha
        ai_services = math.exp(log_ai_services)
        return output, ai_services, ai_services / capability
    effective_labor = h_value ** (
        1.0 / elasticity_coordinate(terminal.sigma_xl)
    )
    static = solve_monopoly_static_block(
        0.0,
        math.log(capability),
        math.log(effective_labor),
        terminal.sigma_xl,
        parameters,
    )
    return (
        math.exp(static.log_output),
        math.exp(static.log_ai_services),
        math.exp(static.log_inference_compute),
    )


def ai_dominated_dynamics(
    coordinates: np.ndarray,
    terminal: FiniteCapTerminalPoint,
    parameters: PositiveAIBenchmarkParameters,
) -> np.ndarray:
    """Exact autonomous dynamics above the threshold in terminal coordinates."""

    h_value, log_d, log_c, log_v, scaled_tau = np.asarray(
        coordinates, dtype=float
    )
    gap_scale = math.exp(log_d)
    consumption_capital = math.exp(log_c)
    shadow_capital = math.exp(log_v)
    varphi = elasticity_coordinate(terminal.sigma_xl)
    tau = (
        scaled_tau
        * terminal.frontier
        / terminal.auxiliary["gap_scale"]
    )
    inverse_capital_scale = tau * h_value ** (1.0 / varphi)
    capability_gap = gap_scale * inverse_capital_scale
    capability = terminal.frontier - capability_gap
    if capability <= 0.0:
        raise FloatingPointError("The normalized state implies nonpositive capability.")
    output_capital, ai_services_capital, inference_capital = (
        _ai_dominated_static_ratios(
            h_value, capability, terminal, parameters
        )
    )
    research_compute = (
        shadow_capital
        * gap_scale
        * parameters.chi
        * parameters.eta
        * capability**parameters.eta
        / terminal.frontier
    ) ** (1.0 / (1.0 - parameters.eta))
    approach_rate = (
        parameters.chi
        * capability**parameters.eta
        * research_compute**parameters.eta
        / terminal.frontier
    )
    research_capital = research_compute * inverse_capital_scale
    capital_growth = (
        output_capital
        - consumption_capital
        - inference_capital
        - research_capital
        - parameters.depreciation
    )
    net_interest = parameters.alpha * output_capital - parameters.depreciation
    service_shadow_return = (
        ai_services_capital / (shadow_capital * capability**2)
    )
    capability_growth = approach_rate * capability_gap / capability
    effective_growth = effective_labor_growth(parameters)
    return np.asarray(
        [
            h_value * varphi * (effective_growth - capital_growth),
            capital_growth - approach_rate,
            parameters.population_growth
            + net_interest
            - parameters.discount
            - capital_growth,
            net_interest
            - service_shadow_return
            - parameters.eta * capability_growth
            + approach_rate
            - capital_growth,
            -effective_growth * scaled_tau,
        ]
    )


def labor_supported_jacobian(
    terminal: FiniteCapTerminalPoint,
    parameters: PositiveAIBenchmarkParameters,
) -> np.ndarray:
    """Return the analytic terminal Jacobian below the critical frontier."""

    log_k, log_c, log_d, log_q, _ = terminal.coordinates
    capital = math.exp(log_k)
    consumption = math.exp(log_c)
    gap_scale = math.exp(log_d)
    frontier = terminal.frontier
    static = solve_monopoly_static_block(
        log_k,
        math.log(frontier),
        0.0,
        terminal.sigma_xl,
        parameters,
    )
    output = math.exp(static.log_output)
    inference_compute = math.exp(static.log_inference_compute)
    output_k, output_b = static.output_log_gradient[:2]
    services_k, services_b = static.ai_services_log_gradient[:2]
    inference_k, inference_b = static.inference_log_gradient[:2]
    net_interest = terminal.net_interest_rate
    growth = terminal.terminal_growth
    research_compute = terminal.research_compute
    eta_ratio = parameters.eta / (1.0 - parameters.eta)
    tau_scale = gap_scale / frontier
    interest_k = (
        parameters.alpha * output / capital * (output_k - 1.0)
    )
    interest_tau = (
        -parameters.alpha
        * output
        / capital
        * output_b
    )
    capital_k = (
        output * output_k - inference_compute * inference_k
    ) / capital - (parameters.depreciation + growth)
    capital_tau = (
        -(output * output_b - inference_compute * inference_b)
        - research_compute / tau_scale
    ) / capital
    service_return_tau = (
        -net_interest * (services_b - 2.0)
    )
    approach_tau = -growth * eta_ratio
    capability_growth_tau = growth
    jacobian = np.zeros((5, 5))
    jacobian[0, 0] = capital_k
    jacobian[0, 1] = -consumption / capital
    jacobian[0, 4] = capital_tau
    jacobian[1, 0] = interest_k
    jacobian[1, 4] = interest_tau
    jacobian[2, 2] = -growth * eta_ratio
    jacobian[2, 3] = -growth * eta_ratio
    jacobian[2, 4] = -approach_tau
    jacobian[3, 0] = interest_k - net_interest * services_k
    jacobian[3, 2] = growth * eta_ratio
    jacobian[3, 3] = net_interest + growth * eta_ratio
    jacobian[3, 4] = (
        interest_tau
        - service_return_tau
        - parameters.eta * capability_growth_tau
        + approach_tau
    )
    jacobian[4, 4] = -growth
    return jacobian


def ai_dominated_jacobian(
    terminal: FiniteCapTerminalPoint,
    parameters: PositiveAIBenchmarkParameters,
) -> np.ndarray:
    """Return the analytic terminal Jacobian above the critical frontier."""

    varphi = elasticity_coordinate(terminal.sigma_xl)
    frontier = terminal.frontier
    output = terminal.auxiliary["output_capital_ratio"]
    inference_compute = terminal.auxiliary["inference_capital_ratio"]
    consumption = terminal.auxiliary["consumption_capital_ratio"]
    growth = terminal.terminal_growth
    net_interest = terminal.net_interest_rate
    eta_ratio = parameters.eta / (1.0 - parameters.eta)
    log_ai_services = (
        math.log(frontier)
        + 2.0 * math.log1p(-parameters.alpha)
        + (1.0 - parameters.alpha)
        / varphi
        * math.log(parameters.omega_x)
    ) / parameters.alpha
    ai_services = math.exp(log_ai_services)
    weight_ratio = (
        (1.0 - parameters.omega_x)
        / (parameters.omega_x * ai_services**varphi)
    )
    implicit_term = (
        -1.0
        + (1.0 - parameters.alpha) / varphi
        + (parameters.alpha - 1.0 / terminal.sigma_xl)
        / (1.0 - parameters.alpha)
    )
    log_services_h = weight_ratio * implicit_term / parameters.alpha
    output_h = output * (
        (1.0 - parameters.alpha) * weight_ratio / varphi
        + (1.0 - parameters.alpha) * log_services_h
    )
    inference_h = inference_compute * log_services_h
    capital_growth_h = output_h - inference_h
    consumption_growth_h = (
        (parameters.alpha - 1.0) * output_h + inference_h
    )
    shadow_growth_h = (
        (parameters.alpha - 1.0) * output_h
        + inference_h
        - net_interest * log_services_h
    )
    jacobian = np.zeros((5, 5))
    jacobian[0, 0] = varphi * (
        effective_labor_growth(parameters) - growth
    )
    jacobian[1, 0] = capital_growth_h
    jacobian[1, 1] = -growth * eta_ratio
    jacobian[1, 2] = -consumption
    jacobian[1, 3] = -growth * eta_ratio
    jacobian[2, 0] = consumption_growth_h
    jacobian[2, 2] = consumption
    jacobian[3, 0] = shadow_growth_h
    jacobian[3, 1] = growth * eta_ratio
    jacobian[3, 2] = consumption
    jacobian[3, 3] = net_interest + growth * eta_ratio
    jacobian[4, 4] = -effective_labor_growth(parameters)
    return jacobian


def terminal_linearization(
    terminal: FiniteCapTerminalPoint,
    parameters: PositiveAIBenchmarkParameters,
    *,
    eigenvalue_tolerance: float = 1e-10,
) -> TerminalLinearization:
    """Construct the stable terminal projection for the selected regime."""

    jacobian = (
        labor_supported_jacobian(terminal, parameters)
        if terminal.regime == "labor_supported"
        else ai_dominated_jacobian(terminal, parameters)
    )
    eigenvalues, eigenvectors = np.linalg.eig(jacobian)
    stable_indices = np.asarray(
        [
            index
            for index, value in enumerate(eigenvalues)
            if value.real < -eigenvalue_tolerance
        ],
        dtype=int,
    )
    unstable_indices = np.asarray(
        [
            index
            for index, value in enumerate(eigenvalues)
            if value.real > eigenvalue_tolerance
        ],
        dtype=int,
    )
    if stable_indices.size != 3 or unstable_indices.size != 2:
        raise RuntimeError(
            "The terminal point must have three stable and two unstable roots."
        )
    stable_values = eigenvalues[stable_indices].real
    stable_basis = eigenvectors[:, stable_indices].real
    order = np.argsort(stable_values)
    stable_values = stable_values[order]
    stable_basis = stable_basis[:, order]
    predetermined = np.asarray(terminal.predetermined_indices)
    for column in range(stable_basis.shape[1]):
        state_norm = float(np.linalg.norm(stable_basis[predetermined, column]))
        if state_norm <= 1e-14:
            raise RuntimeError(
                "A stable direction has no component in the predetermined states."
            )
        stable_basis[:, column] /= state_norm
    projection = stable_basis[
        predetermined, :
    ]
    determinant = float(np.linalg.det(projection))
    condition_number = float(np.linalg.cond(projection))
    if (
        abs(determinant) <= 1e-10
        or not math.isfinite(condition_number)
        or condition_number >= 1e10
    ):
        raise RuntimeError("The stable manifold does not project onto the states.")
    orthogonal, _ = np.linalg.qr(stable_basis, mode="complete")
    terminal_matrix = orthogonal[:, 3:].T
    return TerminalLinearization(
        jacobian=jacobian,
        eigenvalues=eigenvalues,
        stable_eigenvalues=stable_values,
        unstable_eigenvalues=np.sort(eigenvalues[unstable_indices].real),
        stable_basis=stable_basis,
        terminal_matrix=terminal_matrix,
        state_projection_determinant=determinant,
        state_projection_condition_number=condition_number,
    )


def terminal_residual(
    terminal: FiniteCapTerminalPoint,
    parameters: PositiveAIBenchmarkParameters,
) -> np.ndarray:
    """Evaluate the exact normalized vector field at the terminal point."""

    if terminal.regime == "labor_supported":
        return labor_supported_dynamics(
            terminal.coordinates, terminal, parameters
        )
    return ai_dominated_dynamics(terminal.coordinates, terminal, parameters)


def solve_local_terminal_bvp(
    terminal: FiniteCapTerminalPoint,
    parameters: PositiveAIBenchmarkParameters,
    initial_predetermined_deviations: np.ndarray,
    *,
    horizon: float = 400.0,
    nodes: int = 161,
    tolerance: float = 1e-8,
    boundary_tolerance: float = 1e-10,
    maximum_nodes: int = 10_000,
) -> LocalFiniteCapBVP:
    """Solve a nonlinear BVP near one terminal regime.

    The three supplied deviations correspond, in order, to the regime's three
    predetermined coordinates.  The two jump variables are selected by the
    stable terminal projection.
    """

    linearization = terminal_linearization(terminal, parameters)
    predetermined = np.asarray(terminal.predetermined_indices)
    target_deviations = np.asarray(
        initial_predetermined_deviations, dtype=float
    )
    if target_deviations.shape != (3,):
        raise ValueError("Exactly three predetermined deviations are required.")
    projection = linearization.stable_basis[predetermined, :]
    coefficients = np.linalg.solve(projection, target_deviations)
    mesh = np.linspace(0.0, horizon, nodes)
    guess_deviations = (
        linearization.stable_basis[:, :, None]
        * np.exp(
            linearization.stable_eigenvalues[:, None] * mesh[None, :]
        )[None, :, :]
        * coefficients[None, :, None]
    ).sum(axis=1)
    guess = terminal.coordinates[:, None] + guess_deviations
    initial_targets = terminal.coordinates[predetermined] + target_deviations

    def dynamics(times: np.ndarray, values: np.ndarray) -> np.ndarray:
        result = np.empty_like(values)
        for column in range(times.size):
            if terminal.regime == "labor_supported":
                result[:, column] = labor_supported_dynamics(
                    values[:, column], terminal, parameters
                )
            else:
                result[:, column] = ai_dominated_dynamics(
                    values[:, column], terminal, parameters
                )
        return result

    def boundary(left: np.ndarray, right: np.ndarray) -> np.ndarray:
        return np.concatenate(
            (
                left[predetermined] - initial_targets,
                linearization.terminal_matrix
                @ (right - terminal.coordinates),
            )
        )

    result = solve_bvp(
        dynamics,
        boundary,
        mesh,
        guess,
        tol=tolerance,
        bc_tol=boundary_tolerance,
        max_nodes=maximum_nodes,
        verbose=0,
    )
    if not result.success:
        raise RuntimeError(f"The local finite-cap BVP failed: {result.message}")
    boundary_residual = boundary(result.y[:, 0], result.y[:, -1])
    return LocalFiniteCapBVP(
        raw=result,
        terminal=terminal,
        linearization=linearization,
        horizon=horizon,
        initial_predetermined_deviations=target_deviations,
        maximum_boundary_residual=float(np.max(np.abs(boundary_residual))),
    )


def _json_ready_terminal(
    terminal: FiniteCapTerminalPoint,
    linearization: TerminalLinearization,
) -> dict[str, Any]:
    payload = asdict(terminal)
    payload["coordinates"] = terminal.coordinates.tolist()
    payload["linearization"] = {
        "jacobian": linearization.jacobian.tolist(),
        "eigenvalues": linearization.eigenvalues.real.tolist(),
        "stable_eigenvalues": linearization.stable_eigenvalues.tolist(),
        "unstable_eigenvalues": linearization.unstable_eigenvalues.tolist(),
        "terminal_matrix": linearization.terminal_matrix.tolist(),
        "state_projection_determinant": (
            linearization.state_projection_determinant
        ),
        "state_projection_condition_number": (
            linearization.state_projection_condition_number
        ),
    }
    return payload


def build_analysis(
    parameters: PositiveAIBenchmarkParameters,
    sigma_values: tuple[float, ...],
) -> dict[str, Any]:
    """Build the reproducible threshold table and two local BVP diagnostics."""

    thresholds = [
        {
            "sigma_xl": sigma,
            "critical_frontier": critical_capability_frontier(
                sigma, parameters
            ),
        }
        for sigma in sigma_values
    ]
    diagnostic_sigma = 1.10
    critical = critical_capability_frontier(diagnostic_sigma, parameters)
    terminals = [
        terminal_point(
            diagnostic_sigma, ratio * critical, parameters
        )
        for ratio in (0.5, 2.0)
    ]
    local_deviations = {
        "labor_supported": np.asarray([0.01, -0.01, 1e-5]),
        "ai_dominated": np.asarray([1e-5, -0.01, 1e-5]),
    }
    terminal_payloads = []
    for item in terminals:
        linearization = terminal_linearization(item, parameters)
        local = solve_local_terminal_bvp(
            item,
            parameters,
            local_deviations[item.regime],
        )
        terminal_payload = _json_ready_terminal(item, linearization)
        terminal_payload["terminal_residual"] = terminal_residual(
            item, parameters
        ).tolist()
        terminal_payload["local_bvp"] = {
            "success": bool(local.raw.success),
            "iterations": int(local.raw.niter),
            "nodes": int(local.raw.x.size),
            "maximum_rms_residual": float(
                np.max(local.raw.rms_residuals)
            ),
            "maximum_boundary_residual": local.maximum_boundary_residual,
            "initial_predetermined_deviations": (
                local.initial_predetermined_deviations.tolist()
            ),
        }
        terminal_payloads.append(terminal_payload)
    return {
        "parameters": asdict(parameters),
        "thresholds": thresholds,
        "terminal_diagnostics": terminal_payloads,
        "scope": (
            "Local finite-cap BVP diagnostics near the terminal regimes; "
            "not transitions from the paper's date-zero stocks."
        ),
    }


def _parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "numerical_axm" / "finite_cap_bvp_analysis.json",
    )
    return parser.parse_args()


def main() -> None:
    arguments = _parse_arguments()
    parameters = PositiveAIBenchmarkParameters()
    analysis = build_analysis(
        parameters,
        (1.01, 1.02, 1.05, 1.10, 1.25, 1.50, 2.00),
    )
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(
        json.dumps(analysis, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(analysis, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
