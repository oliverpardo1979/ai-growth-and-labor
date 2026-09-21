"""Capped-model BVP designs; export only after equilibrium admission.

Each design supplies predetermined K0 and B0, never a borrowed C0, q0,
or terminal restriction. Cached splines are technical candidates, not figures.
Run each sigma separately to retain reproducible intermediate diagnostics.
"""
from dataclasses import asdict, dataclass, replace
import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
import sys
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / '.python-packages'))
sys.path.insert(0, str(ROOT / 'scripts'))
import numpy as np
from scipy.interpolate import PPoly
from scipy.optimize import brentq
from analyze_axm_finite_cap_bvp import (
    critical_capability_frontier, terminal_point, terminal_linearization,
)
from define_positive_ai_branch import PositiveAIBenchmarkParameters
from solve_near_unit_ai_bvp import elasticity_coordinate, solve_monopoly_static_block
from solve_rck_no_ai_bvp import RCKParameters, steady_state as rck_steady_state
from solve_axm_global_finite_cap_bvp import (
    GlobalFiniteCapBVP, GlobalContinuationStage, solve_global_finite_cap_bvp,
    refine_global_horizon, audit_global_solution, compare_global_solutions,
    audit_counterfactual_developer_sufficiency, reconstruct_levels,
    dated_raw_dynamics, _solution_payload,
)

SIGMAS = (0.9, 1.0, 1.1, 1.5)
PARAMETERS = replace(PositiveAIBenchmarkParameters(), chi=1.4378)
FRONTIER = 1.1 * critical_capability_frontier(1.5, PARAMETERS)
INITIAL_CAPITAL = 4.0
INITIAL_CAPABILITY = 0.10 * FRONTIER
NEAR_TERMINAL_CAPABILITY_RATIO = 0.9999
RAMSEY_START_CAPABILITY_RATIO = 0.01
OUT = ROOT / 'numerical_rewrite'
CACHE = ROOT / 'tmp' / 'rewrite_bvp'


@dataclass(frozen=True)
class SimulationDesign:
    """A complete comparison design; no jump variable is supplied here."""
    name: str
    sigmas: tuple[float, ...]
    parameters: PositiveAIBenchmarkParameters
    frontier: float
    initial_capital: float | None
    initial_capability: float
    output_directory: Path
    cache_directory: Path
    display_horizon: float
    initial_stock_reference: str
    initial_capital_rule: str = 'common'


MAIN_DESIGN = SimulationDesign(
    name='main', sigmas=SIGMAS, parameters=PARAMETERS, frontier=FRONTIER,
    initial_capital=INITIAL_CAPITAL, initial_capability=INITIAL_CAPABILITY,
    output_directory=OUT, cache_directory=CACHE,
    display_horizon=500.0,
    initial_stock_reference=(
        'common interior stocks closer to the capped sigma=1 terminal regime; '
        'K0=4 and B0/Bbar=0.10; jump variables solved by the BVP'),
)
SLOW_PARAMETERS = PositiveAIBenchmarkParameters()
SLOW_FRONTIER = 1.1 * critical_capability_frontier(1.5, SLOW_PARAMETERS)
SLOW_TRANSITION_DESIGN = SimulationDesign(
    name='slow', sigmas=SIGMAS, parameters=SLOW_PARAMETERS, frontier=SLOW_FRONTIER,
    initial_capital=2.027733653970002,
    initial_capability=0.44367093160980464,
    output_directory=OUT / 'slow_transition',
    cache_directory=ROOT / 'tmp' / 'rewrite_bvp_slow',
    display_horizon=4000.0,
    initial_stock_reference=(
        'earlier slow-transition calibration; K0 and B0 from the uncapped '
        'unit-elastic BGP; chi=0.01; jump variables solved anew by the BVP'),
)
NEAR_TERMINAL_DESIGN = SimulationDesign(
    name='near_terminal', sigmas=SIGMAS,
    parameters=PARAMETERS, frontier=FRONTIER,
    initial_capital=None,
    initial_capability=NEAR_TERMINAL_CAPABILITY_RATIO * FRONTIER,
    output_directory=OUT / 'near_terminal',
    cache_directory=ROOT / 'tmp' / 'rewrite_bvp_near_terminal',
    display_horizon=500.0,
    initial_stock_reference=(
        'near-terminal stocks for all four regimes; B0/Bbar=0.9999; '
        'K0/(A0*N0) equals the regime-specific terminal ratio in the '
        'labor-supported cases, while (Bbar-B0)*K0 equals the terminal '
        'gap scale in the AI-dominated case; jump variables solved anew by '
        'the BVP'),
    initial_capital_rule='regime_terminal_reference',
)
RAMSEY_START_RCK_PARAMETERS = RCKParameters(
    alpha=PARAMETERS.alpha,
    population_growth=PARAMETERS.population_growth,
    labor_productivity_growth=PARAMETERS.labor_productivity_growth,
    depreciation=PARAMETERS.depreciation,
    discount=PARAMETERS.discount,
)
RAMSEY_START_STEADY_STATE = rck_steady_state(
    RAMSEY_START_RCK_PARAMETERS)
RAMSEY_START_DESIGN = SimulationDesign(
    name='ramsey_start', sigmas=SIGMAS,
    parameters=PARAMETERS, frontier=FRONTIER,
    initial_capital=RAMSEY_START_STEADY_STATE.capital,
    initial_capability=RAMSEY_START_CAPABILITY_RATIO * FRONTIER,
    output_directory=OUT / 'ramsey_start',
    cache_directory=ROOT / 'tmp' / 'rewrite_bvp_ramsey_start',
    display_horizon=500.0,
    initial_stock_reference=(
        'common pre-AI Ramsey steady-state capital and low latent AI '
        'efficiency; K0/(A0*N0)=5.9415725271 and B0/Bbar=0.01; omega_X '
        'equals zero before date zero and 0.20 thereafter; jump variables '
        'are solved anew by the positive-AI BVP'),
)
DESIGNS = {
    'main': MAIN_DESIGN,
    'ramsey_start': RAMSEY_START_DESIGN,
    'slow': SLOW_TRANSITION_DESIGN,
    'near_terminal': NEAR_TERMINAL_DESIGN,
}


def key(sigma):
    return f'sigma_{sigma:.2f}'.replace('.', '_')


def fixed_efficiency_bgp(sigma, capability, parameters):
    """Pre-RSI BGP with existing AI and B fixed, at A0*N0=1.

    Research is unavailable in this auxiliary pre-event economy (chi=0,
    M=0), not an imposed corner of the post-event positive-chi problem.
    Only its stocks are inherited by the post-event BVP. Its C is NOT an
    initial boundary condition after the unanticipated RSI activation.
    """
    p = parameters
    if capability <= 0 or sigma <= 0 or p.discount <= p.population_growth:
        raise ValueError('The pre-RSI reference requires B>0, sigma>0, rho>n.')
    target = p.alpha / (p.discount + p.labor_productivity_growth + p.depreciation)

    def block(log_k):
        return solve_monopoly_static_block(log_k, math.log(capability), 0., sigma, p)

    def residual(log_k):
        return log_k - block(log_k).log_output - math.log(target)

    # A search bracket in log capital, not an economic restriction. Expand
    # symmetrically around the no-AI ratio's implied stock until bracketed.
    center = math.log(target) / (1-p.alpha)
    for width in (1., 2., 4., 8., 16., 32.):
        lo, hi = center-width, center+width
        if residual(lo)*residual(hi) <= 0:
            break
    else:
        raise ValueError('No positive fixed-B labor-supported BGP was bracketed.')
    log_k = brentq(residual, lo, hi, xtol=1e-12, rtol=1e-14)
    s = block(log_k)
    k, y, u = math.exp(log_k), math.exp(s.log_output), math.exp(s.log_inference_compute)
    x = math.exp(s.log_ai_services)
    revenue = (1-p.alpha)*s.ai_ces_share*y
    c = y-u-(p.depreciation+p.population_growth+p.labor_productivity_growth)*k
    if c <= 0 or abs(residual(log_k)) > 1e-10:
        raise ValueError('The fixed-B reference fails positivity or K/Y consistency.')
    return dict(sigma=sigma, capital=k, capability=capability, output=y,
                consumption=c, inference_compute=u, research_compute=0.,
                ai_services=x, ai_service_price=revenue/x,
                wage=(1-p.alpha)*(1-s.ai_ces_share)*y,
                interest_rate=p.alpha*y/k-p.depreciation,
                capital_output_ratio=k/y, labor_income_share=(1-p.alpha)*(1-s.ai_ces_share),
                ai_revenue_output_share=revenue/y, profit_output_share=(revenue-u)/y,
                inference_output_share=u/y, research_output_share=0.,
                monopoly_foc_residual=s.monopoly_foc_log_residual,
                pre_event_research_available=False)


def design_initial_stocks(design, sigma):
    """Return the predetermined stocks specified by one simulation design."""
    if design.initial_capital_rule == 'regime_terminal_reference':
        terminal = terminal_point(sigma, design.frontier, design.parameters)
        if terminal.regime == 'labor_supported':
            capital = terminal.auxiliary['capital_effective_labor_ratio']
        elif terminal.regime == 'ai_dominated':
            capability_gap = design.frontier - design.initial_capability
            capital = terminal.auxiliary['gap_scale'] / capability_gap
        else:
            raise ValueError(f'Unknown terminal regime: {terminal.regime}')
    elif design.initial_capital_rule == 'fixed_efficiency_bgp':
        capital = fixed_efficiency_bgp(
            sigma, design.initial_capability, design.parameters)['capital']
    elif design.initial_capital_rule == 'common':
        if design.initial_capital is None:
            raise ValueError('A common-capital design must specify initial capital.')
        capital = design.initial_capital
    else:
        raise ValueError(f'Unknown initial-capital rule: {design.initial_capital_rule}')
    return float(capital), float(design.initial_capability)


def ai_services_growth(static, capital_growth, capability_growth,
                       effective_labor_growth):
    """Recover ``g_X`` exactly from the dated static equilibrium block."""
    xk, xb = static.ai_services_log_gradient[:2]
    return (
        xk * capital_growth
        + xb * capability_growth
        + (1.0 - xk) * effective_labor_growth
    )


def real_wage_growth(static, sigma, capital_growth, capability_growth,
                     effective_labor_growth, output_growth, population_growth):
    """Recover ``g_w`` exactly from the static equilibrium block.

    Since ``w=(1-alpha)(1-s_X)Y/L`` and ``L=N``, wage growth equals
    per-person output growth plus the growth of ``1-s_X``.  The CES share
    identity supplies the latter without numerically differentiating a
    plotted series.
    """
    gx = ai_services_growth(
        static, capital_growth, capability_growth, effective_labor_growth)
    labor_share_growth = (
        -elasticity_coordinate(sigma)
        * static.ai_ces_share
        * (gx - effective_labor_growth)
    )
    return output_growth - population_growth + labor_share_growth


def save_solution(solution, filename):
    """Save numerical arrays without executable/pickled Python objects."""
    filename.parent.mkdir(parents=True, exist_ok=True)
    raw = solution.raw
    metadata = dict(sigma=solution.terminal.sigma_xl, frontier=solution.terminal.frontier,
                    parameters=asdict(solution.parameters), initial_capital=solution.initial_capital,
                    initial_capability=solution.initial_capability,
                    initial_effective_labor_scale=solution.initial_effective_labor_scale,
                    horizon=solution.horizon, niter=raw.niter,
                    stages=[asdict(s) for s in solution.stages])
    np.savez_compressed(filename, metadata=json.dumps(metadata), x=raw.x,
                        coefficients=raw.sol.c, spline_x=raw.sol.x,
                        spline_axis=raw.sol.axis,
                        rms_residuals=raw.rms_residuals)


def load_solution(filename):
    with np.load(filename, allow_pickle=False) as saved:
        m = json.loads(str(saved['metadata']))
        p = PositiveAIBenchmarkParameters(**m['parameters'])
        t = terminal_point(m['sigma'], m['frontier'], p)
        # solve_bvp stores a vector-valued PPoly with axis=1. Its canonical
        # coefficients must not be reinterpreted as an axis=0 interpolant.
        axis = int(saved['spline_axis']) if 'spline_axis' in saved else 1
        raw = SimpleNamespace(sol=PPoly.construct_fast(saved['coefficients'].copy(),
                              saved['spline_x'].copy(), axis=axis),
                              x=saved['x'].copy(), rms_residuals=saved['rms_residuals'].copy(),
                              niter=m['niter'], success=True)
        return GlobalFiniteCapBVP(raw, t, terminal_linearization(t, p), p,
                                 m['initial_capital'], m['initial_capability'],
                                 m['initial_effective_labor_scale'], m['horizon'],
                                 tuple(GlobalContinuationStage(**v) for v in m['stages']))


def validate_solution_design(solution, design, sigma):
    """Reject a stale checkpoint before it can enter a design's audit."""
    initial_capital, initial_capability = design_initial_stocks(design, sigma)
    capital_matches = solution.initial_capital == initial_capital
    if design.initial_capital_rule == 'fixed_efficiency_bgp':
        # This stock is recomputed by a scalar root finder. Equivalent, more
        # accurate static evaluations can change its last floating-point bit.
        # Permit only roundoff (8 machine eps), not a different initial stock;
        # the independent pre-event and equilibrium tolerances are unchanged.
        capital_matches = math.isclose(solution.initial_capital, initial_capital,
                                       rel_tol=8*np.finfo(float).eps, abs_tol=0.)
    if (asdict(solution.parameters) != asdict(design.parameters)
            or solution.terminal.frontier != design.frontier
            or solution.terminal.sigma_xl != sigma
            or not capital_matches
            or solution.initial_capability != initial_capability):
        raise ValueError(f'A cached solution differs from the {design.name} design.')


def run(sigma, design=MAIN_DESIGN):
    if sigma not in design.sigmas:
        raise ValueError(f'Use one of the elasticities in the {design.name} design.')
    p = design.parameters
    terminal = terminal_point(sigma, design.frontier, p)
    initial_capital, initial_capability = design_initial_stocks(design, sigma)
    design.output_directory.mkdir(parents=True, exist_ok=True)
    design.cache_directory.mkdir(parents=True, exist_ok=True)
    name = key(sigma)
    base_path = design.cache_directory/f'{name}_base.npz'
    refined_path = design.cache_directory/f'{name}_refined.npz'
    print(f'{design.name}/{name}: frontier={design.frontier:.12g}; '
          f'regime={terminal.regime}', flush=True)
    if base_path.exists():
        base = load_solution(base_path)
        terminal = base.terminal
    else:
        base = solve_global_finite_cap_bvp(
                                         terminal, p, initial_capital,
                                         initial_capability,
                                         continuation_steps=32, nodes=221,
                                         tolerance=2e-6, maximum_nodes=20000)
        save_solution(base, base_path)
    validate_solution_design(base, design, sigma)
    print(f'{name}: base solved, T={base.horizon:.2f}; refining', flush=True)
    if refined_path.exists():
        refined = load_solution(refined_path)
        validate_solution_design(refined, design, sigma)
        refined.terminal = terminal
    else:
        refined = refine_global_horizon(base, base.horizon+500,
                                       nodes=401, tolerance=1e-8,
                                       boundary_tolerance=1e-10, maximum_nodes=40000)
        save_solution(refined, refined_path)
    validate_solution_design(refined, design, sigma)
    print(f'{name}: refined; auditing equations and developer optimality', flush=True)
    audit = audit_global_solution(refined)
    comparison = compare_global_solutions(base, refined)
    sufficiency = audit_counterfactual_developer_sufficiency(
        refined, time_points=81, capability_points=101)
    payload = _solution_payload(refined, audit, horizon_comparison=comparison,
                                counterfactual_sufficiency=sufficiency)
    payload['parameters'] = asdict(p)
    payload['design'] = design.name
    payload['initial_stock_reference'] = design.initial_stock_reference
    payload['status'] = 'numerically_admitted' if payload['equilibrium_certified'] else 'not_admitted'
    payload['settings'] = dict(base_tolerance=2e-6, refined_tolerance=1e-8,
                               horizon_extension=500, continuation_steps=32)
    (design.output_directory/f'{name}_audit.json').write_text(
        json.dumps(payload, indent=2, allow_nan=False)+'\n', encoding='utf-8')
    print(f'{name}: {payload["status"]}; {sufficiency}', flush=True)
    return payload


def export_paths(horizon, points, design=MAIN_DESIGN, additional_times=None):
    """Refuse a partial or uncertified comparison; never extrapolate splines."""
    solutions = []
    checkpoint_hashes = {}
    for sigma in design.sigmas:
        path = design.output_directory/f'{key(sigma)}_audit.json'
        if not path.exists() or not json.loads(path.read_text())['equilibrium_certified']:
            raise RuntimeError(f'No admitted equilibrium for sigma={sigma}; no figure export.')
        report = json.loads(path.read_text())
        checkpoint = design.cache_directory/report['checkpoint_filename']
        if hashlib.sha256(checkpoint.read_bytes()).hexdigest() != report['checkpoint_sha256']:
            raise RuntimeError('The checkpoint has changed since its equilibrium audit.')
        sol = load_solution(checkpoint)
        validate_solution_design(sol, design, sigma)
        if horizon > sol.horizon:
            raise ValueError('Display horizon exceeds a solved and audited horizon.')
        solutions.append(sol)
        checkpoint_hashes[key(sigma)] = report['checkpoint_sha256']
    rows = []
    times = np.linspace(0, horizon, points)
    if additional_times is not None:
        extra = np.asarray(additional_times, dtype=float)
        if (extra.ndim != 1 or not np.all(np.isfinite(extra))
                or np.any(extra < 0) or np.any(extra > horizon)):
            raise ValueError('Additional export dates must lie inside the display horizon.')
        times = np.unique(np.r_[times, extra])
    for sol in solutions:
        p, sigma = sol.parameters, sol.terminal.sigma_xl
        bounded = sol.raw.sol(times)
        v = reconstruct_levels(times, bounded, sol)
        raw = bounded + sol.terminal.terminal_growth*times[None, :]
        rates = dated_raw_dynamics(times, raw, sol.terminal, p, sol.initial_effective_labor_scale)
        for j, time in enumerate(times):
            # Differentiate the static FOC to obtain the actual output growth.
            al = math.log(sol.initial_effective_labor_scale)+(p.population_growth+p.labor_productivity_growth)*time
            static = solve_monopoly_static_block(v['log_capital'][j], v['log_capability'][j], al, sigma, p)
            psi = math.exp(v['log_remaining_frontier_share'][j])
            gb = rates[1,j]*psi  # d logit(B/Bbar)/dt = g_B / psi.
            yk, yb = static.output_log_gradient[:2]
            # The supplied gradient is with respect to (log K, log B, log C,
            # log q). Homogeneity gives the missing log(AL) derivative 1-yk.
            gy = float(yk*rates[0,j] + yb*gb + (1-yk)*(
                                        p.population_growth+p.labor_productivity_growth))
            gx = ai_services_growth(
                static, rates[0,j], gb,
                p.population_growth+p.labor_productivity_growth,
            )
            gw = real_wage_growth(
                static, sigma, rates[0,j], gb,
                p.population_growth+p.labor_productivity_growth,
                gy, p.population_growth,
            )
            sx = v['ai_ces_share'][j]
            revenue = (1-p.alpha)*sx
            u = math.exp(v['log_inference_compute'][j]-v['log_output'][j])
            m = math.exp(v['log_research_compute'][j]-v['log_output'][j])
            rows.append(dict(sigma=sigma, time=time,
                output_effective_labor=math.exp(v['log_output'][j]-al),
                output_effective_labor_growth=(
                    gy-p.population_growth-p.labor_productivity_growth),
                output_per_person_growth=gy-p.population_growth,
                wage_growth=gw,
                wage_productivity=(1-p.alpha)*(1-sx)*math.exp(v['log_output'][j]-al),
                net_interest=v['net_interest_rate'][j], labor_income_share=(1-p.alpha)*(1-sx),
                ai_revenue_output_share=revenue, capability_frontier_ratio=1-psi,
                ai_service_price=math.exp(
                    math.log(revenue)+static.log_output-static.log_ai_services),
                consumption_effective_labor=math.exp(v['log_consumption'][j]-al),
                capital_effective_labor=math.exp(v['log_capital'][j]-al),
                consumption_effective_labor_growth=(
                    rates[2,j]-p.population_growth-p.labor_productivity_growth),
                capital_effective_labor_growth=(
                    rates[0,j]-p.population_growth-p.labor_productivity_growth),
                ai_services_effective_labor_growth=(
                    gx-p.population_growth-p.labor_productivity_growth),
                inference_output_share=u, research_output_share=m,
                profit_output_share=revenue-u-m,
                inference_revenue_share=u/revenue, research_revenue_share=m/revenue,
                profit_revenue_share=1-(u+m)/revenue))
    csv_path = design.output_directory/'equilibrium_paths.csv'
    with csv_path.open('w', newline='', encoding='utf-8') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    transition_dates = None
    if 1.5 in design.sigmas:
        ai_rows = [row for row in rows if row['sigma'] == 1.5]
        terminal_share = terminal_point(
            1.5, design.frontier, design.parameters).labor_income_share
        initial_share = ai_rows[0]['labor_income_share']

        def transition_date(fraction):
            target = initial_share + fraction * (terminal_share-initial_share)
            for left, right in zip(ai_rows, ai_rows[1:]):
                yl, yr = left['labor_income_share'], right['labor_income_share']
                if (yl-target)*(yr-target) <= 0 and yl != yr:
                    weight = (target-yl)/(yr-yl)
                    return left['time']+weight*(right['time']-left['time'])
            return None

        transition_dates = {f'T{int(100*fraction)}': transition_date(fraction)
                            for fraction in (.1, .5, .9)}
        if transition_dates['T50'] is None:
            raise RuntimeError(
                'The export window does not contain the calibrated transition midpoint.')
    manifest = dict(
        design=design.name,
        parameters=asdict(design.parameters),
        frontier=design.frontier,
        initial_capital=design.initial_capital,
        initial_capability=design.initial_capability,
        initial_capital_by_sigma={
            key(sigma): design_initial_stocks(design, sigma)[0]
            for sigma in design.sigmas
        },
        horizon=horizon,
        points_per_scenario=len(times),
        checkpoint_sha256=checkpoint_hashes,
        transition_definition=(
            'fraction of the sigma=1.50 labor-share decline from its date-zero '
            'value to its analytical limit'),
        sigma_1_50_transition_dates=transition_dates,
        csv_sha256=hashlib.sha256(csv_path.read_bytes()).hexdigest(),
    )
    if design.name in ('ramsey_start', 'price_calibrated', 'price_calibrated_low_ai_high_cap'):
        manifest['pre_transition_reference'] = dict(
            omega_x=0.0,
            omega_l=1.0,
            capital_effective_labor=RAMSEY_START_STEADY_STATE.capital,
            consumption_effective_labor=RAMSEY_START_STEADY_STATE.consumption,
            output_effective_labor=RAMSEY_START_STEADY_STATE.output,
            net_interest_rate=RAMSEY_START_STEADY_STATE.net_interest_rate,
            post_transition_omega_x=design.parameters.omega_x,
            post_transition_consumption_and_shadow_value='solved_by_bvp',
        )
    (design.output_directory/'paths_manifest.json').write_text(
        json.dumps(manifest, indent=2)+'\n', encoding='utf-8')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--design', choices=tuple(DESIGNS), default='main')
    parser.add_argument('--sigma', type=float)
    parser.add_argument('--export-horizon', type=float)
    parser.add_argument('--points', type=int, default=1201)
    parser.add_argument('--verify-long-horizon', action='store_true')
    args = parser.parse_args()
    design = DESIGNS[args.design]
    if args.verify_long_horizon:
        for sigma in design.sigmas:
            source = load_solution(design.cache_directory/f'{key(sigma)}_refined.npz')
            validate_solution_design(source, design, sigma)
            target = design.cache_directory/f'{key(sigma)}_long.npz'
            if not target.exists():
                longer = refine_global_horizon(source, source.horizon+500,
                                                nodes=601, tolerance=1e-9,
                                                boundary_tolerance=1e-11)
                save_solution(longer, target)
            else:
                validate_solution_design(load_solution(target), design, sigma)
            print(f'{design.name}/{key(sigma)}: second horizon extension saved', flush=True)
    elif args.export_horizon is not None:
        export_paths(args.export_horizon, args.points, design)
    elif args.sigma is not None:
        run(args.sigma, design)
    else:
        parser.error('Choose --sigma or --export-horizon.')
