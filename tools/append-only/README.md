# Append-only publishing for git-for-law corpora (`append.py`)

Alan's rule (2026-11-02): no force-pushes anywhere. Published history only grows by fast-forward.

`tools/append.py` grows a published corpus repo without rewriting it:
- a new act goes on top as one block of its own commits (first version, then one commit per law per in-force day);
- newer versions of acts main already holds are appended as changes;
- a new documentation commit is appended last; the old one is never replaced.

The full builder re-sorts the whole history by in-force date on every build, which is why adding an act used to
force-push.

## How dates work
- **Author date:** noon local time on the in-force day, exactly as `build.py` sets it.
- **Committer date:** the published head's committer time plus one second per appended commit. Committer dates never
  go backwards, and the same head plus the same corpus always gives the same hashes.
- **Readers:** `tools/on.py` and `tools/check_repo.py` already choose versions by the `In-force` trailer per path, not
  by commit order, so they read an appended block exactly as they read a full build.
- **Limit:** `git rev-list --before=D` over the whole tree is no longer exact for acts added later. Per-file history,
  `git blame` and the tools stay exact.

## What it refuses (stop and decide by hand)
- A local `main` that isn't `origin/main`, or uncommitted changes in the clone.
- A version main already holds whose text differs from the corpus (a correction).
- A form dated on or before the newest one main has for that act (a back-fill).

Both of these need a labelled correction commit, which is not built yet. Versions in force after `--docs-date` are left
for a later run and get appended when their day comes. Existing tags are never moved; new ones are added.

## Use

`append.py` sits beside the corpus's published `build.py` and `check_repo.py`, and imports both. A published copy has
`check_repo.py`; if `build.py` wants `check.py`, copy `check_repo.py` to `check.py` too. Put `gitlaw_common/private.py`
beside them so the docs commit keeps private files out.

```
git clone https://github.com/lexifina/<corpus> R && cd R && git config core.autocrlf false
git rm -q --cached -r . && git reset -q --hard          # LF working tree (Windows)
GITLAW_VERIFIED_PARTS_ONLY=1 python -X utf8 tools/append.py <scripts/<slug>-law> --repo R --docs-date <retrieved day> [--dry-run]
GITLAW_VERIFIED_PARTS_ONLY=1 python -X utf8 tools/check_repo.py R --corpus <scripts/<slug>-law>/corpus.json   # must be 0/0
# privacy audit (gitlaw_common/private.audit_push(R, new, old)) must be empty, then:
git -C R push origin main            # plain push; a rejection means someone else pushed: stop
git -C R push origin <new tag refs>  # only the tags that don't exist on the remote yet
```

Run a dry run against the published head first. `commits: 0` means main and the corpus agree, which is the
precondition for appending.

## Tested
`test_append.py` builds part of the Romanian corpus (5 acts plus the first 30 of the Codul muncii's 61 versions), then
appends the rest (1 new act, 31 more versions). It then checks:
- every published SHA and tag is unchanged;
- check_repo finds 0 mismatches over 212 versions, with no backwards or future dates;
- a second append adds nothing;
- two independent runs give the same head.

`test_credit_only.py` covers a law credited for a version that changes no words (a referendum, a ruling): its commit touches no file. Appending the corpus to a build that already holds that commit adds 0 commits, and so does a second append after it is appended. f5e9d64 re-appended it on every run; append.py now also reads the act days in data/commits.csv.

It also ran against lexifina/romania-law `f22df37` (36 acts, 1,289 versions): check 0/0, dry run 0 commits.

The Romania publishing loop (lexifina-cc, alan-laptop) uses it every 5 minutes.
