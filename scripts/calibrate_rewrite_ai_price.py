"""Price-targeted comparisons, including RSI activation with existing AI.

Calibrate chi at sigma=1 to a specified price decline over 27 months.
All trial objects are BVP candidates, never exported as equilibrium paths.
The final four paths use the paper's full, unchanged admission workflow.
"""
from __future__ import annotations

import argparse
import csv
from dataclasses import asdict, replace
import hashlib
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / '.python-packages'), str(ROOT / 'scripts')]
import numpy as np
from scipy.optimize import brentq
from analyze_axm_finite_cap_bvp import terminal_point, critical_capability_frontier
from simulate_rewrite_finite_frontier import (
    PARAMETERS, FRONTIER, RAMSEY_START_STEADY_STATE, SIGMAS, SimulationDesign,
    key, save_solution, load_solution, run, export_paths, validate_solution_design,
    design_initial_stocks, fixed_efficiency_bgp,
)
from solve_axm_global_finite_cap_bvp import (
    solve_global_finite_cap_bvp, refine_global_horizon, reconstruct_levels,
)

OUTPUT = ROOT / 'numerical_rewrite' / 'price_calibrated'
CACHE = ROOT / 'tmp' / 'rewrite_bvp_price_calibrated'
TARGET_YEARS = 27 / 12
TARGET_PRICE_RATIO = 0.20
CALIBRATION = OUTPUT / 'calibration.json'
SOURCE = ('https://www.oecd.org/en/publications/'
          'artificial-intelligence-markets_d531d73f-en/full-report.html')
VARIANTS = {
    'baseline': ('price_calibrated', PARAMETERS.omega_x, 0.10, FRONTIER),
    'low_ai': ('price_calibrated_low_ai_high_cap', 0.10, 0.01,
               1.10*critical_capability_frontier(1.5, replace(PARAMETERS, omega_x=0.10))),
    'rsi_activation': ('rsi_activation', 0.10, 0.01,
               1.10*critical_capability_frontier(1.5, replace(PARAMETERS, omega_x=0.10))),
    'rsi_activation_half_decline': ('rsi_activation_half_decline', 0.10, 0.01,
               1.10*critical_capability_frontier(1.5, replace(PARAMETERS, omega_x=0.10))),
}
RSI_VARIANTS = ('rsi_activation', 'rsi_activation_half_decline')


def target_price_ratio(variant):
    """Half of the observed percentage decline, not half its log change."""
    if variant not in VARIANTS:
        raise ValueError(f'Unknown price-calibration variant: {variant}')
    return 1 - 0.5 * (1 - TARGET_PRICE_RATIO) if variant == RSI_VARIANTS[1] else TARGET_PRICE_RATIO


def design_price_target(design):
    for variant, specification in VARIANTS.items():
        if specification[0] == design.name:
            return target_price_ratio(variant)
    raise ValueError(f'No price target is defined for {design.name}')


def make_design(chi: float, variant: str = 'baseline') -> SimulationDesign:
    name, omega_x, initial_ratio, frontier = VARIANTS[variant]
    return SimulationDesign(
        name=name, sigmas=SIGMAS,
        parameters=replace(PARAMETERS, chi=float(chi), omega_x=omega_x), frontier=frontier,
        initial_capital=(None if variant in RSI_VARIANTS
                         else RAMSEY_START_STEADY_STATE.capital),
        initial_capability=initial_ratio * frontier,
        output_directory=ROOT/'numerical_rewrite'/name,
        cache_directory=ROOT/'tmp'/f'rewrite_bvp_{name}', display_horizon=500.0,
        initial_capital_rule=('fixed_efficiency_bgp' if variant in RSI_VARIANTS else 'common'),
        initial_stock_reference=(
            'Existing AI with omega_X=0.10 before and after an unanticipated RSI activation. '
            'Pre-event B=B0 is fixed and research is unavailable; pre-event chi=0, M=0. '
            'Each sigma inherits its own fixed-B BGP capital, with K0/Y0=3.30 and r0=0.05. '
            'Only stocks are inherited; C0 and q0 are selected anew by the positive-chi BVP. '
            f'Chi targets a price ratio of {target_price_ratio(variant):.2f} over 2.25 years '
            'at sigma=1 and is shared across sigmas.'
            if variant in RSI_VARIANTS else
            f'No-AI Ramsey steady-state capital, B0/Bbar={initial_ratio:.2f}; omega_X=0 '
            f'before date zero and {omega_x:.2f} thereafter. Chi matches the rounded '
            'OECD price decline at sigma=1 and is held fixed across sigmas. '
            'Consumption and the shadow value are selected anew by the BVP.'),
    )


def log_price_ratio(solution, years=TARGET_YEARS):
    if not 0 < years <= solution.horizon:
        raise ValueError('The price target must lie inside the solved horizon.')
    times = np.array([0.0, float(years)])
    v = reconstruct_levels(times, solution.raw.sol(times), solution)
    p, sigma = solution.parameters, solution.terminal.sigma_xl
    share = v['ai_ces_share']
    elasticity = (1 - share) / sigma + p.alpha * share
    prices = -v['log_capability'] - np.log1p(-elasticity)
    return float(prices[1] - prices[0])


def write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, allow_nan=False) + '\n', encoding='utf-8')


def calibrate(variant='baseline'):
    template = make_design(PARAMETERS.chi, variant)
    target_ratio = target_price_ratio(variant)
    output, cache = template.output_directory, template.cache_directory
    trials = []

    def objective(log_chi):
        chi = math.exp(float(log_chi))
        design = make_design(chi, variant)
        tag = hashlib.sha256(float(chi).hex().encode()).hexdigest()[:16]
        filename = cache / 'calibration_trials' / f'chi_{tag}.npz'
        print(f'Price calibration: solving chi={chi:.10g}', flush=True)
        if filename.exists():
            solution = load_solution(filename)
            validate_solution_design(solution, design, 1.0)
        else:
            terminal = terminal_point(1.0, design.frontier, design.parameters)
            capital, capability = design_initial_stocks(design, 1.0)
            solution = solve_global_finite_cap_bvp(
                terminal, design.parameters, capital,
                capability, continuation_steps=32, nodes=221,
                tolerance=2e-7, boundary_tolerance=1e-10, maximum_nodes=40000)
            save_solution(solution, filename)
        ratio = math.exp(log_price_ratio(solution))
        residual = math.log(ratio / target_ratio)
        trials.append(dict(chi=chi, price_ratio=ratio, log_target_residual=residual,
                           checkpoint=str(filename.relative_to(ROOT)),
                           maximum_rms_residual=float(np.max(solution.raw.rms_residuals))))
        write_json(output / 'calibration_trials.json', trials)
        print(f'chi={chi:.10g}: p(2.25)/p(0)={ratio:.10g}', flush=True)
        return residual

    # These are search brackets, not economic restrictions or fitted data.
    lower = math.log(PARAMETERS.chi)
    # For lower initial B, grow the bracket from the solved small-chi case;
    # there is no need to solve a distant high-chi candidate to bracket the target.
    upper = math.log(2*PARAMETERS.chi if variant == 'low_ai' or variant in RSI_VARIANTS else 64.0)
    fl, fu = objective(lower), objective(upper)
    for _ in range(10):
        if fl * fu <= 0:
            break
        if fl > 0 and fu > 0:
            upper += math.log(2)
            fu = objective(upper)
        else:
            lower -= math.log(2)
            fl = objective(lower)
    else:
        raise RuntimeError('No price-target bracket found; no calibration published.')
    root = brentq(objective, lower, upper, xtol=2e-6, rtol=1e-10)
    chi = math.exp(root)
    residual = objective(root)
    if abs(residual) > 2e-5:
        raise RuntimeError('Price target not matched; no calibration published.')
    payload = dict(
        status='fitted_candidate_pending_equilibrium_admission', chi=chi,
        calibration_sigma=1.0, target_years=TARGET_YEARS,
        target_price_ratio=target_ratio, matched_price_ratio=target_ratio*math.exp(residual),
        observed_rounded_price_ratio=TARGET_PRICE_RATIO,
        target_decline_fraction_of_observed=(1-target_ratio)/(1-TARGET_PRICE_RATIO),
        target_definition='Arithmetic percentage decline over 27 months, not a log decline or a halving of chi.',
        variant=variant, design=template.name,
        target_log_residual=residual, parameters=asdict(make_design(chi, variant).parameters),
        frontier=template.frontier, initial_capital=template.initial_capital,
        initial_capital_rule=template.initial_capital_rule,
        initial_capital_by_sigma={key(s): design_initial_stocks(template, s)[0] for s in SIGMAS},
        initial_capability=template.initial_capability,
        source=dict(url=SOURCE, title='Artificial Intelligence markets: Recent developments and competition issues',
                    institution='OECD', publication_date='2026-07-10', accessed='2026-09-14',
                    window_start='2024-01', window_end='2026-04',
                    measure='Quality-adjusted cloud API price index for text-to-text models',
                    source_precision='nearly 80 percent; rounded to 80 percent for this exercise'),
        numeraire_assumption=(
            'The general final-good price is held constant over the target window. '
            'This uses the rounded dollar-price fall as an approximate relative-price target, '
            'not an exactly deflated empirical estimate.'),
        interpretation=(
            'Conditional timing calibration, not identification of RSI productivity; '
            'competition, hardware, human R&D and task intensity are not separately identified. '
            'Model year zero is an experiment date, not a claim that January 2024 had no AI.'),
        root_log_chi_tolerance=2e-6, trials=trials,
    )
    write_json(output/'calibration.json', payload)
    if variant in RSI_VARIANTS:
        write_json(output/'pre_rsi_reference.json', dict(
            interpretation=template.initial_stock_reference,
            scenarios={key(s): fixed_efficiency_bgp(s, template.initial_capability,
                                                   template.parameters) for s in SIGMAS}))
    return make_design(chi, variant)


def calibrated_design(variant='baseline'):
    path = make_design(PARAMETERS.chi, variant).output_directory/'calibration.json'
    payload = json.loads(path.read_text(encoding='utf-8'))
    if payload['target_years'] != TARGET_YEARS or payload['target_price_ratio'] != target_price_ratio(variant):
        raise ValueError('Stored calibration belongs to another price target.')
    design = make_design(payload['chi'], variant)
    if payload['parameters'] != asdict(design.parameters) or payload['frontier'] != design.frontier:
        raise ValueError('Stored calibration belongs to other parameters.')
    if (payload['initial_capital'] != design.initial_capital
            or payload['initial_capability'] != design.initial_capability):
        raise ValueError('Stored calibration belongs to other initial stocks.')
    if variant in RSI_VARIANTS and (
            payload.get('initial_capital_rule') != design.initial_capital_rule
            or set(payload.get('initial_capital_by_sigma', {})) != {key(s) for s in SIGMAS}
            # Match the checkpoint guard's roundoff allowance for numerically
            # derived BGP stocks. Parameters and explicit stocks remain exact.
            or any(not math.isclose(payload['initial_capital_by_sigma'][key(s)],
                                    design_initial_stocks(design, s)[0],
                                    rel_tol=8*np.finfo(float).eps, abs_tol=0.)
                   for s in SIGMAS)):
        raise ValueError('Stored calibration belongs to another pre-RSI BGP.')
    return design


def extend(sigma, design):
    cache = design.cache_directory
    source = load_solution(cache / f'{key(sigma)}_refined.npz')
    validate_solution_design(source, design, sigma)
    target = cache / f'{key(sigma)}_long.npz'
    if not target.exists():
        longer = refine_global_horizon(source, source.horizon+500, nodes=601,
                                      tolerance=1e-9, boundary_tolerance=1e-11)
        save_solution(longer, target)
    else:
        validate_solution_design(load_solution(target), design, sigma)
    print(f'{key(sigma)}: second horizon extension complete', flush=True)


def render_comparison_views(design, *, show_price_target=True, reference_sigma=1.5,
                            figure_types=None):
    """Same economic panels, with explicit initial and subsequent windows."""
    import matplotlib.pyplot as plt
    from matplotlib.ticker import PercentFormatter, MaxNLocator, FuncFormatter, NullLocator
    from plot_rewrite_equilibria import (
        STYLES, PANELS_QUANTITY_GROWTH, PANELS_PRICES_RETURNS, PANELS_DISTRIBUTION,
    )
    # Match the published RSI window figures regardless of whether render()
    # (which styles the separate full-window figures) ran in this process.
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,
                         'axes.titlesize':12,'axes.labelsize':10,
                         'xtick.labelsize':10,'ytick.labelsize':10,
                         'legend.fontsize':10,'pdf.fonttype':42})
    output = design.output_directory
    manifest = json.loads((output/'figure_manifest.json').read_text())
    csv_path = output/'equilibrium_paths.csv'
    if hashlib.sha256(csv_path.read_bytes()).hexdigest() != manifest['data_sha256']:
        raise ValueError('Price-comparison data differ from the admitted export.')
    with csv_path.open(encoding='utf-8', newline='') as stream:
        rows = [{k:float(v) for k,v in row.items()} for row in csv.DictReader(stream)]
    limits = manifest['analytical_limits'][key(reference_sigma)]
    pre = None
    if design.initial_capital_rule == 'fixed_efficiency_bgp':
        activation_path = output/'activation_audit.json'
        activation = json.loads(activation_path.read_text())
        if not activation['passes']:
            raise ValueError('The RSI event has not passed its continuity audit.')
        pre = {key(s): fixed_efficiency_bgp(s, design.initial_capability, design.parameters)
               for s in design.sigmas}
    views = {v['filename']: v for v in manifest.get('two_window_views', [])}
    focused_distribution = design.name in ('rsi_chi_7_5', 'rsi_chi_1_5')
    for suffix, panels in (('accumulation_growth', PANELS_QUANTITY_GROWTH),
                           ('growth_returns', PANELS_PRICES_RETURNS),
                           ('ai_distribution', PANELS_DISTRIBUTION)):
        if figure_types is not None and suffix not in figure_types:
            continue
        columns = 3 if len(panels) == 3 else 2
        rows_per_view = 1 if columns == 3 else 2
        fig, axes = plt.subplots(2*rows_per_view, columns,
                                 figsize=(7, 5.7 if columns == 3 else 8.5))
        axes = np.asarray(axes).reshape(2, len(panels))
        windows = ((-2.0 if pre else 0.0,10.0), (10.0,design.display_horizon))
        for view, (start, end) in enumerate(windows):
            for axis, (field, title, scale) in zip(axes[view], panels):
                focus_initial = (focused_distribution and view == 0 and
                                 field in ('labor_income_share', 'inference_output_share'))
                for sigma in design.sigmas:
                    series = [r for r in rows if r['sigma'] == sigma and start <= r['time'] <= end]
                    color, linestyle = STYLES[sigma]
                    times, values = [r['time'] for r in series], [r[field] for r in series]
                    if pre and view == 0:
                        reference = dict(pre[key(sigma)],
                            output_effective_labor_growth=0., ai_services_effective_labor_growth=0.,
                            capital_effective_labor_growth=0.,
                            wage_growth=design.parameters.labor_productivity_growth,
                            net_interest=pre[key(sigma)]['interest_rate'])
                        times = [-2., 0.] + times
                        values = [reference[field], reference[field]] + values
                    axis.plot(times, values,
                              color=color, linestyle=linestyle, linewidth=1.4,
                              label=fr'$\sigma={sigma:.2f}$')
                # Short-run A/C scales follow all four initial trajectories,
                # with the existing Matplotlib margins, not distant limits.
                if not focus_initial:
                    axis.axhline(limits[field], color='#222222', linestyle=(0,(1,2)), linewidth=.8)
                axis.set_title(title, loc='left', y=1.02, pad=6)
                if scale in ('rate', 'share'):
                    decimals = (3 if view == 1 and field == 'research_output_share'
                                and axis.get_ylim()[1] < .001 else
                                2 if len(design.sigmas)==1 and field in (
                                    'inference_output_share','research_output_share') else 1)
                    if len(design.sigmas)==1 and scale=='rate' and max(abs(v) for v in axis.get_ylim())<.01:
                        decimals=2
                    axis.yaxis.set_major_formatter(PercentFormatter(1, decimals=decimals))
                    axis.yaxis.set_major_locator(MaxNLocator(4))
                elif scale == 'log_level':
                    axis.set_yscale('log')
                    axis.yaxis.set_major_formatter(FuncFormatter(lambda y,p:f'{y:g}'))
                    if len(design.sigmas)==1 and view==1 and axis.get_ylim()[1]/axis.get_ylim()[0]<3:
                        axis.yaxis.set_major_locator(MaxNLocator(4))
                        axis.yaxis.set_minor_locator(NullLocator())
                if scale == 'share' and not (focus_initial and field == 'labor_income_share'):
                    lo, hi = axis.get_ylim()
                    if len(design.sigmas)==1:
                        hi=max(hi,1.08*max(values))
                    axis.set_ylim(min(0,lo), hi)
                if field.endswith('effective_labor_growth'):
                    axis.axhline(0, color='#999999', linewidth=.5)
                axis.set_xlim(start, end)
                axis.set_xticks(([-2,0,2,4,6,8,10] if pre else np.linspace(0,end,6))
                               if view == 0 else [10,100,200,300,400,500])
                if pre and view == 0:
                    axis.axvline(0, color='#888888', linewidth=.7, linestyle=':')
                axis.set_xlabel(('Years (initial)' if view==0 else 'Years (subsequent)')
                    if len(design.sigmas)==1 else
                    ('Years: initial transition' if view == 0 else 'Years: subsequent transition'))
                axis.grid(axis='y', color='#dddddd', linewidth=.5)
                axis.spines[['top','right']].set_visible(False)
                axis.spines[['left','bottom']].set_color('#888888')
                axis.tick_params(length=3, color='#888888')
                if show_price_target and field == 'ai_service_price' and view == 0:
                    p0 = next(r[field] for r in rows if r['sigma'] == 1. and r['time'] == 0.)
                    axis.plot(TARGET_YEARS, design_price_target(design)*p0, marker='D',
                              color='black', markersize=4, linestyle='none', zorder=5)
            if suffix == 'accumulation_growth':
                lo=min(axes[view, j].get_ylim()[0] for j in (0,2))
                hi=max(axes[view, j].get_ylim()[1] for j in (0,2))
                for j in (0,2):
                    axes[view,j].set_ylim(lo,hi)
        handles, labels = axes[0,0].get_legend_handles_labels()
        fig.legend(handles,labels,ncol=min(4,len(design.sigmas)),loc='upper center',frameon=False,
                   bbox_to_anchor=(.5,.995),handlelength=2.6,columnspacing=1.6)
        fig.subplots_adjust(left=.105,right=.970,bottom=.09 if columns==3 else .055,
                            top=.83 if columns==3 else .90,
                            wspace=.50 if columns==3 else .35,
                            hspace=.95 if columns==3 else .90)
        filename=f'equilibrium_{design.name}_{suffix}_windows'
        for extension in ('pdf','png'):
            fig.savefig(ROOT/'figures_rewrite'/f'{filename}.{extension}', dpi=190)
        plt.close(fig)
        views[filename] = dict(filename=filename, windows=[list(w) for w in windows],
                          fields=[p[0] for p in panels],
                          independent_vertical_scales_between_windows=True)
        if focused_distribution and suffix == 'ai_distribution':
            views[filename]['initial_trajectory_scaled_fields'] = [
                'labor_income_share', 'inference_output_share']
    manifest['two_window_views'] = list(views.values())
    manifest['price_target'] = (dict(years=TARGET_YEARS, ratio=design_price_target(design))
                                if show_price_target else None)
    if pre:
        manifest['pre_event_bgp'] = pre
        manifest['activation_audit_sha256'] = hashlib.sha256(activation_path.read_bytes()).hexdigest()
    write_json(output/'figure_manifest.json', manifest)


def summarize(design):
    """Save the exact CSV observations used in the paper's numerical prose."""
    output = design.output_directory
    with (output/'equilibrium_paths.csv').open(encoding='utf-8', newline='') as stream:
        rows=[{k:float(v) for k,v in row.items()} for row in csv.DictReader(stream)]
    summary=dict(design=design.name, instantaneous_growth_rates=True, scenarios={})
    for sigma in design.sigmas:
        series=[r for r in rows if r['sigma']==sigma]
        snapshots={str(t): next(r for r in series if r['time']==t)
                   for t in (0.,2.25,10.,50.,100.,500.)}
        summary['scenarios'][key(sigma)]=dict(
            snapshots=snapshots,
            target_window_price_ratio=snapshots['2.25']['ai_service_price']/series[0]['ai_service_price'],
            initial_profit_ai_revenue_ratio=series[0]['profit_output_share']/series[0]['ai_revenue_output_share'])
    manifest=json.loads((output/'paths_manifest.json').read_text())
    summary['sigma_1_50_transition_dates']=manifest['sigma_1_50_transition_dates']
    summary['data_sha256']=manifest['csv_sha256']
    write_json(output/'summary.json',summary)


def audit_rsi_activation(design):
    """Check pre-event equations and unchanged production at the RSI event."""
    from solve_near_unit_ai_bvp import solve_monopoly_static_block
    p = design.parameters
    checks = {}
    for sigma in design.sigmas:
        pre = fixed_efficiency_bgp(sigma, design.initial_capability, p)
        sol = load_solution(design.cache_directory/f'{key(sigma)}_long.npz')
        validate_solution_design(sol, design, sigma)
        v = reconstruct_levels(np.array([0.]), sol.raw.sol(np.array([0.])), sol)
        post = {name: math.exp(v['log_'+field][0]) for name, field in (
            ('capital','capital'), ('capability','capability'), ('output','output'),
            ('consumption','consumption'), ('inference_compute','inference_compute'),
            ('research_compute','research_compute'))}
        s = solve_monopoly_static_block(math.log(post['capital']), math.log(post['capability']), 0., sigma, p)
        post.update(ai_services=math.exp(s.log_ai_services),
            ai_service_price=(1-p.alpha)*s.ai_ces_share*post['output']/math.exp(s.log_ai_services),
            wage=(1-p.alpha)*(1-s.ai_ces_share)*post['output'],
            interest_rate=p.alpha*post['output']/post['capital']-p.depreciation)
        continuous = ('capital','capability','output','ai_services','inference_compute',
                      'ai_service_price','wage','interest_rate')
        gaps = {field: abs(math.log(post[field]/pre[field])) for field in continuous}
        bgp_checks=[]
        growth=p.population_growth+p.labor_productivity_growth
        for t in (-10., -2., 0.):
            scale=math.exp(growth*t)
            block=solve_monopoly_static_block(math.log(pre['capital'])+growth*t,
                        math.log(pre['capability']),growth*t,sigma,p)
            y,u=math.exp(block.log_output),math.exp(block.log_inference_compute)
            bgp_checks.append(dict(time=t,
                output_scaling_residual=abs(block.log_output-math.log(pre['output'])-growth*t),
                resource_residual=abs((y-pre['consumption']*scale-u-
                   (p.depreciation+growth)*pre['capital']*scale)/y),
                household_euler_residual=abs(p.alpha*y/(pre['capital']*scale)
                   -p.depreciation-p.discount-p.labor_productivity_growth),
                monopoly_foc_residual=abs(block.monopoly_foc_log_residual)))
        passes=max(gaps.values())<1e-9 and all(
            max(v for k,v in row.items() if k!='time')<1e-9 for row in bgp_checks)
        pre_i=pre['output']-pre['consumption']-pre['inference_compute']
        post_i=post['output']-post['consumption']-post['inference_compute']-post['research_compute']
        reallocation=abs((post_i-pre_i+post['consumption']-pre['consumption']
                         +post['research_compute'])/pre['output'])
        passes=bool(passes and reallocation<1e-9)
        checks[key(sigma)]=dict(pre=pre,post=post,level_log_gaps=gaps,
            pre_event_equation_checks=bgp_checks,passes=passes,
            consumption_jump=post['consumption']/pre['consumption']-1,
            post_event_research_output_share=post['research_compute']/post['output'],
            pre_gross_investment_output_share=pre_i/pre['output'],
            post_gross_investment_output_share=post_i/post['output'],
            post_net_capital_growth=post_i/post['capital']-p.depreciation,
            resource_reallocation_residual=reallocation)
    payload=dict(design=design.name,passes=all(c['passes'] for c in checks.values()),
        interpretation='Unexpected activation of previously unavailable RSI; production weights do not change.',
        tolerance=1e-9, tolerance_reason='Same static equations and inherited stocks, at final BC tolerance 1e-11.',
        scenarios=checks)
    write_json(design.output_directory/'activation_audit.json',payload)
    if not payload['passes']:
        raise RuntimeError('RSI activation continuity/reference audit failed; no figure export.')


def compare_rsi_price_targets(design):
    """Bind the comparison to both admitted exports; never rewrite the baseline."""
    baseline = calibrated_design('rsi_activation')
    old_parameters, new_parameters = asdict(baseline.parameters), asdict(design.parameters)
    old_chi, new_chi = old_parameters.pop('chi'), new_parameters.pop('chi')
    if old_parameters != new_parameters or baseline.frontier != design.frontier:
        raise ValueError('The price sensitivity also changed another parameter.')
    initial_stocks = {}
    for sigma in SIGMAS:
        a,b = design_initial_stocks(baseline,sigma), design_initial_stocks(design,sigma)
        if a != b:
            raise ValueError('The price sensitivity changed initial stocks.')
        initial_stocks[key(sigma)] = dict(capital=a[0],capability=a[1])
    cases = {}
    for candidate in (baseline, design):
        folder = candidate.output_directory
        calibration = json.loads((folder/'calibration.json').read_text())
        summary = json.loads((folder/'summary.json').read_text())
        event = json.loads((folder/'activation_audit.json').read_text())
        digest = hashlib.sha256((folder/'equilibrium_paths.csv').read_bytes()).hexdigest()
        if (calibration['status'] != 'numerically_admitted' or not event['passes']
                or summary['data_sha256'] != digest):
            raise ValueError('The comparison requires admitted, hash-matched source data.')
        initial = {}
        for sigma in SIGMAS:
            row = summary['scenarios'][key(sigma)]['snapshots']['0.0']
            activation = event['scenarios'][key(sigma)]
            initial[key(sigma)] = dict(
                output_per_person_growth=row['output_per_person_growth'],
                wage_growth=row['wage_growth'],net_interest=row['net_interest'],
                consumption_jump=activation['consumption_jump'],
                gross_investment_output_share=activation['post_gross_investment_output_share'],
                research_output_share=row['research_output_share'],
                profit_output_share=row['profit_output_share'],
                research_revenue_share=row['research_revenue_share'],
                profit_revenue_share=row['profit_revenue_share'])
        cases[candidate.name] = dict(
            chi=candidate.parameters.chi, data_sha256=digest,
            target_price_ratio=design_price_target(candidate),
            matched_price_ratio=calibration['refined_matched_price_ratio'],
            activation_audit_sha256=hashlib.sha256((folder/'activation_audit.json').read_bytes()).hexdigest(),
            initial=initial, transition_dates=summary['sigma_1_50_transition_dates'])
    write_json(design.output_directory/'comparison_to_full_decline.json',dict(
        same_parameters_except_chi=True,same_initial_stocks=True,
        common_initial_stocks=initial_stocks,chi_ratio=new_chi/old_chi,
        target_definition='Half of the arithmetic percentage decline over 2.25 years.',
        cases=cases))


def finish(design, *, calibration_validator=None, calibration_filename='calibration.json',
           retain_price_outcome_marker=False, render_figures=True):
    """Shared, unchanged equilibrium gates; validate the selected moment last."""
    cache, output = design.cache_directory, design.output_directory
    calibration = output/calibration_filename
    from audit_rewrite_hamiltonian_support import audit_support
    from audit_rewrite_equilibria import finalize, independent_residuals
    from solve_axm_global_finite_cap_bvp import audit_counterfactual_developer_sufficiency
    from plot_rewrite_equilibria import render
    for sigma in SIGMAS:
        extend(sigma, design)
    checkpoint = cache / f'{key(1.5)}_long.npz'
    solution = load_solution(checkpoint)
    for dates, states in ((81,101), (321,241)):
        result = audit_support(solution, dates, states)
        result['checkpoint_sha256'] = hashlib.sha256(checkpoint.read_bytes()).hexdigest()
        write_json(output / f'{key(1.5)}_support_{dates}_{states}.json', result)
        print(f'Hamiltonian support {dates}/{states}: {result["support_diagnostic_passes"]}', flush=True)
    reports = finalize(design)
    # Uniform long-horizon grids can miss a rapid initial adjustment. Keep all
    # existing checks and add dense early-window tests, not looser tolerances.
    for sigma, report in zip(SIGMAS, reports):
        sol = load_solution(cache / f'{key(sigma)}_long.npz')
        early_times = np.linspace(0.001, 10.0, 801)
        residuals = [independent_residuals(sol, step, early_times)
                     for step in (0.0003, 0.0001)]
        concavity = audit_counterfactual_developer_sufficiency(
            sol, time_points=161, capability_points=161,
            sample_times=np.linspace(0.0, 10.0, 161))
        early_optimality = concavity['developer_sufficiency_gate_passes']
        support = []
        if not early_optimality and sigma == 1.5:
            for dates, states in ((161,161), (321,241)):
                check = audit_support(sol, dates, states,
                                      sample_times=np.linspace(0.0, 10.0, dates))
                check['checkpoint_sha256'] = hashlib.sha256(
                    (cache / f'{key(sigma)}_long.npz').read_bytes()).hexdigest()
                write_json(output / f'{key(sigma)}_early_support_{dates}_{states}.json', check)
                support.append({k:v for k,v in check.items() if k != 'checks'})
            early_optimality = all(
                c['support_diagnostic_passes'] and c['maximum_own_gap'] < 1e-10
                and c['maximum_tail_derivative_ratio'] <= 1 for c in support)
        early_passes = bool(early_optimality and all(
            c['maximum_ode_residual'] < 1e-6
            and c['maximum_research_foc_residual'] < 1e-9
            and c['maximum_monopoly_foc_residual'] < 1e-9 for c in residuals))
        report['early_window_checks'] = dict(
            start=0.0, end=10.0, independent_residuals=residuals,
            concavity=concavity, support=support, passes=early_passes)
        report['equilibrium_certified'] = bool(report['equilibrium_certified'] and early_passes)
        report['status'] = 'numerically_admitted' if report['equilibrium_certified'] else 'not_admitted'
        write_json(output / f'{key(sigma)}_audit.json', report)
        print(f'{key(sigma)}: early-window admission={early_passes}', flush=True)
    if not all(report['equilibrium_certified'] for report in reports):
        raise RuntimeError('Incomplete equilibrium admission: no path or figure export.')
    unit = load_solution(cache / f'{key(1.0)}_long.npz')
    if calibration_validator is None:
        final_ratio = math.exp(log_price_ratio(unit))
        if abs(math.log(final_ratio/design_price_target(design))) > 2e-5:
            raise RuntimeError('Price match changed after horizon refinement; recalibration required.')
        moment_results = dict(refined_matched_price_ratio=final_ratio)
    else:
        moment_results = calibration_validator(unit)
    payload = json.loads(calibration.read_text(encoding='utf-8'))
    payload.update(status='numerically_admitted', **moment_results,
                   final_checkpoint_sha256=hashlib.sha256((cache/f'{key(1.0)}_long.npz').read_bytes()).hexdigest())
    if design.initial_capital_rule == 'fixed_efficiency_bgp':
        audit_rsi_activation(design)
    write_json(calibration, payload)
    export_paths(design.display_horizon, 4001, design,
                 additional_times=np.linspace(0.0, 10.0, 1001))
    if render_figures:
        render(design)
        render_comparison_views(design, show_price_target=(calibration_validator is None
                                                         or retain_price_outcome_marker))
    if retain_price_outcome_marker:
        manifest_path = output/'figure_manifest.json'
        manifest = json.loads(manifest_path.read_text())
        manifest['price_outcome_marker'] = manifest['price_target']
        manifest['price_target'] = None
        write_json(manifest_path, manifest)
    summarize(design)
    if design.name == 'rsi_activation_half_decline':
        compare_rsi_price_targets(design)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--variant', choices=tuple(VARIANTS), default='baseline')
    parser.add_argument('--calibrate-only', action='store_true')
    parser.add_argument('--sigma', type=float, choices=SIGMAS)
    parser.add_argument('--finish', action='store_true')
    args = parser.parse_args()
    if args.calibrate_only:
        calibrate(args.variant)
        return
    calibration = make_design(PARAMETERS.chi, args.variant).output_directory/'calibration.json'
    design = calibrated_design(args.variant) if calibration.exists() else calibrate(args.variant)
    if args.sigma is not None:
        run(args.sigma, design)
    elif args.finish:
        finish(design)
    else:
        for sigma in SIGMAS:
            run(sigma, design)
        finish(design)


if __name__ == '__main__':
    main()
