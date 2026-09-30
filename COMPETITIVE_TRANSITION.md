# From competitive AI to monopoly

This experiment asks whether research financed by monopoly rents can offset
restricted AI use and allow an escape from the labor bottleneck. The main-text
subsection "Monopoly boosts growth" focuses on
sigma=1.5 and compares both research productivities in a single figure.
The supplementary appendix retains the full four-elasticity comparison,
including the original level figures and initial-stock table.
It does not replace the original RSI-activation data or figures, and it does
not update the digital edition. These are mechanism illustrations, not
calibrated predictions of the magnitude or timing of AI-driven growth.

## Economic experiment

Before date zero, AI technology is publicly accessible. AI services are priced
at marginal cost, B is constant, and the economy follows its competitive
labor-bottleneck BGP. Research technology is available: chi is positive, not
zero. Research expenditure is zero because improvements cannot be appropriated
under the competitive benchmark described in Section 5.

At date zero, an unexpected, permanent exclusive right is granted over both
the existing AI technology and all subsequent improvements. Continued supply
by competitive producers using the old technology is excluded. This assumption
is necessary to use the paper's monopoly problem without changing its demand
curve. There are no transition taxes, transfers, enforcement costs, or
adjustment costs. The representative household owns the developer.

K and B remain continuous. Consumption and the research shadow price are
chosen again by the post-event BVP; neither is fixed at its pre-event value.
AI prices, AI use, output, wages, and returns can jump. The figures distinguish
these level jumps from subsequent growth rates. No finite growth rate is
assigned to the date-zero discontinuity.

Each path is compared with continued competition from exactly the same stocks.
The counterfactual keeps B fixed and grows at the competitive BGP rates.

## Parameters and initial conditions

All parameters are inherited from the published illustrative experiments:
alpha=0.33, delta=0.05, rho=0.04, n=0.003, gamma=0.01, omega_X=0.10,
eta=0.20, A0=N0=1, Bbar=1.10 times the monopoly threshold for sigma=1.5,
and B0=0.01 Bbar. Chi is 7.5 or 1.5, each with sigma=0.9, 1, 1.1, 1.5.
These are illustrative parameter values, not new empirical calibrations.

For each sigma, the competitive pricing condition and r=rho+gamma determine
its own K0. Before exclusive rights, K0/Y0=3.3. This ratio need not remain
3.3 immediately after the change, because output can jump. Both chi values
use the same competitive stocks at each sigma.

## Replication

Install the dependencies in `requirements-rewrite.txt`, as in `REPLICATION.md`.
From the repository root:

```sh
python scripts/simulate_competitive_to_monopoly.py --chi 7.5
python scripts/simulate_competitive_to_monopoly.py --chi 1.5
python scripts/simulate_competitive_to_monopoly.py --chi 7.5 --finish
python scripts/simulate_competitive_to_monopoly.py --chi 1.5 --finish
python scripts/report_competitive_to_monopoly.py
python scripts/report_competitive_main_comparison.py
```

Use `--sigma 1.5` to solve one case, or `--prepare-only` to inspect initial
conditions without solving. The optional `--seed-cache PATH` accepts an
existing original-experiment checkpoint directory. It checks the economic
parameters and re-solves the BVP at the new initial capital; the old spline
is only an initial numerical guess. It does not impose old controls. Without
that option, the original continuation algorithm constructs the solution.

New data and audits are in `numerical_rewrite/competitive_to_monopoly_chi_*/`.
New checkpoints are in `tmp/rewrite_bvp_competitive_to_monopoly_chi_*/`.
They never overwrite the `rsi_chi_*` experiments. As in the original code,
checkpoints are local scratch files; all parameters, plotted data, diagnostics,
and their hashes are retained. Numerical admission is not a formal
interval-arithmetic proof of equilibrium existence.

`--finish` applies the same equation residuals, horizon-refinement tests,
transversality diagnostics, and developer-optimality checks as the paper.
The AI-dominated case uses the existing Hamiltonian-support test when the
stronger global concavity test fails. No tolerance is relaxed for this
experiment. The first two driver extensions are recorded separately in
`SIMULATION_EXTENSIONS.json`, preserving the historical migration manifest.

`comparison_paths.csv` contains monopoly trajectories relative to continued
competition; `continued_competition.csv` records the normalized counterfactual;
`policy_event.json` separates the impact jump; `comparison_summary.json`
records selected dates, theoretical limits, and first upward crossings of
competitive output, wages, and consumption on the displayed mesh. A crossing
is not a welfare comparison or a claim of permanent dominance.
The normalized competitive variables are constant, so the counterfactual CSV
records their endpoints rather than repeating identical rows at every date.

The combined eight-page figure PDF is generated at
`output/pdf/competitive_to_monopoly_simulations.pdf`. The corresponding PNGs,
individual vector PDFs used by LaTeX, and a data-hash manifest are in
`figures_rewrite/competitive_to_monopoly/`. Running only the reporting script
rebuilds the figures from stored, audited paths without solving again.

The main-text level figure combines chi=7.5 and chi=1.5 at sigma=1.5, with
continued competition on the same axes. It is generated by
`scripts/report_competitive_main_comparison.py`, which only reads the stored
audited paths. It neither solves equilibria nor rewrites numerical data.
The new figure's source hashes and the unaltered ratio definitions are recorded
in `figures_rewrite/competitive_to_monopoly/competitive_to_monopoly_sigma_1_5_levels_manifest.json`.
The previous main-text discussion is preserved in
`sections_rewrite/archive/14_competitive_to_monopoly_four_sigmas.tex`.

The main-text figure shows two windows: -2 to 10 years (including two
pre-event years) and 10 to 50 years. Its columns show output per worker,
wages, and AI-industry revenue. Output and wages are relative to continued
competition: percentages in the upper row and multiples on logarithmic
scales below. AI revenue is p_X X divided by each economy's own output,
displayed as a percentage in both rows. Its competitive benchmark is
positive, not zero: competitive AI revenue pays for inference compute.
The renderer checks revenue against both the factor-income identity and
the sum of inference expenditure, research expenditure, and net profit.

The two appendix level figures retain consumption and three windows:
-2 to 10, 10 to 100, and 10 to 500 years. Their initial row uses percentages
of continued competition; the middle and last rows use multiples on
logarithmic scales. Vertical scales differ across windows. All percentage
ticks have one decimal place. The six additional appendix figures retain
the original two windows. All windows use the same stored trajectories;
the shorter main-text display does not change the solution horizon.

## Interpretation limits

The immediate output losses for sigma=0.9, 1, 1.1, and 1.5 are respectively
32.4%, 17.6%, 13.7%, and 10.4%. The corresponding wage losses are 36.6%,
17.6%, 11.9%, and 5.4%. These static losses are identical under both chi
values. Subsequent recovery is not: for sigma=1.5, output first reaches its
continued-competition counterpart around year 3.8 with chi=7.5 and year 24.0
with chi=1.5; wages reach their counterpart around years 4.6 and 26.0.
For sigma=0.9, neither output nor wages recover to their competitive
counterpart within the 500-year display window. These dates describe the
illustrative model, not forecasts or an optimal policy schedule.

The calibration has a particularly large monopoly markup for sigma=0.9:
the impact price is about 131 times its competitive level. This makes the
experiment useful for revealing the model's pricing distortion, but difficult
to interpret as a quantitatively realistic policy intervention without
reconsidering that margin. Competitive AI revenue starts at 6.4%-8.6% of
gross output under the inherited parameters; this is not an empirical match
to the current AI industry. The experimental paper figures and this
counterfactual answer different questions and should not be interchanged
without an explicit editorial and calibration decision.

This is a comparison of two institutional regimes, not an optimal policy
exercise. The grant is unexpected; announced or temporary protection changes
incentives and initial consumption. Protection of new improvements alone
would leave competitive access to the old technology and require a different
pricing problem. The same calibration need not match the initial size of the
AI industry under both pricing regimes. Chi changes transition incentives and
timing, while the existing analytical monopoly limits remain unchanged.
