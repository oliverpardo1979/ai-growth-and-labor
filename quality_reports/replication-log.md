# Replication log

Append-only record of scoped numerical reproducibility checks.

## 2026-11-23 — welfare heatmap @ 1d1f181-dirty

Outputs: numerical_rewrite/welfare_grid. Scope: 35 figure cells and eight overlapping table entries. Verdict: PASS.

| Claim | Reported (%) | Computed (%) | How computed | Tolerance | Verdict |
|---|---|---|---|---|---|
| chi_1_5_sigma_0_90 | -31.9 | -31.852735039 | `simulate_welfare_grid.calculate_cell(0.9, 1.5)["stages"]["long"]["consumption_equivalent"] * 100` | 0.1 pp, exact display rounding | PASS/PASS |
| chi_1_5_sigma_1_00 | -9.4 | -9.432057375 | `simulate_welfare_grid.calculate_cell(1.0, 1.5)["stages"]["long"]["consumption_equivalent"] * 100` | 0.1 pp, exact display rounding | PASS/PASS |
| chi_1_5_sigma_1_10 | -2.9 | -2.868879398 | `simulate_welfare_grid.calculate_cell(1.1, 1.5)["stages"]["long"]["consumption_equivalent"] * 100` | 0.1 pp, exact display rounding | PASS/PASS |
| chi_1_5_sigma_1_20 | +0.8 | +0.823647665 | `simulate_welfare_grid.calculate_cell(1.2, 1.5)["stages"]["long"]["consumption_equivalent"] * 100` | 0.1 pp, exact display rounding | PASS/PASS |
| chi_1_5_sigma_1_30 | +3.9 | +3.874185525 | `simulate_welfare_grid.calculate_cell(1.3, 1.5)["stages"]["long"]["consumption_equivalent"] * 100` | 0.1 pp, exact display rounding | PASS/PASS |
| chi_1_5_sigma_1_40 | +7.1 | +7.070144886 | `simulate_welfare_grid.calculate_cell(1.4, 1.5)["stages"]["long"]["consumption_equivalent"] * 100` | 0.1 pp, exact display rounding | PASS/PASS |
| chi_1_5_sigma_1_50 | +11.1 | +11.094849249 | `simulate_welfare_grid.calculate_cell(1.5, 1.5)["stages"]["long"]["consumption_equivalent"] * 100` | 0.1 pp, exact display rounding | PASS/PASS |
| chi_3_0_sigma_0_90 | -31.0 | -31.000291108 | `simulate_welfare_grid.calculate_cell(0.9, 3.0)["stages"]["long"]["consumption_equivalent"] * 100` | 0.1 pp, exact display rounding | PASS/PASS |
| chi_3_0_sigma_1_00 | -5.7 | -5.674216270 | `simulate_welfare_grid.calculate_cell(1.0, 3.0)["stages"]["long"]["consumption_equivalent"] * 100` | 0.1 pp, exact display rounding | PASS/PASS |
| chi_3_0_sigma_1_10 | +2.0 | +2.036743872 | `simulate_welfare_grid.calculate_cell(1.1, 3.0)["stages"]["long"]["consumption_equivalent"] * 100` | 0.1 pp, exact display rounding | PASS/PASS |
| chi_3_0_sigma_1_20 | +7.3 | +7.275848000 | `simulate_welfare_grid.calculate_cell(1.2, 3.0)["stages"]["long"]["consumption_equivalent"] * 100` | 0.1 pp, exact display rounding | PASS/PASS |
| chi_3_0_sigma_1_30 | +12.7 | +12.732615793 | `simulate_welfare_grid.calculate_cell(1.3, 3.0)["stages"]["long"]["consumption_equivalent"] * 100` | 0.1 pp, exact display rounding | PASS/PASS |
| chi_3_0_sigma_1_40 | +20.1 | +20.056935564 | `simulate_welfare_grid.calculate_cell(1.4, 3.0)["stages"]["long"]["consumption_equivalent"] * 100` | 0.1 pp, exact display rounding | PASS/PASS |
| chi_3_0_sigma_1_50 | +32.8 | +32.754413292 | `simulate_welfare_grid.calculate_cell(1.5, 3.0)["stages"]["long"]["consumption_equivalent"] * 100` | 0.1 pp, exact display rounding | PASS/PASS |
| chi_4_5_sigma_0_90 | -30.5 | -30.465406406 | `simulate_welfare_grid.calculate_cell(0.9, 4.5)["stages"]["long"]["consumption_equivalent"] * 100` | 0.1 pp, exact display rounding | PASS/PASS |
| chi_4_5_sigma_1_00 | -2.9 | -2.938874729 | `simulate_welfare_grid.calculate_cell(1.0, 4.5)["stages"]["long"]["consumption_equivalent"] * 100` | 0.1 pp, exact display rounding | PASS/PASS |
| chi_4_5_sigma_1_10 | +5.8 | +5.751223202 | `simulate_welfare_grid.calculate_cell(1.1, 4.5)["stages"]["long"]["consumption_equivalent"] * 100` | 0.1 pp, exact display rounding | PASS/PASS |
| chi_4_5_sigma_1_20 | +12.5 | +12.462050807 | `simulate_welfare_grid.calculate_cell(1.2, 4.5)["stages"]["long"]["consumption_equivalent"] * 100` | 0.1 pp, exact display rounding | PASS/PASS |
| chi_4_5_sigma_1_30 | +20.5 | +20.461496361 | `simulate_welfare_grid.calculate_cell(1.3, 4.5)["stages"]["long"]["consumption_equivalent"] * 100` | 0.1 pp, exact display rounding | PASS/PASS |
| chi_4_5_sigma_1_40 | +32.9 | +32.862950157 | `simulate_welfare_grid.calculate_cell(1.4, 4.5)["stages"]["long"]["consumption_equivalent"] * 100` | 0.1 pp, exact display rounding | PASS/PASS |
| chi_4_5_sigma_1_50 | +59.9 | +59.894939984 | `simulate_welfare_grid.calculate_cell(1.5, 4.5)["stages"]["long"]["consumption_equivalent"] * 100` | 0.1 pp, exact display rounding | PASS/PASS |
| chi_6_0_sigma_0_90 | -30.1 | -30.088534429 | `simulate_welfare_grid.calculate_cell(0.9, 6.0)["stages"]["long"]["consumption_equivalent"] * 100` | 0.1 pp, exact display rounding | PASS/PASS |
| chi_6_0_sigma_1_00 | -0.8 | -0.779846522 | `simulate_welfare_grid.calculate_cell(1.0, 6.0)["stages"]["long"]["consumption_equivalent"] * 100` | 0.1 pp, exact display rounding | PASS/PASS |
| chi_6_0_sigma_1_10 | +8.8 | +8.764535156 | `simulate_welfare_grid.calculate_cell(1.1, 6.0)["stages"]["long"]["consumption_equivalent"] * 100` | 0.1 pp, exact display rounding | PASS/PASS |
| chi_6_0_sigma_1_20 | +16.8 | +16.846653009 | `simulate_welfare_grid.calculate_cell(1.2, 6.0)["stages"]["long"]["consumption_equivalent"] * 100` | 0.1 pp, exact display rounding | PASS/PASS |
| chi_6_0_sigma_1_30 | +27.4 | +27.387268539 | `simulate_welfare_grid.calculate_cell(1.3, 6.0)["stages"]["long"]["consumption_equivalent"] * 100` | 0.1 pp, exact display rounding | PASS/PASS |
| chi_6_0_sigma_1_40 | +45.4 | +45.446474991 | `simulate_welfare_grid.calculate_cell(1.4, 6.0)["stages"]["long"]["consumption_equivalent"] * 100` | 0.1 pp, exact display rounding | PASS/PASS |
| chi_6_0_sigma_1_50 | +92.5 | +92.548200721 | `simulate_welfare_grid.calculate_cell(1.5, 6.0)["stages"]["long"]["consumption_equivalent"] * 100` | 0.1 pp, exact display rounding | PASS/PASS |
| chi_7_5_sigma_0_90 | -29.8 | -29.804393731 | `simulate_welfare_grid.calculate_cell(0.9, 7.5)["stages"]["long"]["consumption_equivalent"] * 100` | 0.1 pp, exact display rounding | PASS/PASS |
| chi_7_5_sigma_1_00 | +1.0 | +1.003949648 | `simulate_welfare_grid.calculate_cell(1.0, 7.5)["stages"]["long"]["consumption_equivalent"] * 100` | 0.1 pp, exact display rounding | PASS/PASS |
| chi_7_5_sigma_1_10 | +11.3 | +11.305047595 | `simulate_welfare_grid.calculate_cell(1.1, 7.5)["stages"]["long"]["consumption_equivalent"] * 100` | 0.1 pp, exact display rounding | PASS/PASS |
| chi_7_5_sigma_1_20 | +20.7 | +20.658613716 | `simulate_welfare_grid.calculate_cell(1.2, 7.5)["stages"]["long"]["consumption_equivalent"] * 100` | 0.1 pp, exact display rounding | PASS/PASS |
| chi_7_5_sigma_1_30 | +33.7 | +33.679684440 | `simulate_welfare_grid.calculate_cell(1.3, 7.5)["stages"]["long"]["consumption_equivalent"] * 100` | 0.1 pp, exact display rounding | PASS/PASS |
| chi_7_5_sigma_1_40 | +57.7 | +57.738724485 | `simulate_welfare_grid.calculate_cell(1.4, 7.5)["stages"]["long"]["consumption_equivalent"] * 100` | 0.1 pp, exact display rounding | PASS/PASS |
| chi_7_5_sigma_1_50 | +130.3 | +130.346350160 | `simulate_welfare_grid.calculate_cell(1.5, 7.5)["stages"]["long"]["consumption_equivalent"] * 100` | 0.1 pp, exact display rounding | PASS/PASS |

## 2026-11-23 — welfare heatmap @ 1d1f181-dirty

Outputs: numerical_rewrite/welfare_grid. Scope: 35 figure cells and eight overlapping table entries. Verdict: PASS.

| Claim | Reported (%) | Computed (%) | How computed | Tolerance | Verdict |
|---|---|---|---|---|---|
| chi_1_5_sigma_0_90 | -31.9 | -31.852735039 | `simulate_welfare_grid.calculate_cell(0.9, 1.5)["stages"]["long"]["consumption_equivalent"] * 100` | 0.1 pp, exact display rounding | PASS/PASS |
| chi_1_5_sigma_1_00 | -9.4 | -9.432057375 | `simulate_welfare_grid.calculate_cell(1.0, 1.5)["stages"]["long"]["consumption_equivalent"] * 100` | 0.1 pp, exact display rounding | PASS/PASS |
| chi_1_5_sigma_1_10 | -2.9 | -2.868879398 | `simulate_welfare_grid.calculate_cell(1.1, 1.5)["stages"]["long"]["consumption_equivalent"] * 100` | 0.1 pp, exact display rounding | PASS/PASS |
| chi_1_5_sigma_1_20 | +0.8 | +0.823647665 | `simulate_welfare_grid.calculate_cell(1.2, 1.5)["stages"]["long"]["consumption_equivalent"] * 100` | 0.1 pp, exact display rounding | PASS/PASS |
| chi_1_5_sigma_1_30 | +3.9 | +3.874185525 | `simulate_welfare_grid.calculate_cell(1.3, 1.5)["stages"]["long"]["consumption_equivalent"] * 100` | 0.1 pp, exact display rounding | PASS/PASS |
| chi_1_5_sigma_1_40 | +7.1 | +7.070144886 | `simulate_welfare_grid.calculate_cell(1.4, 1.5)["stages"]["long"]["consumption_equivalent"] * 100` | 0.1 pp, exact display rounding | PASS/PASS |
| chi_1_5_sigma_1_50 | +11.1 | +11.094849249 | `simulate_welfare_grid.calculate_cell(1.5, 1.5)["stages"]["long"]["consumption_equivalent"] * 100` | 0.1 pp, exact display rounding | PASS/PASS |
| chi_3_0_sigma_0_90 | -31.0 | -31.000291108 | `simulate_welfare_grid.calculate_cell(0.9, 3.0)["stages"]["long"]["consumption_equivalent"] * 100` | 0.1 pp, exact display rounding | PASS/PASS |
| chi_3_0_sigma_1_00 | -5.7 | -5.674216270 | `simulate_welfare_grid.calculate_cell(1.0, 3.0)["stages"]["long"]["consumption_equivalent"] * 100` | 0.1 pp, exact display rounding | PASS/PASS |
| chi_3_0_sigma_1_10 | +2.0 | +2.036743872 | `simulate_welfare_grid.calculate_cell(1.1, 3.0)["stages"]["long"]["consumption_equivalent"] * 100` | 0.1 pp, exact display rounding | PASS/PASS |
| chi_3_0_sigma_1_20 | +7.3 | +7.275848000 | `simulate_welfare_grid.calculate_cell(1.2, 3.0)["stages"]["long"]["consumption_equivalent"] * 100` | 0.1 pp, exact display rounding | PASS/PASS |
| chi_3_0_sigma_1_30 | +12.7 | +12.732615793 | `simulate_welfare_grid.calculate_cell(1.3, 3.0)["stages"]["long"]["consumption_equivalent"] * 100` | 0.1 pp, exact display rounding | PASS/PASS |
| chi_3_0_sigma_1_40 | +20.1 | +20.056935564 | `simulate_welfare_grid.calculate_cell(1.4, 3.0)["stages"]["long"]["consumption_equivalent"] * 100` | 0.1 pp, exact display rounding | PASS/PASS |
| chi_3_0_sigma_1_50 | +32.8 | +32.754413292 | `simulate_welfare_grid.calculate_cell(1.5, 3.0)["stages"]["long"]["consumption_equivalent"] * 100` | 0.1 pp, exact display rounding | PASS/PASS |
| chi_4_5_sigma_0_90 | -30.5 | -30.465406406 | `simulate_welfare_grid.calculate_cell(0.9, 4.5)["stages"]["long"]["consumption_equivalent"] * 100` | 0.1 pp, exact display rounding | PASS/PASS |
| chi_4_5_sigma_1_00 | -2.9 | -2.938874729 | `simulate_welfare_grid.calculate_cell(1.0, 4.5)["stages"]["long"]["consumption_equivalent"] * 100` | 0.1 pp, exact display rounding | PASS/PASS |
| chi_4_5_sigma_1_10 | +5.8 | +5.751223202 | `simulate_welfare_grid.calculate_cell(1.1, 4.5)["stages"]["long"]["consumption_equivalent"] * 100` | 0.1 pp, exact display rounding | PASS/PASS |
| chi_4_5_sigma_1_20 | +12.5 | +12.462050807 | `simulate_welfare_grid.calculate_cell(1.2, 4.5)["stages"]["long"]["consumption_equivalent"] * 100` | 0.1 pp, exact display rounding | PASS/PASS |
| chi_4_5_sigma_1_30 | +20.5 | +20.461496361 | `simulate_welfare_grid.calculate_cell(1.3, 4.5)["stages"]["long"]["consumption_equivalent"] * 100` | 0.1 pp, exact display rounding | PASS/PASS |
| chi_4_5_sigma_1_40 | +32.9 | +32.862950157 | `simulate_welfare_grid.calculate_cell(1.4, 4.5)["stages"]["long"]["consumption_equivalent"] * 100` | 0.1 pp, exact display rounding | PASS/PASS |
| chi_4_5_sigma_1_50 | +59.9 | +59.894939984 | `simulate_welfare_grid.calculate_cell(1.5, 4.5)["stages"]["long"]["consumption_equivalent"] * 100` | 0.1 pp, exact display rounding | PASS/PASS |
| chi_6_0_sigma_0_90 | -30.1 | -30.088534429 | `simulate_welfare_grid.calculate_cell(0.9, 6.0)["stages"]["long"]["consumption_equivalent"] * 100` | 0.1 pp, exact display rounding | PASS/PASS |
| chi_6_0_sigma_1_00 | -0.8 | -0.779846522 | `simulate_welfare_grid.calculate_cell(1.0, 6.0)["stages"]["long"]["consumption_equivalent"] * 100` | 0.1 pp, exact display rounding | PASS/PASS |
| chi_6_0_sigma_1_10 | +8.8 | +8.764535156 | `simulate_welfare_grid.calculate_cell(1.1, 6.0)["stages"]["long"]["consumption_equivalent"] * 100` | 0.1 pp, exact display rounding | PASS/PASS |
| chi_6_0_sigma_1_20 | +16.8 | +16.846653009 | `simulate_welfare_grid.calculate_cell(1.2, 6.0)["stages"]["long"]["consumption_equivalent"] * 100` | 0.1 pp, exact display rounding | PASS/PASS |
| chi_6_0_sigma_1_30 | +27.4 | +27.387268539 | `simulate_welfare_grid.calculate_cell(1.3, 6.0)["stages"]["long"]["consumption_equivalent"] * 100` | 0.1 pp, exact display rounding | PASS/PASS |
| chi_6_0_sigma_1_40 | +45.4 | +45.446474991 | `simulate_welfare_grid.calculate_cell(1.4, 6.0)["stages"]["long"]["consumption_equivalent"] * 100` | 0.1 pp, exact display rounding | PASS/PASS |
| chi_6_0_sigma_1_50 | +92.5 | +92.548200721 | `simulate_welfare_grid.calculate_cell(1.5, 6.0)["stages"]["long"]["consumption_equivalent"] * 100` | 0.1 pp, exact display rounding | PASS/PASS |
| chi_7_5_sigma_0_90 | -29.8 | -29.804393731 | `simulate_welfare_grid.calculate_cell(0.9, 7.5)["stages"]["long"]["consumption_equivalent"] * 100` | 0.1 pp, exact display rounding | PASS/PASS |
| chi_7_5_sigma_1_00 | +1.0 | +1.003949648 | `simulate_welfare_grid.calculate_cell(1.0, 7.5)["stages"]["long"]["consumption_equivalent"] * 100` | 0.1 pp, exact display rounding | PASS/PASS |
| chi_7_5_sigma_1_10 | +11.3 | +11.305047595 | `simulate_welfare_grid.calculate_cell(1.1, 7.5)["stages"]["long"]["consumption_equivalent"] * 100` | 0.1 pp, exact display rounding | PASS/PASS |
| chi_7_5_sigma_1_20 | +20.7 | +20.658613716 | `simulate_welfare_grid.calculate_cell(1.2, 7.5)["stages"]["long"]["consumption_equivalent"] * 100` | 0.1 pp, exact display rounding | PASS/PASS |
| chi_7_5_sigma_1_30 | +33.7 | +33.679684440 | `simulate_welfare_grid.calculate_cell(1.3, 7.5)["stages"]["long"]["consumption_equivalent"] * 100` | 0.1 pp, exact display rounding | PASS/PASS |
| chi_7_5_sigma_1_40 | +57.7 | +57.738724485 | `simulate_welfare_grid.calculate_cell(1.4, 7.5)["stages"]["long"]["consumption_equivalent"] * 100` | 0.1 pp, exact display rounding | PASS/PASS |
| chi_7_5_sigma_1_50 | +130.3 | +130.346350160 | `simulate_welfare_grid.calculate_cell(1.5, 7.5)["stages"]["long"]["consumption_equivalent"] * 100` | 0.1 pp, exact display rounding | PASS/PASS |
