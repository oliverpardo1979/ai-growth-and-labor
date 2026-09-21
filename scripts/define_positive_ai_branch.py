"""Define the nondegenerate positive-AI branch before solving transitions.

The no-AI Ramsey economy and the economy with ``omega_X > 0`` are different
boundary-value problems.  At ``omega_X = 0``, capability ``B``, its shadow value
``q``, inference compute ``U``, research compute ``M``, and the developer's two
dynamic conditions disappear.  This module therefore does not continue the
two-dimensional Ramsey system through zero.

Instead, it constructs the exact unit-elastic balanced-growth equilibrium at a
strictly positive ``omega_X``.  It then writes the four-dimensional system in
the paper's stationary log deviations

``(xi_K, xi_B, xi_C, xi_q) = log((K, B, C, q) / (K*, B*, C*, q*))``.

The functions below provide the exact seed, the normalized right-hand side and
analytic Jacobian, the two-dimensional stable subspace, and the four boundary
conditions required by a later collocation solver.  They do not solve a
transition or write numerical, figure, table, or PDF artifacts.
"""

from __future__ import annotations

import argparse
import json
import math
from dataclasses import asdict, dataclass

import numpy as np


@dataclass(frozen=True)
class PositiveAIBenchmarkParameters:
    """Annual parameters for the automated-research benchmark at sigma_XL=1."""

    alpha: float = 0.33
    omega_x: float = 0.20
    population_growth: float = 0.003
    labor_productivity_growth: float = 0.01
    depreciation: float = 0.05
    discount: float = 0.04
    eta: float = 0.20
    chi: float = 0.01
    initial_labor_productivity: float = 1.0
    initial_population: float = 1.0

    def __post_init__(self) -> None:
        if not 0.0 < self.alpha < 1.0:
            raise ValueError("alpha must lie strictly between zero and one.")
        if not 0.0 < self.omega_x < 1.0:
            raise ValueError(
                "This is the strictly positive-AI branch: omega_x must lie "
                "strictly between zero and one. Use the separate RCK solver "
                "when omega_x is zero."
            )
        if not 0.0 < self.eta < self.alpha:
            raise ValueError("The maintained restriction is 0 < eta < alpha.")
        # The uncapped unit-elastic proof also covers eta > 1/2 by using
        # S=B**(1-eta) only in its concavity verification. Keep the original
        # model coordinates and equations here. The remaining profit and
        # positive-growth restrictions are checked by balanced_growth_seed.
        if self.population_growth < 0.0:
            raise ValueError("Population growth must be nonnegative.")
        if self.labor_productivity_growth < 0.0:
            raise ValueError("Labor-productivity growth must be nonnegative.")
        if (
            self.population_growth + self.labor_productivity_growth
            <= 0.0
        ):
            raise ValueError(
                "The interior research seed requires positive effective-labor "
                "growth."
            )
        if self.depreciation < 0.0:
            raise ValueError("Depreciation must be nonnegative.")
        if self.discount <= self.population_growth:
            raise ValueError("The maintained household condition is rho > n.")
        if self.chi <= 0.0:
            raise ValueError("chi must be strictly positive.")
        if self.initial_labor_productivity <= 0.0:
            raise ValueError("Initial labor productivity must be positive.")
        if self.initial_population <= 0.0:
            raise ValueError("Initial population must be positive.")

    @property
    def omega_l(self) -> float:
        return 1.0 - self.omega_x


@dataclass(frozen=True)
class PositiveAIBalancedGrowth:
    """Exact date-zero levels, growth rates, and shares on the AI BGP."""

    beta: float
    labor_exponent: float
    feedback_determinant: float
    output_growth: float
    capability_growth: float
    shadow_value_growth: float
    net_interest_rate: float
    inference_share: float
    capital_output_ratio: float
    investment_share: float
    research_share: float
    consumption_share: float
    profit_shadow_ratio: float
    labor_productivity: float
    population: float
    capability: float
    output: float
    capital: float
    consumption: float
    inference_compute: float
    research_compute: float
    ai_services: float
    service_composite: float
    shadow_value: float
    wage: float
    ai_service_price: float
    distributed_profit: float


@dataclass(frozen=True)
class PositiveAIInitialStocks:
    """Predetermined stocks selected by an explicit date-zero matching rule."""

    capital: float
    capability: float
    implied_output: float
    capital_output_ratio: float
    log_capital_deviation_from_bgp: float
    log_capability_deviation_from_bgp: float


@dataclass(frozen=True)
class StableSubspace:
    """Linear objects used to close the four-dimensional finite-horizon BVP."""

    eigenvalues: np.ndarray
    stable_basis: np.ndarray
    terminal_matrix: np.ndarray
    state_projection_determinant: float
    state_projection_condition_number: float


def balanced_growth_seed(
    parameters: PositiveAIBenchmarkParameters,
) -> PositiveAIBalancedGrowth:
    """Construct the exact positive-AI BGP from the paper's proposition."""

    beta = (1.0 - parameters.alpha) * parameters.omega_x
    labor_exponent = (1.0 - parameters.alpha) * parameters.omega_l
    if beta > 0.5:
        raise ValueError(
            "The theorem-backed seed requires beta=(1-alpha)*omega_x <= 1/2."
        )
    feedback_determinant = (
        labor_exponent * (1.0 - parameters.eta)
        - beta * parameters.eta
    )
    if feedback_determinant <= 0.0:
        raise ValueError(
            "The unit-elastic positive-AI BGP requires "
            "Delta=lambda*(1-eta)-beta*eta > 0."
        )

    effective_labor_growth = (
        parameters.population_growth
        + parameters.labor_productivity_growth
    )
    output_growth = (
        labor_exponent
        * (1.0 - parameters.eta)
        / feedback_determinant
        * effective_labor_growth
    )
    capability_growth = (
        parameters.eta / (1.0 - parameters.eta) * output_growth
    )
    shadow_value_growth = output_growth - capability_growth
    net_interest_rate = (
        parameters.discount
        + output_growth
        - parameters.population_growth
    )

    inference_share = beta**2
    capital_output_ratio = parameters.alpha / (
        net_interest_rate + parameters.depreciation
    )
    investment_share = (
        output_growth + parameters.depreciation
    ) * capital_output_ratio
    research_denominator = (
        parameters.discount
        - parameters.population_growth
        + parameters.eta * output_growth
    )
    research_share = (
        inference_share
        * parameters.eta
        * capability_growth
        / research_denominator
    )
    consumption_share = (
        1.0 - inference_share - investment_share - research_share
    )
    if consumption_share <= 0.0:
        raise ValueError(
            "The parameterization implies nonpositive BGP consumption."
        )
    profit_shadow_ratio = research_denominator

    level_power = (
        (1.0 - parameters.eta) / parameters.eta
        - beta / labor_exponent
    )
    if level_power <= 0.0:
        raise ValueError("The BGP capability-level exponent must be positive.")
    production_scale = (
        parameters.initial_labor_productivity
        * parameters.initial_population
        * capital_output_ratio ** (parameters.alpha / labor_exponent)
        * inference_share ** (beta / labor_exponent)
    )
    research_scale = (
        (capability_growth / parameters.chi) ** (1.0 / parameters.eta)
        / research_share
    )
    capability = (
        production_scale / research_scale
    ) ** (1.0 / level_power)
    output = production_scale * capability ** (beta / labor_exponent)
    capital = capital_output_ratio * output
    consumption = consumption_share * output
    inference_compute = inference_share * output
    research_compute = research_share * output
    ai_services = capability * inference_compute
    shadow_value = research_compute / (
        parameters.eta * capability_growth * capability
    )
    service_composite = (
        (parameters.initial_labor_productivity * parameters.initial_population)
        ** parameters.omega_l
        * ai_services**parameters.omega_x
    )
    wage = labor_exponent * output / parameters.initial_population
    ai_service_price = beta * output / ai_services
    distributed_profit = (
        ai_service_price * ai_services
        - inference_compute
        - research_compute
    )

    return PositiveAIBalancedGrowth(
        beta=beta,
        labor_exponent=labor_exponent,
        feedback_determinant=feedback_determinant,
        output_growth=output_growth,
        capability_growth=capability_growth,
        shadow_value_growth=shadow_value_growth,
        net_interest_rate=net_interest_rate,
        inference_share=inference_share,
        capital_output_ratio=capital_output_ratio,
        investment_share=investment_share,
        research_share=research_share,
        consumption_share=consumption_share,
        profit_shadow_ratio=profit_shadow_ratio,
        labor_productivity=parameters.initial_labor_productivity,
        population=parameters.initial_population,
        capability=capability,
        output=output,
        capital=capital,
        consumption=consumption,
        inference_compute=inference_compute,
        research_compute=research_compute,
        ai_services=ai_services,
        service_composite=service_composite,
        shadow_value=shadow_value,
        wage=wage,
        ai_service_price=ai_service_price,
        distributed_profit=distributed_profit,
    )


def canonical_seed_residuals(
    parameters: PositiveAIBenchmarkParameters,
    seed: PositiveAIBalancedGrowth | None = None,
) -> dict[str, float]:
    """Reconstruct the dated equilibrium equations at the analytic seed."""

    seed = seed or balanced_growth_seed(parameters)
    effective_labor = seed.labor_productivity * seed.population
    reconstructed_composite = (
        effective_labor**parameters.omega_l
        * seed.ai_services**parameters.omega_x
    )
    reconstructed_output = (
        seed.capital**parameters.alpha
        * seed.service_composite ** (1.0 - parameters.alpha)
    )
    inverse_demand_elasticity = 1.0 - seed.beta
    research_services = seed.capability * seed.research_compute

    residuals = {
        "service_composite_log_residual": math.log(
            seed.service_composite / reconstructed_composite
        ),
        "final_production_log_residual": math.log(
            seed.output / reconstructed_output
        ),
        "inference_identity_log_residual": math.log(
            seed.ai_services
            / (seed.capability * seed.inference_compute)
        ),
        "monopoly_foc_log_residual": math.log(
            seed.ai_service_price
            * (1.0 - inverse_demand_elasticity)
            * seed.capability
        ),
        "research_foc_log_residual": math.log(
            seed.shadow_value
            * parameters.chi
            * parameters.eta
            * seed.capability
            * research_services ** (parameters.eta - 1.0)
        ),
        "capability_law_log_residual": math.log(
            seed.capability_growth
            * seed.capability
            / (parameters.chi * research_services**parameters.eta)
        ),
        "resource_share_residual": (
            seed.consumption_share
            + seed.investment_share
            + seed.inference_share
            + seed.research_share
            - 1.0
        ),
        "euler_growth_residual": (
            seed.output_growth
            - parameters.population_growth
            - seed.net_interest_rate
            + parameters.discount
        ),
        "costate_growth_residual": (
            seed.shadow_value_growth
            - seed.net_interest_rate
            + seed.ai_services
            / (seed.shadow_value * seed.capability**2)
            + parameters.eta * seed.capability_growth
        ),
        "profit_shadow_ratio_residual": (
            seed.inference_compute
            / (seed.shadow_value * seed.capability)
            - seed.profit_shadow_ratio
        ),
    }
    residuals["max_abs_equilibrium_residual"] = max(
        abs(value) for value in residuals.values()
    )
    residuals["tvc_decay_rate"] = (
        parameters.discount - parameters.population_growth
    )
    return residuals


def normalized_dynamics(
    deviations: np.ndarray,
    parameters: PositiveAIBenchmarkParameters,
    seed: PositiveAIBalancedGrowth | None = None,
) -> np.ndarray:
    """Exact autonomous dynamics of (xi_K, xi_B, xi_C, xi_q)."""

    seed = seed or balanced_growth_seed(parameters)
    values = np.asarray(deviations, dtype=float)
    if values.shape[0] != 4:
        raise ValueError("The normalized state order is (K, B, C, q).")
    xi_k, xi_b, xi_c, xi_q = values
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

    output_capital_ratio = np.exp(output_deviation - xi_k)
    consumption_capital_ratio = np.exp(xi_c - xi_k)
    research_capital_ratio = np.exp(research_deviation - xi_k)
    profit_shadow_ratio = np.exp(output_deviation - xi_q - xi_b)
    capability_growth_ratio = np.exp(capability_growth_log_ratio)

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


def normalized_jacobian(
    deviations: np.ndarray,
    parameters: PositiveAIBenchmarkParameters,
    seed: PositiveAIBalancedGrowth | None = None,
) -> np.ndarray:
    """Analytic Jacobian of :func:`normalized_dynamics`."""

    seed = seed or balanced_growth_seed(parameters)
    values = np.asarray(deviations, dtype=float)
    if values.shape[0] != 4:
        raise ValueError("The normalized state order is (K, B, C, q).")
    xi_k, xi_b, xi_c, xi_q = values
    a_k = parameters.alpha / (1.0 - seed.beta)
    a_b = seed.beta / (1.0 - seed.beta)
    output_gradient = np.asarray([a_k, a_b, 0.0, 0.0])
    output_capital_gradient = output_gradient - np.asarray(
        [1.0, 0.0, 0.0, 0.0]
    )
    consumption_capital_gradient = np.asarray([-1.0, 0.0, 1.0, 0.0])
    research_gradient = np.asarray(
        [0.0, parameters.eta / (1.0 - parameters.eta), 0.0,
         1.0 / (1.0 - parameters.eta)]
    )
    research_capital_gradient = research_gradient - np.asarray(
        [1.0, 0.0, 0.0, 0.0]
    )
    profit_shadow_gradient = output_gradient - np.asarray(
        [0.0, 1.0, 0.0, 1.0]
    )
    capability_growth_gradient = np.asarray(
        [
            0.0,
            (2.0 * parameters.eta - 1.0) / (1.0 - parameters.eta),
            0.0,
            parameters.eta / (1.0 - parameters.eta),
        ]
    )

    output_deviation = a_k * xi_k + a_b * xi_b
    research_deviation = (
        xi_q + parameters.eta * xi_b
    ) / (1.0 - parameters.eta)
    capability_growth_log_ratio = (
        (2.0 * parameters.eta - 1.0) * xi_b
        + parameters.eta * xi_q
    ) / (1.0 - parameters.eta)
    output_capital_ratio = np.exp(output_deviation - xi_k)
    consumption_capital_ratio = np.exp(xi_c - xi_k)
    research_capital_ratio = np.exp(research_deviation - xi_k)
    profit_shadow_ratio = np.exp(output_deviation - xi_q - xi_b)
    capability_growth_ratio = np.exp(capability_growth_log_ratio)

    trailing_dimensions = values.shape[1:]

    def scaled_gradient(
        coefficient: np.ndarray | float,
        gradient: np.ndarray,
    ) -> np.ndarray:
        coefficient_array = np.asarray(coefficient)
        reshape = (4,) + (1,) * coefficient_array.ndim
        return gradient.reshape(reshape) * coefficient_array

    capital_row = (
        scaled_gradient(
            (1.0 - seed.inference_share)
            / seed.capital_output_ratio
            * output_capital_ratio,
            output_capital_gradient,
        )
        - scaled_gradient(
            seed.consumption_share
            / seed.capital_output_ratio
            * consumption_capital_ratio,
            consumption_capital_gradient,
        )
        - scaled_gradient(
            seed.research_share
            / seed.capital_output_ratio
            * research_capital_ratio,
            research_capital_gradient,
        )
    )
    capability_row = scaled_gradient(
        seed.capability_growth * capability_growth_ratio,
        capability_growth_gradient,
    )
    consumption_row = scaled_gradient(
        parameters.alpha
        / seed.capital_output_ratio
        * output_capital_ratio,
        output_capital_gradient,
    )
    shadow_row = (
        scaled_gradient(
            parameters.alpha
            / seed.capital_output_ratio
            * output_capital_ratio,
            output_capital_gradient,
        )
        - scaled_gradient(
            seed.profit_shadow_ratio * profit_shadow_ratio,
            profit_shadow_gradient,
        )
        - scaled_gradient(
            parameters.eta
            * seed.capability_growth
            * capability_growth_ratio,
            capability_growth_gradient,
        )
    )
    jacobian = np.stack(
        (capital_row, capability_row, consumption_row, shadow_row),
        axis=0,
    )
    expected_shape = (4, 4) + trailing_dimensions
    if jacobian.shape != expected_shape:
        raise RuntimeError(
            f"Internal Jacobian shape {jacobian.shape} != {expected_shape}."
        )
    return jacobian


def stable_subspace(
    parameters: PositiveAIBenchmarkParameters,
    seed: PositiveAIBalancedGrowth | None = None,
    *,
    eigenvalue_tolerance: float = 1e-10,
) -> StableSubspace:
    """Return the stable basis and two terminal annihilator conditions."""

    seed = seed or balanced_growth_seed(parameters)
    jacobian = normalized_jacobian(np.zeros(4), parameters, seed)
    eigenvalues, eigenvectors = np.linalg.eig(jacobian)
    stable_indices = [
        index
        for index, value in enumerate(eigenvalues)
        if value.real < -eigenvalue_tolerance
    ]
    unstable_indices = [
        index
        for index, value in enumerate(eigenvalues)
        if value.real > eigenvalue_tolerance
    ]
    if len(stable_indices) != 2 or len(unstable_indices) != 2:
        raise RuntimeError(
            "The positive-AI seed must have exactly two stable and two "
            "unstable roots."
        )

    candidate_columns: list[np.ndarray] = []
    for index in stable_indices:
        vector = eigenvectors[:, index]
        if np.linalg.norm(vector.real) > eigenvalue_tolerance:
            candidate_columns.append(vector.real)
        if np.linalg.norm(vector.imag) > eigenvalue_tolerance:
            candidate_columns.append(vector.imag)
    candidates = np.column_stack(candidate_columns)
    left_singular_vectors, singular_values, _ = np.linalg.svd(
        candidates, full_matrices=True
    )
    stable_rank = int(
        np.sum(singular_values > eigenvalue_tolerance * singular_values[0])
    )
    if stable_rank != 2:
        raise RuntimeError("The real stable invariant subspace is not rank two.")
    stable_basis_matrix = left_singular_vectors[:, :2]
    terminal_matrix = left_singular_vectors[:, 2:].T
    state_projection = stable_basis_matrix[[0, 1], :]
    determinant = float(np.linalg.det(state_projection))
    condition_number = float(np.linalg.cond(state_projection))
    if abs(determinant) <= 1e-10 or not math.isfinite(condition_number):
        raise RuntimeError(
            "The stable subspace cannot be represented locally as jump "
            "variables conditional on (K0,B0)."
        )

    order = np.argsort(eigenvalues.real)
    return StableSubspace(
        eigenvalues=eigenvalues[order],
        stable_basis=stable_basis_matrix,
        terminal_matrix=terminal_matrix,
        state_projection_determinant=determinant,
        state_projection_condition_number=condition_number,
    )


def boundary_residual(
    left_deviations: np.ndarray,
    right_deviations: np.ndarray,
    initial_state_deviations: np.ndarray,
    subspace: StableSubspace,
) -> np.ndarray:
    """Return two initial-stock and two stable-terminal BVP conditions."""

    left = np.asarray(left_deviations, dtype=float)
    right = np.asarray(right_deviations, dtype=float)
    initial = np.asarray(initial_state_deviations, dtype=float)
    if left.shape != (4,) or right.shape != (4,):
        raise ValueError("Boundary states must each have shape (4,).")
    if initial.shape != (2,):
        raise ValueError("Initial stock deviations must have shape (2,).")
    return np.concatenate(
        (
            left[[0, 1]] - initial,
            subspace.terminal_matrix @ right,
        )
    )


def boundary_jacobians(
    subspace: StableSubspace,
) -> tuple[np.ndarray, np.ndarray]:
    """Return exact derivatives of the finite-horizon boundary conditions.

    The first two rows impose the predetermined initial stocks.  The final
    two rows eliminate the unstable terminal components.  These matrices can
    be passed directly to a later collocation solver's boundary Jacobian.
    """

    left_jacobian = np.zeros((4, 4))
    right_jacobian = np.zeros((4, 4))
    left_jacobian[0, 0] = 1.0
    left_jacobian[1, 1] = 1.0
    right_jacobian[2:, :] = subspace.terminal_matrix
    return left_jacobian, right_jacobian


def initial_stocks_matching_bgp_capital_output_ratio(
    parameters: PositiveAIBenchmarkParameters,
    capability: float,
    seed: PositiveAIBalancedGrowth | None = None,
) -> PositiveAIInitialStocks:
    """Choose K0 so K0/Y0 equals the positive-AI BGP ratio.

    This is an explicit initialization rule, not an equilibrium condition and
    not a claim that the requested capability lies on the BGP.
    """

    if capability <= 0.0:
        raise ValueError("Initial capability must be strictly positive.")
    seed = seed or balanced_growth_seed(parameters)
    production_scale = (
        parameters.initial_labor_productivity
        * parameters.initial_population
        * seed.capital_output_ratio
        ** (parameters.alpha / seed.labor_exponent)
        * seed.inference_share ** (seed.beta / seed.labor_exponent)
    )
    output = production_scale * capability ** (
        seed.beta / seed.labor_exponent
    )
    capital = seed.capital_output_ratio * output
    return PositiveAIInitialStocks(
        capital=capital,
        capability=capability,
        implied_output=output,
        capital_output_ratio=capital / output,
        log_capital_deviation_from_bgp=math.log(capital / seed.capital),
        log_capability_deviation_from_bgp=math.log(
            capability / seed.capability
        ),
    )


def state_continuation_schedule(
    target_state_deviations: np.ndarray,
    stages: int,
) -> tuple[np.ndarray, ...]:
    """Move from the exact AI BGP to target (K0,B0) in log-state space."""

    target = np.asarray(target_state_deviations, dtype=float)
    if target.shape != (2,):
        raise ValueError("Target stock deviations must have shape (2,).")
    if stages < 1:
        raise ValueError("stages must be at least one.")
    return tuple(
        fraction * target
        for fraction in np.linspace(0.0, 1.0, stages + 1)
    )


def positive_weight_schedule(
    initial_omega_x: float,
    final_omega_x: float,
    stages: int,
) -> tuple[float, ...]:
    """Continue only between two strictly positive CES weights in logit space."""

    for name, value in (
        ("initial_omega_x", initial_omega_x),
        ("final_omega_x", final_omega_x),
    ):
        if not 0.0 < value < 1.0:
            raise ValueError(
                f"{name} must lie strictly between zero and one; omega_x=0 "
                "belongs to the separate RCK branch."
            )
    if stages < 1:
        raise ValueError("stages must be at least one.")
    initial_logit = math.log(initial_omega_x / (1.0 - initial_omega_x))
    final_logit = math.log(final_omega_x / (1.0 - final_omega_x))
    logits = np.linspace(initial_logit, final_logit, stages + 1)
    return tuple(float(1.0 / (1.0 + math.exp(-value))) for value in logits)


def _json_ready_subspace(subspace: StableSubspace) -> dict[str, object]:
    eigenvalues = [
        {
            "real": float(value.real),
            "imaginary": float(value.imag),
        }
        for value in subspace.eigenvalues
    ]
    return {
        "eigenvalues": eigenvalues,
        "stable_basis": subspace.stable_basis.tolist(),
        "terminal_matrix": subspace.terminal_matrix.tolist(),
        "state_projection_determinant": (
            subspace.state_projection_determinant
        ),
        "state_projection_condition_number": (
            subspace.state_projection_condition_number
        ),
    }


def _parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--target-capability",
        type=float,
        default=1.0,
        help="Capability normalization used only to report target stock deviations.",
    )
    return parser.parse_args()


def main() -> None:
    """Print analytic branch diagnostics without solving a transition."""

    arguments = _parse_arguments()
    parameters = PositiveAIBenchmarkParameters()
    seed = balanced_growth_seed(parameters)
    subspace = stable_subspace(parameters, seed)
    target = initial_stocks_matching_bgp_capital_output_ratio(
        parameters, arguments.target_capability, seed
    )
    summary = {
        "parameters": asdict(parameters),
        "balanced_growth_seed": asdict(seed),
        "canonical_seed_audit": canonical_seed_residuals(parameters, seed),
        "normalized_origin_residual": normalized_dynamics(
            np.zeros(4), parameters, seed
        ).tolist(),
        "stable_subspace": _json_ready_subspace(subspace),
        "target_stock_rule": asdict(target),
        "transition_solved": False,
    }
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
