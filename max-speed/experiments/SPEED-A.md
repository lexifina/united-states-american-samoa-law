# Speed experiments A: machine CPU and the shared builder (alan-dell, 2026-10-29)

Agent A. Machine: alan-dell, 24 cores, 128 GB. Times are local (UK).

## 1. "dllhost.exe is the top CPU process": what it is and what actually uses the CPU

### The dllhost
- PID 29864, started 15:39, about 21,300 CPU-seconds by 23:10 (0.79 of a core on average over 7.5 hours).
- Command line: `C:\WINDOWS\system32\DllHost.exe /Processid:{DFB65C4C-B34F-435D-AFE9-A86218684AA8}`, parent svchost 1992
  (DcomLaunch).
- That AppID has one CLSID, `{AFC7B6DE-D642-41B7-AB0C-A01019510741}` "Plan9FileSystem", in-proc server
  `C:\WINDOWS\System32\vp9fs.dll`; `tasklist /m` also shows `lxutil.dll` and `vmvirtio.dll`. **It is the WSL 9P file
  server:** it serves Windows folders to Linux in the WSL2 VM, which here is Docker Desktop's bind mounts
  (`/run/desktop/mnt/host/c/...`).
- Not thumbnails, not Search, not Defender, not Word COM.
- **What drives it, measured** (dllhost CPU in cores, 15 s windows, containers paused one at a time):

  | State | dllhost cores |
  |---|---|
  | baseline | 0.35 |
  | `lexifina-frontend` paused | **0.01** |
  | frontend back, `mt-fetch` paused | 0.41 |
  | all running | 0.44 |

  The driver is the dev frontend container: `docker-compose.local.dev.yml` (lines 493-495) and
  `src/frontend/Dockerfile.dev.local` set `CHOKIDAR_USEPOLLING=true` and `WATCHPACK_POLLING=true`, so the React dev
  server stats every file of the bind-mounted `src/frontend` and `src/shared/frontend` over 9P, all day, whether or not
  anyone is editing. The law builds do not touch it (they run on Windows Python, not through 9P); the `mt-fetch`
  container (scripts/state-law/mt bind mount) adds nothing measurable.

### The real CPU users
`Get-Process` cannot read MsMpEng's CPU time (a protected process), which is why dllhost looked like the top process.
The `\Process(*)\% Processor Time` counters, summed by name over 5 s at 23:12 (17.9 cores busy in total):

| Process | Cores |
|---|---|
| **MsMpEng (Defender real-time scan)** | **5.0** |
| python (46 processes) | 4.6 |
| vmmemWSL (Docker VM) | 1.3 |
| svchost (103) | 1.2 |
| git (90) | 1.1 |
| find | 0.8 |
| SearchIndexer | 0.7 |
| git-receive-pack | 0.6 |
| dllhost (9P) | 0.5 |

Defender was scanning every file the builds, fetches and git write (hundreds of thousands of small .md files, git
objects, cache files): 28% of the busy CPU, more than all Python together. **At 23:11:50 the Defender log shows
"Real-time Protection ... was disabled"** (event 5001; not done by this agent, which made only read-only queries).
After that MsMpEng dropped out of the top list. Tamper protection is on, so Windows will normally turn real-time
protection back on by itself; it should not stay off.

Windows Search: 181 folders under Documents are already excluded one by one, but `C:\Users\` is included, so every new
folder is indexed. 55 law-related folders under Documents are still indexed today (armenia-law, swiss-law, malta-law,
state-law, global-law-mcp, world-law-repos, ...). SearchIndexer costs about 0.6-0.7 of a core.

### Steps for Alan (nothing below was changed by the agent)
1. **Turn real-time protection back on, with exclusions instead** (needs an elevated PowerShell; with tamper
   protection on, use Windows Security > Virus & threat protection > Manage settings > Exclusions > Add an exclusion
   if the cmdlets are refused):
   ```powershell
   Set-MpPreference -DisableRealtimeMonitoring $false
   Add-MpPreference -ExclusionPath 'C:\Users\alany\Documents\lexifina\scripts'
   # the country repo checkouts live as siblings in Documents; one line each, or move them under one parent (step 3)
   Get-ChildItem C:\Users\alany\Documents -Directory -Filter '*-law*' | ForEach-Object { Add-MpPreference -ExclusionPath $_.FullName }
   Add-MpPreference -ExclusionProcess 'C:\Program Files\Git\mingw64\bin\git.exe'
   Add-MpPreference -ExclusionProcess 'C:\Program Files\Git\mingw64\libexec\git-core\git.exe'
   ```
   Narrowest useful choice: exclude the folders the builds write (scripts\*-law\.cache and the country repo
   checkouts), not python.exe. A process exclusion for python.exe would also skip everything Python downloads, so
   prefer folder exclusions. Excluding git.exe is the common developer setting and covers fast-import and checkout.
   Exclusions only stop real-time scanning of those files; scheduled scans still cover the rest of the disk.
2. **Windows Search:** Settings > Privacy & security > Searching Windows > Advanced indexing options > Modify, and
   untick `C:\Users\alany\Documents` (one tick covers all 236 law folders, present and future), or at least the 55
   listed above. Or, if Documents search is not needed at all, stop indexing it entirely this way rather than
   disabling the WSearch service.
3. Optional, makes 1 and 2 one entry each: keep new country repos and build scratch folders under one parent
   (for example `Documents\gitlaw-repos\`) instead of 230 siblings in Documents.
4. **The 9P dllhost:** stop `lexifina-frontend` when no one is working on the web app
   (`docker compose -f docker-compose.local.dev.yml stop frontend`), or slow its polling: add
   `CHOKIDAR_INTERVAL=2000` and `WATCHPACK_POLLING=2000` (watchpack takes a number as the interval in ms) to the
   frontend's environment in docker-compose.local.dev.yml. Saves 0.35-0.8 of a core. That is a repo change, so it is
   only proposed here.

## 2. The shared builder: profile, fixes, timings

Scratch copies only (`scripts/gitlaw_common` copied to a scratch folder; corpora copied without `.cache`/`.tmp*`;
nothing under scripts/ or Documents/<slug>-law was written). Patches in `patches/speed-a/` apply cleanly to the live
tree (`git apply --check`) and are **not applied**. Raw timings: `patches/speed-a/times.jsonl` (`timeit.py`), profiles
with `prof.py` (cProfile).

### Where the time went
- **check.py** ran `git ls-tree` as a new process twice per version (the day and the day before), then read every
  file back through `cat-file`. Process start-up on this loaded Windows machine is 0.1-0.3 s, so a 1,575-version
  corpus (Colombia) took over 10 minutes.
- **build.py**, Uruguay, 27 s: `git checkout -f main` writing 7,118 files, 11-12 s; `docs_files` 9.5 s, nearly all
  `folder.rglob('*')` + `relative_to` over 15,853 paths, because agents' scratch builds (`.tmp-build`, `.tmp-build-2`,
  whole repositories, 7,542 files each) and `.cache` sit inside the country folder and were listed before being
  skipped (chile-law holds 82,072 files, colombia-law 33,947); `git fast-import` packing 2.8 s; three `git
  hash-object` and two `--version` processes 1.4 s. Planning, validation and messages: under 1.5 s in total.

### Fixes (output unchanged)
1. check.py: read each act's tree through the `cat-file --batch` process it already has, cache it per (commit, act),
   and compare **blob ids** (sha1 of `blob <len>\0<text>`, computed in Python) instead of reading contents back.
2. build.py: `os.walk` that prunes the skipped folders instead of `rglob` then skip; same files, same order.
3. build.py: `git -c checkout.workers=0 checkout` (parallel checkout, git 2.32+; here 2.46).
4. build.py: `GITLAW_NO_CHECKOUT=1` skips the checkout altogether. For autopush, which pushes from objects
   (`audit_push` reads objects too). The repo is then `.git` only until `git checkout -f main`.

### Timings (seconds, wall)

| Corpus | Size | build before | build after (checkout) | build after (no checkout) | check before | check after |
|---|---|---|---|---|---|---|
| eswatini (median) | 0.65 MB, 3 acts, 5 versions | 4.6 | | 2.3 | 2.9 | 1.6 |
| uruguay | 5.7 MB, 18 acts, 237 versions | 27.3 (rebuild) / 32.9 (first) | 14.6 (rebuild) / 12.6 (first) | 9.0 (rebuild) / 6.5 (first) | **103.1** | **6.2** |
| colombia | 55 MB, 44 acts, 1,575 versions | 51.1 | | 26.0 | **620.8** | **26.0** |

### Same output, verified
- History commits (main~1) and every tag: identical in all three corpora (uruguay `f38f95fb`, colombia `f5ffa1f3`,
  eswatini `f29df3c9`). The documentation commit differs only in `tools/build.py`, `tools/check_repo.py` and the
  builder blob-hash line of REPRODUCE.md, because the builder's code itself changed. The checked-out working tree of
  the patched build is file-for-file identical to the old one apart from those three files.
- check.py output JSON byte-identical (old vs new) on uruguay clean, on a uruguay corpus with 22 injected changes
  (219 mismatches, same 50 detail lines), and same results on colombia (0 mismatches).

## 3. The autopush loop: per-country time and worker count

### Measured
- Running as `autopush.py --each 60 --workers 8`: 126 country loops; 290 country visits from 21:24 to 23:38 UTC, so
  each country came round about every 35-40 minutes, not every 60 s. Only 2 visits found "unchanged".
- Why everything rebuilds: the rebuild hash covers `gitlaw_common/private.py` and the builder files, so **one edit to
  private.py (last at 23:09) makes every country rebuild**: ~65 corpora at once.
- **wip() costs 6-61 s per visit, every visit, for every country,** even when nothing changed: it lists the whole
  folder (including `.cache`) and runs two git processes per file. Patched (pruned walk; one `hash-object
  --stdin-paths` and one `update-index --index-info` for all files), the same tree id:

  | Folder | files | wip before | wip after | tree |
  |---|---|---|---|---|
  | eswatini | 15 | 6.4 | 0.7 | identical |
  | uruguay | 40 | 23.6 | 1.5 | identical |
  | chile | 61 | 41.1 | 5.0 | identical |
  | colombia | 92 | 61.0 | 4.7 | identical |

- A changed, PUBLISHed country with unverified parts runs build+check up to 4 times per visit (preview and main,
  each built a second time when the check is new, so REPRODUCE.md can quote it). Per visit:

  | Country | before | after (all three patches) |
  |---|---|---|
  | eswatini | 6 + 4×(4.6+2.9) = ~36 s | 0.7 + 4×(2.3+1.6) = ~16 s |
  | uruguay | 24 + 4×(27+103) = ~9 min | 1.5 + 4×(9+6.2) = ~62 s |
  | colombia | 61 + 4×(51+621) = ~46 min | 4.7 + 4×(26+26) = ~3.5 min |

  That matches the observed ~400 s average slot per build visit (8 workers × 134 min / ~160 build visits).

### Recommendation
- **Apply the three patches first;** they cut the loop's work 5-15x, which more workers cannot do on a machine whose
  CPU is already pinned. Each worker is about one core (single-threaded Python plus one git child at a time;
  fast-import overlaps briefly).
- **Workers: 8 now; 6 once patched.** Unpatched, more than 8 only adds contention with the fetch/parse agents. Patched,
  a full rebuild wave of ~65 corpora is ~65 × 60 s / 6 ≈ 11 minutes, and in steady state most visits are wip-only
  (about 1-5 s), so 6 slots keep every country within a few minutes of a change and leave ~18 cores for the agents.
- Keep `--each 60`; with wip at 1-5 s a visit to an unchanged country is cheap.
- Follow-ups not done here: hash only the parts of private.py that change what is published (or rebuild lazily after
  a private.py edit), so one edit does not rebuild 65 countries at once; skip `hash-object -w` when the folder's
  (path, size, mtime) list is the same as last pass.
