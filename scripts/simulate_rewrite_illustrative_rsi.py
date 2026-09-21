"""Two illustrative RSI productivities, not empirical calibrations.

Run from the repository root after installing requirements-rewrite.txt:
  python scripts/simulate_rewrite_illustrative_rsi.py
Optional --chi 7.5 or --chi 1.5 selects one comparison; --sigma selects
one elasticity, --solve-only prepares all four, and --finish repeats
admission and exports. Earlier experiments and their checkpoints are untouched.
"""
from dataclasses import asdict, replace
import argparse
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'.python-packages'), str(ROOT/'scripts')]
from calibrate_rewrite_ai_price import make_design as price_design, finish, write_json
from calibrate_rewrite_research_share import checked_moment
from simulate_rewrite_finite_frontier import (
    SIGMAS, key, run, design_initial_stocks, fixed_efficiency_bgp,
    load_solution, validate_solution_design,
)

PRODUCTIVITIES = (7.5, 1.5)
MOMENT_HORIZON_LOG_TOLERANCE = 2e-5


def make_design(chi):
    if chi not in PRODUCTIVITIES:
        raise ValueError('This comparison fixes chi at 7.5 or 1.5.')
    name = 'rsi_chi_'+str(float(chi)).replace('.', '_')
    return replace(price_design(chi, 'rsi_activation'), name=name,
        output_directory=ROOT/'numerical_rewrite'/name,
        cache_directory=ROOT/'tmp'/f'rewrite_bvp_{name}',
        initial_stock_reference=(
            'Illustrative research productivity, not estimated or fitted to a target. '
            'Omega_X=0.10; Bbar=1.10*threshold(1.50); B0/Bbar=0.01. '
            'Each elasticity starts from its own existing-AI, fixed-B pre-RSI BGP '
            'with K0/Y0=3.30. RSI activation is unexpected; K0 and B0 are inherited, '
            'whereas C0, q0 and M0 are solved endogenously. '
            f'Chi={chi:g} is identical across all four elasticities.'))


def prepare(design):
    path = design.output_directory/'scenario.json'
    if path.exists():
        stored = json.loads(path.read_text())
        if (stored['parameters'] != asdict(design.parameters)
                or stored['frontier'] != design.frontier
                or stored['initial_capability'] != design.initial_capability):
            raise ValueError('Stored scenario differs from the requested design.')
        return
    write_json(path, dict(status='awaiting_equilibrium_checks',
        parameters=asdict(design.parameters), frontier=design.frontier,
        initial_capability=design.initial_capability,
        initial_stocks_by_sigma={key(s):list(design_initial_stocks(design,s)) for s in SIGMAS},
        choice='Author-selected illustrative productivities 7.5 and 1.5; no moment is targeted.',
        empirical_target=None, source_code_base_commit='02c0233',
        same_chi_across_elasticities=True, numerical_tolerances_unchanged=True))
    write_json(design.output_directory/'pre_rsi_reference.json', dict(
        scenarios={key(s):fixed_efficiency_bgp(s,design.initial_capability,design.parameters)
                   for s in SIGMAS}))


def finish_scenario(design):
    def record_outcomes(unit):
        outcomes = {}
        for sigma in SIGMAS:
            stages = {}
            for suffix in ('base','refined','long'):
                sol = load_solution(design.cache_directory/f'{key(sigma)}_{suffix}.npz')
                validate_solution_design(sol, design, sigma)
                stages[suffix] = checked_moment(sol)
            gap = max(abs(math.log(v['share']/stages['long']['share'])) for v in stages.values())
            if gap >= MOMENT_HORIZON_LOG_TOLERANCE:
                raise RuntimeError(f'Annual research outcome is horizon-sensitive: sigma={sigma}.')
            outcomes[key(sigma)] = dict(first_year=stages['long'],
                second_year=checked_moment(sol,1.), horizon_stages=stages,
                maximum_horizon_log_change=gap)
        write_json(design.output_directory/'annual_moments.json', dict(
            outcomes_not_targets=True, scenarios=outcomes))
        return dict(outcomes_not_targets=True,
            unit_first_year_research_share=checked_moment(unit)['share'])
    finish(design, calibration_validator=record_outcomes, calibration_filename='scenario.json')
    # A paper comparison is generated only when both complete scenarios exist.
    if all((make_design(chi).output_directory/'summary.json').exists()
           for chi in PRODUCTIVITIES):
        from report_rewrite_illustrative_rsi import write_reports
        write_reports()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--chi', type=float, choices=PRODUCTIVITIES)
    parser.add_argument('--sigma', type=float, choices=SIGMAS)
    parser.add_argument('--solve-only', action='store_true')
    parser.add_argument('--finish', action='store_true')
    parser.add_argument('--prepare-only', action='store_true')
    args = parser.parse_args()
    for chi in PRODUCTIVITIES if args.chi is None else (args.chi,):
        design = make_design(chi)
        prepare(design)
        if args.prepare_only:
            continue
        if args.finish:
            finish_scenario(design)
            continue
        for sigma in SIGMAS if args.sigma is None else (args.sigma,):
            run(sigma,design)
        if args.sigma is None and not args.solve_only:
            finish_scenario(design)


if __name__ == '__main__':
    main()
