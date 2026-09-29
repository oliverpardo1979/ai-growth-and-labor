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

### Numerical implementation and tolerances

The following details complement the compact numerical appendix in the
paper. They document the existing calculations; no simulation settings
were changed when the appendix was shortened.

For each RSI-activation configuration, the solver starts near the analytical
limiting point and moves the initial stocks to the prescribed values in 32
continuation stages. These stages are numerical problems, not dates on the
economic trajectory. At unit elasticity the static block uses its exact
Cobb-Douglas limit. Near one, `log1p` and `expm1` reduce cancellation errors.
Under complementarity, marginal revenue is evaluated directly and the static
root is polished when necessary near zero marginal revenue; the first-order
condition is unchanged.

Each computational horizon is extended twice by 500 years. The collocation
tolerances are `2e-6`, `1e-8`, and `1e-9`, with initial meshes of 221, 401,
and 601 points that adapt as needed; the final boundary tolerance is `1e-11`.
Final mesh sizes are retained in each admission report's `audit.nodes` field.
The displayed window is inside the solved horizon, without extrapolation.
Figure windows select dates from the stored paths; they do not alter the
economy or the solution horizon.

The independent checks reconstruct the original equations with five-point
differences at 1,001 dates, using steps of 0.003 and 0.001 years. An additional
801-date check over the first ten years uses steps of 0.0003 and 0.0001 years.
Acceptance requires dynamic residuals below `1e-6`, first-order residuals
below `1e-9`, final-horizon changes below `2e-5` in detrended logarithmic
coordinates, and terminal-coordinate gaps below `1e-4`.

The saved audits include additional checks in the original
logarithmic-efficiency coordinate `R_B = -Bbar * log(1 - B/Bbar)`.
When the concavity diagnostic fails, the Hamiltonian-support checks use grids with
81 dates and 101 alternative states, then 321 dates and 241 alternative
states, supplemented by dense first-decade checks when needed. At each date,
the test holds capital, effective labor, and the transformed shadow price
fixed while varying counterfactual AI efficiency. Counterfactual-state
minimization and the analytical continuation bound implemented in
`scripts/audit_rewrite_equilibria.py` supplement these grids.
These diagnostics and the recorded admission procedure are retained for
reproducibility. The current manuscript establishes sufficient conditions
for developer optimality using
`eta * (1 - B0/Bbar) <= min(alpha, 1/sigma)`, which holds for all the
illustrative RSI and competitive-to-monopoly configurations.
The asymptotic decay rate of both transversality expressions is `n - rho < 0`.

The activation audit checks the pre-event Euler, resource, and monopoly
conditions, continuity of production quantities and prices, and the jumps
in consumption and research. On the pre-event BGP, capital, output,
consumption, inference compute, and AI services grow at `n + gamma`, wages
grow at `gamma`, and efficiency, prices, the interest rate, and income shares
are constant. The inequality `rho > n` ensures finite pre-event developer
value and decay of the household transversality expression. Checkpoint and
CSV hashes link the audit reports to the plotted data. A comparison is
exported only after all four elasticities pass its equilibrium and
activation-continuity checks.

### Annual research-expenditure outcomes

The stored first-year research expenditure ratio is
`integral_0^1 M(t) dt / integral_0^1 Y(t) dt`, not the impact ratio `M(0)/Y(0)`.
Gauss-Legendre quadrature with 64 and 128 nodes must agree within `1e-8`
in logs, and the annual ratio must change by less than `2e-5` in logs across
horizon extensions. These checks are recorded in `annual_moments.json`.
Research shares and price declines are outputs, not calibration targets.

### Additional institutional experiments

The additional competitive-to-monopoly experiment in the paper is documented in
[`COMPETITIVE_TRANSITION.md`](COMPETITIVE_TRANSITION.md). It uses the same two
research productivities and four elasticities, but starts on a competitive
BGP and introduces exclusive AI rights. Its outputs do not replace the
published RSI-activation simulations. Run
`python scripts/report_competitive_to_monopoly.py` to regenerate its figures
from stored data, including the intermediate 10--100-year level panels.

The growth-reversal experiment is documented separately in
[`MONOPOLY_GROWTH_REVERSAL.md`](MONOPOLY_GROWTH_REVERSAL.md). It starts with
efficiency above the competitive threshold but an upper bound below the
monopoly threshold. It advances a competitive prehistory until output,
wage growth, and interest are within 0.1 percentage point of their limits,
inherits all stocks from that date, and compares both research productivities.
Run `python scripts/simulate_monopoly_growth_reversal_burnin.py --report` to solve that
reference and regenerate the new figures from the saved monopoly paths.
The preceding version remains reproducible in the folders without `_burnin`.

## 5. Compile the paper and online appendix

Select **main_rewrite.tex** as the main document in Overleaf. Locally, either:

```sh
latexmk -pdf main_rewrite.tex
latexmk -pdf online_appendix.tex
```

or, with Tectonic installed and an existing output directory:

```sh
tectonic --keep-logs --keep-intermediates --outdir output/pdf main_rewrite.tex
tectonic --keep-logs --keep-intermediates --outdir output/pdf online_appendix.tex
```

Compile the main paper first and retain `main_rewrite.aux`: the online appendix
imports its equation, section, and table numbers with links to the public paper.
The appendix reuses the saved figures; it does not recompute simulations.
In Overleaf, compile `main_rewrite.tex` before selecting `online_appendix.tex`
as the main document to build the separate supplement.

The GitHub workflow compiles both documents and publishes the main PDF and
[online appendix](https://oliverpardo1979.github.io/ai-growth-and-labor/paper/online-appendix.pdf)
together. It does not rerun the simulations or rebuild the digital reader.
