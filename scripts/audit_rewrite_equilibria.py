"""Independent dated residuals and final admission of a simulation design."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'.python-packages'))
sys.path.insert(0, str(ROOT/'scripts'))
import numpy as np
from solve_axm_global_finite_cap_bvp import (reconstruct_levels, raw_to_terminal_coordinates,
    audit_global_solution, compare_global_solutions, audit_counterfactual_developer_sufficiency)
from solve_near_unit_ai_bvp import solve_monopoly_static_block
from simulate_rewrite_finite_frontier import (
    DESIGNS, MAIN_DESIGN, key, load_solution, validate_solution_design,
)


def independent_residuals(sol, step, sample_times=None):
    times = (np.linspace(1., sol.horizon-1., 1001) if sample_times is None
             else np.asarray(sample_times, dtype=float))
    if (times.ndim != 1 or times.size == 0 or not np.all(np.isfinite(times))
            or np.min(times)-2*step < 0 or np.max(times)+2*step > sol.horizon):
        raise ValueError('Finite-difference sample times must stay inside the solved horizon.')
    # Five-point differences of the saved spline VALUES, not its derivatives
    # or the solver RHS. All four original equations are reconstructed below.
    derivative = (-sol.raw.sol(times+2*step)+8*sol.raw.sol(times+step)
                  -8*sol.raw.sol(times-step)+sol.raw.sol(times-2*step))/(12*step)
    derivative += sol.terminal.terminal_growth
    v = reconstruct_levels(times, sol.raw.sol(times), sol)
    p, bbar = sol.parameters, sol.terminal.frontier
    yk = np.exp(v['log_output']-v['log_capital'])
    ck = np.exp(v['log_consumption']-v['log_capital'])
    uk = np.exp(v['log_inference_compute']-v['log_capital'])
    mk = np.exp(v['log_research_compute']-v['log_capital'])
    log_bm = v['log_capability']+v['log_research_compute']
    approach = np.exp(math.log(p.chi)+p.eta*log_bm-math.log(bbar))
    gb = np.exp(math.log(p.chi)+p.eta*log_bm+v['log_remaining_frontier_share']-v['log_capability'])
    sx = v['ai_ces_share']
    e = (1-sx)/sol.terminal.sigma_xl+p.alpha*sx
    rate = p.alpha*yk-p.depreciation
    service_return = np.exp(v['log_ai_services']-v['log_shadow_value']-2*v['log_capability'])
    exact = np.array([yk-ck-uk-mk-p.depreciation, gb+approach,
                      p.population_growth+rate-p.discount,
                      rate-service_return-p.eta*gb+approach])
    foc = (math.log(p.chi*p.eta)+v['log_shadow_value']+p.eta*v['log_capability']
           +(p.eta-1)*v['log_research_compute']+v['log_remaining_frontier_share'])
    # Algebraically identical to 1-e, without subtracting an elasticity
    # rounded close to one. Keep the original 1e-9 admission threshold.
    revenue_fraction = ((sol.terminal.sigma_xl-1)/sol.terminal.sigma_xl
                        +(1/sol.terminal.sigma_xl-p.alpha)*sx)
    monopoly = (np.log((1-p.alpha)*sx*revenue_fraction)+v['log_output']
                 +v['log_capability']-v['log_ai_services'])
    return dict(difference_step=step, samples=len(times),
                maximum_ode_residual=float(np.max(np.abs(derivative-exact))),
                maximum_research_foc_residual=float(np.max(np.abs(foc))),
                maximum_monopoly_foc_residual=float(np.max(np.abs(monopoly))))


def terminal_support_bound(sol, fraction=.75):
    p, t, time = sol.parameters, sol.terminal, sol.horizon
    if not 1 < t.sigma_xl <= 1/p.alpha or not fraction > (1-2*p.alpha)/(1-p.alpha):
        raise ValueError('The analytical upper-domain concavity bound does not apply.')
    v = reconstruct_levels(np.array([time]), sol.raw.sol(time)[:,None], sol)
    lb, ly, lp = [v[k][0] for k in ('log_capability', 'log_output', 'log_remaining_frontier_share')]
    b = math.exp(lb)
    u = math.exp(v['log_inference_compute'][0]-ly)
    m = math.exp(v['log_research_compute'][0]-ly)
    revenue = (1-p.alpha)*v['ai_ces_share'][0]
    za = -lp
    z0 = -math.log1p(-sol.initial_capability/t.frontier)
    al = math.log(sol.initial_effective_labor_scale)+(p.population_growth+p.labor_productivity_growth)*time
    other = solve_monopoly_static_block(v['log_capital'][0], math.log(fraction*t.frontier), al, t.sigma_xl, p)
    coefficient, exponent = (1-p.eta)/p.eta, p.eta/(1-p.eta)
    hstar = ((1-p.alpha)*other.ai_ces_share*math.exp(other.log_output-ly)
             -math.exp(other.log_inference_compute-ly)
             +coefficient*m*(fraction*t.frontier/b)**exponent)
    slope_z = (u+m)*math.exp(lp)*t.frontier/b
    margin = revenue-u+coefficient*m-slope_z*(za-z0)-hstar
    limit = p.alpha*(1-p.alpha)*(1-fraction**((1-p.alpha)/p.alpha))
    return dict(frontier_fraction=fraction, terminal_capability_above_cutoff=b>fraction*t.frontier,
                terminal_margin=margin, analytical_limiting_margin=limit)


def finalize(design=MAIN_DESIGN):
    reports=[]
    for sigma in design.sigmas:
        name=key(sigma)
        report=json.loads((design.output_directory/f'{name}_audit.json').read_text())
        cache=design.cache_directory/f'{name}_long.npz'
        sol=load_solution(cache)
        shorter=load_solution(design.cache_directory/f'{name}_refined.npz')
        validate_solution_design(sol, design, sigma)
        validate_solution_design(shorter, design, sigma)
        shorter.terminal=sol.terminal
        report['first_horizon_comparison']=report.get('first_horizon_comparison',report['horizon_comparison'])
        report['horizon_comparison']=compare_global_solutions(
            shorter, sol, common_window=design.display_horizon)
        report['audit']=audit_global_solution(sol)
        report['counterfactual_developer_sufficiency']=audit_counterfactual_developer_sufficiency(
            sol, time_points=161, capability_points=161)
        checks=[independent_residuals(sol, h) for h in (.003,.001)]
        report['independent_dated_checks']=checks
        optimality=report['counterfactual_developer_sufficiency']['developer_sufficiency_gate_passes']
        report['optimality_method']='global_profit_concavity_in_research_depth'
        if not optimality and sigma==1.5:
            support=[]
            for dates, states in ((81,101),(321,241)):
                result=json.loads((design.output_directory/f'{name}_support_{dates}_{states}.json').read_text())
                if result['checkpoint_sha256'] != hashlib.sha256(cache.read_bytes()).hexdigest():
                    raise ValueError('Support audit does not belong to the final checkpoint.')
                support.append({k:v for k,v in result.items() if k!='checks'})
            report['global_hamiltonian_support']=support
            bound=terminal_support_bound(sol)
            report['analytical_support_continuation']=bound
            optimality=(all(s['support_diagnostic_passes'] and s['maximum_own_gap']<1e-10
                            and s['maximum_tail_derivative_ratio']<=1 for s in support)
                        and bound['terminal_capability_above_cutoff'] and bound['terminal_margin']>0)
            report['optimality_method']='global_hamiltonian_upper_tangent_with_analytical_continuation'
        raw=sol.raw.sol(sol.horizon)+sol.terminal.terminal_growth*sol.horizon
        terminal_coordinates=raw_to_terminal_coordinates(sol.horizon, raw, sol.terminal, sol.parameters,
                                                         sol.initial_effective_labor_scale)
        report['maximum_terminal_coordinate_gap']=float(np.max(np.abs(terminal_coordinates-sol.terminal.coordinates)))
        independent=all(c['maximum_ode_residual']<1e-6 and c['maximum_research_foc_residual']<1e-9
                        and c['maximum_monopoly_foc_residual']<1e-9 for c in checks)
        comparison=report['horizon_comparison']
        report['equilibrium_certified']=bool(report['audit']['dated_candidate_accepted'] and independent
            and optimality and comparison['maximum_initial_jump_change']<2e-5
            and comparison['maximum_common_window_coordinate_change']<2e-5
            and report['maximum_terminal_coordinate_gap']<1e-4)
        report['status']='numerically_admitted' if report['equilibrium_certified'] else 'not_admitted'
        report['checkpoint_sha256']=hashlib.sha256(cache.read_bytes()).hexdigest()
        report['checkpoint_filename']=cache.name
        report['design']=design.name
        report['long_run_scope']='Regime-specific stable continuation, both TVCs, and sufficient developer optimality.'
        (design.output_directory/f'{name}_audit.json').write_text(
            json.dumps(report, indent=2, allow_nan=False)+'\n', encoding='utf-8')
        print(name, report['status'], 'independent=',checks, 'terminal gap=',report['maximum_terminal_coordinate_gap'], flush=True)
        reports.append(report)
    return reports


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--design',choices=tuple(DESIGNS),default='main')
    arguments=parser.parse_args()
    finalize(DESIGNS[arguments.design])
