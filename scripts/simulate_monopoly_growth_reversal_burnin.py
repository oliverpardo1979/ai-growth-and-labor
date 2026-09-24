"""Growth reversal after a competitive prehistory near long-run growth.

Keep the original reversal experiment intact. Advance all predetermined
stocks along its competitive equilibrium, then grant unexpected monopoly
rights. The research-productivity parameters retain their original units.
"""
from dataclasses import asdict, replace
import argparse
import math
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'.python-packages'), str(ROOT/'scripts')]
import numpy as np
from simulate_monopoly_growth_reversal import (
    make_design as seed_design, solve_monopoly, PRODUCTIVITIES, SIGMA)
from solve_competitive_ai_transition import solve, audit, rows
from calibrate_rewrite_ai_price import write_json
from report_monopoly_growth_reversal import write_csv

OUT = ROOT/'numerical_rewrite'/'monopoly_growth_reversal_burnin'
RATE_TOLERANCE = .001  # 0.1 percentage point, fixed before selecting the event.


def prepare():
    seed = seed_design(7.5)
    p = seed.parameters
    args = (seed.initial_capability, SIGMA, p, seed.initial_capital)
    short = solve(*args, horizon=1200.)
    long = solve(*args, horizon=1800., previous=short)
    checks = audit(short, long, display_horizon=1000.)
    if not checks['passes']:
        raise RuntimeError('Competitive prehistory failed admission.')
    limits = dict(net_interest=checks['limiting_interest_rate'],
        output_per_person_growth=checks['limiting_output_per_worker_growth'],
        wage_growth=checks['limiting_wage_growth'])
    annual = rows(long, np.arange(0., 1001.))
    errors = np.array([max(abs(r[k]-v) for k,v in limits.items()) for r in annual])
    # The first whole year after which every sampled subsequent year remains
    # within tolerance, not a transient crossing of the selected criterion.
    eligible = np.flatnonzero(np.maximum.accumulate(errors[::-1])[::-1] < RATE_TOLERANCE)
    if not len(eligible):
        raise RuntimeError('No near-limit date within the inspected prehistory.')
    event = int(eligible[0])
    state = annual[event]
    a0 = p.initial_labor_productivity*math.exp(p.labor_productivity_growth*event)
    n0 = p.initial_population*math.exp(p.population_growth*event)
    stocks = dict(A0=a0, N0=n0, K0=state['capital_effective_labor']*a0*n0,
                  B0=seed.initial_capability)
    # Re-solve from inherited *physical* stocks, verifying a change of time
    # origin rather than a change in technology, population, or compute units.
    newp = replace(p, initial_labor_productivity=a0, initial_population=n0)
    newargs = (stocks['B0'], SIGMA, newp, stocks['K0'])
    rebased_short = solve(*newargs, horizon=1200.)
    rebased_long = solve(*newargs, horizon=1800., previous=rebased_short)
    rebased_audit = audit(rebased_short, rebased_long)
    t = np.linspace(0,500,1001)
    inherited = rows(long, t+event)
    restarted = rows(rebased_long, t)
    fields = ('capital_effective_labor','consumption_effective_labor',
              'output_effective_labor','wage_productivity')
    rebase_error = max(abs(math.log(x[k]/y[k]))
        for x,y in zip(inherited,restarted) for k in fields)
    if not rebased_audit['passes'] or rebase_error > 2e-7:
        raise RuntimeError('Inherited competitive path is inconsistent after rebasing.')
    spec = dict(burnin_years=event, rate_tolerance=RATE_TOLERANCE,
        criterion='First whole year with all three rates within 0.1 percentage point of their limits; checked through seed year 1000.',
        seed_parameters=asdict(p), seed_capital=seed.initial_capital,
        stocks=stocks, pre_event=state, limits=limits,
        selection_rate_error=float(errors[event]),
        previous_year_rate_error=float(errors[event-1]),
        maximum_rebase_log_error=rebase_error, prehistory_audit=checks,
        rebased_competitive_audit=rebased_audit)
    filename = OUT/'initialization.json'
    if filename.exists():
        saved = json.loads(filename.read_text())
        if (saved['burnin_years'] != event or any(not math.isclose(
                saved['stocks'][k], v, rel_tol=2e-9) for k,v in stocks.items())):
            raise ValueError('Stored stocks differ; preserve them and investigate.')
        print('Competitive prehistory reproduced; preserving committed initialization and its units.', flush=True)
        return
    write_json(filename, spec)
    prehistory = rows(long, event+np.linspace(-10,0,501))
    for r in prehistory:
        r['seed_time'] = r['time']
        r['time'] -= event
        r['capability_frontier_ratio'] = r['capability']/seed.frontier
        r['ai_services_counterfactual_ratio'] = 1.
    write_csv(OUT/'competitive_prehistory.csv', prehistory)
    print(json.dumps({k:spec[k] for k in ('burnin_years','stocks','selection_rate_error',
        'maximum_rebase_log_error','pre_event')}, indent=2), flush=True)


def make_design(chi):
    old = seed_design(chi)
    init = json.loads((OUT/'initialization.json').read_text())
    stocks = init['stocks']
    name = f'monopoly_growth_reversal_burnin_chi_{str(float(chi)).replace(".", "_")}'
    return replace(old, name=name, initial_capital=stocks['K0'],
        parameters=replace(old.parameters, initial_labor_productivity=stocks['A0'],
                           initial_population=stocks['N0']),
        output_directory=ROOT/'numerical_rewrite'/name,
        cache_directory=ROOT/'tmp'/f'rewrite_bvp_{name}',
        initial_stock_reference=(
            f'Competitive prehistory of {init["burnin_years"]} years; growth of output '
            'per worker, wage growth, and interest are each within 0.1 percentage '
            'point of their AI-dominated limits. A0,N0,K0 are jointly inherited '
            'without changing units; B0 is fixed. Not an exact stationary state. '
            'Unexpected exclusive rights cover existing AI and improvements.'))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--chi', type=float, choices=PRODUCTIVITIES)
    parser.add_argument('--prepare', action='store_true')
    parser.add_argument('--report', action='store_true')
    args = parser.parse_args()
    if args.prepare or not (OUT/'initialization.json').exists():
        prepare()
    if args.chi is not None:
        solve_monopoly(args.chi, design=make_design(args.chi))
    if args.report:
        from report_monopoly_growth_reversal_burnin import main
        main()
    if not (args.prepare or args.chi is not None or args.report):
        parser.error('Choose --prepare, --chi or --report.')
