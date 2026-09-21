# Manuscript editing and publication

- The active manuscript is `main_rewrite.tex` and its associated files.
- After completing user-approved paper edits, validate the changes, commit them, and push to `origin/main` without asking for a separate confirmation. Oliver explicitly requested this standing workflow on 2026-09-21.
- Before committing and pushing, check the working tree and fetch the remote. Preserve user edits and resolve overlapping changes carefully; never force-push or discard changes to make synchronization work.
- Commit only changes within the approved task. Do not include unrelated work.
- After pushing, check that the GitHub Actions workflow builds and publishes the PDF successfully. Report any failure or pending publication accurately.
- GitHub publication and Overleaf synchronization are separate. Do not claim Overleaf is updated unless its state has been verified, and do not overwrite unsynchronized Overleaf edits.
