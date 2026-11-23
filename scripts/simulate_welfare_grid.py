"""Welfare on the approved 7-by-5 monopoly/competition grid.

Eight admitted baseline cases are reused without rewriting their files.
New cases have separate outputs and checkpoints. No simulation tolerance,
equilibrium condition, technology unit, or initial-state rule is changed.
Default reporting reproduces welfare from committed scalar splines.
"""
import os
for _name in ('OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'OMP_NUM_THREADS'):
    os.environ[_name] = '1'

import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import asdict, replace
import csv
import json
import math
from pathlib import Path
import platform
import sys
import traceback

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import numpy as np
import scipy
from scipy.integrate import quad
from scipy.interpolate import PPoly

from competitive_ai_bgp import competitive_fixed_efficiency_bgp
from simulate_competitive_to_monopoly import make_design as baseline_design
from simulate_rewrite_finite_frontier import (
    key, load_solution, save_solution, validate_solution_design, run,
)
from solve_axm_global_finite_cap_bvp import (
    GlobalFiniteCapBVP, GlobalContinuationStage, _solve_stage,
    initial_raw_coordinates, recommended_global_horizon, reconstruct_levels,
    audit_counterfactual_developer_sufficiency,
)
from analyze_axm_finite_cap_bvp import terminal_point, terminal_linearization
from calibrate_rewrite_ai_price import extend
from audit_rewrite_equilibria import finalize, independent_residuals
from report_rewrite_welfare import (
    calculate_case as baseline_welfare, STAGES, read_json, write_json, digest,
    identifier, limiting_monopoly_growth, weighted_integral, affine_tail,
    ce_from_integral,
)

SIGMAS = tuple(value / 10 for value in range(9, 16))
CHIS = (1.5, 3.0, 4.5, 6.0, 7.5)
ORIGINAL_SIGMAS = (0.9, 1.0, 1.1, 1.5)
ORIGINAL_CHIS = (1.5, 7.5)
OUT = ROOT / 'numerical_rewrite/welfare_grid'
CACHE = ROOT / 'tmp/rewrite_bvp_welfare_grid'


def cell_id(sigma, chi):
    if sigma not in SIGMAS or chi not in CHIS:
        raise ValueError('Use an approved grid combination.')
    return f'chi_{identifier(chi)}_{key(sigma)}'


def is_original(sigma, chi):
    return sigma in ORIGINAL_SIGMAS and chi in ORIGINAL_CHIS


def make_design(sigma, chi):
    source = baseline_design(7.5)
    name = cell_id(sigma, chi)
    return replace(source, name=f'welfare_grid_{name}', sigmas=(sigma,),
                   parameters=replace(source.parameters, chi=chi),
                   output_directory=OUT / name, cache_directory=CACHE / name)


def prepare(design, sigma):
    p = design.parameters
    reference = competitive_fixed_efficiency_bgp(sigma, design.initial_capability, p)
    specification = dict(
        design=design.name, sigma=sigma, parameters=asdict(p), frontier=design.frontier,
        initial_capability=design.initial_capability,
        initial_capital=reference['capital'], initial_stock_reference=design.initial_stock_reference,
        initial_capital_rule=design.initial_capital_rule,
        developer_sufficiency_margin=min(p.alpha, 1 / sigma)
        - p.eta * (1 - design.initial_capability / design.frontier))
    if specification['developer_sufficiency_margin'] <= 0:
        raise ValueError('The sufficient developer-optimality condition fails.')
    path = design.output_directory / 'scenario.json'
    if path.exists() and read_json(path) != specification:
        raise ValueError('The stored scenario differs. Do not overwrite it.')
    write_json(path, specification)
    write_json(design.output_directory / 'competitive_reference.json', reference)
    return reference


def original_checkpoint(sigma, chi):
    return (ROOT / f'tmp/rewrite_bvp_competitive_to_monopoly_chi_{identifier(chi)}'
            / f'{key(sigma)}_long.npz')


def target_checkpoint(sigma, chi):
    return make_design(sigma, chi).cache_directory / f'{key(sigma)}_long.npz'


def seed_base(design, sigma, seed_path):
    """Change parameters/stocks and solve anew. A seed supplies no controls."""
    path = design.cache_directory / f'{key(sigma)}_base.npz'
    if path.exists():
        validate_solution_design(load_solution(path), design, sigma)
        return
    source = load_solution(seed_path)
    p = design.parameters
    terminal = terminal_point(sigma, design.frontier, p)
    if source.terminal.regime != terminal.regime:
        raise ValueError('Use a numerical seed from the same asymptotic regime.')
    reference = competitive_fixed_efficiency_bgp(sigma, design.initial_capability, p)
    horizon = recommended_global_horizon(terminal, p, 1.0)
    linearization = terminal_linearization(terminal, p)
    targets = initial_raw_coordinates(terminal, reference['capital'], design.initial_capability)
    raw, boundary = _solve_stage(
        source.raw, source.horizon, horizon, targets, 1.0, terminal, linearization, p,
        nodes=601, tolerance=2e-6, boundary_tolerance=1e-9, maximum_nodes=40000)
    stage = GlobalContinuationStage(
        fraction=1.0, horizon=horizon, initial_effective_labor_scale=1.0,
        iterations=int(raw.niter), nodes=int(raw.x.size),
        maximum_rms_residual=float(np.max(raw.rms_residuals)),
        maximum_boundary_residual=boundary)
    solution = GlobalFiniteCapBVP(raw, terminal, linearization, p, reference['capital'],
                                 design.initial_capability, 1.0, horizon, (stage,))
    validate_solution_design(solution, design, sigma)
    design.cache_directory.mkdir(parents=True, exist_ok=True)
    save_solution(solution, path)
    write_json(design.output_directory / 'seed_provenance.json', dict(
        source_path=seed_path.relative_to(ROOT).as_posix(), source_sha256=digest(seed_path),
        source_sigma=source.terminal.sigma_xl, source_chi=source.parameters.chi,
        note='Numerical initial guess only. Target parameters and stocks are imposed and all controls re-solved.'))


def audit_cell(design, sigma):
    # Reuse the original final admission gates rather than solver success alone.
    from audit_rewrite_hamiltonian_support import audit_support
    checkpoint=design.cache_directory / f'{key(sigma)}_long.npz'
    if sigma==1.5:
        solution=load_solution(checkpoint)
        for dates,states in ((81,101),(321,241)):
            path=design.output_directory/f'{key(sigma)}_support_{dates}_{states}.json'
            if not path.exists():
                result=audit_support(solution,dates,states)
                result['checkpoint_sha256']=digest(checkpoint)
                write_json(path,result)
            elif read_json(path)['checkpoint_sha256']!=digest(checkpoint):
                raise ValueError('The Hamiltonian audit belongs to another checkpoint.')
    reports = finalize(design)
    report = reports[0]
    sol = load_solution(design.cache_directory / f'{key(sigma)}_long.npz')
    times = np.linspace(.001, 10., 801)
    residuals = [independent_residuals(sol, step, times) for step in (.0003, .0001)]
    concavity = audit_counterfactual_developer_sufficiency(
        sol, time_points=161, capability_points=161,
        sample_times=np.linspace(0., 10., 161))
    optimality=concavity['developer_sufficiency_gate_passes']
    support=[]
    if not optimality and sigma==1.5:
        for dates,states in ((161,161),(321,241)):
            path=design.output_directory/f'{key(sigma)}_early_support_{dates}_{states}.json'
            if not path.exists():
                result=audit_support(sol,dates,states,sample_times=np.linspace(0.,10.,dates))
                result['checkpoint_sha256']=digest(checkpoint)
                write_json(path,result)
            result=read_json(path)
            if result['checkpoint_sha256']!=digest(checkpoint):
                raise ValueError('The early support audit belongs to another checkpoint.')
            support.append({k:v for k,v in result.items() if k!='checks'})
        optimality=all(item['support_diagnostic_passes'] and item['maximum_own_gap']<1e-10
                       and item['maximum_tail_derivative_ratio']<=1 for item in support)
    passes = bool(optimality and all(
        item['maximum_ode_residual'] < 1e-6
        and item['maximum_research_foc_residual'] < 1e-9
        and item['maximum_monopoly_foc_residual'] < 1e-9 for item in residuals))
    report['early_window_checks'] = dict(start=0., end=10., independent_residuals=residuals,
                                        concavity=concavity, support=support, passes=passes)
    report['equilibrium_certified'] = bool(report['equilibrium_certified'] and passes)
    report['status'] = 'numerically_admitted' if report['equilibrium_certified'] else 'not_admitted'
    report['settings']['base_initialization'] = 'parameter continuation from an existing numerical seed'
    report['settings']['continuation_steps'] = 1
    write_json(design.output_directory / f'{key(sigma)}_audit.json', report)
    if not report['equilibrium_certified']:
        raise RuntimeError('The new cell fails the unchanged final equilibrium gates.')
    return report


def provenance(design, sigma):
    return {path.relative_to(ROOT).as_posix(): digest(path) for path in (
        design.output_directory / 'scenario.json',
        design.output_directory / 'competitive_reference.json',
        design.output_directory / f'{key(sigma)}_audit.json')}


def export_splines(design, sigma, reference, audit):
    stages = {}
    for stage in STAGES:
        path = design.cache_directory / f'{key(sigma)}_{stage}.npz'
        sol = load_solution(path)
        validate_solution_design(sol, design, sigma)
        if stage == 'long' and digest(path) != audit['checkpoint_sha256']:
            raise ValueError('The final checkpoint changed since admission.')
        coefficients = sol.raw.sol.c[:, :, 2].copy()
        knots = sol.raw.sol.x.copy()
        drift = float(sol.terminal.terminal_growth) - (
            sol.parameters.population_growth + sol.parameters.labor_productivity_growth)
        coefficients[-2] += drift
        coefficients[-1] += drift * knots[:-1] - math.log(reference['consumption'])
        stages[stage] = dict(checkpoint_sha256=digest(path), horizon=sol.horizon,
                             x=knots.tolist(), coefficients=coefficients.tolist(),
                             maximum_rms_residual=float(np.max(sol.raw.rms_residuals)))
    # Check the extracted ratio against independently reconstructed dated levels.
    times = np.unique(np.r_[np.linspace(0., 10., 1001), np.linspace(10., 500., 601)])
    levels = reconstruct_levels(times, sol.raw.sol(times), sol)
    ratios = levels['log_consumption'] - math.log(reference['consumption']) - (
        sol.parameters.population_growth + sol.parameters.labor_productivity_growth) * times
    path = design.output_directory / 'consumption_validation.csv'
    with path.open('w', newline='', encoding='utf-8') as stream:
        writer = csv.writer(stream, lineterminator='\n')
        writer.writerow(('time', 'log_consumption_ratio'))
        writer.writerows(zip(times, ratios))
    source = {**provenance(design, sigma), path.relative_to(ROOT).as_posix(): digest(path)}
    write_json(design.output_directory / 'consumption_splines.json', dict(
        sigma=sigma, chi=design.parameters.chi, variable='log(C_mon/C_comp)=log(c_mon/c_comp)',
        source_sha256=source, stages=stages))


def calculate_new(sigma, chi):
    design = make_design(sigma, chi)
    folder = design.output_directory
    scenario = read_json(folder / 'scenario.json')
    reference = read_json(folder / 'competitive_reference.json')
    audit = read_json(folder / f'{key(sigma)}_audit.json')
    stored = read_json(folder / 'consumption_splines.json')
    if not audit['equilibrium_certified'] or not audit['early_window_checks']['passes']:
        raise ValueError('Welfare requires an admitted equilibrium.')
    p = asdict(design.parameters)
    if (scenario['parameters'] != p or audit['parameters'] != p
            or stored['sigma'] != sigma or stored['chi'] != chi
            or scenario['frontier'] != design.frontier
            or audit['sigma_xl'] != sigma or audit['frontier'] != design.frontier
            or reference != competitive_fixed_efficiency_bgp(sigma, design.initial_capability, design.parameters)):
        raise ValueError('Grid technology, reference or parameter provenance differs.')
    for name, expected in stored['source_sha256'].items():
        if digest(ROOT / name) != expected:
            raise ValueError(f'Stale welfare input: {name}')
    if stored['stages']['long']['checkpoint_sha256'] != audit['checkpoint_sha256']:
        raise ValueError('Consumption extract and equilibrium audit differ.')
    beta = p['discount'] - p['population_growth']
    g_mon, regime = limiting_monopoly_growth(sigma, p, design.frontier)
    if regime != audit['terminal_regime'] or beta <= 0:
        raise ValueError('The analytical growth regime or discounting differs.')
    slope = g_mon - p['labor_productivity_growth']
    stages, splines = {}, {}
    for stage, data in stored['stages'].items():
        spline = PPoly(np.asarray(data['coefficients']), np.asarray(data['x']), extrapolate=False)
        end = data['horizon']
        if spline.x[0] != 0 or spline.x[-1] != end:
            raise ValueError('The spline and solved horizon differ.')
        integral = weighted_integral(spline, beta, end)
        other = weighted_integral(spline, beta, end, 8)
        tail = affine_tail(float(spline(end)), slope, beta, end)
        stages[stage] = dict(horizon=end, integrated_utility_difference=integral,
            tail_utility_difference=tail, utility_difference_per_initial_person=integral + tail,
            consumption_equivalent=ce_from_integral(integral + tail, beta),
            quadrature_8_16_difference=abs(integral - other),
            terminal_log_ratio=float(spline(end)),
            terminal_growth_gap_error=abs(float(spline(end, 1)) - slope))
        splines[stage] = spline
    spline, final = splines['long'], stages['long']
    separate, separate_error = quad(
        lambda t: math.exp(-beta * t) * float(spline(t)), 0., spline.x[-1],
        points=spline.x[1:-1], epsabs=1e-10, epsrel=1e-10, limit=len(spline.x) + 100)
    rows = np.genfromtxt(folder / 'consumption_validation.csv', delimiter=',', names=True)
    csv_gap = float(np.max(np.abs(spline(rows['time']) - rows['log_consumption_ratio'])))
    cutoffs = {}
    for end in (50., 100., 250., 500., 1000.):
        value = weighted_integral(spline, beta, end)
        tail = affine_tail(float(spline(end)), slope, beta, end)
        cutoffs[str(int(end))] = dict(discounted_log_contribution=beta * value,
            ce_without_tail=ce_from_integral(value, beta),
            ce_with_limiting_growth_tail=ce_from_integral(value + tail, beta),
            ce_change_from_full_solution=ce_from_integral(value + tail, beta) - final['consumption_equivalent'])
    checks = dict(csv_maximum_log_ratio_gap=csv_gap,
        independent_quad_difference=abs(separate - final['integrated_utility_difference']),
        independent_quad_error_estimate=separate_error,
        maximum_quadrature_difference=max(s['quadrature_8_16_difference'] for s in stages.values()),
        base_to_refined_ce_change=abs(stages['base']['consumption_equivalent'] - stages['refined']['consumption_equivalent']),
        refined_to_long_ce_change=abs(stages['refined']['consumption_equivalent'] - final['consumption_equivalent']),
        final_tail_ce_effect=abs(ce_from_integral(final['integrated_utility_difference'], beta) - final['consumption_equivalent']))
    if (csv_gap > 1e-10 or checks['independent_quad_difference'] > 1e-9
            or checks['maximum_quadrature_difference'] > 1e-9
            or checks['base_to_refined_ce_change'] > 2e-5
            or checks['refined_to_long_ce_change'] > 2e-7
            or final['terminal_growth_gap_error'] > 1e-7
            or abs(cutoffs['500']['ce_change_from_full_solution']) > 1e-6):
        raise RuntimeError(f'Welfare checks fail at sigma={sigma}, chi={chi}: {checks}')
    return dict(sigma=sigma, chi=chi, parameters=p, frontier=design.frontier,
        initial_capital=reference['capital'], initial_capability=reference['capability'],
        competitive_initial_consumption=reference['consumption'], effective_discount=beta,
        monopoly_growth=g_mon, competitive_growth=p['labor_productivity_growth'],
        monopoly_regime=regime, stages=stages, horizon_checks=cutoffs, checks=checks,
        source_sha256={**stored['source_sha256'],
            (folder / 'consumption_splines.json').relative_to(ROOT).as_posix(): digest(folder / 'consumption_splines.json')},
        numerically_verified=True, origin='new_grid_cell')


def calculate_cell(sigma, chi):
    if is_original(sigma, chi):
        return {**baseline_welfare(chi, sigma), 'origin': 'reused_original'}
    return calculate_new(sigma, chi)


def solve_cell(sigma, chi, seed_path):
    print(f'GRID START sigma={sigma:g} chi={chi:g}', flush=True)
    design = make_design(sigma, chi)
    reference = prepare(design, sigma)
    audit_path = design.output_directory / f'{key(sigma)}_audit.json'
    if not (audit_path.exists() and read_json(audit_path).get('early_window_checks', {}).get('passes')):
        seed_base(design, sigma, Path(seed_path))
        run(sigma, design)
        extend(sigma, design)
        audit = audit_cell(design, sigma)
        export_splines(design, sigma, reference, audit)
    result = calculate_new(sigma, chi)
    print(f'GRID PASS sigma={sigma:g} chi={chi:g} CE={100 * result["stages"]["long"]["consumption_equivalent"]:.7f}%', flush=True)
    return result


def choose_seed(sigma, chi, registry):
    regime = terminal_point(sigma, make_design(sigma, chi).frontier,
                            make_design(sigma, chi).parameters).regime
    candidates = []
    for (s, c), path in registry.items():
        sol = load_solution(path)
        if sol.terminal.regime == regime:
            candidates.append((5 * abs(s - sigma) + abs(math.log(c / chi)), str(path)))
    if not candidates:
        raise RuntimeError('No existing seed has the required regime.')
    return min(candidates)[1]


def build_report():
    cases = [calculate_cell(sigma, chi) for chi in CHIS for sigma in SIGMAS]
    for sigma in SIGMAS:
        group = [c for c in cases if c['sigma'] == sigma]
        for name in ('initial_capital', 'initial_capability', 'frontier',
                     'competitive_initial_consumption', 'monopoly_growth', 'competitive_growth'):
            if len({c[name] for c in group}) != 1:
                raise ValueError(f'The cells differ in {name} at sigma={sigma}.')
    return dict(sigmas=list(SIGMAS), chis=list(CHIS), attempted=35, admitted=len(cases),
                reused=sum(c['origin'] == 'reused_original' for c in cases), new=27, unresolved=[],
                definition='log(1+lambda)=(rho-n)*integral exp(-(rho-n)*t)*log(c_mon/c_comp) dt',
                fixed_parameters={k:v for k,v in cases[0]['parameters'].items() if k != 'chi'},
                frontier=cases[0]['frontier'], initial_capability=cases[0]['initial_capability'],
                initial_capital_rule='Competitive fixed-B labor-bottleneck BGP at each sigma; common stocks within a cell',
                welfare_percent=[[100 * c['stages']['long']['consumption_equivalent']
                    for c in cases if c['chi'] == chi] for chi in CHIS], cases=cases)


def solve_grid(workers):
    registry = {(s,c): original_checkpoint(s,c) for s in ORIGINAL_SIGMAS for c in ORIGINAL_CHIS}
    results = {(s,c): calculate_cell(s,c) for s,c in registry}
    failures = {}
    def retain(sigma, chi, result):
        results[(sigma,chi)] = result
        registry[(sigma,chi)] = target_checkpoint(sigma,chi)
        write_json(CACHE / 'progress.json', dict(admitted=len(results), attempted=35,
            new_admitted=len(results)-8, failures=failures,
            completed=[dict(sigma=s,chi=c,ce=r['stages']['long']['consumption_equivalent'])
                       for (s,c),r in sorted(results.items())]))
    # Fill the missing high-chi elasticities successively, retaining same-regime seeds.
    for sigma in (1.2,1.3,1.4):
        try:
            retain(sigma,7.5,solve_cell(sigma,7.5,choose_seed(sigma,7.5,registry)))
        except Exception as error:
            failures[cell_id(sigma,7.5)] = str(error)
            traceback.print_exc()
    with ProcessPoolExecutor(max_workers=workers) as executor:
        for chi in (6.0,4.5,3.0,1.5):
            futures = {executor.submit(solve_cell,sigma,chi,choose_seed(sigma,chi,registry)):sigma
                       for sigma in SIGMAS if (sigma,chi) not in results}
            for future in as_completed(futures):
                sigma = futures[future]
                try:
                    retain(sigma,chi,future.result())
                except Exception as error:
                    failures[cell_id(sigma,chi)] = str(error)
                    traceback.print_exc()
                    write_json(CACHE / 'failures.json', failures)
    write_json(CACHE / 'final_status.json',dict(attempted=35,admitted=len(results),failures=failures))
    if len(results) != 35:
        raise RuntimeError(f'{len(results)}/35 cells admitted. Failed cells are not interpolated: {failures}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--solve', action='store_true')
    parser.add_argument('--workers', type=int, default=2)
    parser.add_argument('--cell', nargs=2, type=float, metavar=('SIGMA','CHI'))
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    if args.solve and args.check:
        parser.error('--check never solves or writes outputs')
    if args.workers < 1 or args.workers > 4:
        parser.error('Use 1 to 4 bounded worker processes.')
    if args.cell:
        if not args.solve:
            parser.error('--cell is only for a single --solve operation')
        sigma,chi=args.cell
        cell_id(sigma,chi)
        if is_original(sigma,chi):
            parser.error('Original baseline cells are reused, not overwritten or re-solved here.')
        seed=original_checkpoint(1.5 if sigma==1.5 else 1.1,7.5)
        solve_cell(sigma,chi,seed)
        return
    if args.solve:
        solve_grid(args.workers)
    report = build_report()
    path = OUT / 'grid_results.json'
    if args.check:
        if read_json(path) != report:
            raise ValueError('Stored grid report differs from the admitted calculations.')
    else:
        write_json(path,report)
        write_json(CACHE/'final_status.json',dict(attempted=35,admitted=35,failures={},
            verification='All admitted consumption extracts and their provenance recomputed.'))
        write_json(OUT / 'environment.json',dict(python=sys.version,numpy=np.__version__,
            scipy=scipy.__version__,platform=platform.platform(),
            parameter_source='Original baseline scenario and the approved discrete grid. No parameter is estimated or fitted to welfare.'))
    print(json.dumps(dict(admitted=report['admitted'],reused=report['reused'],
                          sigmas=report['sigmas'],chis=report['chis'],welfare_percent=report['welfare_percent']),indent=2))


if __name__ == '__main__':
    main()
