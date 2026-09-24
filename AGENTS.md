# Manuscript editing and publication

- The active manuscript is `main_rewrite.tex` and its associated files.
- After completing user-approved paper edits, rebuild and validate both the PDF and the digital edition from the same current manuscript, then commit the changes and push to `origin/main` without asking for a separate confirmation. Oliver requested commit/push on 2026-09-21 and explicitly added digital-edition updates to this standing workflow on 2026-09-24.
- Before committing and pushing, check the working tree and fetch the remote. Preserve user edits and resolve overlapping changes carefully; never force-push or discard changes to make synchronization work.
- Commit only changes within the approved task. Do not include unrelated work.
- After pushing paper changes, check that the GitHub Actions workflow builds and publishes both the PDF and the digital edition successfully. Verify that the live digital edition includes the latest approved changes and that the stable public PDF link works. A successful commit/push alone does not complete publication; report any failure, stale version, or pending deployment accurately.
- Keep the digital edition at `https://oliverpardo1979.github.io/ai-growth-and-labor/` synchronized with the PDF, including citations, equations, and links. Regenerate it using the existing build workflow and stored simulation data; do not rerun or alter simulations solely to update the digital edition.
- GitHub publication and Overleaf synchronization are separate. Do not claim Overleaf is updated unless its state has been verified, and do not overwrite unsynchronized Overleaf edits.
