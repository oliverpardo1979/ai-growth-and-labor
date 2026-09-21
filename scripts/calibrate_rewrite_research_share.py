"""Fit chi to the 2025 US annual research-compute/GDP proxy.

Reuse the existing positive-AI BVP, pre-RSI stocks and admission workflow.
No price target, time-varying chi, new equilibrium restriction or new solver.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict, replace
import hashlib
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'.python-packages'), str(ROOT/'scripts')]
import numpy as np
from scipy.optimize import brentq, minimize_scalar
from scipy.special import logsumexp
from calibrate_rewrite_ai_price import (
    make_design as price_design, write_json, log_price_ratio, finish as shared_finish, extend,
)
from simulate_rewrite_finite_frontier import (
    PARAMETERS, SIGMAS, key, design_initial_stocks, fixed_efficiency_bgp,
    load_solution, save_solution, validate_solution_design, run,
)
from analyze_axm_finite_cap_bvp import terminal_point
from solve_axm_global_finite_cap_bvp import solve_global_finite_cap_bvp, reconstruct_levels

NAME = 'rsi_research_share_2025'
TARGET_SHARE = 109.58 / 30762.099
TARGET_YEARS = 1.0
TARGET_LOG_TOLERANCE = 2e-5
QUADRATURE_LOG_TOLERANCE = 1e-8
SOURCE = dict(
    geography='United States', year=2025,
    research_compute_billion_usd=109.58, nominal_gdp_billion_usd=30762.099,
    compute_url='https://www.piie.com/sites/default/files/2026-05/wp26-9.pdf',
    method_url='https://www.piie.com/sites/default/files/2026-05/wp26-9-appendix.pdf',
    gdp_url='https://fred.stlouisfed.org/data/GDPA',
    accessed='2026-09-14',
    limitations=[
        'Rental-equivalent compute expenditure is estimated, not a sum of observed bills.',
        'Research/training is assumed to account for 50 percent of total AI compute spending.',
        'This US proxy is neither a global total nor a direct measure of autonomous RSI.',
        'The ratio of nominal annual flows proxies the model ratio in final-good units.',
        'The 2025 value is the higher dated estimate, not an upper confidence bound.',
    ],
)


def make_design(chi):
    base = price_design(chi, 'rsi_activation')
    return replace(base, name=NAME, output_directory=ROOT/'numerical_rewrite'/NAME,
        cache_directory=ROOT/'tmp'/f'rewrite_bvp_{NAME}',
        initial_stock_reference=(
            'Same existing-AI fixed-B BGP stocks as the price-calibrated RSI activation. '
            'Research is unavailable before the unanticipated event; pre-event chi=M=0. '
            'Post-event constant chi is tested against integral_0^1 M dt / integral_0^1 Y dt '
            'using the 2025 US proxy at sigma=1; a fitted chi would be common across elasticities. '
            'Only K0 and B0 are inherited; C0 and q0 are re-solved by the BVP.'))


def annual_research_share(solution, start=0., years=TARGET_YEARS, order=64):
    """Ratio of integrals, NOT a mean of M/Y or an initial instantaneous ratio."""
    if not 0 <= start < start+years <= solution.horizon:
        raise ValueError('Annual moment must lie inside the solved horizon.')
    if order < 2:
        raise ValueError('At least two quadrature points are required.')
    x, weights = np.polynomial.legendre.leggauss(order)
    times = start + years*(x+1)/2
    levels = reconstruct_levels(times, solution.raw.sol(times), solution)
    # The common interval-length factor cancels. Separate log sums avoid
    # overflow without changing the weights or the economic denominator.
    logs = np.log(weights)
    result = float(np.exp(logsumexp(logs+levels['log_research_compute'])
                        -logsumexp(logs+levels['log_output'])))
    if not np.isfinite(result) or result <= 0:
        raise ValueError('Invalid annual research expenditure share.')
    return result


def checked_moment(solution, start=0.):
    coarse = annual_research_share(solution, start, order=64)
    fine = annual_research_share(solution, start, order=128)
    error = abs(math.log(fine/coarse))
    if error > QUADRATURE_LOG_TOLERANCE:
        raise RuntimeError('Annual-moment quadrature has not converged.')
    return dict(share=fine, quadrature_log_gap=error, orders=[64,128])


def trial_objective(trials):
    """Return a cached BVP moment evaluator, without admitting a trajectory."""
    def objective(log_chi):
        chi = math.exp(float(log_chi))
        # Reuse the recorded float across log/exp round trips (a few ulps),
        # not across economically or numerically distinct parameter values.
        for prior in trials:
            if math.isclose(chi,prior['chi'],rel_tol=8*np.finfo(float).eps,abs_tol=0):
                chi=prior['chi']
                break
        design = make_design(chi)
        tag = hashlib.sha256(float(chi).hex().encode()).hexdigest()[:16]
        path = design.cache_directory/'calibration_trials'/f'chi_{tag}.npz'
        print(f'Research-share calibration: chi={chi:.10g}', flush=True)
        if path.exists():
            sol = load_solution(path)
            validate_solution_design(sol, design, 1.)
        else:
            terminal = terminal_point(1., design.frontier, design.parameters)
            k0,b0 = design_initial_stocks(design,1.)
            sol = solve_global_finite_cap_bvp(terminal,design.parameters,k0,b0,
                continuation_steps=32,nodes=221,tolerance=2e-7,
                boundary_tolerance=1e-10,maximum_nodes=40000)
            save_solution(sol,path)
        moment = checked_moment(sol)
        error = math.log(moment['share']/TARGET_SHARE)
        row=dict(chi=chi,annual_research_share=moment['share'],
            log_target_residual=error,quadrature_log_gap=moment['quadrature_log_gap'],
            checkpoint=str(path.relative_to(ROOT)),
            checkpoint_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
            maximum_rms_residual=float(np.max(sol.raw.rms_residuals)))
        trials[:] = [t for t in trials if t['chi'] != chi]
        trials.append(row)
        write_json(design.output_directory/'calibration_trials.json',trials)
        print(f'chi={chi:.10g}: annual M/Y={moment["share"]:.10g}',flush=True)
        return error
    return objective


def diagnose():
    """Search a stated finite range and refine its highest interior peak.

    This does not prove a global bound for every chi or every equilibrium.
    Log-chi tolerance .002 resolves a broad peak; it is not a target tolerance.
    """
    output=make_design(1.).output_directory
    path=output/'calibration_trials.json'
    trials=json.loads(path.read_text()) if path.exists() else []
    objective=trial_objective(trials)
    grid=np.log(PARAMETERS.chi)+np.arange(-3,9)*math.log(2)
    failures=[]
    values=[]
    for x in grid:
        try:
            values.append(objective(x))
        except RuntimeError as exc:
            # A failed BVP is missing evidence, not a zero expenditure share.
            failures.append(dict(chi=math.exp(x),error=str(exc)))
            values.append(np.nan)
            write_json(output/'diagnostic_solver_failures.json',failures)
    values=np.array(values)
    best=int(np.nanargmax(values))
    if best in (0,len(grid)-1):
        raise RuntimeError('Peak is on search boundary; extend diagnostic range explicitly.')
    if not np.all(np.isfinite(values[best-1:best+2])):
        raise RuntimeError('A failed BVP interrupts the local peak bracket.')
    optimum=minimize_scalar(lambda x:-objective(x),
        bounds=(grid[best-1],grid[best+1]),method='bounded',
        options={'xatol':.002})
    if not optimum.success:
        raise RuntimeError('Local peak search did not converge.')
    error=objective(optimum.x)
    actual_design=make_design(1.)
    common_parameters=asdict(actual_design.parameters)
    common_parameters.pop('chi')
    payload=dict(status='diagnostic_only_not_a_fitted_calibration',
        target_share=TARGET_SHARE,source=SOURCE,parameters_except_chi=common_parameters,
        frontier=actual_design.frontier,
        initial_stocks_by_sigma={key(s):list(design_initial_stocks(actual_design,s)) for s in SIGMAS},
        explored_chi_range=[math.exp(grid[0]),math.exp(grid[-1])],
        solver_failures=failures,
        local_peak_chi=math.exp(optimum.x),
        local_peak_share=TARGET_SHARE*math.exp(error),
        relative_target_shortfall=1-math.exp(error),
        peak_log_chi_tolerance=.002,trials=sorted(trials,key=lambda t:t['chi']),
        interpretation='Finite-range candidate search, not a global impossibility theorem. '
        'No four-regime equilibrium comparison is exported without a fitted target and admission.')
    write_json(output/'feasibility_diagnostic.json',payload)
    print(json.dumps({k:v for k,v in payload.items() if k not in ('trials','source')},indent=2),flush=True)
    return payload


def calibrate():
    path=make_design(1.).output_directory/'calibration_trials.json'
    trials=json.loads(path.read_text()) if path.exists() else []
    objective=trial_objective(trials)

    # Follow the increasing low-chi branch. A turning point is not a
    # bracket: stop and report it rather than silently fitting a nearby target.
    lower,upper=math.log(PARAMETERS.chi),math.log(2*PARAMETERS.chi)
    fl,fu=objective(lower),objective(upper)
    for _ in range(10):
        if fl*fu <= 0:
            break
        if fl < fu < 0:
            next_upper=upper+math.log(2)
            next_value=objective(next_upper)
            if next_value < fu:
                diagnose()
                raise RuntimeError('Research-share curve turns below target; inspect feasibility_diagnostic.json.')
            lower,fl,upper,fu=upper,fu,next_upper,next_value
        elif 0 < fl < fu:
            upper,fu=lower,fl
            lower-=math.log(2)
            fl=objective(lower)
        else:
            raise RuntimeError('No monotone local target bracket; inspect the moment curve.')
    else:
        raise RuntimeError('No research-share bracket; no fitted calibration published.')
    root = brentq(objective,lower,upper,xtol=2e-6,rtol=1e-10)
    residual = objective(root)
    if abs(residual) > TARGET_LOG_TOLERANCE:
        raise RuntimeError('Research-share target not matched.')
    design = make_design(math.exp(root))
    write_json(design.output_directory/'calibration.json',dict(
        status='fitted_candidate_pending_equilibrium_admission',
        design=NAME,chi=design.parameters.chi,calibration_sigma=1.,
        target_definition='integral_0^1 M(t) dt / integral_0^1 Y(t) dt',
        target_years=TARGET_YEARS,target_share=TARGET_SHARE,
        matched_share=TARGET_SHARE*math.exp(residual),target_log_residual=residual,
        parameters=asdict(design.parameters),frontier=design.frontier,
        initial_capability=design.initial_capability,
        initial_capital_rule=design.initial_capital_rule,
        initial_stocks_by_sigma={key(s):list(design_initial_stocks(design,s)) for s in SIGMAS},
        source=SOURCE,root_log_chi_tolerance=2e-6,
        target_log_tolerance=TARGET_LOG_TOLERANCE,
        quadrature_log_tolerance=QUADRATURE_LOG_TOLERANCE,
        interpretation='Conditional expenditure calibration; not global parameter identification. Price changes remain untargeted.',
        trials=trials))
    write_json(design.output_directory/'pre_rsi_reference.json',dict(
        interpretation=design.initial_stock_reference,
        scenarios={key(s):fixed_efficiency_bgp(s,design.initial_capability,design.parameters)
                   for s in SIGMAS}))
    return design


def verify_peak():
    """Independently refine the diagnostic peak; never label it a target fit."""
    from audit_rewrite_equilibria import finalize,independent_residuals
    from solve_axm_global_finite_cap_bvp import audit_counterfactual_developer_sufficiency
    output=make_design(1.).output_directory
    diagnostic=json.loads((output/'feasibility_diagnostic.json').read_text())
    row=min(diagnostic['trials'],key=lambda x:abs(math.log(x['chi']/diagnostic['local_peak_chi'])))
    source=ROOT/row['checkpoint']
    if hashlib.sha256(source.read_bytes()).hexdigest()!=row['checkpoint_sha256']:
        raise ValueError('Peak trial checkpoint hash changed.')
    solution=load_solution(source)
    base=make_design(solution.parameters.chi)
    design=replace(base,sigmas=(1.,),name=NAME+'_diagnostic_peak',
        output_directory=output/'peak_audit',
        cache_directory=base.cache_directory/'peak_audit')
    validate_solution_design(solution,design,1.)
    save_solution(solution,design.cache_directory/f'{key(1.)}_base.npz')
    run(1.,design)
    extend(1.,design)
    report=finalize(design)[0]
    refined=load_solution(design.cache_directory/f'{key(1.)}_long.npz')
    times=np.linspace(.001,10.,801)
    checks=[independent_residuals(refined,h,times) for h in (.0003,.0001)]
    optimality=audit_counterfactual_developer_sufficiency(refined,
        time_points=161,capability_points=161,sample_times=np.linspace(0.,10.,161))
    early=bool(optimality['developer_sufficiency_gate_passes'] and all(
        c['maximum_ode_residual']<1e-6 and c['maximum_research_foc_residual']<1e-9
        and c['maximum_monopoly_foc_residual']<1e-9 for c in checks))
    first=checked_moment(refined)
    moment_change=abs(math.log(first['share']/row['annual_research_share']))
    passed=bool(report['equilibrium_certified'] and early
                and moment_change<TARGET_LOG_TOLERANCE)
    initial=reconstruct_levels(np.array([0.]),refined.raw.sol(np.array([0.])),refined)
    payload=dict(status='verified_diagnostic_peak_not_a_target_fit' if passed else 'not_admitted',
        passes=passed,chi=design.parameters.chi,target_share=TARGET_SHARE,
        first_year=first,second_year=checked_moment(refined,1.),
        initial_share=float(np.exp(initial['log_research_compute'][0]-initial['log_output'][0])),
        untargeted_price_ratio_27_months=math.exp(log_price_ratio(refined)),
        moment_log_change_after_two_horizon_extensions=moment_change,
        original_equilibrium_report=report,early_window_passes=early,
        early_residuals=checks,early_optimality=optimality,
        checkpoint=str((design.cache_directory/f'{key(1.)}_long.npz').relative_to(ROOT)),
        interpretation='The numerically admitted path validates one local moment-curve peak. '
        'It is not a successful fit, not a global bound, and not a four-regime comparison.')
    write_json(output/'peak_verification.json',payload)
    if not passed:
        raise RuntimeError('Diagnostic peak failed equilibrium or moment-stability checks.')
    print(json.dumps({k:v for k,v in payload.items() if k not in (
        'original_equilibrium_report','early_residuals','early_optimality')},indent=2),flush=True)
    return payload


def compare_published():
    """Measure existing admitted paths without modifying their calibrations."""
    scenarios={}
    for name in ('rsi_activation','rsi_activation_half_decline'):
        directory=ROOT/'numerical_rewrite'/name
        report=json.loads((directory/f'{key(1.)}_audit.json').read_text())
        if not report['equilibrium_certified'] or not report['early_window_checks']['passes']:
            raise ValueError('Published comparison is not admitted.')
        checkpoint=ROOT/'tmp'/f'rewrite_bvp_{name}'/report['checkpoint_filename']
        digest=hashlib.sha256(checkpoint.read_bytes()).hexdigest()
        if digest!=report['checkpoint_sha256']:
            raise ValueError('Published comparison checkpoint hash changed.')
        sol=load_solution(checkpoint)
        validate_solution_design(sol,price_design(sol.parameters.chi,name),1.)
        initial=reconstruct_levels(np.array([0.]),sol.raw.sol(np.array([0.])),sol)
        scenarios[name]=dict(chi=sol.parameters.chi,first_year=checked_moment(sol),
            second_year=checked_moment(sol,1.),
            initial_share=float(np.exp(initial['log_research_compute'][0]-initial['log_output'][0])),
            price_ratio_27_months=math.exp(log_price_ratio(sol)),checkpoint_sha256=digest)
    write_json(make_design(1.).output_directory/'published_comparison.json',scenarios)
    print(json.dumps(scenarios,indent=2),flush=True)
    return scenarios


def publish_unit():
    """Publish the author-approved approximate fit, without relaxing any gate.

    Only the verified sigma=1 path is included. Preserve the failed exact
    calibration and diagnostic; record acceptance of its empirical mismatch.
    """
    from simulate_rewrite_finite_frontier import export_paths
    from calibrate_rewrite_ai_price import audit_rsi_activation,render_comparison_views,summarize
    from plot_rewrite_equilibria import render
    base=make_design(1.)
    diagnostic=json.loads((base.output_directory/'feasibility_diagnostic.json').read_text())
    row=min(diagnostic['trials'],key=lambda x:abs(math.log(x['chi']/diagnostic['local_peak_chi'])))
    if not (ROOT/row['checkpoint']).exists():
        # A fresh checkout recreates this already selected chi; it need not
        # repeat the entire unsuccessful exact-target search.
        trials=list(diagnostic['trials'])
        trial_objective(trials)(math.log(row['chi']))
        replacement=next(t for t in trials if t['chi']==row['chi'])
        for i,t in enumerate(diagnostic['trials']):
            if t['chi']==row['chi']:
                diagnostic['trials'][i]=replacement
        write_json(base.output_directory/'feasibility_diagnostic.json',diagnostic)
    peak=verify_peak()
    if not peak['passes']:
        raise RuntimeError('No verified unit-elastic path to publish.')
    original=make_design(peak['chi'])
    design=replace(original,name='rsi_research_share_approximate_unit',sigmas=(1.,),
        output_directory=base.output_directory/'published_unit',
        cache_directory=original.cache_directory/'peak_audit')
    checkpoint=ROOT/peak['checkpoint']
    validate_solution_design(load_solution(checkpoint),design,1.)
    if hashlib.sha256(checkpoint.read_bytes()).hexdigest()!=peak['original_equilibrium_report']['checkpoint_sha256']:
        raise ValueError('Publication source differs from the verified checkpoint.')
    report=dict(peak['original_equilibrium_report'])
    report.update(design=design.name,early_window_checks=dict(
        passes=peak['early_window_passes'],independent_residuals=peak['early_residuals'],
        concavity=peak['early_optimality']))
    write_json(design.output_directory/f'{key(1.)}_audit.json',report)
    audit_rsi_activation(design)
    export_paths(design.display_horizon,4001,design,
                 additional_times=np.r_[np.linspace(0.,10.,1001),2.25])
    render(design,reference_sigma=1.)
    render_comparison_views(design,show_price_target=False,reference_sigma=1.)
    summarize(design)
    csv_path=design.output_directory/'equilibrium_paths.csv'
    figures=json.loads((design.output_directory/'figure_manifest.json').read_text())
    figure_hashes={}
    for view in figures['two_window_views']:
        for ext in ('pdf','png'):
            file=ROOT/'figures_rewrite'/f'{view["filename"]}.{ext}'
            figure_hashes[str(file.relative_to(ROOT))]=hashlib.sha256(file.read_bytes()).hexdigest()
    write_json(design.output_directory/'calibration.json',dict(
        status='numerically_admitted_approximate_calibration',
        author_acceptance='Author explicitly accepted the mismatch and requested a new subsection.',
        sigmas=[1.],chi=peak['chi'],parameters=asdict(design.parameters),
        frontier=design.frontier,initial_stocks=list(design_initial_stocks(design,1.)),
        target_share=TARGET_SHARE,matched_share=peak['first_year']['share'],
        target_exactly_matched=False,
        relative_shortfall=1-peak['first_year']['share']/TARGET_SHARE,
        numerical_tolerances_unchanged=True,source=SOURCE,
        peak_verification_sha256=hashlib.sha256((base.output_directory/'peak_verification.json').read_bytes()).hexdigest(),
        checkpoint_sha256=report['checkpoint_sha256'],
        csv_sha256=hashlib.sha256(csv_path.read_bytes()).hexdigest(),figure_sha256=figure_hashes))
    print('Published the admitted sigma=1 approximate calibration; no other elasticity was exported.',flush=True)
    return design


def calibrated_design():
    payload=json.loads((make_design(1.).output_directory/'calibration.json').read_text())
    design=make_design(payload['chi'])
    if (payload['target_share'] != TARGET_SHARE or payload['target_years'] != TARGET_YEARS
        or payload['parameters'] != asdict(design.parameters)
        or payload['frontier'] != design.frontier
        or payload['initial_capability'] != design.initial_capability
        or payload['initial_capital_rule'] != design.initial_capital_rule
        or payload['initial_stocks_by_sigma'] != {
            key(s):list(design_initial_stocks(design,s)) for s in SIGMAS}):
        raise ValueError('Stored calibration belongs to different parameters, stocks or target.')
    return design


def validate_final_moment(solution):
    moment=checked_moment(solution)
    error=math.log(moment['share']/TARGET_SHARE)
    if abs(error) > TARGET_LOG_TOLERANCE:
        raise RuntimeError('Research-share match changed after horizon refinement.')
    return dict(refined_matched_share=moment['share'],refined_target_log_residual=error,
                refined_quadrature_log_gap=moment['quadrature_log_gap'])


def finish(design):
    shared_finish(design,calibration_validator=validate_final_moment)
    moments={}
    for sigma in SIGMAS:
        sol=load_solution(design.cache_directory/f'{key(sigma)}_long.npz')
        first,second=checked_moment(sol),checked_moment(sol,1.)
        moments[key(sigma)]=dict(first_year=first,second_year=second,
            annual_share_growth=second['share']/first['share']-1,
            untargeted_price_ratio_27_months=math.exp(log_price_ratio(sol)))
    write_json(design.output_directory/'annual_moments.json',dict(
        target_share=TARGET_SHARE,target_sigma=1.,scenarios=moments,
        csv_sha256=hashlib.sha256((design.output_directory/'equilibrium_paths.csv').read_bytes()).hexdigest()))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--calibrate-only',action='store_true')
    parser.add_argument('--diagnose',action='store_true')
    parser.add_argument('--verify-peak',action='store_true')
    parser.add_argument('--compare-published',action='store_true')
    parser.add_argument('--publish-unit',action='store_true')
    parser.add_argument('--sigma',type=float,choices=SIGMAS)
    parser.add_argument('--finish',action='store_true')
    args=parser.parse_args()
    if args.publish_unit:
        publish_unit()
        return
    if args.compare_published:
        compare_published()
        return
    if args.verify_peak:
        verify_peak()
        return
    if args.diagnose:
        diagnose()
        return
    if args.calibrate_only:
        calibrate()
        return
    path=make_design(1.).output_directory/'calibration.json'
    design=calibrated_design() if path.exists() else calibrate()
    if args.sigma is not None:
        run(args.sigma,design)
    elif args.finish:
        finish(design)
    else:
        for sigma in SIGMAS:
            run(sigma,design)
        finish(design)


if __name__ == '__main__':
    main()
