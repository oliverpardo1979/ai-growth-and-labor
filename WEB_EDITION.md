# Digital edition

Read the paper and explore its stored simulations at
<https://oliverpardo1979.github.io/ai-growth-and-labor/>.
The [main PDF](https://oliverpardo1979.github.io/ai-growth-and-labor/paper/the-future-of-growth-and-human-labor-under-recursive-ai-self-improvement.pdf)
and [supplementary PDF](https://oliverpardo1979.github.io/ai-growth-and-labor/paper/online-appendix.pdf)
are published together. Additional proofs, supplementary simulations, and
numerical implementation details can also be read directly
in the [digital edition](https://oliverpardo1979.github.io/ai-growth-and-labor/#additional-results).
The [replication guide](REPLICATION.md) describes how to solve the model and reproduce its figures.

## One manuscript, two reading formats

`main_rewrite.tex` and its active inputs remain the authoritative manuscript.
The web build does not edit them. It follows active inputs, removes commented-out
material, and uses the compiled AUX and bibliography to retain equation,
proposition, section, figure, table, and citation references. The four TikZ
diagrams are extracted from the compiled paper; simulation figures in the main
text and appendices use the existing figure PDFs. No simulation is rerun by the web build.

`online_appendix.tex` and its active inputs supply supplementary material in the
HTML reader: S1/S2 contain the additional simulations, S3 the bounded-efficiency
results outside the main existence construction, S4 the proofs without an
efficiency bound, and S5 the numerical implementation details and accuracy table.
These follow the main paper and its references, retain their S-section numbering,
and link back to the main paper's results. A PDF download remains
available, but links from the paper lead directly to the relevant HTML section.
Both source graphs and their compiled inputs are recorded in the reader metadata.
The converter resolves both ordinary and legacy `paper-` references to main-paper
anchors, checks the separate supplementary theorem/equation counters against its
compiled AUX, and merges the two compiled bibliographies without duplicate entries.

The HTML reader is a generated edition, not a second manuscript to edit.
Its equations are rendered using MathJax 3.2.2. The typeset PDF is the reference
if a browser renders an equation differently. JavaScript is required for the
reader and explorer; the PDF and repository remain available without it.

## Explorer: scope and provenance

`scripts/build_web_data.py` exports the two illustrative RSI-activation exercises,
`rsi_chi_7_5` and `rsi_chi_1_5`, for the four stored elasticities 0.9, 1.0, 1.1,
and 1.5. It retains every sampled observation and its floating-point precision.
The separate competition-to-monopoly experiments and their figures are included
in the complete HTML reader, not in this eight-path interactive explorer.
Source CSV hashes are checked against the figure, path, and summary manifests,
and the recorded numerical-admission and activation checks must pass.

There are no continuous parameter sliders and no interpolated parameter
combinations. Lines connect sampled dates without curve smoothing; the
observation slider and pointer inspection use actual stored rows. The negative
time segment comes from the saved pre-RSI balanced-growth reference, not from
new simulated data. Values at 0-minus and 0-plus are kept separate.

Rates and shares are fractions in the source and displayed as percentages with
one decimal. The price is in final-good units per AI service and uses a log
axis. AI revenue divided by output uses the income identity
`1 - alpha - labor_income_share`, checked against the original CSV. Revenue
is not profit. The explorer distinguishes normalization by effective labor
from output per worker. Year 500 is an observation, not a claim of convergence.
Axes fit the selected data; their scales may change across selections. Source
links and hashes appear below the charts. Parameter selections are retained in
the URL, so an explorer view can be bookmarked or shared.

The digital edition draws inspiration from the reading/exploration format of
[Epoch AI's model playground](https://epoch.ai/gate), but implements no part of
that model and copies no simulation results or interface assets.

## Synchronized paper and digital-edition updates

Under Oliver's standing instruction of 2026-09-27, each completed paper update
includes rebuilding and validating both PDFs and the digital edition. No
separate request to update the website is needed. This supersedes the earlier
PDF-only policy; an explicit request to defer publication still takes precedence.
The editing workflow refreshes the immutable snapshot before the final push.

Every push to `main` runs `.github/workflows/paper.yml`:

1. Compile the current LaTeX manuscript, then `online_appendix.tex`, which imports the main paper's AUX labels.
2. Read the immutable snapshot commit pinned in `DIGITAL_EDITION.json`.
3. Export that approved digital edition from `codex/digital-edition`.
4. Replace `paper/the-future-of-growth-and-human-labor-under-recursive-ai-self-improvement.pdf` and `paper/online-appendix.pdf` with the new compilations.
5. Verify that every other file, including `index.html`, is byte-identical to the pinned snapshot, then publish to GitHub Pages.

A manual run of this CI workflow also overlays only the PDFs; it does not build
HTML. A source-only push therefore does not by itself synchronize the reader.
Complete the snapshot-update steps below for each paper-editing task, so the
HTML manuscript, supplementary material, and figures match the current
sources. Refresh the explorer from the stored data without rerunning simulations.
Missing snapshots or invalid files stop publication; they never trigger an
automatic digital rebuild. Snapshots are kept in Git rather than expiring
Actions artifacts. Do not delete or force-rewrite the snapshot branch.

### Updating the digital edition

Do this as part of each approved paper update, unless publication has been deferred:

1. Build and validate the current PDF and digital edition using the commands below.
2. Review the generated reader and explorer, including citations, math, figures, and links.
3. In a separate checkout of `codex/digital-edition`, prepare a complete snapshot from the validated `docs/` output (including generated assets and both PDFs). Preserve the branch history; do not force-push. Use `core.autocrlf=false` so snapshot bytes are unchanged.
4. Commit and push the new snapshot, then set `snapshot_commit` in `DIGITAL_EDITION.json` to its full SHA and update the manuscript provenance. Commit and push that pointer change on `main`.
5. Verify successful deployment, the requested digital changes, and the stable PDF link. An unsuccessful deployment may be retried without rebuilding the approved snapshot.

Updates to the online appendix follow the same workflow. Changes under `docs/`
are unpublished until included in a validated snapshot and referenced by
`DIGITAL_EDITION.json`. Do not treat a successful PDF build as verification of
the digital edition.

Conversion stops on missing labels, unresolved internal references, unsupported
TeX, Pandoc warnings, or inconsistent simulation provenance. A failed build does
not replace the currently published edition. Review the failed workflow if a
new LaTeX construct needs explicit conversion support.

Generated files under `docs/generated/` and `docs/paper/` remain ignored on
`main`; their approved publication copies are retained on `codex/digital-edition`.
The source hash and conversion checks are stored in
`generated/manuscript-meta.json` on the published site.

## Local build and checks

Requires Python 3.10+ and a working LaTeX build environment. The pinned Python
dependencies include Pandoc; no network is needed during conversion after
installation.

```sh
pip install -r requirements-web.txt
latexmk -pdf main_rewrite.tex
latexmk -pdf online_appendix.tex
python scripts/build_web_manuscript.py --build-dir .
python scripts/build_web_data.py
python scripts/build_web_data.py --check
python -m unittest discover -s tests -p 'test_web_*.py'
python -m http.server 8765 --directory docs
```

If the PDF/AUX/BBL files are under `output/pdf`, use
`--build-dir output/pdf` instead. For the local PDF link, copy the compiled PDF
to `docs/paper/the-future-of-growth-and-human-labor-under-recursive-ai-self-improvement.pdf`.
Also copy `online_appendix.pdf` to `docs/paper/online-appendix.pdf`.
The CI build instead overlays both new PDFs on the pinned site snapshot,
without changing any HTML.

Presentation lives in `docs/index.html`, `docs/web.css`, and `docs/web.js`.
Edits here affect only the web interface, not the model, numerical code, data,
manuscript, or Overleaf project.
