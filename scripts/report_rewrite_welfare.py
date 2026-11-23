"""Consumption-equivalent welfare for the existing institutional experiments.

Default: read committed scalar consumption splines, check their provenance,
and write the welfare report/table. --check verifies without writing.
--export-checkpoints extracts those splines from the original local BVP
checkpoints. It never solves or changes an equilibrium or its parameters.
"""
import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
import sys

import numpy as np
from scipy.integrate import quad
from scipy.interpolate import PPoly

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
OUT = ROOT / 'numerical_rewrite/welfare_comparison'
STAGES = ('base', 'refined', 'long')
CHIS = (7.5, 1.5)
SIGMA = 1.5
SIGMAS = (0.9, 1.0, 1.1, 1.5)


def read_json(path):
    return json.loads(path.read_text(encoding='utf-8'))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def identifier(chi):
    return str(chi).replace('.', '_')


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and read_json(path) == data:
        return
    path.write_text(json.dumps(data, indent=2, allow_nan=False) + '\n', encoding='utf-8', newline='\n')


def sigma_key(sigma):
    if sigma not in SIGMAS:
        raise ValueError('Use one of the four original stored elasticities.')
    return 'sigma_' + f'{sigma:.2f}'.replace('.', '_')


def spline_path(chi, sigma):
    # Retain the published sigma=1.5 extracts and their filenames unchanged.
    prefix = '' if sigma == SIGMA else sigma_key(sigma) + '_'
    return OUT / f'{prefix}chi_{identifier(chi)}_consumption_splines.json'


def limiting_monopoly_growth(sigma, parameters, bound):
    """Use the analytical regime, not the final plotted growth observation."""
    p = parameters
    if sigma == 1.0:
        return p['labor_productivity_growth'], 'labor_supported'
    a, w = p['alpha'], p['omega_x']
    critical = ((p['discount'] + p['labor_productivity_growth'] + p['depreciation']) / a) ** (
        a / (1 - a)) / ((1 - a) ** 2 * w ** (sigma / (sigma - 1)))
    if sigma < 1:
        if bound <= critical:
            raise ValueError('This calculation does not cover the omitted AI-bottleneck case.')
        return p['labor_productivity_growth'], 'labor_supported'
    if bound < critical:
        return p['labor_productivity_growth'], 'labor_supported'
    if bound == critical:
        raise ValueError('The threshold boundary case is not one of these experiments.')
    interest_limit = a * ((1 - a) ** 2 * bound * w ** (sigma / (sigma - 1))) ** (
        (1 - a) / a) - p['depreciation']
    return interest_limit - p['discount'], 'ai_dominated'


def inputs(chi, sigma=SIGMA):
    key = sigma_key(sigma)
    folder = ROOT / f'numerical_rewrite/competitive_to_monopoly_chi_{identifier(chi)}'
    scenario = read_json(folder / 'scenario.json')
    audit = read_json(folder / f'{key}_audit.json')
    manifest = read_json(folder / 'paths_manifest.json')
    reference = read_json(folder / 'competitive_reference.json')[key]
    if (scenario['status'] != 'numerically_admitted' or not audit['equilibrium_certified']
            or audit['status'] != 'numerically_admitted' or not audit['early_window_checks']['passes']):
        raise ValueError('Welfare requires the admitted equilibrium, not a candidate.')
    if (manifest['csv_sha256'] != digest(folder / 'equilibrium_paths.csv')
            or manifest['checkpoint_sha256'][key] != audit['checkpoint_sha256']):
        raise ValueError('Path, checkpoint, and admission hashes differ.')
    if scenario['parameters'] != audit['parameters'] or scenario['parameters'] != manifest['parameters']:
        raise ValueError('Scenario and audit parameters differ.')
    if (audit['sigma_xl'] != sigma or reference['sigma'] != sigma
            or scenario['frontier'] != audit['frontier'] or scenario['frontier'] != manifest['frontier']):
        raise ValueError('Scenario, reference and audit technologies differ.')
    p = scenario['parameters']
    if p['chi'] != chi or not p['discount'] > p['population_growth']:
        raise ValueError('Incompatible research productivity or discounting.')
    if not math.isclose(reference['capital'], scenario['initial_capital_by_sigma'][key]):
        raise ValueError('Competitive and monopoly initial capital differ.')
    if reference['capability'] != scenario['initial_capability']:
        raise ValueError('Competitive and monopoly initial AI efficiency differ.')
    if not math.isclose(reference['interest_rate'], p['discount'] + p['labor_productivity_growth']):
        raise ValueError('Reference is not the competitive labor-bottleneck BGP.')
    expected_c = (reference['output'] - reference['inference_compute']
                  - (p['depreciation'] + p['population_growth']
                     + p['labor_productivity_growth']) * reference['capital'])
    if not math.isclose(reference['consumption'], expected_c, rel_tol=1e-12):
        raise ValueError('Competitive reference violates its resource constraint.')
    paths = ('scenario.json', 'competitive_reference.json', 'paths_manifest.json',
             f'{key}_audit.json', 'equilibrium_paths.csv')
    provenance = {str((folder / name).relative_to(ROOT)).replace('\\', '/'): digest(folder / name)
                  for name in paths}
    return folder, scenario, audit, reference, provenance


def export_checkpoints(chi, sigma=SIGMA):
    """Extract only log aggregate consumption, preserving the original spline."""
    sys.path.insert(0, str(ROOT / 'scripts'))
    from simulate_rewrite_finite_frontier import load_solution
    _, scenario, audit, reference, provenance = inputs(chi, sigma)
    cache = ROOT / f'tmp/rewrite_bvp_competitive_to_monopoly_chi_{identifier(chi)}'
    stages = {}
    for stage in STAGES:
        path = cache / f'{sigma_key(sigma)}_{stage}.npz'
        if stage == 'long' and digest(path) != audit['checkpoint_sha256']:
            raise ValueError('Final checkpoint does not match the admitted path.')
        sol = load_solution(path)
        p = sol.parameters
        if (sol.terminal.sigma_xl != sigma or sol.terminal.frontier != scenario['frontier']
                or sol.initial_capability != scenario['initial_capability']
                or not math.isclose(sol.initial_capital, reference['capital'], rel_tol=2e-15)
                or vars(p) != scenario['parameters']):
            raise ValueError('Checkpoint has different parameters or initial stocks.')
        # The stored raw coordinate is log C minus its terminal aggregate trend.
        # Canonical PPoly shape is (degree+1, interval, variable), C at index 2.
        coeff = sol.raw.sol.c[:, :, 2].copy()
        x = sol.raw.sol.x.copy()
        drift = float(sol.terminal.terminal_growth) - (
            p.population_growth + p.labor_productivity_growth)
        c_comp_0 = reference['consumption'] * sol.initial_effective_labor_scale
        # Transform to log(C_mon/C_comp), which also equals log(c_mon/c_comp).
        coeff[-2] += drift
        coeff[-1] += drift * x[:-1] - math.log(c_comp_0)
        stages[stage] = dict(checkpoint_sha256=digest(path), horizon=sol.horizon,
                             x=x.tolist(), coefficients=coeff.tolist(),
                             initial_capital=sol.initial_capital,
                             initial_capability=sol.initial_capability,
                             initial_effective_labor_scale=sol.initial_effective_labor_scale,
                             maximum_rms_residual=float(np.max(sol.raw.rms_residuals)))
    write_json(spline_path(chi, sigma),
               dict(chi=chi, sigma=sigma, variable='log(C_mon/C_comp)=log(c_mon/c_comp)',
                    source_sha256=provenance, stages=stages))


def weighted_integral(spline, beta, end, order=16):
    """Gauss-Legendre quadrature on every original collocation interval."""
    if beta <= 0 or not 0 <= end <= spline.x[-1]:
        raise ValueError('Discounting must be positive and integration stay in the solved interval.')
    left = spline.x[:-1][spline.x[:-1] < end]
    right = np.minimum(spline.x[1:len(left) + 1], end)
    nodes, weights = np.polynomial.legendre.leggauss(order)
    half = (right - left) / 2
    times = (left + right)[:, None] / 2 + half[:, None] * nodes
    return float(np.sum(half * ((np.exp(-beta * times) * spline(times)) @ weights)))


def affine_tail(level, slope, beta, start):
    """Integral of an affine log consumption ratio beyond the solved horizon."""
    if beta <= 0:
        raise ValueError('Infinite-horizon log utility requires rho>n.')
    return math.exp(-beta * start) * (level / beta + slope / beta ** 2)


def ce_from_integral(value, beta):
    return math.expm1(beta * value)


def calculate_case(chi, sigma=SIGMA):
    folder, scenario, audit, reference, provenance = inputs(chi, sigma)
    source_path = spline_path(chi, sigma)
    stored = read_json(source_path)
    if stored['source_sha256'] != provenance or stored['chi'] != chi or stored['sigma'] != sigma:
        raise ValueError('Derived consumption spline is stale.')
    if stored['stages']['long']['checkpoint_sha256'] != audit['checkpoint_sha256']:
        raise ValueError('Derived spline is not from the admitted checkpoint.')
    p = scenario['parameters']
    beta = p['discount'] - p['population_growth']
    bound = scenario['frontier']
    g_mon, regime = limiting_monopoly_growth(sigma, p, bound)
    if regime != audit['terminal_regime']:
        raise ValueError('Analytical regime differs from the original equilibrium audit.')
    slope = g_mon - p['labor_productivity_growth']
    stages = {}
    splines = {}
    for stage in STAGES:
        data = stored['stages'][stage]
        spline = PPoly(np.asarray(data['coefficients']), np.asarray(data['x']), extrapolate=False)
        end = data['horizon']
        if spline.x[0] != 0 or spline.x[-1] != end:
            raise ValueError('Stored spline and solved horizon differ.')
        integral = weighted_integral(spline, beta, end, 16)
        other = weighted_integral(spline, beta, end, 8)
        terminal_level = float(spline(end))
        tail = affine_tail(terminal_level, slope, beta, end)
        stages[stage] = dict(horizon=end, utility_difference_per_initial_person=integral + tail,
                             integrated_utility_difference=integral, tail_utility_difference=tail,
                             consumption_equivalent=ce_from_integral(integral + tail, beta),
                             quadrature_8_16_difference=abs(integral - other),
                             terminal_log_ratio=terminal_level,
                             terminal_growth_gap_error=abs(float(spline(end, 1)) - slope))
        splines[stage] = spline
    final = stages['long']
    spline = splines['long']
    # Independent integration routine, with knots supplied to avoid missed early dynamics.
    quad_value, quad_error = quad(lambda t: math.exp(-beta * t) * float(spline(t)),
                                 0, spline.x[-1], points=spline.x[1:-1],
                                 epsabs=1e-10, epsrel=1e-10, limit=len(spline.x) + 100)
    csv_rows = []
    with (folder / 'equilibrium_paths.csv').open(newline='', encoding='utf-8') as stream:
        csv_rows = [row for row in csv.DictReader(stream) if float(row['sigma']) == sigma]
    if len(csv_rows) != manifest_count(folder):
        raise ValueError('The CSV comparison must cover every original plotted observation.')
    times = np.array([float(row['time']) for row in csv_rows])
    ratios = np.array([math.log(float(row['consumption_effective_labor']) / reference['consumption'])
                       for row in csv_rows])
    csv_gap = float(np.max(np.abs(spline(times) - ratios)))
    cutoffs = {}
    for end in (50., 100., 250., 500., 1000.):
        integral = weighted_integral(spline, beta, end)
        with_tail = integral + affine_tail(float(spline(end)), slope, beta, end)
        cutoffs[str(int(end))] = dict(
            discounted_log_contribution=beta * integral,
            ce_without_tail=ce_from_integral(integral, beta),
            ce_with_limiting_growth_tail=ce_from_integral(with_tail, beta),
            ce_change_from_full_solution=ce_from_integral(with_tail, beta) - final['consumption_equivalent'])
    checks = dict(
        csv_maximum_log_ratio_gap=csv_gap,
        independent_quad_difference=abs(quad_value - final['integrated_utility_difference']),
        independent_quad_error_estimate=quad_error,
        maximum_quadrature_difference=max(s['quadrature_8_16_difference'] for s in stages.values()),
        base_to_refined_ce_change=abs(stages['base']['consumption_equivalent'] - stages['refined']['consumption_equivalent']),
        refined_to_long_ce_change=abs(stages['refined']['consumption_equivalent'] - final['consumption_equivalent']),
        final_tail_ce_effect=abs(ce_from_integral(final['integrated_utility_difference'], beta)
                                 - final['consumption_equivalent']))
    if (csv_gap > 1e-10 or checks['independent_quad_difference'] > 1e-9
            or checks['maximum_quadrature_difference'] > 1e-9
            or checks['base_to_refined_ce_change'] > 2e-5
            or checks['refined_to_long_ce_change'] > 2e-7
            or final['terminal_growth_gap_error'] > 1e-7
            or abs(cutoffs['500']['ce_change_from_full_solution']) > 1e-6):
        raise ValueError(f'Welfare numerical checks failed: {checks}')
    return dict(chi=chi, sigma=sigma, parameters=p, frontier=bound, monopoly_regime=regime,
                initial_capital=reference['capital'], initial_capability=reference['capability'],
                competitive_initial_consumption=reference['consumption'],
                effective_discount=beta, competitive_growth=p['labor_productivity_growth'],
                monopoly_growth=g_mon, stages=stages, horizon_checks=cutoffs, checks=checks,
                source_sha256={**provenance, str(source_path.relative_to(ROOT)).replace('\\', '/'):digest(source_path)},
                numerically_verified=True)


def manifest_count(folder):
    return read_json(folder / 'paths_manifest.json')['points_per_scenario']


def build_report():
    cases = []
    for sigma in SIGMAS:
        pair = [calculate_case(chi, sigma) for chi in CHIS]
        first, second = pair
        for key in ('initial_capital', 'initial_capability', 'frontier', 'competitive_initial_consumption'):
            if first[key] != second[key]:
                raise ValueError(f'The two research productivities inherit different {key}.')
        if {k:v for k,v in first['parameters'].items() if k != 'chi'} != {
                k:v for k,v in second['parameters'].items() if k != 'chi'}:
            raise ValueError('More than research productivity differs.')
        cases.extend(pair)
    from report_rewrite_reversal_welfare import build_reversal_report
    return dict(scope='Eight existing baseline paths at four elasticities and two sigma=1.5 reversal paths, not an optimal policy or continuous parameter map',
                definition='log(1+lambda)=(rho-n)*integral exp(-(rho-n)*t)*log(c_mon/c_comp) dt',
                tail_method='Integrate original spline to its solved horizon, then use its analytical limiting growth rate',
                cases=cases, reversal=build_reversal_report())


def render_table(report):
    lines = [r'% Generated by scripts/report_rewrite_welfare.py.',
             r'\begin{table}[htbp]', r'\centering',
             r'\caption{Welfare from granting monopoly rights}',
             r'\label{tab:rewrite-welfare}', r'\small\setstretch{1.0}',
             r'\setlength{\tabcolsep}{4pt}',
             r'\begin{tabular}{lccrrr}', r'\toprule',
             r'Experiment & $\sigma$ & $\chi$ & Monopoly growth & Competitive growth & Consumption equivalent\\',
             r'\midrule']
    for label, cases in (('A', report['cases']), ('B', report['reversal']['cases'])):
        if label == 'B':
            lines.append(r'\midrule')
        for index, case in enumerate(cases):
            sigma_cell = f"{case['sigma']:g}" if index % 2 == 0 else ''
            lines.append((label if index == 0 else '') + f" & {sigma_cell} & {case['chi']:g} & {100*case['monopoly_growth']:.1f}\\% & "
                         f"{100*case['competitive_growth']:.1f}\\% & "
                         f"{100*case['stages']['long']['consumption_equivalent']:.1f}\\%" + r'\\')
    lines += [r'\bottomrule', r'\end{tabular}', r'\par\vspace{4pt}',
              r'\parbox{0.95\textwidth}{\footnotesize\emph{Notes:} Growth rates refer to long-run consumption per person. A uses the competitive-to-monopoly experiment in Section~\ref{subsec:rewrite-competitive-transition} and its three additional elasticities in the supplementary simulations. For each elasticity, all paths inherit the same competitive initial state, with capital derived from the corresponding competitive balanced-growth path. Only at $\sigma=1.5$ does monopoly enable AI-dominated growth. B uses the supplementary growth-reversal experiment, with different initial stocks and a lower efficiency bound. The consumption equivalent is the permanent proportional change in competitive consumption that gives the household the same discounted utility as monopoly. Positive values favor monopoly and negative values favor competition. Preferences are unchanged throughout.}',
              r'\end{table}', '']
    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--export-checkpoints', action='store_true')
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    if args.check and args.export_checkpoints:
        parser.error('--check does not write extracted checkpoints')
    if args.export_checkpoints:
        for sigma in SIGMAS:
            for chi in CHIS:
                export_checkpoints(chi, sigma)
    report = build_report()
    report_path = OUT / 'welfare_results.json'
    table_path = ROOT / 'sections_rewrite/welfare_table.tex'
    if args.check:
        previous = read_json(report_path)
        current_cases = report['cases'] + report['reversal']['cases']
        previous_cases = previous['cases'] + previous['reversal']['cases']
        if len(current_cases) != len(previous_cases):
            raise ValueError('A welfare comparison is missing from the stored report.')
        for a, b in zip(current_cases, previous_cases):
            if a['source_sha256'] != b['source_sha256']:
                raise ValueError('Source provenance changed.')
            if not math.isclose(a['stages']['long']['consumption_equivalent'],
                                b['stages']['long']['consumption_equivalent'], abs_tol=1e-10):
                raise ValueError('Stored consumption-equivalent result differs.')
        if table_path.read_text(encoding='utf-8') != render_table(report):
            raise ValueError('Manuscript table is stale.')
    else:
        write_json(report_path, report)
        table_path.write_text(render_table(report), encoding='utf-8', newline='\n')
    for case in report['cases'] + report['reversal']['cases']:
        print(json.dumps(dict(chi=case['chi'], sigma=case['sigma'],
                              consumption_equivalent=case['stages']['long']['consumption_equivalent'],
                              checks=case['checks'], horizon_checks=case['horizon_checks']), indent=2))


if __name__ == '__main__':
    main()
