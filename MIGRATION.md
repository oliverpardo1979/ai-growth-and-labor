# Publication copy and safe synchronization

This is a new repository, not a rename or history rewrite.
It was initialized from development commit `7b8c672` in
[the original repository](https://github.com/oliverpardo1979/AI-Future-Paper-WTF).
The original repository, companion papers, archived simulations, and original
Overleaf project are preserved. No original files were deleted.

Only the current manuscript, its required figures, the two published numerical
comparisons, and their solver dependencies are included. Disabled presentation
branches were resolved in the publication copy. The source equations and
numerical results were not changed. The appendix's replication links and this
repository's documentation were updated for the new location.

## Overleaf workflow

Import this repository as a **new** Overleaf project, rather than relinking or
overwriting the original project. Select `main_rewrite.tex` as the main document.

Before editing in Overleaf, pull the latest GitHub changes into the **new**
project. After editing there, push to GitHub before editing locally. Before
editing locally, fetch and integrate the latest GitHub commits. Never resolve
a sync conflict by force-pushing or replacing one side wholesale.

The GitHub synchronization is manual; it is not continuous background sync.
The repository is the shared source, and GitHub Pages builds the public PDF.

The old public PDF URL remains owned by the original repository. This migration
does not silently repoint existing website or CV links. Update that arrangement
separately after the new publication and Overleaf project have been verified.
