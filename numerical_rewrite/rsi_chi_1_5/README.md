# Illustrative RSI productivity: chi=1.5

[Paper](../../main_rewrite.tex) · [Replication guide](../../REPLICATION.md)

Four newly solved equilibria: sigma=0.9, 1, 1.1, 1.5. Only chi differs
between the two displayed comparisons. No expenditure or price target
is fitted. Each elasticity inherits its pre-RSI fixed-efficiency BGP.

Reproduce: `python scripts/simulate_rewrite_illustrative_rsi.py --chi 1.5`.

`scenario.json` records assumptions; `annual_moments.json` records
annual outcomes and quadrature/horizon checks. `*_audit.json` and support
files test equations, optimality and long-run continuation;
`activation_audit.json` tests pre-event equations and continuity.
`equilibrium_paths.csv` feeds the figures, with hashes in the manifests.
Window figures show years -2 to 10 and 10 to 500. Numerical admission
is not an interval-arithmetic proof. Calendar dates are not forecasts.
