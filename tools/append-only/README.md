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

Without `--corrections`, the last two stop the run. With it, they are fixed by labelled correction commits (below).
Versions in force after `--docs-date` are left for a later run and get appended when their day comes. Existing tags are
never moved; new ones are added.

## Correction commits (`--corrections`)
Format agreed with gitlaw-mcp (2026-11-02), so readers can apply corrections by date. Before anything new, the run
appends **one correction commit per act version** whose text main holds wrongly, or lacks (a back-filled version). They
are ordered by in-force day, then act slug. Each commit's files hold that version's corrected text, for the files that
were wrong. The commit for an act's newest held version also sets back any file the earlier corrections changed at the
tip. So after the corrections, the tip equals the corpus, and the versions appended after them build on corrected text.

Each is made by Lexifina, dated noon on the version's first day, and carries:

```
Kind: correction
In-force: <the version's first day>
Corrects: <act> <from>..<to>     <to> = the day before the act's next version; open (<from>..) if it runs to the present
Files: <path> <path> ...         the files it corrects; its tree holds their text (a path it lacks is removed)
Supersedes: <sha>                the published commit that carried the wrong text for that version, or none
Reason: <one line>               --reason (default "text corrected from the official source"); fixed wording for a
                                 back-fill ("version found late …") and for a tip restore
```

`Files` is one addition to the agreed format. A correction can set a file to the text the tip already has: a version
found late whose text the act came back to. Such a commit changes nothing git can show, so the trailer names the files.
Readers take them from the commit's tree. With no `Files` trailer, a reader takes the files the commit changes.

The subject is `Correction: <act short>, version in force from <day>`. The body says which provisions were wrong and how
(wording differed, missing, published but not in force), which law made the corrected text, and that the history is
not re-sorted. All text comes from the corpus; nothing is edited by hand. No published commit or tag moves, and no tag
is added for a correction. `data/commits.csv` lists them with kind `correction`.

**Reading with corrections applied** (`Reader` in append.py): the text of an act on a day is the commit the `In-force`
trailer picks among the commits that are *not* corrections. Then, file by file and in commit order, each correction
whose `Corrects` range holds the day is applied (its `Files`, as its tree has them). An open range ends the day before the act's next non-correction
commit. The published `tools/on.py` and `tools/check_repo.py` don't apply corrections yet (they still run; they read the
correction commit's tree for days on or after its In-force day). Until they do, check a corrected main with
`check_corrected()`: 0 mismatches read this way, and the tip equal to the corpus on `--docs-date`. With
`--corrections`, append_gate.py checks it that way.

A second run reads main with its corrections applied, finds nothing to correct, and adds nothing. A main that holds
corrections is read the same way without `--corrections` too, so a later run doesn't refuse it.

## Use

`append.py` sits beside the corpus's published `build.py` and `check_repo.py`, and imports both. A published copy has
`check_repo.py`; if `build.py` wants `check.py`, copy `check_repo.py` to `check.py` too. Put `gitlaw_common/private.py`
beside them so the docs commit keeps private files out.

```
git clone https://github.com/lexifina/<corpus> R && cd R && git config core.autocrlf false
git rm -q --cached -r . && git reset -q --hard          # LF working tree (Windows)
GITLAW_VERIFIED_PARTS_ONLY=1 python -X utf8 tools/append.py <scripts/<slug>-law> --repo R --docs-date <retrieved day> [--corrections] [--dry-run]
GITLAW_VERIFIED_PARTS_ONLY=1 python -X utf8 tools/check_repo.py R --corpus <scripts/<slug>-law>/corpus.json   # must be 0/0
# a main holding correction commits: append.check_corrected(R, corpus, docs date) instead (0 mismatches, 0 at the tip)
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

`test_corrections.py` builds a small synthetic corpus as published, then appends a corrected one with
`--corrections`. Its cases are: one unit wrong in the newest version (1 correction commit); one wrong in a middle version
that the next version changes again (the correction plus the tip restore); a 2010 version missing (back-filled); and a
correction followed by a newer version in the same run. For each, without `--corrections` the run refuses and changes
nothing. With it:
- `check_corrected()` finds 0 mismatches and an equal tip;
- reading with corrections applied gives the corpus text before, inside and after the corrected range;
- the plain check_repo still runs;
- the trailers are as above, in in-force order;
- no published SHA or tag changed;
- a second run adds 0;
- another clone of the same head with the same corpus gets the same hashes.

It also ran against lexifina/romania-law `f22df37` (36 acts, 1,289 versions): check 0/0, dry run 0 commits.

The Romania publishing loop (lexifina-cc, alan-laptop) uses it every 5 minutes.
