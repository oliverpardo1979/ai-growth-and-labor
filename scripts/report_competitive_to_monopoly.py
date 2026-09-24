"""Paper-style figures, with an explicit continued-competition counterfactual.

No growth rate is computed across the date-zero discontinuity. Level jumps
and subsequent continuous-time growth are separate objects. Only export
paths that have passed the manuscript's unchanged numerical admission gates.
"""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'.python-packages'), str(ROOT/'scripts')]
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.lines import Line2D
from matplotlib.ticker import PercentFormatter, MaxNLocator, FuncFormatter, LogLocator, NullLocator, FixedLocator
from calibrate_rewrite_ai_price import write_json
from plot_rewrite_equilibria import (
    STYLES, PANELS_QUANTITY_GROWTH, PANELS_PRICES_RETURNS, PANELS_DISTRIBUTION,
    analytical_plot_limits)
from simulate_competitive_to_monopoly import make_design, SIGMAS, key

FIGDIR = ROOT/'figures_rewrite'/'competitive_to_monopoly'
PDF = ROOT/'output'/'pdf'/'competitive_to_monopoly_simulations.pdf'
LEVEL_PANELS = (
    ('output_counterfactual_ratio', 'A. Output\nper worker', 'ratio'),
    ('wage_counterfactual_ratio', 'B. Wage', 'ratio'),
    ('consumption_counterfactual_ratio', 'C. Consumption\nper person', 'ratio'))
LEVEL_WINDOWS = ((-2., 10.), (10., 100.), (10., 500.))
DETAIL_WINDOWS = ((-2., 10.), (10., 500.))


def read_json(path):
    return json.loads(path.read_text(encoding='utf-8'))


def checked_data(design):
    folder = design.output_directory
    path = folder/'equilibrium_paths.csv'
    manifest = read_json(folder/'paths_manifest.json')
    if manifest['csv_sha256'] != hashlib.sha256(path.read_bytes()).hexdigest():
        raise ValueError('Data changed after the equilibrium audit.')
    for sigma in SIGMAS:
        report = read_json(folder/f'{key(sigma)}_audit.json')
        if not report['equilibrium_certified']:
            raise ValueError('Cannot plot an incomplete or unadmitted comparison.')
        if manifest['checkpoint_sha256'][key(sigma)] != report['checkpoint_sha256']:
            raise ValueError('CSV and audit refer to different solutions.')
    with path.open(newline='', encoding='utf-8') as stream:
        rows = [{k:float(v) for k,v in row.items()} for row in csv.DictReader(stream)]
    return rows, read_json(folder/'competitive_reference.json')


def baseline(v, p):
    """Normalized competitive BGP, constant at all dates in these units."""
    return dict(v, output_effective_labor=v['output'],
        consumption_effective_labor=v['consumption'], capital_effective_labor=v['capital'],
        wage_productivity=v['wage'], net_interest=v['interest_rate'],
        output_effective_labor_growth=0., ai_services_effective_labor_growth=0.,
        capital_effective_labor_growth=0., consumption_effective_labor_growth=0.,
        output_per_person_growth=p.labor_productivity_growth, wage_growth=p.labor_productivity_growth,
        capability_frontier_ratio=.01, output_counterfactual_ratio=1.,
        wage_counterfactual_ratio=1., consumption_counterfactual_ratio=1.)


def first_upcrossing(series, field):
    """First recovery to competitive level on the displayed mesh, not a welfare test."""
    for left,right in zip(series, series[1:]):
        if left[field] < 1 <= right[field]:
            return left['time']+(right['time']-left['time'])*(1-left[field])/(right[field]-left[field])
    return None


def write_report(design):
    rows, pre = checked_data(design)
    reference = {s:baseline(pre[key(s)],design.parameters) for s in SIGMAS}
    for row in rows:
        b = reference[row['sigma']]
        row['output_counterfactual_ratio'] = row['output_effective_labor']/b['output']
        row['consumption_counterfactual_ratio'] = row['consumption_effective_labor']/b['consumption']
        row['wage_counterfactual_ratio'] = row['wage_productivity']/b['wage']
        row['capital_counterfactual_ratio'] = row['capital_effective_labor']/b['capital']
        row['price_counterfactual_ratio'] = row['ai_service_price']/b['ai_service_price']
    summary = {}
    jumps = {}
    for sigma in SIGMAS:
        series = [r for r in rows if r['sigma']==sigma]
        initial=series[0]
        b=reference[sigma]
        # The numerical solver imposes only K0 and B0 at the policy change.
        if (abs(initial['capital_counterfactual_ratio']-1)>1e-9
                or abs(initial['capability_frontier_ratio']-.01)>1e-10):
            raise ValueError('Predetermined stocks jump at the policy change.')
        jump=dict(output=initial['output_counterfactual_ratio']-1,
            wage=initial['wage_counterfactual_ratio']-1,
            consumption=initial['consumption_counterfactual_ratio']-1,
            ai_service_price=initial['price_counterfactual_ratio']-1,
            ai_services=(initial['inference_output_share']*initial['output_effective_labor']
                         /b['inference_compute']-1),
            interest_rate_pp=100*(initial['net_interest']-b['interest_rate']),
            initial_capital_output_ratio=initial['capital_effective_labor']/initial['output_effective_labor'],
            initial_research_output_share=initial['research_output_share'])
        if not (jump['output']<0 and jump['wage']<0 and jump['ai_service_price']>0):
            raise ValueError('Unexpected static event direction; inspect before plotting.')
        jumps[key(sigma)]=jump
        summary[key(sigma)]=dict(
            observations={str(t):min(series,key=lambda r:abs(r['time']-t)) for t in (0,1,10,50,100,250,500)},
            first_recovery_year={f:first_upcrossing(series,f) for f in
                ('output_counterfactual_ratio','wage_counterfactual_ratio','consumption_counterfactual_ratio')},
            analytical_monopoly_limits=analytical_plot_limits(sigma,design.frontier,design.parameters))
    write_json(design.output_directory/'policy_event.json',dict(
        description=design.initial_stock_reference, stock_continuity_passes=True,
        jumps=jumps, interpretation='Level changes, not instantaneous growth rates.'))
    write_json(design.output_directory/'comparison_summary.json',summary)
    for filename, content in (
        ('comparison_paths.csv',[{k:v for k,v in row.items() if k in ('sigma','time')
                                 or k.endswith('_counterfactual_ratio')} for row in rows]),
        ('continued_competition.csv',[dict(sigma=s,time=t,**{k:v for k,v in reference[s].items()
           if k not in ('sigma','pre_event_research_available')})
           for s in SIGMAS for t in (-2.,0.,design.display_horizon)])):
        with (design.output_directory/filename).open('w',newline='',encoding='utf-8') as stream:
            writer=csv.DictWriter(stream,fieldnames=list(content[0]))
            writer.writeheader(); writer.writerows(content)
    return rows,reference


def figure(design, rows, references, panels, title, levels=False):
    n=len(panels)
    windows=LEVEL_WINDOWS if levels else DETAIL_WINDOWS
    # Distribution follows the paper's A/B, C/D arrangement in each time window.
    fig,axes=plt.subplots(len(windows) if n==3 else 2*len(windows),3 if n==3 else 2,
                         figsize=(8.6,9.0 if levels else (6.6 if n==3 else 9.2)))
    axes=np.asarray(axes).reshape(len(windows),n)
    limits=analytical_plot_limits(1.5,design.frontier,design.parameters)
    for view,(start,end) in enumerate(windows):
        for axis,(field,label,scale) in zip(axes[view],panels):
            for sigma in SIGMAS:
                color,style=STYLES[sigma]
                series=[r for r in rows if r['sigma']==sigma and start<=r['time']<=end]
                vals=np.array([r[field] for r in series])
                if not np.all(np.isfinite(vals)):
                    raise ValueError('Nonfinite plotted observations.')
                axis.plot([r['time'] for r in series],vals,color=color,ls=style,lw=1.5)
                ref=references[sigma][field]
                if view==0:
                    axis.plot([-2,0],[ref,ref],color=color,ls=style,lw=1.2)
                    axis.plot(0,ref,marker='o',mfc='white',mec=color,ms=3)
                    axis.plot(0,vals[0],marker='o',color=color,ms=3)
                if not levels and len({references[s][field] for s in SIGMAS})>1:
                    axis.hlines(ref,max(0,start),end,color=color,ls=':',lw=.7,alpha=.65)
            if levels:
                axis.axhline(1,color='#999999',lw=.8)
            elif len({references[s][field] for s in SIGMAS})==1:
                axis.axhline(references[1.][field],color='#999999',lw=.8)
            if view==len(windows)-1 and not levels:
                axis.axhline(limits[field],color='#222222',ls=(0,(1,2)),lw=.9)
            axis.set_title(label,loc='left',pad=8,fontsize=11)
            if levels and view>0:
                axis.set_yscale('log')
                lo,hi=axis.get_ylim()
                if hi/lo<10:
                    ticks=[v for v in (.5,.75,1.,1.5,2.,3.,5.,10.) if lo<=v<=hi]
                    axis.yaxis.set_major_locator(FixedLocator(ticks))
                else:
                    axis.yaxis.set_major_locator(LogLocator(base=10,numticks=5))
                axis.yaxis.set_minor_locator(NullLocator())
                axis.yaxis.set_major_formatter(FuncFormatter(lambda v,pos:
                    fr'$10^{{{int(round(np.log10(v)))}}}\times$' if v>=10000
                    else fr'${v:g}\times$'))
            elif scale in ('rate','share','ratio'):
                axis.yaxis.set_major_formatter(PercentFormatter(1,decimals=1))
                axis.yaxis.set_major_locator(MaxNLocator(4))
            elif scale=='log_level':
                axis.set_yscale('log')
                axis.yaxis.set_major_formatter(FuncFormatter(lambda v,pos:f'{v:g}'))
            # Never let a distant analytical limit flatten the short-run A/C panels.
            axis.set_xlim(start,end)
            axis.set_xticks([-2,0,5,10] if view==0 else
                           ([10,25,50,75,100] if end==100 else [10,100,250,500]))
            axis.set_xlabel('Years: initial transition' if view==0 else
                            ('Years: intermediate window' if end==100 else 'Years: longer window'))
            if view==0:
                axis.axvline(0,color='#999999',ls=':',lw=.7)
            axis.grid(axis='y',color='#dddddd',lw=.5)
            axis.spines[['top','right']].set_visible(False)
            axis.spines[['left','bottom']].set_color('#999999')
    handles=[Line2D([],[],color=STYLES[s][0],ls=STYLES[s][1],lw=1.5,label=fr'$\sigma={s:g}$') for s in SIGMAS]
    fig.suptitle(fr'{title} | $\chi={design.parameters.chi:g}$',fontsize=14,y=.99)
    fig.legend(handles=handles,loc='upper center',bbox_to_anchor=(.5,.948),ncol=4,frameon=False)
    note=('Top: 100.0% = continued competition. Middle/bottom: multiples (log scale); 1x = competition.' if levels else
          'Thin lines: continued competition. Black dotted long-run line: monopoly limit for sigma = 1.5.')
    note+='\nOpen/filled dots: before/after exclusive rights. Growth rates exclude the date-zero level jumps.'
    fig.text(.08,.018,note,fontsize=8,color='#444444',va='bottom')
    fig.subplots_adjust(left=.10,right=.97,top=.855 if levels else (.83 if n==3 else .87),
                        bottom=.105 if levels else (.13 if n==3 else .12),
                        wspace=.48 if n==3 else .33,hspace=.95 if levels else .90)
    return fig


def render_all():
    FIGDIR.mkdir(parents=True,exist_ok=True)
    PDF.parent.mkdir(parents=True,exist_ok=True)
    plt.rcParams.update({'font.family':'DejaVu Serif','font.size':10,'pdf.fonttype':42})
    # Validate both sets before creating the final combined artifact.
    datasets=[(make_design(chi),*write_report(make_design(chi))) for chi in (7.5,1.5)]
    outputs=[]
    individual_pdfs=[]
    with PdfPages(PDF, metadata={'Title':'From competitive AI to monopoly: eight equilibrium simulations'}) as pdf:
        for d,rows,refs in datasets:
            for name,panels,title in (
                ('levels',LEVEL_PANELS,'Levels relative to continued competition'),
                ('accumulation_growth',PANELS_QUANTITY_GROWTH,'Output, AI services, and capital growth'),
                ('growth_returns',PANELS_PRICES_RETURNS,'Wages, interest rates, and AI prices'),
                ('distribution',PANELS_DISTRIBUTION,'Income and compute expenditure shares')):
                fig=figure(d,rows,refs,panels,title,levels=name=='levels')
                png=FIGDIR/f'{d.name}_{name}.png'
                fig.savefig(png,dpi=165)
                individual_pdf=png.with_suffix('.pdf')
                fig.savefig(individual_pdf,metadata={'Title':f'{title} | chi={d.parameters.chi:g}'})
                pdf.savefig(fig)
                plt.close(fig)
                outputs.append(str(png.relative_to(ROOT)))
                individual_pdfs.append(str(individual_pdf.relative_to(ROOT)))
    write_json(FIGDIR/'manifest.json',dict(pdf=str(PDF.relative_to(ROOT)), figures=outputs,
        individual_pdfs=individual_pdfs,
        source_sha256={d.name:hashlib.sha256((d.output_directory/'comparison_paths.csv').read_bytes()).hexdigest()
                       for d,_,_ in datasets},
        percent_decimals=1, short_window=[-2,10], long_window=[10,500],
        levels_windows=LEVEL_WINDOWS, detail_windows=DETAIL_WINDOWS,
        levels_scales=['linear_percent','log_multiple','log_multiple'],
        note='Separate pre/post-event segments; no finite growth rate assigned to a discrete level jump.'))
    print(PDF,flush=True)


if __name__=='__main__':
    render_all()
