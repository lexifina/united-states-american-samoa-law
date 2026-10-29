# Czechia (gitlaw-CZ, world wave): progress

Status 2026-10-28: **stopped before building, on purpose. Phase 1 is already covered by the existing repo.** No corpus.json is
written here. Do not add one without the coordinator's decision (see "Why no corpus.json").

## What I found

`lexifina/czechia-law` is not a scaffold. Its `main` already holds a complete history built today by another session,
with its own builder (`tools/build/` in that repo: ingest.py, build.py, render.py, check_repo.py, release.py), from
e-Sbírka's open datasets (opendata.eselpoint.cz, 45 files, 2.3 GB, Last-Modified 2026-10-28):

- 18,573 acts of the Sbírka zákonů, 52,732 consolidated versions, 33,780 commits (33,640 on `main`, 139 on `future`), 242 tags, history from 1918.
- check_repo.py: 52,732 versions checked, 0 differ, 0 fidelity mismatches; 9,641 act ends checked, 0 wrong; 7/7 repo tests; two builds hash-identical (REPRODUCE.md).
- Head of `main`: 35e53bb38 (docs commit dated 2026-10-28); `law-head` 138211d2e. The scaffold commit survives only on `sync/main` (691c50a66).
- Its README cites `scripts/czechia-law/fetch.sh` and `PROGRESS.md` in the monorepo, but this folder did not exist and no clone of its data is in C:/Users/alany/Documents; the building session's working files are elsewhere.

Phase 1 acts, as they stand in that repo (read from the clone, `git log` with the `In-force` trailer):

| Act | File | Commits | Checked |
| --- | --- | --- | --- |
| Ústava 1/1993 Sb. | `sb/1993/1.md` | 12: 1992-12-28 (promulgated), 1993-01-01, 347/1997 (2000-01-01), 300/2000, 448/2001, 395/2001, 515/2002, 319/2009, 71/2012 (two days), 98/2013, 87/2024 (2026-01-01) | sequence matches the known constitutional amendments |
| Občanský zákoník 89/2012 Sb. | `sb/2012/89.md` | 25 (latest 2026-01-01: 333/2025, 290/2025, 270/2025, 268/2025, 176/2025) | builder's own byte check |
| Trestní zákoník 40/2009 Sb. | `sb/2009/40.md` | 60 (one 2027-01-01 version on `future`) | builder's own byte check |

`tools/czlaw.py on 2013-03-07 sb/1993/1.md` works from the clone.

## Why no corpus.json

autopush.py picks up any `scripts/<slug>-law` with corpus.json or corpus.d/, rebuilds `C:/Users/alany/Documents/czechia-law`
with gitlaw_common, and once PUBLISH exists pushes `main` with `--prune` on tags. A 3-act gitlaw_common corpus would
replace the 18,573-act verified history and delete its 242 tags. Even without PUBLISH it would push a `preview` branch and
a `wip` branch into a repo built by a different builder. This folder holds only this file, so autopush ignores it
(czechia is not in its COUNTRIES list).

## Differences from the wave brief (for the coordinator)

- Future branch is `future`, not `budouci`; the on-date tool is `tools/czlaw.py on`, not `ucinne_k`.
- Layout is one file per act (`sb/<year>/<n>.md`), one fragment per line, not one file per provision.
- Commit dates: noon Prague, `In-force:` trailer; pre-1970 clamped, as in the shared rules.
Renaming would need the other session's builder and data, and a rebuild of the whole corpus.

## Checklist

- [x] Read WAVE.md, FANOUT.md, BRIEF.md, SCHEMA.md, git_for_law.md
- [x] Cloned lexifina/czechia-law to C:/Users/alany/Documents/czechia-law (read-only use; nothing committed or pushed)
- [x] Phase 1 acts confirmed present with dated histories
- [ ] Coordinator decision: keep the existing repo as is (recommended), or rename `future` → `budouci` and add a `ucinne_k` wrapper in the owning session's builder

Requests made: 0 to e-Sbírka, 0 WebSearch. Cache: none.
