"""Consumption-equivalent welfare for the existing sigma=1.5 policy experiment.

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
OUT = ROOT / 'numerical_rewrite/welfare_comparison'
STAGES = ('base', 'refined', 'long')
CHIS = (7.5, 1.5)
SIGMA = 1.5


def read_json(path):
    return json.loads(path.read_text(encoding='utf-8'))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def identifier(chi):
    return str(chi).replace('.', '_')


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, allow_nan=False) + '\n', encoding='utf-8')


def inputs(chi):
    folder = ROOT / f'numerical_rewrite/competitive_to_monopoly_chi_{identifier(chi)}'
    scenario = read_json(folder / 'scenario.json')
    audit = read_json(folder / 'sigma_1_50_audit.json')
    manifest = read_json(folder / 'paths_manifest.json')
    reference = read_json(folder / 'competitive_reference.json')['sigma_1_50']
    if scenario['status'] != 'numerically_admitted' or not audit['equilibrium_certified']:
        raise ValueError('Welfare requires the admitted equilibrium, not a candidate.')
    if (manifest['csv_sha256'] != digest(folder / 'equilibrium_paths.csv')
            or manifest['checkpoint_sha256']['sigma_1_50'] != audit['checkpoint_sha256']):
        raise ValueError('Path, checkpoint, and admission hashes differ.')
    if scenario['parameters'] != audit['parameters']:
        raise ValueError('Scenario and audit parameters differ.')
    p = scenario['parameters']
    if p['chi'] != chi or not p['discount'] > p['population_growth']:
        raise ValueError('Incompatible research productivity or discounting.')
    if not math.isclose(reference['capital'], scenario['initial_capital_by_sigma']['sigma_1_50']):
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
             'sigma_1_50_audit.json', 'equilibrium_paths.csv')
    provenance = {str((folder / name).relative_to(ROOT)).replace('\\', '/'): digest(folder / name)
                  for name in paths}
    return folder, scenario, audit, reference, provenance


def export_checkpoints(chi):
    """Extract only log aggregate consumption, preserving the original spline."""
    sys.path.insert(0, str(ROOT / 'scripts'))
    from simulate_rewrite_finite_frontier import load_solution
    _, scenario, audit, reference, provenance = inputs(chi)
    cache = ROOT / f'tmp/rewrite_bvp_competitive_to_monopoly_chi_{identifier(chi)}'
    stages = {}
    for stage in STAGES:
        path = cache / f'sigma_1_50_{stage}.npz'
        if stage == 'long' and digest(path) != audit['checkpoint_sha256']:
            raise ValueError('Final checkpoint does not match the admitted path.')
        sol = load_solution(path)
        p = sol.parameters
        if (sol.terminal.sigma_xl != SIGMA or sol.terminal.frontier != scenario['frontier']
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
    write_json(OUT / f'chi_{identifier(chi)}_consumption_splines.json',
               dict(chi=chi, sigma=SIGMA, variable='log(C_mon/C_comp)=log(c_mon/c_comp)',
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


def calculate_case(chi):
    folder, scenario, audit, reference, provenance = inputs(chi)
    source_path = OUT / f'chi_{identifier(chi)}_consumption_splines.json'
    stored = read_json(source_path)
    if stored['source_sha256'] != provenance or stored['chi'] != chi or stored['sigma'] != SIGMA:
        raise ValueError('Derived consumption spline is stale.')
    if stored['stages']['long']['checkpoint_sha256'] != audit['checkpoint_sha256']:
        raise ValueError('Derived spline is not from the admitted checkpoint.')
    p = scenario['parameters']
    beta = p['discount'] - p['population_growth']
    a, w, bound = p['alpha'], p['omega_x'], scenario['frontier']
    interest_limit = a * ((1 - a) ** 2 * bound * w ** (SIGMA / (SIGMA - 1))) ** (
        (1 - a) / a) - p['depreciation']
    g_mon = interest_limit - p['discount']
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
        csv_rows = [row for row in csv.DictReader(stream) if float(row['sigma']) == SIGMA]
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
    return dict(chi=chi, sigma=SIGMA, parameters=p, frontier=bound,
                initial_capital=reference['capital'], initial_capability=reference['capability'],
                competitive_initial_consumption=reference['consumption'],
                effective_discount=beta, competitive_growth=p['labor_productivity_growth'],
                monopoly_growth=g_mon, stages=stages, horizon_checks=cutoffs, checks=checks,
                source_sha256={**provenance, str(source_path.relative_to(ROOT)).replace('\\', '/'):digest(source_path)},
                numerically_verified=True)


def build_report():
    cases = [calculate_case(chi) for chi in CHIS]
    first, second = cases
    for key in ('initial_capital', 'initial_capability', 'frontier', 'competitive_initial_consumption'):
        if first[key] != second[key]:
            raise ValueError(f'The two research productivities inherit different {key}.')
    if {k:v for k,v in first['parameters'].items() if k != 'chi'} != {
            k:v for k,v in second['parameters'].items() if k != 'chi'}:
        raise ValueError('More than research productivity differs.')
    return dict(scope='Two existing sigma=1.5 competitive-to-monopoly paths, not an optimal policy or parameter sweep',
                definition='log(1+lambda)=(rho-n)*integral exp(-(rho-n)*t)*log(c_mon/c_comp) dt',
                tail_method='Integrate original spline to its solved horizon, then use its analytical limiting growth rate',
                cases=cases)


def render_table(report):
    lines = [r'% Generated by scripts/report_rewrite_welfare.py.',
             r'\begin{table}[htbp]', r'\centering',
             r'\caption{Welfare from granting monopoly rights at $\sigma=1.5$}',
             r'\label{tab:rewrite-welfare}', r'\small\setstretch{1.0}',
             r'\begin{tabular}{crr}', r'\toprule',
             r'Research productivity $\chi$ & Long-run growth of $C/N$ & Consumption-equivalent gain\\',
             r'\midrule']
    for case in report['cases']:
        lines.append(f"{case['chi']:g} & {100*case['monopoly_growth']:.1f}\\% & "
                     f"{100*case['stages']['long']['consumption_equivalent']:.1f}\\%" + r'\\')
    lines += [r'\bottomrule', r'\end{tabular}', r'\par\vspace{4pt}',
              r'\parbox{0.95\textwidth}{\footnotesize\emph{Notes:} Both comparisons start from the same competitive balanced-growth path used in Section~\ref{subsec:rewrite-competitive-transition}. Continued competition has consumption-per-person growth of $1.0\%$. The gain is the permanent proportional increase in competitive consumption that gives the representative household the same discounted utility as the monopoly path. Preferences and all other parameters retain the values in Table~\ref{tab:rewrite-rsi-parameters}.}',
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
        for chi in CHIS:
            export_checkpoints(chi)
    report = build_report()
    report_path = OUT / 'welfare_results.json'
    table_path = ROOT / 'sections_rewrite/welfare_table.tex'
    if args.check:
        previous = read_json(report_path)
        for a, b in zip(report['cases'], previous['cases']):
            if a['source_sha256'] != b['source_sha256']:
                raise ValueError('Source provenance changed.')
            if not math.isclose(a['stages']['long']['consumption_equivalent'],
                                b['stages']['long']['consumption_equivalent'], abs_tol=1e-10):
                raise ValueError('Stored consumption-equivalent result differs.')
        if table_path.read_text(encoding='utf-8') != render_table(report):
            raise ValueError('Manuscript table is stale.')
    else:
        write_json(report_path, report)
        table_path.write_text(render_table(report), encoding='utf-8')
    for case in report['cases']:
        print(json.dumps(dict(chi=case['chi'],
                              consumption_equivalent=case['stages']['long']['consumption_equivalent'],
                              checks=case['checks'], horizon_checks=case['horizon_checks']), indent=2))


if __name__ == '__main__':
    main()
