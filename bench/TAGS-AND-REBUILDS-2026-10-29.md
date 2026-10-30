# Tag pushes and rebuild hot spots (2026-10-29)

Scripts and raw results are in `bench/tags-and-rebuilds/`. Nothing was pushed to any lexifina country repo. Tag tests
used a throwaway private repo, lexifina/tagpush-bench, left for Alan to delete. Rebuilds wrote only into the scratchpad
or a temporary folder, deleted afterwards.

**Machine state for every number here:** total CPU averaged 99.9% (typeperf, every 5 s), because of other sessions'
builds. Fixed per-process costs (TLS set-up, credential helper, git start-up) are inflated by that, and repeat runs
vary by about ±30%. **Windows Defender real-time protection is off on this machine** (`Get-MpComputerStatus`:
RealTimeProtectionEnabled, OnAccessProtectionEnabled and IoavProtectionEnabled all False; tamper protection on). No
settings were changed.

## Headline

1. **Tag pushes cost 100–250 s per 1,000 tags here, and the cost is per ref, not per push.** A 1,000-tag push costs
   about 34 s client-side and 34 s on GitHub's side, against about 13–25 s for an empty push. Bigger batches only
   amortise the fixed part. The 80-tag batches in push_clean.py cost 490–680 s per 1,000 tags. A 1,000-tag glob batch
   costs about 100 s.
2. **Command-line refspecs scale badly.** git matches each explicit refspec against every local ref, so a 300-refspec
   push from a repo with 19,682 tags spends 10–25 s in matching on the client alone. A glob refspec over a staging
   namespace, or a push from a bare repo holding only that batch's refs, avoids the matching and the 32,767-character
   limit.
3. **There were no GH013 or "(failed)" rejections** in any of the pushes so far (see the tables).
4. **Rebuilds are CPU-bound in Python parsing, then single-threaded git.** Denmark took 634 s: parse and diff 396 s
   (4 workers), fast-import 149 s, checkout 65 s. Ireland took 495 s, with its PDF readings already cached: build_act
   348 s (serial), write_repo 123 s.
5. **Two memo caches cut Denmark's worker CPU by 45%,** with identical results. A regex anchor plus a skip cuts
   Ireland's hyphen pass by 4×. Running Ireland's acts in a pool of 4 is the other big gain.
6. **Defender costs nothing measurable right now.** MsMpEng averaged 0.3–0.4% of one core during the builds, and the
   Denmark build was no slower in a Documents folder (615 s) than in the scratchpad (634 s). If real-time protection
   is switched back on, re-measure: the checkout stage (38k small files) is where it would bite.

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
| (wave 2 rows still running) | | | | | | | | | | |

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
