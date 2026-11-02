# Tag pushes and rebuild hot spots (2026-10-29)

Status: complete (runs finished 2026-10-30 02:07).

Scripts and raw results are in `bench/tags-and-rebuilds/`. Nothing was pushed to any lexifina country repo. Tag tests
used a throwaway private repo, lexifina/tagpush-bench, left for Alan to delete. Rebuilds wrote only into the scratchpad
or a temporary folder, deleted afterwards.

**Machine state for every number here:** total CPU averaged 99.9% (typeperf, every 5 s), because of other sessions'
builds. Fixed per-process costs (TLS set-up, credential helper, git start-up) are inflated by that, and repeat runs
vary by about ±30%. **Windows Defender real-time protection is off on this machine** (`Get-MpComputerStatus`:
RealTimeProtectionEnabled, OnAccessProtectionEnabled and IoavProtectionEnabled all False; tamper protection on). No
settings were changed.

## Headline

1. **push_clean.py's 80-tag command-line batches cost 530–680 s per 1,000 tags,** which is about 3–3.7 hours for Hong
   Kong's 19,682 tags. **Batches of 1,000 from a tag-only bare repo, 4 pushes at a time, cost 42 s per 1,000,**
   about 14 minutes for Hong Kong: a 13–16× gain. That was measured with 37k refs already on the remote and the
   machine's CPU at 100%.
2. **The cost is per ref, on both ends,** and it grows with the refs already on the remote: about 3.6 s more per
   1,000-tag push for every 1,000 refs there. An empty push costs 13–25 s. Big batches only amortise that fixed part.
3. **Command-line refspecs scale badly.** git matches each explicit refspec against every local ref, so a
   300-refspec push from a 19,682-tag repo spends 10–25 s matching on the client alone. A glob refspec avoids the
   matching and the 32,767-character limit. Pushing from a bare repo that holds only the batch's refs also avoids
   making the client walk 19,682 local refs.
4. **Big pushes fail with "Timed out validating the rule", not GH013.** With 25k refs on the remote, a 3,000-ref push
   ran about 7.5 minutes and was rejected whole, and so was its retry. No push printed GH013 or a bare "(failed)".
   Keep pushes to ≤1,000 refs.
5. **Parallel pushes to one repo scale:** 2× throughput with 2, about 2.6× with 4, with no rejections.
6. **Rebuilds are CPU-bound in Python parsing, then in single-threaded git.** Denmark took 634 s: parse and diff
   396 s (4 workers), fast-import 149 s, checkout 65 s. Ireland took 495 s with its PDF readings cached: build_act
   348 s (serial), write_repo 123 s. Two memo caches cut Denmark's worker CPU by 45% with identical output. Ireland's
   hyphen regex is 4× faster with a skip and an anchor, and its acts can run in a pool of 4.
7. **Defender costs nothing measurable now, because real-time protection is off.** MsMpEng averaged 0.3–0.4% of
   one core during the builds. Denmark was no slower in a Documents folder (615 s) than in the scratchpad (634 s).

## A. Tag pushes

**Method.** The source is a bare copy of hong-kong-law-build: main has 10,357 commits and a 112 MB pack, and there are
19,682 lightweight tags, every one on main. main was pushed first (47.9 s), as push_clean.py does, so every tag push
after that is a ref-only update. Each config pushes copies of real tags under its own prefix
(`refs/tags/<config>/<original name>`). `bench_tags.py` records each push's seconds and stderr, then checks each
config's refs with ls-remote ("on remote").

Methods compared:
- **cli**: explicit `src:dst` refspecs on the command line, as push_clean.py does now.
- **glob**: the batch is written to `refs/stage/<config>/<i>/*` with `git update-ref --stdin` (no command-line
  limit), pushed with one refspec `refs/stage/<config>/<i>/*:refs/tags/<config>/*`, then removed.
- **bare**: a fresh bare repo per batch, borrowing the source's objects through `objects/info/alternates`, holding only
  that batch's tags, pushed with `refs/tags/*:refs/tags/<config>/*`.
- **auth modes**: the default (Git Credential Manager, OpenSSL); `h`, an `Authorization` header passed as config
  through `GIT_CONFIG_COUNT`/`GIT_CONFIG_KEY_n`/`GIT_CONFIG_VALUE_n` environment variables (no credential helper, no
  401 round trip, and the token never on a command line); `hs`, that plus `http.sslBackend=schannel`.

`git push origin 'refs/tags/*:refs/tags/*'` straight from a build folder is the glob method with the whole tag set as
one batch (the `glob19682` row).

| Config | Method | Batch | Auth | Parallel | Tags | Median s per push | s per 1,000 tags | On remote | GH013 | (failed) |
|---|---|---|---|---|---|---|---|---|---|---|
| cli80_n800 | cli | 80 | GCM | 1 | 800 | 56.1 | 678 | 800 | 0 | 0 |
| cli80_h_n800 | cli | 80 | header | 1 | 800 | 41.8 | 531 | 800 | 0 | 0 |
| cli300_n1500 | cli | 300 | GCM | 1 | 1,500 | 70.7 | 249 | 1,500 | 0 | 0 |
| cli300_h_n1500 | cli | 300 | header | 1 | 1,500 | 71.9 | 243 | 1,500 | 0 | 0 |
| glob300_n1500 | glob | 300 | GCM | 1 | 1,500 | 46.7 | 156 | 1,500 | 0 | 0 |
| glob1000_n3000 | glob | 1,000 | GCM | 1 | 3,000 | 93.6 | 102 | 3,000 | 0 | 0 |
| glob3000_n6000 | glob | 3,000 | GCM | 1 | 6,000 | 274.5 | 98 | 6,000 | 0 | 0 |
| bare3000_n6000 | bare | 3,000 | GCM | 1 | 6,000 | 168.2 | 57 | 6,000 | 0 | 0 |
| glob1000_hs_n3000 | glob | 1,000 | header+schannel | 1 | 3,000 | 151.5 | 164 | 3,000 | 0 | 0 |
| glob3000_hs_n6000 | glob | 3,000 | header+schannel | 1 | 6,000 | 460.7 | (313) | **0** | 0 | 0 |
| glob1000_hs_p2_n6000 | glob | 1,000 | header+schannel | 2 | 6,000 | 157.8 | 83 | 6,000 | 0 | 0 |
| glob1000_hs_p4_n6000 | glob | 1,000 | header+schannel | 4 | 6,000 | 175.7 | 63 | 6,000 | 0 | 0 |
| **bare1000_hs_p4_n6000** | **bare** | **1,000** | header+schannel | **4** | 6,000 | 124.0 | **42** | 6,000 | 0 | 0 |
| glob19682_hs_n19682 (`refs/tags/*` in one push) | glob | 19,682 | header+schannel | 1 | 19,682 | >2,766 (stopped) | – | **0** | 0 | 0 |

The remote held these many refs before each wave-3 row: p2 25,263, p4 31,263, bare p4 37,263 and the full set 43,263.

**The whole set in one push does not work.** `refs/tags/*` (19,682 refs, 43,263 already on the remote) was still
uploading or validating after 46 minutes, with nothing landed, and was stopped. Extrapolating from the 3,000-ref
rejections, it would have ended in the same rule-validation timeout. `git push origin 'refs/tags/*:refs/tags/*'` from
a build folder is only safe for small tag sets: a few hundred tags on a fresh repo.

**Parallel pushes scale.** At 1,000 refs a push, each push took about as long with 2 or 4 running (158 s and 176 s,
against 152 s alone at a similar remote size), so throughput went up 2× with 2 pushes and about 2.6× with 4. Six
batches over 4 workers leaves the last round half empty. GitHub did not serialise the concurrent pushes to one repo,
and none of them was rejected.

**The bare tag-only repo beats staging in the build repo.** At 3,000 a push and 1 at a time, bare took 168 s a push
where glob took 274 s. At 1,000 a push and 4 at a time, bare took 124 s where glob took 176 s, on a bigger remote.
Every ref in the pushing repo costs client time, and a bare repo holding only the batch (objects borrowed through
`alternates`) has 1,000 refs instead of 19,682.

**The remote's ref count matters as much as the method.** The rows ran in table order, and each one added its tags
to the remote. The remote held 163 refs before the first row and 25,263 before glob3000_hs. A 1,000-tag glob push
took 93.6 s with 6,263 refs on the remote and 151.5 s with 22,263, so a push gets roughly 3.6 s slower for every 1,000
refs already there, and the auth mode makes no visible difference at that size. Read rows against their
`remote_refs_before` in `tags.jsonl`, not against each other alone.

**"Timed out validating the rule": the real failure mode.** With 25k refs on the remote, both 3,000-ref pushes of
glob3000_hs were rejected whole after about 7.5 minutes (460.7 s and 441.8 s), and each one-time retry was rejected
again (431.7 s and 428.7 s): `! [remote rejected] ... (Timed out validating the rule.)` on every ref, so nothing
landed. Earlier 3,000-ref pushes, with 9–15k refs on the remote, went through in 148–274 s. The repo has no rulesets
(a private repo on the free plan cannot have any), so this is GitHub's own per-push rule check running out of time.
No push printed GH013 or a bare "(failed)". push_clean.py's halving retry would cope, but only after about 15 minutes
lost per batch. Keep each push well under about 5 minutes: ≤1,000 refs once a repo holds about 10k tags.

Notes:
- A first attempt at the glob configs pushed nothing: a text-mode pipe on Windows turned `\n` into `\r\n`, and
  `update-ref --stdin` refused it. Those configs became a measure of the empty push (13.0 s, 13.1 s and 25 s), and were
  run again after the fix. Pass bytes to `update-ref --stdin`.
- **Where a single-tag push goes** (GIT_TRACE2_PERF, default auth): 31 s in all. About 14 s passes before the first
  credential call (TLS set-up 2.6 s, plus process start-up under load), 2.6 s goes on two Git Credential Manager calls,
  10 s on listing remote refs, and 13 s on send-pack, 6 s of it waiting on the server. curl to the same URL answers in
  0.2 s, so the network is not the cost.
- **ls-remote with each auth mode** (3 runs each): OpenSSL + GCM took 8.4–15.9 s, schannel 3.8–7.9 s, header 2.2–11.6 s,
  and schannel + header 2.1–3.2 s.
- **Where a 1,000-tag glob push from a tag-only bare repo goes** (`hs` auth, about 25k refs already on the remote):
  71.7 s in all. Remote refs were listed in 0.8 s. send-pack then worked locally for 34 s before posting, pack-objects
  took 0.7 s, and the 124 KB upload was sent at once. GitHub took 34 s to answer for 1,000 ref updates.
- **The same push to a local `file://` bare repo, with no network:** 21.0 s against a remote holding only main, and
  51.6 s against one holding 20,000 refs. Per-ref work on both ends of git, and the remote's existing ref count, are
  the cost. A remote with tens of thousands of tags makes every later push slower.

## B. Rebuild hot spots

**Method.** `stage_run.py` imports a builder, wraps its stage functions and every `git` subprocess with wall-clock
timers, and runs its `main()` unchanged. Hot functions inside stages come from cProfile over a serial sample: every
14th Denmark act (103 acts) and every 10th Ireland act (60). typeperf sampled MsMpEng and total CPU every 5 s during
each full build.

### Denmark (`build.py --offline --workers 4`): 634 s, 1,432 acts, 12,725 commits, 19,131 tags

| Stage | s | Bound by |
|---|---|---|
| build_all: read + diff in 4 worker processes | 396 | CPU (Python regex, lxml); fetch I/O is 3% |
| git fast-import | 149 | one CPU core in git |
| git reset --hard (writes 38.5k files) | 65 | small-file writes |
| git add + commit (documentation) | 14 | |
| tables, README, gate, compose | 4 | |

Two runs into different folders gave the same main and the same tags (byte-identical history). The output's history
differs from denmark-law-build's current main, which was built from older code or acts.

Worker profile (103 acts, 103 s under cProfile):
- `dkparse.commencement` takes 43 s (42%). It is called 6,158 times, and on each call it re-splits and re-matches every
  sentence of the amending act. Only 2,904 calls have distinct arguments.
- `dkparse.lines_of` takes 43 s (42%). It is called 1,494 times, but only 745 documents are distinct: the same HTML is
  parsed by lxml twice (`act_norm` and `analyse_act` both call it).
- **Measured fix** (`memo_dk.py`, patched from outside, builder unchanged): memoise `lines_of` on the HTML and
  `commencement` on its arguments. The sample went from 51.3 s to 28.1 s (**−45%**), with identical results. Expected
  build_all: about 396 → 220 s.

fast-import: replaying the history's 168 MB stream into an empty repo took 142 s. It took 135 s at compression 1 and
depth 10, 211 s with `--depth=0` (and a 432 MB pack), 145 s with `--big-file-threshold=1`, and 145–147 s with 1 MB or
64 KB mmap windows. Deltas, zlib and mmap are not the cost. The root tree is 96 KB (1,440 act folders) and is rewritten
on every one of the 12.7k commits, which is about 1.2 GB of tree data to hash, deflate and delta. fast-import is
single-threaded. Only a different layout (folders sharded under a prefix) would shrink that, and the layout is part
of the published record, so this is noted rather than recommended.

checkout: `git reset --hard main` writes 38.5k files only so that the documentation commit can be made with
`git add -A`. Writing the documentation files into the fast-import stream as its last commit, and checking out
afterwards only if a working tree is needed, saves about 65 + 14 s (12%).

### Ireland (`build.py --offline`, run with the PDF readings cached): 495 s, 594 acts, 3,617 commits, 3,709 tags

| Stage | s | Bound by |
|---|---|---|
| build_act, serial (load_versions 220 s inside it) | 348 | CPU (Python regex) |
| write_repo: git reset --hard | 52 | small-file writes |
| write_repo: git fast-import | 43 | git |
| preparse: re-reads and re-hashes every revision PDF to see whether it is read | 23 | I/O + sha256 |
| history: the version list, read twice per act (1,200 calls) | 21 | |
| gate_published, tables, add, commit | 18 | |

Profile (60 acts, 33.5 s under cProfile): `re.sub` is 15 s of self time (45%). Most of it is the line-end-hyphen pass
in `load_versions`, `re.sub(r"([\w'-]*\w)" + HY + r'(\w+)', ...)` over every unit of every version. It backtracks
over every word, although only 1,144 of 6,201 units hold a mark. Measured on 6,201 units (`rx.py`): as built 2.84 s, with a
word-start anchor `(?<![\w'-])` 1.28 s, and skipping units without the mark 0.70 s, all with identical output. Next
come `canon_text` (6.5 s, 19%) and the word-set build (4.7 s, 14%). Both are pure functions of the cached reading, so
they can be cached with it.

**PDF reading, when PARSER is bumped:** a peer's real build re-read 2,498 PDFs with 4 reader processes in about 11
minutes (23:34–23:45, from the cache files' times), about 3.8 PDFs a second. That is the cold cost of every parser
bump. My first attempt duplicated that work and was stopped. It then waited for the peer's cache, so the 495 s above
is the warm cost.

**Long paths:** Ireland cannot build into a folder whose path is longer than about 90 characters. The longest file
path inside the repo is about 166 characters (a regulations slug), `LongPathsEnabled` is 0 in the registry, and Python's writes fail
past 260 characters (`FileNotFoundError` in write_tables when building into the scratchpad). Denmark sets
`core.longpaths`, but that covers only git's own writes. Keep build folders at short paths such as
`C:\Users\alany\Documents\<name>`.

### Expected gains

| Change | Where | Expected saving |
|---|---|---|
| Memoise `lines_of` and `commencement` (measured −45% of worker CPU) | Denmark | build_all 396 → ~220 s |
| Documentation files in the fast-import stream; no `reset --hard` | Denmark, Ireland | 65–80 s; 50–55 s |
| Run `build_act` in a pool of 4 (offline, pure CPU) | Ireland | 348 → ~100–120 s |
| Hyphen regex: skip units without the mark, anchor at word start | Ireland | about 4× on the pass, ~80–100 s serial |
| Cache `canon_text` and the word set with the parsed reading | Ireland | ~30% of load_versions |
| Keep a url→sha index for the cache; read `history` once per act | Ireland | ~30–40 s |

Denmark comes to about 634 → ~400 s, and Ireland to about 495 → ~200 s, before any tag push.

### Defender

| Run | Output folder | Wall | MsMpEng mean (% of one core) | MsMpEng max | Total CPU |
|---|---|---|---|---|---|
| Denmark | scratchpad (AppData\Local\Temp) | 634 s | 0.34 | 1.9 | 99.97% |
| Denmark | `C:\Users\alany\Documents\_bench-tmp-dk-out` (deleted afterwards) | 615 s | 0.37 | 9.0 | 99.99% |
| Ireland | `%TEMP%\ieb` (deleted afterwards) | 495 s | 0.28 | 1.2 | 99.92% |

With real-time protection off, Defender's share of wall time is nil here. The 3% gap between the two Denmark runs is
noise, and it goes the other way: the Documents run was faster.

## Recommended settings

**Tag pushes** (for push_clean.py; nothing was changed):
1. **Push batches from a temporary bare repo.** Give it `objects/info/alternates` pointing at the build's objects,
   write the batch's tags into it with `git update-ref --stdin` (as bytes with LF line ends; a text-mode pipe on
   Windows breaks it), and push `refs/tags/*:refs/tags/*`. Keep explicit refspecs with `--force-with-lease` only for
   the few tags that move.
2. **Batch 1,000.** Drop to 500 once the remote holds about 30k refs, and never 3,000 or more: those hit the
   rule-validation timeout.
3. **Run 4 pushes at once** to the same repo, keeping push_clean's halving retry for rejections.
4. **Auth through environment config, not the credential manager.** Set `GIT_CONFIG_COUNT`/`KEY`/`VALUE` to
   `credential.helper=` and `http.https://github.com/.extraheader=Authorization: Basic <x-access-token:token>`, plus
   `http.sslBackend=schannel`. That makes ls-remote 2–3 s instead of 8–16 s and keeps the token off command lines. It
   matters for small batches, and barely at 1,000.
5. **Expect:** Hong Kong's 19,682 tags in about 14–21 minutes instead of about 3–3.7 hours. Tasmania's 9,628 should
   take about 7–10 minutes.

**Rebuilds:**
1. **Denmark:** memoise `dkparse.lines_of` (on the HTML) and `commencement` (on its arguments, per amending act).
   That was measured at −45% of worker CPU with identical results.
2. **Both:** write the documentation files as a last commit in the fast-import stream, and drop
   `reset --hard` / `add -A` / `commit`. That saves 65–80 s for Denmark and 50–55 s for Ireland, and makes builds
   work without a working tree (check out only when a check needs files).
3. **Ireland:** run `build_act` over a pool of 4 processes (offline, pure CPU, about 348 → ~100 s). Fix the hyphen
   pass: skip units without the mark and anchor at word start (4× on that pass). Cache `canon_text` and the word set
   with the parsed reading. Read `history` once per act, and keep a url→sha index so preparse need not re-hash every
   PDF.
4. **Keep build folders at short paths:** Ireland fails past about 90 characters of folder path
   (`LongPathsEnabled` = 0).
5. **Defender:** nothing to do while real-time protection is off. If it comes back on, re-measure the checkout stage
   first, since that is the 38k-small-file step. Exclusions need admin and were not touched.
6. **Workers:** Denmark at 4 workers on a fully loaded machine spends 396 s in the pool. The memo fix gains about as
   much as 4 → 8 workers would, without taking more of the shared CPU.
