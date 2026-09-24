# Manuscript editing and publication

- The active manuscript is `main_rewrite.tex` and its associated files.
- After completing user-approved paper edits, rebuild and validate the PDF, then commit the changes and push to `origin/main` without asking for a separate confirmation. The public PDF updates automatically; the digital edition and simulation website update ONLY when Oliver explicitly requests it. His later instruction on 2026-09-24 supersedes the earlier automatic digital-update agreement.
- Before committing and pushing, check the working tree and fetch the remote. Preserve user edits and resolve overlapping changes carefully; never force-push or discard changes to make synchronization work.
- Commit only changes within the approved task. Do not include unrelated work.
- After pushing paper changes, check that GitHub Actions successfully publishes the PDF at the stable public link while preserving the pinned digital edition. A successful commit/push alone does not complete PDF publication; report any failure or pending deployment accurately.
- `DIGITAL_EDITION.json` pins an immutable site snapshot on `codex/digital-edition`. Normal pushes and workflow dispatches replace only the stable PDF inside that snapshot. Do not advance this pointer or rebuild/publish the digital edition without an explicit request. A difference between the current PDF and the older digital edition is intentional.
- When Oliver requests a digital update, follow `WEB_EDITION.md`: regenerate from the current manuscript and stored simulation data, validate, commit a new snapshot without rewriting its history, advance the pointer, push, and verify publication. Do not rerun or alter simulations solely to update the digital edition.
- GitHub publication and Overleaf synchronization are separate. Do not claim Overleaf is updated unless its state has been verified, and do not overwrite unsynchronized Overleaf edits.
