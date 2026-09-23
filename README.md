# The Future of Growth and Human Labor Under Recursive AI Self-Improvement

**Oliver Pardo** · Departamento de Administración, Pontificia Universidad Javeriana

Working paper and replication files. The model studies growth, wages, capital
returns, and AI-industry income when a monopolistic AI developer invests in
recursive self-improvement.

- [Read the paper](https://oliverpardo1979.github.io/ai-growth-and-labor/paper/the-future-of-growth-and-human-labor-under-recursive-ai-self-improvement.pdf)
- [Digital edition and simulation explorer](https://oliverpardo1979.github.io/ai-growth-and-labor/)
- [Replication guide](REPLICATION.md)
- [Manuscript source](main_rewrite.tex)
- [Web-edition build and update guide](WEB_EDITION.md)

## Start here

Use Python 3.12 and install the pinned dependencies:

```sh
python -m pip install -r requirements-rewrite.txt
python scripts/reproduce_rewrite_results.py --check
```

The check validates the saved numerical evidence and CSV hashes. It does **not**
solve the model again. To recompute all eight trajectories and their audits:

```sh
python scripts/reproduce_rewrite_results.py --solve
```

The paper compares research productivity **7.5** and **1.5**, each with substitution
elasticities **0.9, 1.0, 1.1, 1.5**. These are illustrative scenarios, not estimated
forecasts. The numerical appendix explains the equilibrium algorithm and its checks.

## Files

| Location | Contents |
| --- | --- |
| `main_rewrite.tex`, `sections_rewrite/`, `references.bib` | Current paper and its appendices |
| `scripts/` | Solver, numerical checks, and figure generation |
| `numerical_rewrite/rsi_chi_7_5/` | Higher-productivity scenario, paths, and audits |
| `numerical_rewrite/rsi_chi_1_5/` | Lower-productivity scenario, paths, and audits |
| `figures_rewrite/` | Figures included in the paper |
| `tests/` | Replication and solver regression checks |

Some internal solver filenames retain historical names. They are dependencies
of the current algorithm, not additional papers. Their numerical equations,
tolerances, and initial conditions were not changed for this publication copy.

This repository excludes unfinished companion manuscripts and unused simulation
outputs. The original development repository remains unchanged; see
[migration and synchronization notes](MIGRATION.md). `PUBLICATION_MANIFEST.json`
records the source commit and initial copied-file hashes.

## Cite and contact

Oliver Pardo (2026), *The Future of Growth and Human Labor Under Recursive AI
Self-Improvement*, working paper. Contact: pardoo@javeriana.edu.co.

Please cite the paper and identify the repository commit used when reporting a
replication. No additional license is granted by this migration.
