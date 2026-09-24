"""Illustrate Corollary 1 without changing any earlier simulation.

Run --chi 7.5 and --chi 1.5 to solve and audit monopoly paths, then --report
to solve the continued-competition benchmark and render the comparison.
All parameters are illustrative; no empirical moment is targeted.
"""
from dataclasses import asdict, replace
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'.python-packages'), str(ROOT/'scripts')]
import numpy as np
from analyze_axm_finite_cap_bvp import critical_capability_frontier, terminal_point
from simulate_rewrite_illustrative_rsi import make_design as original_design
from simulate_rewrite_finite_frontier import run, key, load_solution, export_paths
from calibrate_rewrite_ai_price import write_json, extend
from audit_rewrite_equilibria import finalize, independent_residuals
from solve_axm_global_finite_cap_bvp import audit_counterfactual_developer_sufficiency

SIGMA = 1.5
PRODUCTIVITIES = (7.5, 1.5)
CAP_THRESHOLD_RATIO = 0.9
INITIAL_CAP_RATIO = 0.9


def make_design(chi):
    old = original_design(chi)
    cap = CAP_THRESHOLD_RATIO * critical_capability_frontier(SIGMA, old.parameters)
    terminal = terminal_point(SIGMA, cap, old.parameters)
    # An illustrative inherited stock, independent of research productivity.
    # This is not a claim that the pre-event competitive economy is stationary.
    k0 = terminal.auxiliary['capital_effective_labor_ratio']
    name = f'monopoly_growth_reversal_chi_{str(float(chi)).replace(".", "_")}'
    return replace(old, name=name, sigmas=(SIGMA,), frontier=cap,
        initial_capability=INITIAL_CAP_RATIO*cap, initial_capital=k0,
        initial_capital_rule='common', display_horizon=500.,
        output_directory=ROOT/'numerical_rewrite'/name,
        cache_directory=ROOT/'tmp'/f'rewrite_bvp_{name}',
        initial_stock_reference=(
            'Illustrative Corollary 1 experiment: sigma=1.5, Bbar=0.9*Bmon, '
            'B0=0.9*Bbar, A0=N0=1. K0/(A0*N0) equals the limiting monopoly '
            'capital/effective-labor ratio at Bbar, independently of chi. '
            'The competitive reference is a nonstationary equilibrium from '
            'these same stocks, not a labor-bottleneck BGP. Exclusive rights '
            'are unexpected and cover existing AI and future improvements.'))


def solve_monopoly(chi):
    design = make_design(chi)
    spec = dict(parameters=asdict(design.parameters), sigma=SIGMA,
        frontier=design.frontier, initial_capability=design.initial_capability,
        initial_capital=design.initial_capital,
        initial_stock_reference=design.initial_stock_reference)
    path = design.output_directory/'scenario.json'
    if path.exists() and json.loads(path.read_text()) != spec:
        raise ValueError('Existing experiment differs; do not overwrite it.')
    write_json(path, spec)
    run(SIGMA, design)
    extend(SIGMA, design)
    report = finalize(design)[0]
    sol = load_solution(design.cache_directory/f'{key(SIGMA)}_long.npz')
    times = np.linspace(.001, 10., 801)
    checks = [independent_residuals(sol, h, times) for h in (.0003, .0001)]
    concavity = audit_counterfactual_developer_sufficiency(sol,
        time_points=161, capability_points=161, sample_times=np.linspace(0,10,161))
    passes = concavity['developer_sufficiency_gate_passes'] and all(
        c['maximum_ode_residual'] < 1e-6 and
        c['maximum_research_foc_residual'] < 1e-9 and
        c['maximum_monopoly_foc_residual'] < 1e-9 for c in checks)
    report['early_window_checks'] = dict(passes=bool(passes),
        independent_residuals=checks, concavity=concavity)
    report['equilibrium_certified'] = bool(report['equilibrium_certified'] and passes)
    report['status'] = 'numerically_admitted' if report['equilibrium_certified'] else 'not_admitted'
    write_json(design.output_directory/f'{key(SIGMA)}_audit.json', report)
    if not report['equilibrium_certified']:
        raise RuntimeError('Monopoly path failed admission; no figure export.')
    # This is not a midpoint-calibrated experiment. A nonmonotonic labor
    # share need not cross half its distance to the limit inside 500 years.
    # All equation, horizon, and optimality admission checks above still apply.
    export_paths(500., 4001, design, additional_times=np.linspace(0,10,1001),
                 track_transition_midpoint=False)
    print(design.name, 'fully admitted and exported', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--chi', type=float, choices=PRODUCTIVITIES)
    parser.add_argument('--report', action='store_true')
    args = parser.parse_args()
    if args.report:
        from report_monopoly_growth_reversal import main
        main()
    elif args.chi is not None:
        solve_monopoly(args.chi)
    else:
        parser.error('Choose --chi or --report.')
