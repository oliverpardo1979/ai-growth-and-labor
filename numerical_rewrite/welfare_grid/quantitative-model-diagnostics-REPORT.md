# Quantitative diagnostics for the welfare grid

All 35 of 35 approved parameter combinations are admitted. Eight original paths are reused and 27 additional pairs are solved. No cell is dropped or filled by interpolation.

The consumption equivalent ranges from -31.852735039% at sigma=0.9, chi=1.5 to 130.346350160% at sigma=1.5, chi=7.5. Competition is preferred in 10 cells and monopoly in 25.

## Parameter inventory and scope

Sigma takes the seven approved values 0.9 through 1.5 in steps of 0.1. Chi takes 1.5, 3.0, 4.5, 6.0 and 7.5. These are illustrative choices, not estimated parameters or a literature-based confidence region. No empirical fit or non-targeted data moment is claimed.

All other parameters are inherited without refitting. Their values are {"alpha": 0.33, "depreciation": 0.05, "discount": 0.04, "eta": 0.2, "initial_labor_productivity": 1.0, "initial_population": 1.0, "labor_productivity_growth": 0.01, "omega_x": 0.1, "population_growth": 0.003}.
The fixed efficiency bound is 1360.99213924156 and initial AI efficiency is 13.6099213924156. The bound was originally selected as 1.10 times the monopoly threshold at sigma=1.5, not fitted to welfare.

Initial capital is derived from the competitive fixed-efficiency BGP at each sigma. At a given sigma the same stocks are used across all five chi values and both market structures. Capital differs across sigma. CES weights and efficiency units are unchanged, not re-normalized across elasticities. The map ranks market structures within each technology, not absolute utility across technologies.

## Numerical and optimality checks

The new driver reuses the original equilibrium equations and admission functions. Base, refined and extended checkpoints retain tolerances 2e-6, 1e-8 and 1e-9 and two 500-year horizon extensions. Independent finite differences check dynamics and both first-order conditions over the full horizon and densely in years 0--10. Terminal-state, feasibility and transversality diagnostics are retained.

The original developer-optimality diagnostic methods recorded across the 35 audits are {"global_hamiltonian_upper_tangent_with_analytical_continuation": 5, "global_profit_concavity_in_research_depth": 30}. Cases requiring Hamiltonian support retain the two original support grids and the analytical continuation check. This is an alternative sufficient optimality test, not an acceptance of first-order conditions alone.

Maximum recorded equation residual: 1.24619e-09. Maximum terminal-coordinate discrepancy: 3.37137e-06.

Welfare is computed from the original scalar log-consumption splines. Maximum final refinement effect is 9.72139e-08 percentage point. Maximum effect of replacing the path after year 500 with its limiting-growth continuation is 2.42433e-07 percentage point. The final-horizon tail is included explicitly.

Maximum difference between independent quadrature routines is 2.13163e-14 utility units per initial person. All original welfare integration thresholds are retained. Source hashes link each extract to its admitted checkpoint and recorded scenario.

## Coverage and limits

This is the approved two-dimensional illustrative grid. Rho, preferences, the efficiency bound, initial efficiency, production nesting, market closure and the initial-state rule are not varied. It is not a general robustness result over those assumptions. The dashed zero contour is linearly interpolated between solved grid points. It does not certify an exactly solved indifference frontier or extrapolate outside the grid.

Parameter estimation, bootstrap uncertainty, Bayesian identification and empirical out-of-sample fit are NOT_APPLICABLE. No additive causal mechanism decomposition or planner comparison is claimed. A representative-household welfare comparison is not a distributional welfare result for workers and owners separately.

## Reproduction

Run `python scripts/simulate_welfare_grid.py --check`, `python scripts/report_welfare_grid.py --check` and `python scripts/report_welfare_grid.py --audit`. Solving new grid cells uses `python scripts/simulate_welfare_grid.py --solve --workers 2` after the original competition-to-monopoly checkpoints are available. New files never replace the original simulation files. The environment is recorded alongside the outputs.

Confidence High in the admitted numerical calculations at these specified parameter pairs. No empirical forecasting claim is made.
