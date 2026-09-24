# Replication guide

Companion code for Oliver Pardo's [working paper](https://oliverpardo1979.github.io/ai-growth-and-labor/paper/the-future-of-growth-and-human-labor-under-recursive-ai-self-improvement.pdf),
*The Future of Growth and Human Labor Under Recursive AI Self-Improvement*.

## 1. Install

Clone or download this repository. From its root, using Python 3.12:

```sh
python -m venv .venv
```

Activate with `.venv\Scripts\Activate.ps1` in Windows PowerShell, or
`source .venv/bin/activate` on macOS/Linux. Then:

```sh
python -m pip install -r requirements-rewrite.txt
```

The environment pins NumPy, SciPy, and Matplotlib. No proprietary software,
external empirical dataset, or API key is required to solve these illustrative
experiments. Different platforms can produce small floating-point differences.

## 2. Check the published results without rerunning the solver

```sh
python scripts/reproduce_rewrite_results.py --check
```

This checks all eight saved admission reports, the initial BGP conditions,
the common parameters, and the hashes linking the reported data to the figures.
It is a check of stored evidence, not an independent new solution.

```sh
python -m unittest discover -s tests -v
```

The regression suite additionally checks the underlying equations, analytical
Jacobians, limiting regimes, and selected boundary-value solutions.

## 3. Solve the model again

```sh
python scripts/reproduce_rewrite_results.py --solve
```

This invokes the original solver for both research productivities and all four
elasticities. It recomputes or resumes BVP checkpoints, extends each horizon,
checks optimality and transversality diagnostics, and exports only complete
admitted comparisons. Full recomputation is substantially slower than checking
the committed outputs; duration depends on the machine and scenario.

For one case:

```sh
python scripts/simulate_rewrite_illustrative_rsi.py --chi 7.5 --sigma 1.0
```

For one complete comparison:

```sh
python scripts/simulate_rewrite_illustrative_rsi.py --chi 1.5
```

`--solve-only` prepares trajectories without final export. Once the four
checkpoint sets exist, `--chi 1.5 --finish` repeats the admission checks and
exports that comparison. Checkpoints are generated under `tmp/`, not shipped
in this repository. A fresh clone therefore starts without cached solutions.
Use a separate fresh clone if you want to recompute without replacing any
previous local outputs.

The solver does not mechanically continue from zero AI weight or zero research
productivity. It starts near each analytical long-run regime and moves the
initial stocks to the prescribed pre-RSI BGP. The jump variables are solved,
not fixed at their pre-event levels. See the paper's numerical appendix.

## 4. Data, audits, and figures

Each `numerical_rewrite/rsi_chi_*/` folder contains:

- `scenario.json` and `pre_rsi_reference.json`: parameters and initial stocks;
- `equilibrium_paths.csv`: plotted trajectories;
- `*_audit.json` and `*_support_*.json`: equation, refinement, and optimality checks;
- `activation_audit.json`: pre-RSI BGP and continuity checks;
- `annual_moments.json`: research expenditure outcomes and quadrature checks;
- `summary.json`, `paths_manifest.json`, and `figure_manifest.json`: summaries,
  plotting conventions, and data hashes.

Only research productivity differs between the two comparisons. The four
elasticities share the remaining parameters and AI efficiency at activation;
each inherits its own pre-RSI capital stock. Neither productivity is fitted to
a price-decline or expenditure target.

The original generation routines also create numerical digests and an accuracy
table. The manually edited discussion in the two simulation subsections is
separate from those digests. Reproduction does not rewrite that discussion.
Numerical admission is not an interval-arithmetic proof of existence.

## 5. Compile the paper

An additional, separate competitive-to-monopoly experiment is documented in
[`COMPETITIVE_TRANSITION.md`](COMPETITIVE_TRANSITION.md). It uses the same two
research productivities and four elasticities, but starts on a competitive
BGP and introduces exclusive AI rights. Its outputs do not replace the
published RSI-activation simulations.

Select **main_rewrite.tex** as the main document in Overleaf. Locally, either:

```sh
latexmk -pdf main_rewrite.tex
```

or, with Tectonic installed and an existing output directory:

```sh
tectonic --keep-logs --outdir output/pdf main_rewrite.tex
```

The GitHub workflow builds this manuscript and publishes its PDF at the stable
link above whenever the manuscript changes. It does not rerun the simulations
on every textual edit.
