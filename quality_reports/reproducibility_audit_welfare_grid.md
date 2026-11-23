# Reproducibility audit of the welfare grid

Date: 2026-11-23. Revision: 1d1f181-dirty.

Scope is the new heatmap, its source data, and its eight overlaps with Table 4. This is not an audit of every numeric claim in the manuscript.

Vertical comparisons: 35/35 PASS. Horizontal comparisons: 35/35 PASS, including all eight table overlaps. No unmatched or explained discrepancies.

Percentages use the replication protocol tolerance of 0.1 percentage point. The displayed values agree exactly after rounding to one decimal. All 35 printed signed labels are also extracted from the vector PDF and checked against the source labels. Both image formats are saved from the same checked figure.

The existing eight baselines were recomputed from their committed consumption splines before extending the grid. Their unrounded values and provenance are unchanged. Mtime alone is not treated as staleness because those older baselines are intentionally reused and their input hashes are checked.

Environment is recorded in numerical_rewrite/welfare_grid/environment.json. No empirical estimate, standard error or p-value is part of this calculation.

| Sigma | Chi | Displayed (%) | Computed (%) | Difference (pp) | Vertical | Horizontal |
|---|---|---|---|---|---|---|
| 0.9 | 1.5 | -31.9 | -31.852735039 | 0.047264961 | PASS | PASS |
| 1 | 1.5 | -9.4 | -9.432057375 | 0.032057375 | PASS | PASS |
| 1.1 | 1.5 | -2.9 | -2.868879398 | 0.031120602 | PASS | PASS |
| 1.2 | 1.5 | +0.8 | +0.823647665 | 0.023647665 | PASS | PASS |
| 1.3 | 1.5 | +3.9 | +3.874185525 | 0.025814475 | PASS | PASS |
| 1.4 | 1.5 | +7.1 | +7.070144886 | 0.029855114 | PASS | PASS |
| 1.5 | 1.5 | +11.1 | +11.094849249 | 0.005150751 | PASS | PASS |
| 0.9 | 3 | -31.0 | -31.000291108 | 0.000291108 | PASS | PASS |
| 1 | 3 | -5.7 | -5.674216270 | 0.025783730 | PASS | PASS |
| 1.1 | 3 | +2.0 | +2.036743872 | 0.036743872 | PASS | PASS |
| 1.2 | 3 | +7.3 | +7.275848000 | 0.024152000 | PASS | PASS |
| 1.3 | 3 | +12.7 | +12.732615793 | 0.032615793 | PASS | PASS |
| 1.4 | 3 | +20.1 | +20.056935564 | 0.043064436 | PASS | PASS |
| 1.5 | 3 | +32.8 | +32.754413292 | 0.045586708 | PASS | PASS |
| 0.9 | 4.5 | -30.5 | -30.465406406 | 0.034593594 | PASS | PASS |
| 1 | 4.5 | -2.9 | -2.938874729 | 0.038874729 | PASS | PASS |
| 1.1 | 4.5 | +5.8 | +5.751223202 | 0.048776798 | PASS | PASS |
| 1.2 | 4.5 | +12.5 | +12.462050807 | 0.037949193 | PASS | PASS |
| 1.3 | 4.5 | +20.5 | +20.461496361 | 0.038503639 | PASS | PASS |
| 1.4 | 4.5 | +32.9 | +32.862950157 | 0.037049843 | PASS | PASS |
| 1.5 | 4.5 | +59.9 | +59.894939984 | 0.005060016 | PASS | PASS |
| 0.9 | 6 | -30.1 | -30.088534429 | 0.011465571 | PASS | PASS |
| 1 | 6 | -0.8 | -0.779846522 | 0.020153478 | PASS | PASS |
| 1.1 | 6 | +8.8 | +8.764535156 | 0.035464844 | PASS | PASS |
| 1.2 | 6 | +16.8 | +16.846653009 | 0.046653009 | PASS | PASS |
| 1.3 | 6 | +27.4 | +27.387268539 | 0.012731461 | PASS | PASS |
| 1.4 | 6 | +45.4 | +45.446474991 | 0.046474991 | PASS | PASS |
| 1.5 | 6 | +92.5 | +92.548200721 | 0.048200721 | PASS | PASS |
| 0.9 | 7.5 | -29.8 | -29.804393731 | 0.004393731 | PASS | PASS |
| 1 | 7.5 | +1.0 | +1.003949648 | 0.003949648 | PASS | PASS |
| 1.1 | 7.5 | +11.3 | +11.305047595 | 0.005047595 | PASS | PASS |
| 1.2 | 7.5 | +20.7 | +20.658613716 | 0.041386284 | PASS | PASS |
| 1.3 | 7.5 | +33.7 | +33.679684440 | 0.020315560 | PASS | PASS |
| 1.4 | 7.5 | +57.7 | +57.738724485 | 0.038724485 | PASS | PASS |
| 1.5 | 7.5 | +130.3 | +130.346350160 | 0.046350160 | PASS | PASS |

Recompute with `python scripts/report_welfare_grid.py --audit`. Each computed value is obtained through `simulate_welfare_grid.calculate_cell(sigma, chi)["stages"]["long"]["consumption_equivalent"] * 100`, including independent integration and the final-horizon tail.

Overall verdict: PASS.
