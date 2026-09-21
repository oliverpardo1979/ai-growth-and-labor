"""Check a global upper tangent to the research-depth Hamiltonian.

This is an alternative sufficient optimality condition, not a relaxation of
the FOCs. Fix the candidate q_R=q*psi at each date and maximize over all M.
The resulting Hamiltonian is pi(B)+(1-eta)/eta*M_a*(B/B_a)**(eta/(1-eta)).
It need not be globally concave if it lies below its tangent at the candidate
state throughout the reachable domain. A separate appendix proof is required
before using these diagnostics for numerical equilibrium admission.
"""
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
from scipy.optimize import minimize_scalar
from solve_near_unit_ai_bvp import solve_monopoly_static_block
from solve_axm_global_finite_cap_bvp import _capability_logs, reconstruct_levels
from simulate_rewrite_finite_frontier import (
    DESIGNS, key, load_solution, validate_solution_design,
)


def dated_support(solution, time, points=121):
    """Minimize the normalized tangent gap over all counterfactual capabilities.

    The unbounded research-depth tail is covered by an analytical derivative
    upper bound. Inspect every sampled local minimum, not just the best bin.
    All values are divided by candidate Y to avoid large-level overflow.
    """
    p, terminal = solution.parameters, solution.terminal
    values = np.asarray(solution.raw.sol(time))[:, None]
    v = reconstruct_levels(np.array([time]), values, solution)
    la, ly = v['log_capability'][0], v['log_output'][0]
    logpsi = v['log_remaining_frontier_share'][0]
    ba = math.exp(la)/terminal.frontier
    za = -logpsi
    u = math.exp(v['log_inference_compute'][0]-ly)
    m = math.exp(v['log_research_compute'][0]-ly)
    revenue = (1-p.alpha)*v['ai_ces_share'][0]
    mu = p.eta/(1-p.eta)
    coefficient = (1-p.eta)/p.eta
    ha = revenue-u+coefficient*m
    slope = (u+m)*math.exp(logpsi)/ba  # d(H/Y_a)/d(R_B/Bbar).
    al = math.log(solution.initial_effective_labor_scale)+(p.population_growth+p.labor_productivity_growth)*time
    lk = v['log_capital'][0]
    lower = math.log(solution.initial_capability/(terminal.frontier-solution.initial_capability))
    actual = la-math.log(terminal.frontier)-logpsi

    def counter(logit):
        lb, _, lp = _capability_logs(logit, terminal.frontier)
        static = solve_monopoly_static_block(lk, lb, al, terminal.sigma_xl, p)
        pib = ((1-p.alpha)*static.ai_ces_share*math.exp(static.log_output-ly)
               - math.exp(static.log_inference_compute-ly))
        mb = m*math.exp(mu*(lb-la))
        return pib+coefficient*mb, -lp

    def gap(logit):
        hb, zb = counter(float(logit))
        return ha+slope*(zb-za)-hb

    # For z>=z_top, H_z/Y_a <= exp(-z_top)*Bbar*
    # [X(Bbar)/(Y_a*B_top^2)+M_hat(Bbar)/(Y_a*B_top)].
    # X and M_hat increase in B. If this bound is below the candidate
    # tangent slope, the gap is increasing on the entire unbounded tail.
    capped = solve_monopoly_static_block(lk, math.log(terminal.frontier), al, terminal.sigma_xl, p)
    ztop = max(30.0, za+2)
    for _ in range(20):
        btop = terminal.frontier*(-math.expm1(-ztop))
        bound = math.exp(-ztop)*terminal.frontier*(
            math.exp(capped.log_ai_services-ly)/btop**2
            + m*math.exp(mu*(math.log(terminal.frontier)-la))/btop)
        if bound <= slope:
            break
        ztop += math.log(bound/slope)+1
    else:
        raise RuntimeError('Could not certify the unbounded counterfactual tail.')
    upper = ztop+math.log1p(-math.exp(-ztop))
    grid = np.unique(np.r_[np.linspace(lower, upper, points), actual])
    gaps = np.array([gap(x) for x in grid])
    index = int(np.argmin(gaps))
    minimum, location = float(gaps[index]), float(grid[index])
    for j in range(1, len(grid)-1):
        if gaps[j] <= gaps[j-1] and gaps[j] <= gaps[j+1]:
            result = minimize_scalar(gap, bounds=(grid[j-1], grid[j+1]), method='bounded',
                                     options={'xatol':1e-10})
            if result.fun < minimum:
                minimum, location = float(result.fun), float(result.x)
    # A nontrivial diagnostic: the exact candidate has zero support gap.
    own_gap = gap(actual)
    return dict(time=float(time), minimum_gap=minimum,
                counterfactual_logit=location, own_gap=float(own_gap),
                actual_capability_ratio=ba, unbounded_tail_derivative_ratio=bound/slope)


def audit_support(solution, time_points=161, capability_points=121, sample_times=None):
    times = (np.linspace(0, solution.horizon, time_points) if sample_times is None
             else np.asarray(sample_times, dtype=float))
    if (times.ndim != 1 or times.size == 0 or not np.all(np.isfinite(times))
            or np.min(times) < 0 or np.max(times) > solution.horizon):
        raise ValueError('Support sample times must stay inside the solved horizon.')
    checks = [dated_support(solution, float(t), capability_points) for t in times]
    worst = min(checks, key=lambda c:c['minimum_gap'])
    # Reconstructing revenue and spending involves subtraction. The gap is
    # scaled by Y, and -1e-10 is a rounding/optimization diagnostic bound,
    # not a changed economic condition. Repeat at twice the grid resolution.
    return dict(time_points=len(times), capability_points=capability_points,
                gap_roundoff_tolerance=1e-10, worst=worst,
                maximum_own_gap=max(abs(c['own_gap']) for c in checks),
                maximum_tail_derivative_ratio=max(c['unbounded_tail_derivative_ratio'] for c in checks),
                support_diagnostic_passes=worst['minimum_gap'] >= -1e-10,
                checks=checks)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--design', choices=tuple(DESIGNS), default='main')
    parser.add_argument('--sigma', type=float, required=True)
    parser.add_argument('--time-points', type=int, default=161)
    parser.add_argument('--capability-points', type=int, default=121)
    args = parser.parse_args()
    design = DESIGNS[args.design]
    checkpoint = design.cache_directory/f'{key(args.sigma)}_long.npz'
    if not checkpoint.exists():
        checkpoint = design.cache_directory/f'{key(args.sigma)}_refined.npz'
    sol = load_solution(checkpoint)
    validate_solution_design(sol, design, args.sigma)
    result = audit_support(sol, args.time_points, args.capability_points)
    result['checkpoint_sha256'] = hashlib.sha256(checkpoint.read_bytes()).hexdigest()
    target = design.output_directory/f'{key(args.sigma)}_support_{args.time_points}_{args.capability_points}.json'
    target.write_text(json.dumps(result, indent=2, allow_nan=False)+'\n', encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k != 'checks'}, indent=2), flush=True)
