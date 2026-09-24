# Monopoly and the loss of AI-dominated growth

This illustrative experiment accompanies the subsection *When monopoly
eliminates AI-dominated growth*. It leaves every earlier simulation intact.

## Design

Fix sigma = 1.5 and the common parameters from the main experiments. Compare
continued competitive supply with an unexpected permanent grant of exclusive
rights over existing AI and all subsequent improvements. RSI is technologically
available throughout; competitive suppliers cannot appropriate improvements.
The two monopoly paths use chi = 7.5 and 1.5.

Choose the efficiency upper bound as 90% of the monopoly threshold and initial
efficiency as 90% of that bound. This puts initial efficiency above the
competitive threshold while the bound remains below the monopoly threshold.
Initial capital per effective worker equals the limiting monopoly ratio at
the chosen bound; A0 = N0 = 1. These are illustrative choices, not estimates
or empirical matches. They are identical across all three paths.

Unlike the previous grant experiment, the competitive reference is a
nonstationary equilibrium, not a labor-bottleneck BGP. Its initial K/Y is
about 1.82, not 3.3. Consumption and research are solved, not inherited.
The monopoly limit has 1.0% annual per-worker output growth rather than
zero growth; the competitive limit is about 5.7%. No welfare ranking is
inferred from output growth.

## Reproduce

Install the requirements described in [REPLICATION.md](REPLICATION.md).
From the repository root:

```sh
python scripts/simulate_monopoly_growth_reversal.py --chi 7.5
python scripts/simulate_monopoly_growth_reversal.py --chi 1.5
python scripts/simulate_monopoly_growth_reversal.py --report
python -m unittest discover -s tests -p test_monopoly_growth_reversal.py -v
```

The first two commands solve and audit the monopoly paths. They may take
several minutes. The report command can also run on a fresh clone using
the committed monopoly CSVs and admission reports: it checks their hashes,
solves the competitive transition at horizons of 1,200 and 1,800 years,
checks that solution, and regenerates the combined data and figures.

## Method and evidence

- `scripts/solve_competitive_ai_transition.py` solves the competitive Ramsey
  resource constraint and Euler equation, imposing initial capital and the
  limiting C/K = rho - n. It uses logarithmic capital per effective worker
  with its limiting trend removed and log(C/K). The static CES choice is
  solved in log odds of the AI share to avoid cancellation near one.
- `numerical_rewrite/monopoly_growth_reversal_chi_7_5/` and its `chi_1_5`
  counterpart hold separate scenario specifications, monopoly CSVs, hashes,
  and full admission reports. Checkpoints are generated under `tmp/`, not
  shipped. The final monopoly horizon is about 4,592 years.
- `numerical_rewrite/monopoly_growth_reversal/` holds the competitive CSV,
  its independent residual and horizon audit, the combined plotted data,
  impact changes, limits, and figure provenance manifest.
- `figures_rewrite/monopoly_growth_reversal/` holds two three-window figures
  (0--10, 10--100, 100--500 years). The service ratio is relative to the
  growing competitive path. Its decline is not a decline of AI services
  toward zero in absolute units. Instantaneous output/wage level losses
  are not plotted as finite annual growth rates.

The monopoly solver retains the existing admission gates, supplemented by
dense first-decade residual and developer-concavity checks. Only the export
of a labor-share halfway date is disabled for this experiment: the share
is nonmonotonic and crossing that point is not an equilibrium condition.
The competitive audit checks static optimality, resource/Euler residuals,
initial capital, horizon sensitivity, theoretical limits, and the household
transversality diagnostic. Numerical admission is not a formal error-bound
proof of existence. Tests independently reconstruct CES output, optimal
compute, the envelope and wage derivatives, and check saved-data hashes.
