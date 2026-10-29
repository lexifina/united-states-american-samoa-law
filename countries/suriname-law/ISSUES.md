# ISSUES (gitlaw-SR)

- on.py `branches()` takes the first local branch that is not `main` and not `wip*` as the future branch. A reader
  who checks out autopush's `preview` branch locally (or any other branch) would have it read as the future branch
  when no `toekomst` exists. Suggest matching `country.future_branch` (from data/versions.json) instead.

**Fixed by the coordinator (2026-10-28):** build.py now writes data/repo.json with future_branch, and on.py reads it (local branch or origin/<name>), so preview and wip branches are never mistaken for the future branch. Takes effect on the next build.
