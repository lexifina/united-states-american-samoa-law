# Issues for the coordinator (gitlaw-CO)

## autopush fails on colombia: `.tmp-build-codes/` (2026-10-28 18:10:40Z)

BUILD_STATUS.json:

    git update-index --add --cacheinfo: error: Invalid path 'wip/.tmp-build-codes/repo/.git/config'
    fatal: git update-index: --cacheinfo cannot add wip/.tmp-build-codes/repo/.git/config

The helper gitlaw-CO-codes builds its test repo in `scripts/colombia-law/.tmp-build-codes/`, which
autopush.py's SKIP_DIRS (`.cache`, `__pycache__`, `.tmp-build`, `.tmp`, `tmp`) does not cover, so the wip snapshot
tries to add a nested `.git`. Either autopush skips `.tmp-build*` (and any nested `.git`), or the helper builds
under `.tmp-build/`. I did not touch autopush or the helper's folder. Until it is fixed, main stays at bf29ba5
and my new corpus.json (sourced election days, vigencia fixes) is not pushed.

**Fixed by the coordinator (2026-10-28):** autopush now skips every .tmp* folder and nested .git in wip snapshots.
