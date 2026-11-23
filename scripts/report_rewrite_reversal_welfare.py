"""Welfare in the existing growth-reversal experiment, with a transitioning benchmark.

--export-checkpoints reproduces the original competitive reference at its
unchanged settings and extracts scalar consumption splines. It reads, but
does not solve again or overwrite, the original monopoly checkpoints.
Default calculation uses only committed extracts and verifies their hashes.
"""
import argparse
import csv
from dataclasses import asdict
import math
from pathlib import Path
import sys

import numpy as np
from scipy.integrate import quad
from scipy.interpolate import PPoly

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from report_rewrite_welfare import (
    OUT, CHIS, SIGMA, STAGES, read_json, write_json, digest, identifier,
    weighted_integral, affine_tail, ce_from_integral)

REFERENCE = ROOT / 'numerical_rewrite/monopoly_growth_reversal_burnin'


def inputs(chi):
    folder = ROOT / f'numerical_rewrite/monopoly_growth_reversal_burnin_chi_{identifier(chi)}'
    scenario = read_json(folder / 'scenario.json')
    audit = read_json(folder / 'sigma_1_50_audit.json')
    manifest = read_json(folder / 'paths_manifest.json')
    initial = read_json(REFERENCE / 'initialization.json')
    competitive_audit = read_json(REFERENCE / 'competitive_audit.json')
    p, stocks = scenario['parameters'], initial['stocks']
    if (not audit['equilibrium_certified'] or audit['status'] != 'numerically_admitted'
            or not audit['early_window_checks']['passes'] or not competitive_audit['passes']):
        raise ValueError('Both market structures must pass their original equilibrium checks.')
    if (manifest['csv_sha256'] != digest(folder / 'equilibrium_paths.csv')
            or manifest['checkpoint_sha256']['sigma_1_50'] != audit['checkpoint_sha256']):
        raise ValueError('Monopoly CSV and checkpoint provenance differ.')
    if scenario['parameters'] != audit['parameters'] or p != manifest['parameters']:
        raise ValueError('Parameter provenance differs.')
    if (scenario['frontier'] != manifest['frontier'] or scenario['frontier'] != audit['frontier']
            or scenario['sigma'] != SIGMA or audit['sigma_xl'] != SIGMA):
        raise ValueError('Technology provenance differs.')
    for value, expected in ((scenario['initial_capital'], stocks['K0']),
                            (scenario['initial_capability'], stocks['B0']),
                            (p['initial_labor_productivity'], stocks['A0']),
                            (p['initial_population'], stocks['N0']), (p['chi'], chi)):
        if value != expected:
            raise ValueError('The paths do not inherit the original common initial state.')
    if not p['discount'] > p['population_growth']:
        raise ValueError('Require finite discounted log utility.')
    files = [folder / name for name in ('scenario.json', 'sigma_1_50_audit.json',
                                       'paths_manifest.json', 'equilibrium_paths.csv')]
    files += [REFERENCE / name for name in ('initialization.json', 'competitive_audit.json',
                                           'continued_competition.csv', 'comparison_paths.csv')]
    provenance = {path.relative_to(ROOT).as_posix(): digest(path) for path in files}
    return folder, scenario, audit, initial, provenance


def add_affine(spline, slope, intercept=0.):
    coefficients = spline.c.copy()
    coefficients[-2] += slope
    coefficients[-1] += slope * spline.x[:-1] + intercept
    return PPoly(coefficients, spline.x.copy(), extrapolate=False)


def difference(first, second):
    """Exact polynomial regridding, not interpolation between sampled levels."""
    end = min(first.x[-1], second.x[-1])
    knots = np.unique(np.r_[first.x[first.x < end], second.x[second.x < end], end])
    left = knots[:-1]
    coefficients = np.stack([(first(left, order) - second(left, order)) / math.factorial(order)
                             for order in (3, 2, 1, 0)])
    return PPoly(coefficients, knots, extrapolate=False)


def export_checkpoints():
    from define_positive_ai_branch import PositiveAIBenchmarkParameters
    from solve_competitive_ai_transition import solve, audit as check_competition
    from simulate_rewrite_finite_frontier import load_solution
    _, scenario, _, _, _ = inputs(7.5)
    p = PositiveAIBenchmarkParameters(**scenario['parameters'])
    args = (scenario['initial_capability'], SIGMA, p, scenario['initial_capital'])
    # Same solver, horizons, tolerance and stocks as the original published reference.
    short = solve(*args, horizon=1200.)
    long = solve(*args, horizon=1800., previous=short)
    competitive_checks = check_competition(short, long)
    if not competitive_checks['passes']:
        raise ValueError('Reproduced competitive reference failed the unchanged checks.')
    # Extend only the same reference, in memory, to cover the full monopoly horizon.
    longest = load_solution(ROOT / 'tmp/rewrite_bvp_monopoly_growth_reversal_burnin_chi_7_5/sigma_1_50_long.npz')
    extended = solve(*args, horizon=longest.horizon, previous=long)
    extension_checks = check_competition(long, extended)
    if not extension_checks['passes']:
        raise ValueError('Extended competitive reference failed the unchanged checks.')
    competitive = {}
    for name, path in (('short', short), ('long', long), ('extended', extended)):
        coeff = path.raw.sol.c[:, :, 0] + path.raw.sol.c[:, :, 1]
        scalar = PPoly(coeff, path.raw.sol.x.copy(), extrapolate=False)
        trend = path.trend + p.population_growth + p.labor_productivity_growth
        scale = p.initial_labor_productivity * p.initial_population
        competitive[name] = add_affine(scalar, trend, math.log(scale))
    with (REFERENCE / 'continued_competition.csv').open(newline='', encoding='utf-8') as stream:
        benchmark_rows = list(csv.DictReader(stream))
    times = np.array([float(row['time']) for row in benchmark_rows])
    log_scale = math.log(p.initial_labor_productivity * p.initial_population)
    csv_logs = np.array([math.log(float(row['consumption_effective_labor'])) for row in benchmark_rows])
    csv_logs += log_scale + (p.population_growth + p.labor_productivity_growth) * times
    reproduction_error = float(np.max(np.abs(competitive['long'](times) - csv_logs)))
    if reproduction_error > 2e-7:
        raise ValueError('Reproduced competition differs from the stored counterfactual.')
    for chi in CHIS:
        _, scenario, admitted, _, provenance = inputs(chi)
        cache = ROOT / f'tmp/rewrite_bvp_monopoly_growth_reversal_burnin_chi_{identifier(chi)}'
        stages = {}
        for stage in STAGES:
            source = cache / f'sigma_1_50_{stage}.npz'
            if stage == 'long' and digest(source) != admitted['checkpoint_sha256']:
                raise ValueError('Monopoly checkpoint differs from its admission report.')
            sol = load_solution(source)
            if (asdict(sol.parameters) != scenario['parameters']
                    or sol.initial_capital != scenario['initial_capital']
                    or sol.initial_capability != scenario['initial_capability']
                    or sol.terminal.frontier != scenario['frontier']
                    or sol.terminal.sigma_xl != SIGMA):
                raise ValueError('Monopoly checkpoint has different economic primitives.')
            scalar = PPoly(sol.raw.sol.c[:, :, 2].copy(), sol.raw.sol.x.copy(), extrapolate=False)
            mon = add_affine(scalar, sol.terminal.terminal_growth)
            comp_name = {'base':'short', 'refined':'long', 'long':'extended'}[stage]
            comp = competitive[comp_name]
            gap = difference(mon, comp)
            stages[stage] = dict(x=gap.x.tolist(), coefficients=gap.c.tolist(),
                                 horizon=float(gap.x[-1]), monopoly_horizon=sol.horizon,
                                 competitive_horizon=float(comp.x[-1]),
                                 monopoly_checkpoint_sha256=digest(source))
        write_json(OUT / f'reversal_chi_{identifier(chi)}_consumption_splines.json',
                   dict(chi=chi, sigma=SIGMA, variable='log(C_mon/C_comp)=log(c_mon/c_comp)',
                        source_sha256=provenance, stages=stages,
                        competitive_reproduction_checks=competitive_checks,
                        competitive_extension_checks=extension_checks,
                        competitive_csv_maximum_log_consumption_change=reproduction_error))


def calculate_case(chi):
    _, scenario, audit, initial, provenance = inputs(chi)
    source = OUT / f'reversal_chi_{identifier(chi)}_consumption_splines.json'
    stored = read_json(source)
    if (stored['source_sha256'] != provenance or stored['chi'] != chi or stored['sigma'] != SIGMA
            or stored['stages']['long']['monopoly_checkpoint_sha256'] != audit['checkpoint_sha256']
            or not stored['competitive_reproduction_checks']['passes']
            or not stored['competitive_extension_checks']['passes']):
        raise ValueError('Reversal welfare extracts have stale provenance.')
    p = scenario['parameters']
    beta = p['discount'] - p['population_growth']
    g_mon = p['labor_productivity_growth']
    g_comp = read_json(REFERENCE / 'competitive_audit.json')['limiting_output_per_worker_growth']
    slope = g_mon - g_comp
    stages, splines = {}, {}
    for stage in STAGES:
        data = stored['stages'][stage]
        spline = PPoly(np.asarray(data['coefficients']), np.asarray(data['x']), extrapolate=False)
        end = data['horizon']
        if spline.x[0] != 0 or spline.x[-1] != end:
            raise ValueError('Invalid solved interval.')
        value = weighted_integral(spline, beta, end)
        tail = affine_tail(float(spline(end)), slope, beta, end)
        stages[stage] = dict(horizon=end, integrated_utility_difference=value,
                             tail_utility_difference=tail,
                             utility_difference_per_initial_person=value + tail,
                             consumption_equivalent=ce_from_integral(value + tail, beta),
                             quadrature_8_16_difference=abs(value - weighted_integral(spline, beta, end, 8)),
                             terminal_growth_gap_error=abs(float(spline(end, 1)) - slope))
        splines[stage] = spline
    final, spline = stages['long'], splines['long']
    with (REFERENCE / 'comparison_paths.csv').open(newline='', encoding='utf-8') as stream:
        csv_rows = [row for row in csv.DictReader(stream) if row['scenario'] == f'Monopoly, chi = {chi:g}']
    times = np.array([float(row['time']) for row in csv_rows])
    csv_logs = np.array([math.log(float(row['consumption_counterfactual_ratio'])) for row in csv_rows])
    csv_gap = float(np.max(np.abs(spline(times) - csv_logs)))
    other, error = quad(lambda t: math.exp(-beta*t) * float(spline(t)),
                        0, spline.x[-1], points=spline.x[1:-1],
                        epsabs=1e-10, epsrel=1e-10, limit=len(spline.x) + 100)
    cutoffs = {}
    for end in (10., 50., 100., 250., 500., 1000.):
        value = weighted_integral(spline, beta, end)
        with_tail = value + affine_tail(float(spline(end)), slope, beta, end)
        cutoffs[str(int(end))] = dict(discounted_log_contribution=beta*value,
                                     ce_without_tail=ce_from_integral(value, beta),
                                     ce_with_limiting_growth_tail=ce_from_integral(with_tail, beta),
                                     ce_change_from_full_solution=ce_from_integral(with_tail, beta)-final['consumption_equivalent'])
    checks = dict(csv_maximum_log_ratio_gap=csv_gap,
                  independent_quad_difference=abs(other-final['integrated_utility_difference']),
                  independent_quad_error_estimate=error,
                  maximum_quadrature_difference=max(s['quadrature_8_16_difference'] for s in stages.values()),
                  base_to_refined_ce_change=abs(stages['base']['consumption_equivalent']-stages['refined']['consumption_equivalent']),
                  refined_to_long_ce_change=abs(stages['refined']['consumption_equivalent']-final['consumption_equivalent']),
                  final_tail_ce_effect=abs(ce_from_integral(final['integrated_utility_difference'], beta)-final['consumption_equivalent']))
    if (csv_gap > 2e-7 or checks['independent_quad_difference'] > 1e-9
            or checks['maximum_quadrature_difference'] > 1e-9
            or checks['base_to_refined_ce_change'] > 2e-5
            or checks['refined_to_long_ce_change'] > 2e-7
            or final['terminal_growth_gap_error'] > 1e-7
            or abs(cutoffs['500']['ce_change_from_full_solution']) > 1e-6):
        raise ValueError(f'Reversal welfare checks failed: {checks}')
    return dict(chi=chi, sigma=SIGMA, parameters=p, frontier=scenario['frontier'],
                initial_capital=scenario['initial_capital'], initial_capability=scenario['initial_capability'],
                effective_discount=beta, monopoly_growth=g_mon, competitive_growth=g_comp,
                initial_state=initial['stocks'], stages=stages, horizon_checks=cutoffs, checks=checks,
                competitive_reproduction_checks=stored['competitive_reproduction_checks'],
                competitive_extension_checks=stored['competitive_extension_checks'],
                source_sha256={**provenance, source.relative_to(ROOT).as_posix():digest(source)},
                numerically_verified=True)


def build_reversal_report():
    cases = [calculate_case(chi) for chi in CHIS]
    if cases[0]['initial_state'] != cases[1]['initial_state']:
        raise ValueError('The research productivities do not share the same initial state.')
    if {k:v for k,v in cases[0]['parameters'].items() if k != 'chi'} != {
            k:v for k,v in cases[1]['parameters'].items() if k != 'chi'}:
        raise ValueError('More than research productivity differs between reversal cases.')
    return dict(scope='Existing near-AI-dominated competitive state followed by monopoly growth reversal', cases=cases)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--export-checkpoints', action='store_true')
    args = parser.parse_args()
    if args.export_checkpoints:
        export_checkpoints()
    for case in build_reversal_report()['cases']:
        print(dict(chi=case['chi'], ce=case['stages']['long']['consumption_equivalent'],
                   checks=case['checks'], horizon_checks=case['horizon_checks']))
