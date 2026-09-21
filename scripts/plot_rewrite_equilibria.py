"""Render the agreed figures from admitted equilibrium data."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'.python-packages'))
sys.path.insert(0,str(ROOT/'scripts'))
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import PercentFormatter, MaxNLocator, FuncFormatter
from simulate_rewrite_finite_frontier import DESIGNS, MAIN_DESIGN, key
from analyze_axm_finite_cap_bvp import terminal_point

PANELS_QUANTITY_GROWTH=(
 ('output_effective_labor_growth', 'A. Output\n$g_Y-(n+\\gamma)$', 'rate'),
 ('ai_services_effective_labor_growth', 'B. AI services\n$g_X-(n+\\gamma)$', 'rate'),
 ('capital_effective_labor_growth', 'C. Capital\n$g_K-(n+\\gamma)$', 'rate'),
)
PANELS_PRICES_RETURNS=(
 ('wage_growth', 'A. Wage\ngrowth, $g_w$', 'rate'),
 ('net_interest', 'B. Net interest\nrate, $r$', 'rate'),
 ('ai_service_price', 'C. AI-service\nprice, $p_X$', 'log_level'),
)
PANELS_DISTRIBUTION=(
 ('labor_income_share', 'A. Labor income\n$wL/Y$', 'share'),
 ('profit_output_share', 'B. AI profit\n$\\Pi/Y$', 'share'),
 ('inference_output_share', 'C. Inference expenditure\n$U/Y$', 'share'),
 ('research_output_share', 'D. Research expenditure\n$M/Y$', 'share'),
)
PANELS_NEAR_TERMINAL=(
 ('output_per_person_growth', 'A. Output-per-person\ngrowth, $g_Y-n$', 'rate'),
 ('wage_growth', 'B. Wage\ngrowth, $g_w$', 'rate'),
 ('net_interest', 'C. Net interest\nrate, $r$', 'rate'),
)
NEAR_TERMINAL_YLIMS={
    'output_per_person_growth':(0.008,0.036),
    'wage_growth':(0.008,0.028),
    'net_interest':(0.048,0.076),
}
STYLES={.9:('#677748',(0,(5,2))),1.:('#414141','-'),
        1.1:('#bd8620',(0,(1,1.8))),1.5:('#24618c',(0,(5,1.8,1,1.8)))}
LIMIT_STYLE=('#222222',(0,(1,2)))


def analytical_plot_limits(sigma, frontier, parameters):
    """Use the selected regime, not AI-only pricing for a labor-supported limit."""
    terminal = terminal_point(sigma, frontier, parameters)
    revenue = (1-parameters.alpha)*terminal.ai_ces_share
    elasticity = (1-terminal.ai_ces_share)/sigma + parameters.alpha*terminal.ai_ces_share
    normalized_growth = (terminal.terminal_growth-parameters.population_growth
                         -parameters.labor_productivity_growth)
    return {
        'output_effective_labor_growth': normalized_growth,
        'ai_services_effective_labor_growth': normalized_growth,
        'capital_effective_labor_growth': normalized_growth,
        'wage_growth': parameters.labor_productivity_growth+normalized_growth/sigma,
        'net_interest': terminal.net_interest_rate,
        'ai_service_price': 1/((1-elasticity)*frontier),
        'labor_income_share': terminal.labor_income_share,
        'profit_output_share': revenue-terminal.inference_output_share,
        'inference_output_share': terminal.inference_output_share,
        'research_output_share': 0.0,
    }


def render(design=MAIN_DESIGN, *, reference_sigma=1.5):
    output=design.output_directory
    cache=design.cache_directory
    parameters=design.parameters
    frontier=design.frontier
    sigmas=design.sigmas
    reports={s:json.loads((output/f'{key(s)}_audit.json').read_text()) for s in sigmas}
    provenance=json.loads((output/'paths_manifest.json').read_text())
    if provenance.get('design') != design.name:
        raise ValueError('The path manifest belongs to a different simulation design.')
    if hashlib.sha256((output/'equilibrium_paths.csv').read_bytes()).hexdigest()!=provenance['csv_sha256']:
        raise ValueError('The plotted data have changed since their audited export.')
    for s,r in reports.items():
        if r.get('design') != design.name:
            raise ValueError(f'The sigma={s} audit belongs to a different design.')
        if not r['equilibrium_certified']:
            raise ValueError(f'sigma={s} is not admitted; refuse a partial comparison.')
        if hashlib.sha256((cache/r['checkpoint_filename']).read_bytes()).hexdigest()!=r['checkpoint_sha256']:
            raise ValueError('An audited checkpoint has changed.')
        if provenance['checkpoint_sha256'][key(s)]!=r['checkpoint_sha256']:
            raise ValueError('The CSV and current audit refer to different checkpoints.')
    rows=list(csv.DictReader((output/'equilibrium_paths.csv').open(encoding='utf-8')))
    data={s:[{k:float(v) for k,v in r.items()} for r in rows if float(r['sigma'])==s] for s in sigmas}
    if any(not v for v in data.values()):
        raise ValueError('The CSV omits a requested scenario.')
    figdir=ROOT/'figures_rewrite'
    figdir.mkdir(exist_ok=True)
    plt.rcParams.update({'font.family':'DejaVu Serif','font.size':9,
                         'axes.titlesize':9,'axes.labelsize':9,
                         'xtick.labelsize':8,'ytick.labelsize':8,
                         'legend.fontsize':9,'pdf.fonttype':42})
    prefix='equilibrium' if design.name=='main' else f'equilibrium_{design.name}'
    extra_limits=None
    if design.name=='near_terminal':
        common_limits={
            'output_per_person_growth': parameters.labor_productivity_growth,
            'wage_growth': parameters.labor_productivity_growth,
            'net_interest': parameters.discount+parameters.labor_productivity_growth,
        }
        ai_terminal=terminal_point(1.5,frontier,parameters)
        extra_limits={
            'output_per_person_growth': (
                ai_terminal.terminal_growth-parameters.population_growth),
            'wage_growth': parameters.labor_productivity_growth+(
                ai_terminal.net_interest_rate-parameters.discount
                -parameters.labor_productivity_growth)/ai_terminal.sigma_xl,
            'net_interest': ai_terminal.net_interest_rate,
        }
        figures=(
            (f'{prefix}_growth_returns',PANELS_NEAR_TERMINAL,'three',common_limits),
        )
        analytical_limits={
            'common_labor_bottleneck':common_limits,
            'sigma_1_50':extra_limits,
        }
    else:
        ai_limits=analytical_plot_limits(reference_sigma,frontier,parameters)
        figures=(
            (f'{prefix}_accumulation_growth',PANELS_QUANTITY_GROWTH,'three',ai_limits),
            (f'{prefix}_growth_returns',PANELS_PRICES_RETURNS,'three',ai_limits),
            (f'{prefix}_ai_distribution',PANELS_DISTRIBUTION,'four',ai_limits),
        )
        analytical_limits={key(reference_sigma):ai_limits}
    for filename,panels,layout,limits in figures:
        if layout=='three':
            fig,axis_array=plt.subplots(1,3,figsize=(7,3.15),sharex=True)
            axes=list(axis_array)
            bottom_axes=axes
        elif layout=='two':
            fig,axis_array=plt.subplots(1,2,figsize=(7,3.15),sharex=True)
            axes=list(axis_array)
            bottom_axes=axes
        elif layout=='four':
            fig,axis_array=plt.subplots(2,2,figsize=(7,4.80),sharex=True)
            axes=list(axis_array.ravel())
            bottom_axes=axes[2:]
        else:
            raise ValueError(f'Unknown layout: {layout}')
        for axis,(field,title,scale) in zip(axes,panels):
            for sigma in sigmas:
                series=data[sigma]
                values=np.array([r[field] for r in series])
                if not np.all(np.isfinite(values)):
                    raise ValueError(f'Invalid plotted values in {field}, sigma={sigma}.')
                color,linestyle=STYLES[sigma]
                axis.plot([r['time'] for r in series],values,color=color,linestyle=linestyle,
                          linewidth=1.5,label=fr'$\sigma={sigma:.2f}$')
            if limits is not None:
                axis.axhline(limits[field],color=LIMIT_STYLE[0],linestyle=LIMIT_STYLE[1],
                             linewidth=.9)
            if extra_limits is not None:
                axis.axhline(extra_limits[field],color=STYLES[1.5][0],
                             linestyle=LIMIT_STYLE[1],linewidth=.9)
            # An explicit title coordinate prevents Matplotlib from moving the
            # top-row titles into the shared legend when log-axis offset text
            # differs across panels.
            axis.set_title(title,loc='left',pad=7,y=1.02)
            if scale in ('rate','share'):
                decimals = (2 if design.name=='near_terminal' else
                            1 if scale=='rate' or field=='research_output_share' else 0)
                axis.yaxis.set_major_formatter(PercentFormatter(1,decimals=decimals))
                axis.yaxis.set_major_locator(MaxNLocator(5))
            if scale=='log_level':
                axis.set_yscale('log')
                axis.yaxis.set_major_formatter(FuncFormatter(lambda y,p:f'{y:g}'))
            if scale=='fraction':
                axis.set_ylim(0,1.02)
                axis.set_yticks([0,.5,1])
            if scale=='share':
                lower,upper=axis.get_ylim()
                axis.set_ylim(min(0,lower),upper)
            if design.name=='near_terminal':
                axis.set_ylim(*NEAR_TERMINAL_YLIMS[field])
                axis.set_yticks(np.linspace(*NEAR_TERMINAL_YLIMS[field],5))
            if field in ('output_effective_labor_growth','capital_effective_labor_growth',
                          'ai_services_effective_labor_growth'):
                axis.axhline(0,color='#999999',linewidth=.6,zorder=0)
            axis.set_xlim(0,data[1.][-1]['time'])
            tick_count=5 if data[1.][-1]['time'] >= 1000 else 6
            axis.set_xticks(np.linspace(0,data[1.][-1]['time'],tick_count))
            axis.xaxis.set_major_formatter(FuncFormatter(lambda x,p:f'{x:,.0f}'))
            axis.grid(axis='y',which='major',color='#dddddd',linewidth=.5)
            axis.spines[['top','right']].set_visible(False)
            axis.spines[['left','bottom']].set_color('#888888')
            axis.tick_params(length=3,color='#888888')
        if filename==f'{prefix}_accumulation_growth':
            comparable_axes=(axes[0],axes[2])
            common_lower=min(axis.get_ylim()[0] for axis in comparable_axes)
            common_upper=max(axis.get_ylim()[1] for axis in comparable_axes)
            for axis in comparable_axes:
                axis.set_ylim(common_lower,common_upper)
        for axis in bottom_axes:
            axis.set_xlabel('Years')
        handles,labels=axes[0].get_legend_handles_labels()
        fig.legend(handles,labels,ncol=len(sigmas),loc='upper center',frameon=False,
                   bbox_to_anchor=(.5,.995),handlelength=2.6,columnspacing=1.6)
        if layout=='three':
            fig.subplots_adjust(left=.095,right=.970,bottom=.18,top=.70,wspace=.48)
        elif layout=='four':
            fig.subplots_adjust(left=.105,right=.970,bottom=.11,top=.80,
                                wspace=.32,hspace=.58)
        else:
            fig.subplots_adjust(left=.095,right=.970,bottom=.18,top=.70,wspace=.34)
        fig.savefig(figdir/f'{filename}.pdf',metadata={'Title':filename})
        fig.savefig(figdir/f'{filename}.png',dpi=190)
        plt.close(fig)
    manifest=dict(design=design.name,
                  data_sha256=hashlib.sha256((output/'equilibrium_paths.csv').read_bytes()).hexdigest(),
                  sigmas=list(sigmas),horizon=data[1.][-1]['time'],
                  panels={'quantity_growth':[p[0] for p in PANELS_QUANTITY_GROWTH],
                          'prices_returns':[p[0] for p in PANELS_PRICES_RETURNS],
                          'distribution':[p[0] for p in PANELS_DISTRIBUTION],
                          'near_terminal':[p[0] for p in PANELS_NEAR_TERMINAL]},
                  analytical_limits=analytical_limits,
                  all_scenarios_admitted=True)
    (output/'figure_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(manifest,indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--design',choices=tuple(DESIGNS),default='main')
    arguments=parser.parse_args()
    render(DESIGNS[arguments.design])
