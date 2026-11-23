"""Render the admitted welfare grid without solving or interpolating cell values."""
from collections import Counter
import csv
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap, Normalize
import numpy as np

from simulate_welfare_grid import OUT, SIGMAS, CHIS, build_report, cell_id
from report_rewrite_welfare import digest, read_json, write_json

FIGURES = ROOT / 'figures_rewrite/welfare_grid'


def grid_values(report):
    """Reject partial grids and duplicate cells. No missing cell becomes zero."""
    expected = {(s,c) for s in SIGMAS for c in CHIS}
    pairs = [(c['sigma'],c['chi']) for c in report['cases']]
    if set(pairs) != expected or len(pairs) != len(expected):
        raise ValueError('The heatmap requires every distinct approved combination.')
    if not all(c['numerically_verified'] for c in report['cases']):
        raise ValueError('An unresolved equilibrium cannot be colored as a welfare result.')
    lookup = {(c['sigma'],c['chi']):c for c in report['cases']}
    values = np.array([[100 * lookup[(s,c)]['stages']['long']['consumption_equivalent']
                        for s in SIGMAS] for c in CHIS])
    if not np.all(np.isfinite(values)) or not np.all(values > -100):
        raise ValueError('Invalid consumption-equivalent values.')
    if not np.allclose(values, report['welfare_percent'], atol=1e-12, rtol=0):
        raise ValueError('The report matrix and individual welfare cases differ.')
    return values


def cell_label(value):
    return f'{value:+.1f}'


def edges(centers):
    centers = np.asarray(centers,dtype=float)
    mids = (centers[:-1]+centers[1:])/2
    return np.r_[centers[0]-(mids[0]-centers[0]),mids,centers[-1]+(centers[-1]-mids[-1])]


def render(report):
    values = grid_values(report)
    FIGURES.mkdir(parents=True,exist_ok=True)
    low = 10 * math.floor(float(values.min())/10)
    high = 10 * math.ceil(float(values.max())/10)
    if not low < 0 < high:
        raise ValueError('The signed palette requires a range on both sides of zero.')
    # The colorbar is linear in welfare percentages. White is exactly zero,
    # even when the observed negative and positive ranges are asymmetric.
    zero = -low/(high-low)
    cmap = LinearSegmentedColormap.from_list('welfare',
        [(0.,'#2166ac'),(zero,'#faf9f6'),(1.,'#b2182b')],N=1024)
    norm = Normalize(vmin=low,vmax=high)
    plt.rcParams.update({'font.family':'serif','mathtext.fontset':'cm',
                         'font.size':11,'axes.labelsize':12,'pdf.fonttype':42})
    fig,ax = plt.subplots(figsize=(7.4,4.55))
    mesh = ax.pcolormesh(edges(SIGMAS),edges(CHIS),values,cmap=cmap,norm=norm,
                         edgecolors='white',linewidth=.8,shading='flat',rasterized=False)
    zero_line = ax.contour(SIGMAS,CHIS,values,levels=[0.],colors='#222222',
                           linewidths=1.2,linestyles='--')
    cells = []
    for row,chi in enumerate(CHIS):
        for column,sigma in enumerate(SIGMAS):
            value = float(values[row,column])
            rgb = cmap(norm(value))[:3]
            luminance = .2126*rgb[0]+.7152*rgb[1]+.0722*rgb[2]
            color = 'white' if luminance < .53 else '#171717'
            label = cell_label(value)
            ax.text(sigma,chi,label,ha='center',va='center',color=color,
                    fontsize=10.5,zorder=4,
                    bbox=dict(boxstyle='square,pad=0.15',facecolor=cmap(norm(value)),
                              edgecolor='none',linewidth=0))
            cells.append(dict(id=cell_id(sigma,chi),sigma=sigma,chi=chi,
                              welfare_percent=value,label=label))
    ax.set_xticks(SIGMAS,[f'{s:.1f}' for s in SIGMAS])
    ax.set_yticks(CHIS,[f'{c:g}' for c in CHIS])
    ax.set_xlabel(r'Elasticity of substitution, $\sigma$')
    ax.set_ylabel(r'Research productivity, $\chi$')
    colorbar = fig.colorbar(mesh,ax=ax,pad=.035,fraction=.048)
    colorbar.set_label(r'Consumption equivalent, $\lambda$ (%)',labelpad=9)
    colorbar.ax.tick_params(labelsize=9.5)
    fig.tight_layout(pad=1.1)
    pdf,png = FIGURES/'welfare_heatmap.pdf',FIGURES/'welfare_heatmap.png'
    fig.savefig(pdf,bbox_inches='tight')
    fig.savefig(png,dpi=220,bbox_inches='tight')
    plt.close(fig)
    csv_path = OUT/'heatmap_cells.csv'
    with csv_path.open('w',newline='',encoding='utf-8') as stream:
        writer = csv.DictWriter(stream,fieldnames=list(cells[0]),lineterminator='\n')
        writer.writeheader()
        writer.writerows(cells)
    lines = [segment.tolist() for segment in zero_line.allsegs[0] if len(segment)>1]
    write_json(FIGURES/'welfare_heatmap_manifest.json',dict(
        source_json=(OUT/'grid_results.json').relative_to(ROOT).as_posix(),
        source_sha256=digest(OUT/'grid_results.json'),
        cells_csv=csv_path.relative_to(ROOT).as_posix(),cells_csv_sha256=digest(csv_path),
        cell_values='Computed from admitted consumption paths, not interpolated.',
        zero_contour='Piecewise-linear interpolation of the zero level between computed grid points, not an equilibrium solved on the boundary.',
        zero_contour_segments=lines,normalization='Linear in percentage consumption equivalent; zero is white.',
        color_minimum=low,color_maximum=high,display_precision=1,cells=cells,
        pdf_sha256=digest(pdf),png_sha256=digest(png)))
    write_json(OUT/'figure_environment.json',dict(matplotlib=matplotlib.__version__,
        backend=matplotlib.get_backend(),font_family='serif',mathtext_fontset='cm',
        cell_values='One decimal in percentage consumption-equivalent units'))
    # The vector PDF is a separate displayed artifact, checked numerically too.
    import fitz
    import re
    document = fitz.open(pdf)
    text = '\n'.join(p.get_text() for p in document).replace('\u2212','-')
    shown = re.findall(r'[+-]\d+\.\d',text)
    if Counter(shown) != Counter(c['label'] for c in cells):
        raise ValueError('The labels printed in the PDF differ from the data.')
    print(json.dumps(dict(pdf=pdf.relative_to(ROOT).as_posix(),cells=len(cells),
                          minimum_percent=float(values.min()),maximum_percent=float(values.max()),
                          zero_contour_segments=len(lines),printed_pdf_labels_verified=True),indent=2))


def main():
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check',action='store_true')
    parser.add_argument('--audit',action='store_true')
    args = parser.parse_args()
    report = build_report()
    if read_json(OUT/'grid_results.json') != report:
        raise ValueError('Reproduce the welfare grid report before rendering.')
    if args.check or args.audit:
        values = grid_values(report)
        manifest = read_json(FIGURES/'welfare_heatmap_manifest.json')
        if manifest['source_sha256'] != digest(OUT/'grid_results.json'):
            raise ValueError('The heatmap is from a different grid report.')
        for suffix in ('pdf','png'):
            if manifest[f'{suffix}_sha256'] != digest(FIGURES/f'welfare_heatmap.{suffix}'):
                raise ValueError('A figure changed since validation.')
        if manifest['cells_csv_sha256'] != digest(OUT/'heatmap_cells.csv'):
            raise ValueError('The displayed cell data changed.')
        for index,cell in enumerate(manifest['cells']):
            row = CHIS.index(cell['chi'])
            column = SIGMAS.index(cell['sigma'])
            if cell['welfare_percent'] != float(values[row,column]) or cell['label'] != cell_label(values[row,column]):
                raise ValueError('The displayed value differs from its underlying welfare calculation.')
        print('Verified all 35 displayed heatmap values and figure hashes.')
    else:
        render(report)
    if args.audit:
        audit_displays(report)
        write_diagnostics(report)


def write_diagnostics(report):
    values=grid_values(report)
    cases=report['cases']
    audits=[]
    for case in cases:
        audits.append(read_json(ROOT/next(name for name in case['source_sha256'] if name.endswith('_audit.json'))))
    methods=Counter(a['optimality_method'] for a in audits)
    min_case=min(cases,key=lambda c:c['stages']['long']['consumption_equivalent'])
    max_case=max(cases,key=lambda c:c['stages']['long']['consumption_equivalent'])
    max_refinement=100*max(c['checks']['refined_to_long_ce_change'] for c in cases)
    max_cutoff=100*max(abs(c['horizon_checks']['500']['ce_change_from_full_solution']) for c in cases)
    lines=['# Quantitative diagnostics for the welfare grid','',
        f'All {report["admitted"]} of {report["attempted"]} approved parameter combinations are admitted. Eight original paths are reused and 27 additional pairs are solved. No cell is dropped or filled by interpolation.','',
        f'The consumption equivalent ranges from {100*min_case["stages"]["long"]["consumption_equivalent"]:.9f}% at sigma={min_case["sigma"]}, chi={min_case["chi"]} to {100*max_case["stages"]["long"]["consumption_equivalent"]:.9f}% at sigma={max_case["sigma"]}, chi={max_case["chi"]}. Competition is preferred in {int((values<0).sum())} cells and monopoly in {int((values>0).sum())}.','',
        '## Parameter inventory and scope','',
        'Sigma takes the seven approved values 0.9 through 1.5 in steps of 0.1. Chi takes 1.5, 3.0, 4.5, 6.0 and 7.5. These are illustrative choices, not estimated parameters or a literature-based confidence region. No empirical fit or non-targeted data moment is claimed.','',
        'All other parameters are inherited without refitting. Their values are '+json.dumps(report['fixed_parameters'],sort_keys=True)+'.',
        f'The fixed efficiency bound is {report["frontier"]:.15g} and initial AI efficiency is {report["initial_capability"]:.15g}. The bound was originally selected as 1.10 times the monopoly threshold at sigma=1.5, not fitted to welfare.','',
        'Initial capital is derived from the competitive fixed-efficiency BGP at each sigma. At a given sigma the same stocks are used across all five chi values and both market structures. Capital differs across sigma. CES weights and efficiency units are unchanged, not re-normalized across elasticities. The map ranks market structures within each technology, not absolute utility across technologies.','',
        '## Numerical and optimality checks','',
        'The new driver reuses the original equilibrium equations and admission functions. Base, refined and extended checkpoints retain tolerances 2e-6, 1e-8 and 1e-9 and two 500-year horizon extensions. Independent finite differences check dynamics and both first-order conditions over the full horizon and densely in years 0--10. Terminal-state, feasibility and transversality diagnostics are retained.','',
        'The original developer-optimality diagnostic methods recorded across the 35 audits are '+json.dumps(dict(methods),sort_keys=True)+'. Cases requiring Hamiltonian support retain the two original support grids and the analytical continuation check. This is an alternative sufficient optimality test, not an acceptance of first-order conditions alone.','',
        f'Maximum recorded equation residual: {max(a["audit"]["maximum_equation_residual"] for a in audits):.6g}. Maximum terminal-coordinate discrepancy: {max(a["maximum_terminal_coordinate_gap"] for a in audits):.6g}.','',
        f'Welfare is computed from the original scalar log-consumption splines. Maximum final refinement effect is {max_refinement:.6g} percentage point. Maximum effect of replacing the path after year 500 with its limiting-growth continuation is {max_cutoff:.6g} percentage point. The final-horizon tail is included explicitly.','',
        f'Maximum difference between independent quadrature routines is {max(c["checks"]["independent_quad_difference"] for c in cases):.6g} utility units per initial person. All original welfare integration thresholds are retained. Source hashes link each extract to its admitted checkpoint and recorded scenario.','',
        '## Coverage and limits','',
        'This is the approved two-dimensional illustrative grid. Rho, preferences, the efficiency bound, initial efficiency, production nesting, market closure and the initial-state rule are not varied. It is not a general robustness result over those assumptions. The dashed zero contour is linearly interpolated between solved grid points. It does not certify an exactly solved indifference frontier or extrapolate outside the grid.','',
        'Parameter estimation, bootstrap uncertainty, Bayesian identification and empirical out-of-sample fit are NOT_APPLICABLE. No additive causal mechanism decomposition or planner comparison is claimed. A representative-household welfare comparison is not a distributional welfare result for workers and owners separately.','',
        '## Reproduction','',
        'Run `python scripts/simulate_welfare_grid.py --check`, `python scripts/report_welfare_grid.py --check` and `python scripts/report_welfare_grid.py --audit`. Solving new grid cells uses `python scripts/simulate_welfare_grid.py --solve --workers 2` after the original competition-to-monopoly checkpoints are available. New files never replace the original simulation files. The environment is recorded alongside the outputs.','',
        'Confidence High in the admitted numerical calculations at these specified parameter pairs. No empirical forecasting claim is made.','']
    (OUT/'quantitative-model-diagnostics-REPORT.md').write_text('\n'.join(lines),encoding='utf-8',newline='\n')


def audit_displays(report):
    """Scope: 35 heatmap cells and their eight overlaps with Table 4."""
    import subprocess
    manifest=read_json(FIGURES/'welfare_heatmap_manifest.json')
    lookup={(c['sigma'],c['chi']):c for c in report['cases']}
    table={}
    experiment=None
    sigma=None
    for line in (ROOT/'sections_rewrite/welfare_table.tex').read_text(encoding='utf-8').splitlines():
        fields=[field.strip() for field in line.split('&')]
        if len(fields)!=6 or fields[2] not in ('7.5','1.5'):
            continue
        if fields[0]:
            experiment=fields[0]
        if fields[1]:
            sigma=float(fields[1])
        if experiment=='A':
            shown=float(fields[-1].split('\\%')[0])
            table[(sigma,float(fields[2]))]=shown
    claims=[]
    failures=[]
    for cell in manifest['cells']:
        case=lookup[(cell['sigma'],cell['chi'])]
        computed=100*case['stages']['long']['consumption_equivalent']
        reported=float(cell['label'])
        vertical=abs(reported-computed)<.1
        horizontal=cell['label']==cell_label(computed)
        table_value=table.get((cell['sigma'],cell['chi']))
        if table_value is not None:
            horizontal=horizontal and table_value==reported
        claim=dict(claim_id=cell['id'],location='Figure fig:rewrite-welfare-grid',
            kind='percentage',sigma=cell['sigma'],chi=cell['chi'],reported_value=reported,
            computed_value=computed,absolute_difference=abs(reported-computed),
            tolerance_percentage_points=.1,source='scripts.simulate_welfare_grid.calculate_cell(sigma,chi)',
            source_field='stages.long.consumption_equivalent * 100',
            displays=['figure vector PDF','figure PNG','heatmap_cells.csv']+(['Table 4'] if table_value is not None else []),
            vertical='PASS' if vertical else 'FAIL',horizontal='PASS' if horizontal else 'FAIL')
        claims.append(claim)
        if not vertical or not horizontal:
            failures.append(cell['id'])
    if len(table)!=8 or len(claims)!=35:
        raise ValueError('The figure or table audit is incomplete.')
    revision=subprocess.check_output(['git','rev-parse','--short','HEAD'],cwd=ROOT,text=True).strip()
    dirty=subprocess.check_output(['git','status','--porcelain','--','.',':(exclude)quality_reports'],
                                  cwd=ROOT,text=True).strip()
    if dirty:
        revision+='-dirty'
    quality=ROOT/'quality_reports'
    quality.mkdir(exist_ok=True)
    write_json(quality/'reproducibility_claims_welfare_grid.json',dict(
        date='2026-11-23',revision=revision,scope='35 heatmap percentages and eight overlapping table entries',claims=claims))
    lines=['# Reproducibility audit of the welfare grid','',
           'Date: 2026-11-23. Revision: '+revision+'.','',
           'Scope is the new heatmap, its source data, and its eight overlaps with Table 4. This is not an audit of every numeric claim in the manuscript.','',
           f'Vertical comparisons: {sum(c["vertical"]=="PASS" for c in claims)}/35 PASS. Horizontal comparisons: {sum(c["horizontal"]=="PASS" for c in claims)}/35 PASS, including all eight table overlaps. No unmatched or explained discrepancies.','',
           'Percentages use the replication protocol tolerance of 0.1 percentage point. The displayed values agree exactly after rounding to one decimal. All 35 printed signed labels are also extracted from the vector PDF and checked against the source labels. Both image formats are saved from the same checked figure.','',
           'The existing eight baselines were recomputed from their committed consumption splines before extending the grid. Their unrounded values and provenance are unchanged. Mtime alone is not treated as staleness because those older baselines are intentionally reused and their input hashes are checked.','',
           'Environment is recorded in numerical_rewrite/welfare_grid/environment.json. No empirical estimate, standard error or p-value is part of this calculation.','',
           '| Sigma | Chi | Displayed (%) | Computed (%) | Difference (pp) | Vertical | Horizontal |',
           '|---|---|---|---|---|---|---|']
    for c in claims:
        lines.append(f'| {c["sigma"]:g} | {c["chi"]:g} | {c["reported_value"]:+.1f} | {c["computed_value"]:+.9f} | {c["absolute_difference"]:.9f} | {c["vertical"]} | {c["horizontal"]} |')
    lines+=['','Recompute with `python scripts/report_welfare_grid.py --audit`. Each computed value is obtained through `simulate_welfare_grid.calculate_cell(sigma, chi)["stages"]["long"]["consumption_equivalent"] * 100`, including independent integration and the final-horizon tail.','',
            'Overall verdict: '+('FAIL' if failures else 'PASS')+'.','']
    (quality/'reproducibility_audit_welfare_grid.md').write_text('\n'.join(lines),encoding='utf-8',newline='\n')
    log=quality/'replication-log.md'
    if not log.exists():
        log.write_text('# Replication log\n\nAppend-only record of scoped numerical reproducibility checks.\n\n',encoding='utf-8',newline='\n')
    with log.open('a',encoding='utf-8',newline='\n') as stream:
        stream.write('## 2026-11-23 — welfare heatmap @ '+revision+'\n\n')
        stream.write('Outputs: numerical_rewrite/welfare_grid. Scope: 35 figure cells and eight overlapping table entries. Verdict: '+('FAIL' if failures else 'PASS')+'.\n\n')
        stream.write('| Claim | Reported (%) | Computed (%) | How computed | Tolerance | Verdict |\n|---|---|---|---|---|---|\n')
        for c in claims:
            stream.write(f'| {c["claim_id"]} | {c["reported_value"]:+.1f} | {c["computed_value"]:+.9f} | `simulate_welfare_grid.calculate_cell({c["sigma"]}, {c["chi"]})["stages"]["long"]["consumption_equivalent"] * 100` | 0.1 pp, exact display rounding | {c["vertical"]}/{c["horizontal"]} |\n')
        stream.write('\n')
    if failures:
        raise ValueError(f'Reproducibility failures: {failures}')
    print('Scoped reproducibility audit PASS: 35 figure percentages and eight table overlaps.')


if __name__=='__main__':
    main()
