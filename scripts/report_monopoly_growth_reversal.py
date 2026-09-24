"""Verified paper-style comparison for the monopoly growth reversal."""
from dataclasses import asdict
import csv
import hashlib
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'.python-packages'),str(ROOT/'scripts')]
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.ticker import PercentFormatter, MaxNLocator, LogLocator, NullLocator, MultipleLocator
from simulate_monopoly_growth_reversal import make_design, PRODUCTIVITIES, SIGMA
from solve_competitive_ai_transition import solve, audit, rows as competitive_rows
from analyze_axm_finite_cap_bvp import critical_capability_frontier, terminal_point
from calibrate_rewrite_ai_price import write_json
from simulate_rewrite_finite_frontier import key

OUT=ROOT/'numerical_rewrite'/'monopoly_growth_reversal'
FIG=ROOT/'figures_rewrite'/'monopoly_growth_reversal'
STYLES={'Competition':('#414141',(0,(4,2))),
        'Monopoly, chi = 7.5':('#24618c','-'),
        'Monopoly, chi = 1.5':('#bd8620',(0,(5,1.8,1,1.8)))}
WINDOWS=((0.,10.),(10.,100.),(100.,500.))


def read_json(path):
    return json.loads(path.read_text(encoding='utf-8'))


def write_csv(path, data):
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('w',newline='',encoding='utf-8') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(data[0]))
        writer.writeheader(); writer.writerows(data)


def checked_monopoly(design):
    path=design.output_directory/'equilibrium_paths.csv'
    manifest=read_json(design.output_directory/'paths_manifest.json')
    audit_record=read_json(design.output_directory/f'{key(SIGMA)}_audit.json')
    if any(manifest[k] != value for k,value in dict(
            parameters=asdict(design.parameters), frontier=design.frontier,
            initial_capital=design.initial_capital,
            initial_capability=design.initial_capability).items()):
        raise RuntimeError('Stored paths do not match the requested initial stocks or parameters.')
    if (not audit_record['equilibrium_certified'] or
            not audit_record['early_window_checks']['passes'] or
            hashlib.sha256(path.read_bytes()).hexdigest()!=manifest['csv_sha256'] or
            manifest['checkpoint_sha256'][key(SIGMA)]!=audit_record['checkpoint_sha256']):
        raise RuntimeError('Unverified monopoly data; no figure export.')
    with path.open(newline='',encoding='utf-8') as stream:
        data=[{k:float(v) for k,v in r.items()} for r in csv.DictReader(stream)]
    for r in data:
        r['capability']=r['capability_frontier_ratio']*design.frontier
        r['ai_services_effective_labor']=(r['capability']*r['inference_output_share']
            *r['output_effective_labor'])
    return data,manifest


def figure(data,kind,monopoly_limit,competition_limit,prehistory=None):
    panels=(('output_per_person_growth','A. Output per worker\n$g_Y-n$','rate'),
            ('wage_growth','B. Wage growth\n$g_w$','rate'),
            ('net_interest','C. Net interest rate\n$r$','rate')) if kind=='growth' else (
            ('capability_frontier_ratio','A. AI efficiency\n$B/\\overline{B}$','share'),
            ('ai_services_counterfactual_ratio','B. AI services\nrelative to competition','ratio'),
            ('labor_income_share','C. Labor income\n$wL/Y$','share'))
    plt.rcParams.update({'font.family':'DejaVu Serif','font.size':9})
    fig,axes=plt.subplots(3,3,figsize=(8.6,9.0))
    windows = ((-10.,10.), *WINDOWS[1:]) if prehistory else WINDOWS
    for i,(start,end) in enumerate(windows):
        for ax,(field,label,scale) in zip(axes[i],panels):
            if i == 0 and prehistory:
                ax.plot([r['time'] for r in prehistory], [r[field] for r in prehistory],
                    color=STYLES['Competition'][0], ls=STYLES['Competition'][1], lw=1.5)
                ax.axvline(0, color='#aaaaaa', ls=':', lw=.8)
            for name,series in data.items():
                chosen=[r for r in series if start<=r['time']<=end]
                t=np.array([r['time'] for r in chosen])
                values=np.array([r[field] for r in chosen])
                if not np.all(np.isfinite(values)):
                    raise ValueError('Nonfinite plotted values.')
                color,style=STYLES[name]
                ax.plot(t,values,color=color,ls=style,lw=1.5)
                if i==0:
                    ax.plot(0,values[0],marker='o',ms=3,color=color,
                        mfc='white' if name=='Competition' else color,clip_on=False)
            if i==2 and kind=='growth':
                ax.axhline(monopoly_limit[field],color='#888888',ls=':',lw=.8)
                ax.axhline(competition_limit[field],color='#888888',ls=':',lw=.8)
            if scale=='ratio' and i>0:
                ax.set_yscale('log')
                ax.yaxis.set_major_locator(LogLocator(base=10,numticks=5))
                ax.yaxis.set_minor_locator(NullLocator())
            else:
                ax.yaxis.set_major_formatter(PercentFormatter(1,decimals=1))
                ax.yaxis.set_major_locator(MaxNLocator(4))
            if prehistory and field=='labor_income_share' and i<2:
                # Distinct one-decimal percent ticks (not repeated 0.1% labels).
                ax.set_ylim(0, .002 if i==0 else .003)
                ax.yaxis.set_major_locator(MultipleLocator(.001))
            if prehistory and field=='capability_frontier_ratio':
                ax.set_ylim(.89,1.005)
                ax.set_yticks([.9,.95,1.])
            if prehistory and kind=='growth' and field!='net_interest':
                minimum = min(r[field] for series in data.values() for r in series
                              if start<=r['time']<=end)
                if minimum < 0:
                    # Keep a labeled negative tick so contraction is explicit.
                    lower, upper = ax.get_ylim()
                    negative_tick = np.floor(minimum*100)/100
                    if upper > .1:
                        negative_tick = min(negative_tick,-.02)
                    ticks = [v for v in ax.get_yticks() if 0<=v<=upper]
                    ax.set_yticks([negative_tick,*ticks])
                    ax.set_ylim(min(lower,negative_tick-.001),upper)
            ax.set_title(label,loc='left',fontsize=10,pad=8)
            ax.set_xlim(start,end)
            ax.set_xticks(([-10,-5,0,5,10] if prehistory else [0,5,10]) if i==0 else ([10,25,50,75,100] if i==1 else [100,250,500]))
            ax.set_xlabel(['Years: initial transition','Years: intermediate window','Years: longer window'][i])
            ax.grid(axis='y',color='#dddddd',lw=.5)
            ax.spines[['top','right']].set_visible(False)
            ax.spines[['left','bottom']].set_color('#999999')
    handles=[Line2D([],[],color=c,ls=ls,lw=1.5,label=name.replace('chi',r'$\chi$'))
             for name,(c,ls) in STYLES.items()]
    fig.legend(handles=handles,loc='upper center',bbox_to_anchor=(.52,.97),ncol=3,frameon=False,fontsize=9)
    note=('Rates on the smooth paths; the date-zero losses in output and wages are separate level changes.\n'
          'Gray dotted lines in the bottom row: theoretical long-run limits.') if kind=='growth' else (
          'Panel B: 100.0% or 1 = continued competition; logarithmic scale in the middle and bottom rows.\n'
          'All paths share initial capital and AI efficiency. Vertical scales differ across windows.')
    fig.text(.095,.015,note,fontsize=8,color='#444444',va='bottom')
    fig.subplots_adjust(left=.10,right=.97,bottom=.105,top=.89,wspace=.46,hspace=.92)
    return fig


def main(design_factory=make_design, output=OUT, figure_directory=FIG,
         initialization=None, prehistory=None):
    OUT, FIG = output, figure_directory
    design=design_factory(7.5)
    mon,manifest=checked_monopoly(design)
    low,low_manifest=checked_monopoly(design_factory(1.5))
    times=np.array([r['time'] for r in mon])
    if not np.array_equal(times,[r['time'] for r in low]):
        raise ValueError('Unequal comparison dates.')
    args=(design.initial_capability,SIGMA,design.parameters,design.initial_capital)
    first=solve(*args,horizon=1200.)
    final=solve(*args,horizon=1800.,previous=first)
    checks=audit(first,final)
    if not checks['passes']:
        raise RuntimeError(f'Competitive benchmark not admitted: {checks}')
    benchmark=competitive_rows(final,times)
    for r in benchmark:
        r['capability_frontier_ratio']=r['capability']/design.frontier
    data={'Competition':benchmark,'Monopoly, chi = 7.5':mon,'Monopoly, chi = 1.5':low}
    for series in data.values():
        for r,ref in zip(series,benchmark):
            for field in ('ai_services_effective_labor','output_effective_labor',
                          'consumption_effective_labor','wage_productivity'):
                target=dict(ai_services_effective_labor='ai_services',output_effective_labor='output',
                    consumption_effective_labor='consumption',wage_productivity='wage')[field]
                r[f'{target}_counterfactual_ratio']=r[field]/ref[field]
    p=design.parameters
    terminal=terminal_point(SIGMA,design.frontier,p)
    monlimit=dict(output_per_person_growth=p.labor_productivity_growth,
        wage_growth=p.labor_productivity_growth,net_interest=terminal.net_interest_rate,
        labor_income_share=terminal.labor_income_share)
    complimit=dict(output_per_person_growth=checks['limiting_output_per_worker_growth'],
        wage_growth=checks['limiting_wage_growth'],net_interest=checks['limiting_interest_rate'],
        labor_income_share=0.)
    threshold=critical_capability_frontier(SIGMA,p)
    initial_k = design.initial_capital/(p.initial_labor_productivity*p.initial_population)
    summary=dict(parameters=asdict(p),sigma=SIGMA,chi_values=list(PRODUCTIVITIES),
        frontier=design.frontier,initial_capability=design.initial_capability,
        initial_capital=design.initial_capital,monopoly_threshold=threshold,
        competitive_threshold=(1-p.alpha)*threshold,
        competitive_initial_capital_output_ratio=initial_k/benchmark[0]['output_effective_labor'],
        monopoly_initial_capital_output_ratio=initial_k/mon[0]['output_effective_labor'],
        monopoly_limits=monlimit,competitive_limits=complimit,
        competitive_audit=checks,observations={},impacts={})
    for name,series in data.items():
        summary['observations'][name]={str(t):min(series,key=lambda r:abs(r['time']-t))
                                      for t in (0,1,10,50,100,250,500)}
        summary['impacts'][name]={field:series[0][field]-1 for field in
            ('ai_services_counterfactual_ratio','output_counterfactual_ratio',
             'wage_counterfactual_ratio','consumption_counterfactual_ratio')}
        if name!='Competition':
            # Verify the economic event rather than depicting connected rate jumps.
            if not (abs(series[0]['capital_effective_labor']/initial_k-1)<1e-10
                and abs(series[0]['capability']/design.initial_capability-1)<1e-10
                and series[0]['output_counterfactual_ratio']<1
                and series[0]['ai_services_counterfactual_ratio']<1):
                raise ValueError('Event continuity or pricing check failed.')
    OUT.mkdir(parents=True,exist_ok=True); FIG.mkdir(parents=True,exist_ok=True)
    write_csv(OUT/'continued_competition.csv',benchmark)
    write_json(OUT/'competitive_audit.json',checks)
    if initialization is not None:
        summary['initialization'] = initialization
    write_json(OUT/'summary.json',summary)
    comparison=[dict(scenario=name,**{field:r[field] for field in
        ('time','capability_frontier_ratio','output_per_person_growth','wage_growth','net_interest',
         'labor_income_share','ai_services_counterfactual_ratio','output_counterfactual_ratio',
         'wage_counterfactual_ratio','consumption_counterfactual_ratio')})
        for name,series in data.items() for r in series]
    write_csv(OUT/'comparison_paths.csv',comparison)
    outputs=[]
    for kind in ('growth','technology'):
        fig=figure(data,kind,monlimit,complimit,prehistory=prehistory)
        for suffix in ('pdf','png'):
            path=FIG/f'monopoly_growth_reversal_{kind}.{suffix}'
            fig.savefig(path,dpi=190); outputs.append(path)
        plt.close(fig)
    inputs = [OUT/'comparison_paths.csv',OUT/'continued_competition.csv',*outputs]
    if prehistory is not None:
        inputs += [OUT/'competitive_prehistory.csv', OUT/'initialization.json']
    provenance=dict(parameters=asdict(p),monopoly_input_csv_sha256={
        '7.5':manifest['csv_sha256'],'1.5':low_manifest['csv_sha256']},
        competitive_solver='scripts/solve_competitive_ai_transition.py',
        files_sha256={path.relative_to(ROOT).as_posix():hashlib.sha256(path.read_bytes()).hexdigest()
                      for path in inputs})
    write_json(OUT/'figure_manifest.json',provenance)
    print(json.dumps({k:summary[k] for k in ('competitive_initial_capital_output_ratio',
          'monopoly_initial_capital_output_ratio','monopoly_limits','competitive_limits','impacts')},indent=2))


if __name__=='__main__':
    main()
