# Tag pushes and rebuild hot spots (2026-10-29) — PARTIAL, in progress

Scripts and raw results: `bench/tags-and-rebuilds/`. Machine state for every number here: total CPU at 99.97% (mean of
typeperf samples every 5 s) from other sessions' builds, so fixed per-process costs are inflated. Windows Defender
real-time protection is **off** on this machine (`Get-MpComputerStatus`: RealTimeProtectionEnabled False,
OnAccessProtection False; tamper protection on).

## A. Tag pushes (throwaway private repo lexifina/tagpush-bench)

Source: a bare copy of hong-kong-law-build (main, 10,357 commits, 112 MB pack; 19,682 lightweight tags, all on main).
main was pushed first (48 s), as push_clean.py does, so every tag push is a ref-only update. Each config pushes copies
of real tags under its own prefix.

First results (sequential, 1 push at a time):

| Method | Batch | Tags | s per push (median) | s per 1,000 tags |
|---|---|---|---|---|
| refspecs on the command line | 80 | 160 | 46.6 | 492 |
| refspecs on the command line | 300 | 1,500 | 70.7 | 249 |

A single-tag push took 31 s (GIT_TRACE2_PERF): 14 s before the first credential call (TLS setup ~2.6 s, process
start-up under load), 2.6 s in two Git Credential Manager calls, 10 s listing remote refs, 13 s send-pack (6 s of it
waiting on the server). An empty push costs 13–25 s. Network is not the cost: curl to the same URL answers in 0.2 s.

## B. Rebuilds

Denmark (scripts/denmark-law/build.py --offline --workers 4, into the scratchpad): 634 s wall.

| Stage | s |
|---|---|
| build_all (read + diff, 4 worker processes) | 396 |
| git fast-import (12,725 commits, 19,131 tags) | 149 |
| git reset --hard (checks out 38.5k files) | 65 |
| git add + commit (docs) | 14 |
| tables, README, gate | 4 |

More to follow.
