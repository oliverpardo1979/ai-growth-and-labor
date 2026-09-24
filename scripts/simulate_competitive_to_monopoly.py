"""Unexpected exclusive rights over existing AI and future improvements.

Run eight cases separately from the published RSI-activation simulations.
Before the event, AI efficiency is fixed by nonappropriability, not chi=0.
After the event the unchanged monopoly BVP chooses consumption and research.
"""
from dataclasses import asdict, replace
import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'.python-packages'), str(ROOT/'scripts')]
from competitive_ai_bgp import competitive_fixed_efficiency_bgp
from simulate_rewrite_illustrative_rsi import make_design as original_design
from simulate_rewrite_finite_frontier import (
    SIGMAS, key, run, load_solution, save_solution, design_initial_stocks,
    validate_solution_design)
from calibrate_rewrite_ai_price import finish, write_json


def make_design(chi):
    old = original_design(chi)
    name = f'competitive_to_monopoly_chi_{str(chi).replace(".", "_")}'
    return replace(old, name=name,
        output_directory=ROOT/'numerical_rewrite'/name,
        cache_directory=ROOT/'tmp'/f'rewrite_bvp_{name}',
        initial_capital_rule='competitive_fixed_efficiency_bgp',
        initial_stock_reference=(
            'Each sigma inherits its competitive fixed-B labor-bottleneck BGP stocks. '
            'Chi is positive and unchanged; pre-event M=0 reflects public access and '
            'nonappropriability. At date zero, an unexpected perpetual exclusive right '
            'covers existing technology and subsequent improvements. No old competitive '
            'suppliers remain. K and B are continuous; all controls are solved anew. '
            'Continued competition from identical stocks is the counterfactual.'))


def prepare(design):
    reference = {key(s): competitive_fixed_efficiency_bgp(
        s, design.initial_capability, design.parameters) for s in design.sigmas}
    path = design.output_directory/'scenario.json'
    specification = dict(design=design.name, parameters=asdict(design.parameters),
        frontier=design.frontier, initial_capability=design.initial_capability,
        initial_stock_reference=design.initial_stock_reference,
        initial_capital_by_sigma={k:v['capital'] for k,v in reference.items()})
    if path.exists():
        old = json.loads(path.read_text())
        if any(old.get(k) != v for k,v in specification.items()):
            raise ValueError('Existing experiment differs; do not overwrite it.')
    else:
        write_json(path, dict(specification, status='awaiting_equilibrium_checks'))
    write_json(design.output_directory/'competitive_reference.json', reference)
    return reference


def seed_from_original(design, sigma, seed_directory):
    """Re-solve with new stocks; the old spline is only a numerical initial guess."""
    from solve_axm_global_finite_cap_bvp import (
        _solve_stage, initial_raw_coordinates, GlobalContinuationStage)
    import numpy as np
    target = design.cache_directory/f'{key(sigma)}_base.npz'
    if target.exists():
        return
    source = seed_directory/f'{key(sigma)}_long.npz'
    sol = load_solution(source)
    if (asdict(sol.parameters) != asdict(design.parameters)
            or sol.terminal.frontier != design.frontier
            or sol.terminal.sigma_xl != sigma
            or sol.initial_capability != design.initial_capability):
        raise ValueError('Numerical seed has incompatible economic parameters.')
    k0, b0 = design_initial_stocks(design, sigma)
    targets = initial_raw_coordinates(sol.terminal, k0, b0)
    raw, boundary = _solve_stage(sol.raw, sol.horizon, sol.horizon, targets,
        sol.initial_effective_labor_scale, sol.terminal, sol.linearization, sol.parameters,
        nodes=601, tolerance=2e-6, boundary_tolerance=1e-9, maximum_nodes=40000)
    stage = GlobalContinuationStage(fraction=1., horizon=sol.horizon,
        initial_effective_labor_scale=sol.initial_effective_labor_scale,
        iterations=int(raw.niter), nodes=int(raw.x.size),
        maximum_rms_residual=float(np.max(raw.rms_residuals)), maximum_boundary_residual=boundary)
    candidate = replace(sol, raw=raw, initial_capital=k0, stages=(stage,))
    validate_solution_design(candidate, design, sigma)
    save_solution(candidate, target)
    write_json(design.output_directory/f'{key(sigma)}_seed_provenance.json',
        dict(source_design=f'rsi_chi_{str(design.parameters.chi).replace(".", "_")}',
             source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
             source_initial_capital=sol.initial_capital, target_initial_capital=k0,
             note='Re-solved at new stocks; no inherited consumption or shadow-price constraint.'))
    print(f'{design.name}/{key(sigma)}: new-stock BVP solved from original numerical seed', flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--chi', type=float, required=True, choices=(7.5,1.5))
    parser.add_argument('--sigma', type=float, choices=SIGMAS)
    parser.add_argument('--prepare-only', action='store_true')
    parser.add_argument('--finish', action='store_true')
    parser.add_argument('--seed-cache', type=Path)
    args = parser.parse_args()
    design = make_design(args.chi)
    reference = prepare(design)
    if args.prepare_only:
        print(json.dumps(reference, indent=2))
        return
    if args.finish:
        # This invokes the same full admission checks as the published experiments.
        finish(design, calibration_filename='scenario.json',
               calibration_validator=lambda sol: dict(chi_is_illustrative=True), render_figures=False)
        from report_competitive_to_monopoly import write_report
        write_report(design)
        return
    for sigma in ([args.sigma] if args.sigma is not None else SIGMAS):
        if args.seed_cache:
            seed_from_original(design, sigma, args.seed_cache)
        report = run(sigma, design)
        provenance = design.output_directory/f'{key(sigma)}_seed_provenance.json'
        if provenance.exists():
            report['settings']['base_initialization'] = 'original-experiment spline re-solved at competitive stocks'
            report['settings']['continuation_steps'] = 1
            write_json(design.output_directory/f'{key(sigma)}_audit.json',report)


if __name__ == '__main__':
    main()
