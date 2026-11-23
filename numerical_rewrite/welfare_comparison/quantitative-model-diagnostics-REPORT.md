# Welfare comparison: numerical scope and verification

## Result and scope

The existing sigma=1.5 competition-to-monopoly experiment gives consumption-equivalent gains of 130.3463502% for chi=7.5 and 11.0948492% for chi=1.5. Both monopoly paths approach consumption-per-person growth of 3.1349976%, against 1% under continued competition. These are household welfare differences from one specified common initial state, not an optimal-policy result or a general ranking over parameters.

Confidence High in the formula and the numerical integration of these admitted solutions. No empirical welfare prediction or calibration robustness is claimed.

## Parameter inventory and anchors

Values are inherited without modification from the original illustrative experiment. Alpha=.33, depreciation=.05 and rho=.04 are conventional illustrative calibration choices, not estimates identified for AI. Population growth n=.003 and labor-augmenting growth gamma=.01 retain the projection-based choices described in the parameter table. Omega_X=.10, eta=.20, sigma=1.5 and chi in {7.5,1.5} are assumed illustrative values, not empirical anchors or fitted targets. Bbar=1360.9921392415592 is deliberately 1.10 times the monopoly threshold at sigma=1.5, and B0=.01 Bbar. A0=N0=1 are normalizations. K0=6.53547722915475 follows from the competitive fixed-efficiency balanced-growth equations, not welfare targeting. Initial competitive consumption is 1.3986937158332973 from the resource constraint. Post-event consumption and research are endogenous.

The welfare number uses rho-n=.037 because utility is population-weighted log consumption per person. Market-interest discounting is not used. The consumption-equivalent number is a transformation of the endogenous consumption paths, not an independent moment matched by the model.

## Checks actually run

`scripts/report_rewrite_welfare.py --export-checkpoints` extracts scalar log-consumption splines from the existing base, refined and long BVP checkpoints without solving again. Committed extracts allow reproduction without scratch checkpoints. The final checkpoint hashes match the original admission reports, and CSV source hashes match the original path manifests. Parameters, initial stocks, competitive Euler and resource conditions are checked. Extracted log consumption ratios match all 4,961 plotted observations for each case to less than 1.1e-14.

Piecewise Gauss-Legendre quadrature at 8 and 16 nodes agrees within 4e-15 utility units. A separate adaptive integral agrees within 3e-14. Final horizons are about 4,013 and 4,632 years. Beyond each solved endpoint, a log-linear continuation uses the analytical limiting consumption-growth difference. Its contribution is negligible at reported precision, but it is included rather than implicitly set to zero.

The final solver refinement changes consumption-equivalent gains by less than 1e-6 percentage point. Replacing the full path after year 500 with limiting-growth continuation also changes either gain by less than 1e-6 percentage point. Earlier cutoffs at 50, 100 and 250 are recorded without selecting whichever looks best. A 50-year limiting-growth continuation does not reproduce the result and is not used.

`tests/test_welfare_comparison.py` tests identical paths, permanent level premiums, growth differences with an analytical infinite tail, sign reversal, positive effective discounting, published numbers and generated-table consistency. `welfare_results.json` records all values and provenance.

## Coverage limits

- Calibration sensitivity: only the two existing chi cases were compared, as agreed. No broad sweep over rho, sigma, Bbar, B0, initial states or household preferences was run. No general robustness claim is made. There are 2 admitted cases used out of 2 requested, with 0 new equilibrium solves and 0 dropped cases.
- Targeted versus untargeted empirical moments: NOT_APPLICABLE to this illustrative welfare calculation. It is not fitted to observed welfare or evaluated as an empirical prediction.
- Mechanism attribution: the two cases share technology limits and initial stocks but differ in research productivity. Their differing welfare reflects the whole resulting consumption path, not a difference in limiting growth. No additive causal channel decomposition or planner benchmark is claimed.
- Functional-form and closure alternatives, heterogeneous ownership, public research, infrastructure constraints and policy optimization: not run. They are outside this requested numerical subsection.
- Parameter identification, bootstrap uncertainty, Bayesian priors and out-of-sample fit: NOT_APPLICABLE because no parameter is estimated in this exercise.
- Equilibrium validation: reused original recorded dynamic, optimality and terminal checks, with strict checkpoint/CSV consistency. No new existence or uniqueness theorem is inferred from those checks.
