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
First solve a competitive prehistory, seeded at A = N = 1 and K = 14,047.3
(the limiting monopoly capital/effective-labor ratio at this bound).
Select the first whole year when output-per-worker growth, wage growth,
and interest are all within **0.1 percentage point** of their competitive
limits, checking that subsequent annual observations through year 1,000
also satisfy this criterion. This selects seed year **190**. Reset time
to zero and inherit **all** stocks: A0 = 6.6858944423, N0 = 1.7682670514,
K0 = 7,290,728,575.251 and B0 = 1,002.1851207142. Keep chi in its original
units. These are illustrative choices, not empirical matches.

Unlike the previous grant experiment, the competitive reference is a
nonstationary equilibrium near its AI-dominated limiting rates, not an
exact steady state with stationary K/(AN). Its initial K/Y is about 2.23,
not 3.3. Initial output-per-worker growth, wage growth, and interest are
5.8%, 4.2%, and 9.8%. Consumption and research are solved, not inherited.
The monopoly limit has 1.0% annual per-worker output growth rather than
zero growth; the competitive limit is about 5.7%. No welfare ranking is
inferred from output growth.

## Reproduce

Install the requirements described in [REPLICATION.md](REPLICATION.md).
From the repository root:

```sh
python scripts/simulate_monopoly_growth_reversal_burnin.py --prepare
python scripts/simulate_monopoly_growth_reversal_burnin.py --chi 7.5
python scripts/simulate_monopoly_growth_reversal_burnin.py --chi 1.5
python scripts/simulate_monopoly_growth_reversal_burnin.py --report
python -m unittest discover -s tests -p test_monopoly_growth_reversal_burnin.py -v
python -m unittest discover -s tests -p test_monopoly_growth_reversal.py -v
```

The preparation command solves and checks the competitive prehistory,
selects the event date, and verifies that restarting from the inherited
physical stocks reproduces the original competitive continuation. The
next two commands solve and audit the monopoly paths; they may take
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
- `numerical_rewrite/monopoly_growth_reversal_burnin_chi_7_5/` and its `chi_1_5`
  counterpart hold separate scenario specifications, monopoly CSVs, hashes,
  and full admission reports. Checkpoints are generated under `tmp/`, not
  shipped. The final monopoly horizon is about 4,592 years.
- `numerical_rewrite/monopoly_growth_reversal_burnin/` holds the initialization,
  last ten years of competitive prehistory, competitive continuation CSV,
  its independent residual and horizon audit, the combined plotted data,
  impact changes, limits, and figure provenance manifest.
- `figures_rewrite/monopoly_growth_reversal_burnin/` holds two three-window figures
  (-10--10, 10--100, 100--500 years). Negative dates are the common
  competitive prehistory; the grant occurs at zero. The service ratio is relative to the
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

Both monopoly paths are still adjusting at year 500: output-per-worker
growth is about -0.1%, wage growth 0.3%, and interest 3.9%. These are not
the theoretical limits. The high-chi path initially grows rapidly after
the instantaneous output loss, then also contracts. No welfare conclusion
is inferred from these growth rates or the initial consumption increase.

## Preserved original experiment

The original experiment remains in the folders **without** `_burnin`.
It grants monopoly rights immediately at A0 = N0 = 1 and K0 = 14,047.3,
with the same B0, upper bound, and research productivities. Its competitive
initial K/Y is 1.82. Its exposition is retained, but not included in the PDF,
in `sections_rewrite/archive/15_monopoly_growth_reversal_original.tex`.
Run `python scripts/simulate_monopoly_growth_reversal.py --report` to
regenerate those original figures, or its `--chi` options to solve it.
Neither the original data nor the other manuscript experiments are replaced.
