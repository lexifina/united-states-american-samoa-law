# global-law orchestrator: what runs here and how to resume

Everything here runs outside any Claude session, so closing or reopening a session loses nothing.

| Loop | Script | What it does | Log |
|---|---|---|---|
| repoint | `repoint_loop.sh` → `repoint_fast.py --push` | Every 15 min (or at once when `repoint-now` exists): add new country repos to lexifina/global-law and repin changed ones, one commit per branch per pass; gates each new commit first; runs `tools/verify.py` after a push; writes `heartbeat.json` | `repoint_loop.log` (one summary line a pass), `repoint-last-pass.log` (the last pass in full), `repoint-held.log`, `verify.log` |
| pushwatch | `pushwatch.sh` | The repoint watchdog: a line in `alerts.log` when no pass has completed for 30 min (heartbeat), global-law hasn't been pushed for 60 min, or the loop logs an error | `alerts.log` |
| cpulog | `cpu_log.ps1` | One line a minute (cpu1, cpu5, ram) to `%LOCALAPPDATA%\gitlaw-cpu.log`, which the scrapers read to pace themselves | `..\gitlaw-cpu.log` |

State that persists between runs: the global-law clone `%LOCALAPPDATA%\gl-repoint`, plus the caches `gl-repoint-tips.json`, `gl-repoint-names.json` and `gl-repoint-probes.json` beside it. Each pass is stateless beyond these, so a killed pass just reruns.

## The repoint pass (since 2026-11-04 evening)

1. Fetch global-law main (and global-law-preview main), list the org's `*-law` repos, read each corpus's tips.
2. Candidate pins: every corpus whose main (or preview) moved, unless it is in `repoint-hold.txt` (people curate it; the loop never writes it) or the GitHub compare API says it is not a fast-forward. New corpora: placed by `repoint-placement.json`, then the repo's `corpus.json` path, then the slug.
3. Gates (`repoint_gates.py` + `gate_check.py`), parallel (8), time-boxed (fetch 240 s, check 180 s, all gates 540 s): global-law main's `tools/check_corpus.py` at the new commit, on a blob-less bare clone kept in `%LOCALAPPDATA%\gl-repoint\.git\gate-clones\<repo>.git`. Held when the new commit has a fatal problem, or more stale-HEAD files (check 11: "HEAD must still equal the text in force", check_corpus's `stale_at_head`) than the commit pinned now. Problems already true at the pin do not hold. A held corpus is skipped for that pass only, with the reason in `repoint-held.log` (`gate: <repo> <old> -> <new>: <reason>`). A first clone that outruns its cap keeps fetching in the background and is checked next pass. `--no-gates` turns them off for one run.
4. One commit per branch with every passing pin, `data/future-pins.tsv` rewritten in it, the .gitmodules/gitlink count check, fast-forward push (never forced; a race is retried from a fresh fetch, up to 3 times), then future-commit tags.
5. After a main push: global-law's `tools/verify.py --remote --github-heads` at the pushed commit (written to `gl-repoint\tools\verify.py`; incremental from its checkpoint in `gl-repoint\.git\global-law-verify\verified.json`; 600 s cap). Output in `verify.log`; a failure goes to `alerts.log` once per distinct problem.
6. `heartbeat.json`: `at`, `result` (pushed / nothing to do / held only / push failed / error), `last_success_at`, `last_push_at`, counts (moved, added, gate checked/passed/held, hold list), the held corpora with reasons, the last verify.

## Start / check / stop

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "$env:LOCALAPPDATA\gitlaw-orchestrator\start.ps1"   # idempotent
Get-Content "$env:LOCALAPPDATA\gitlaw-orchestrator\repoint_loop.log" -Tail 4
Get-Content "$env:LOCALAPPDATA\gitlaw-orchestrator\alerts.log" -Tail 5
Get-Content "$env:LOCALAPPDATA\gitlaw-orchestrator\heartbeat.json"                   # last pass: when, result, counts
New-Item -ItemType File "$env:LOCALAPPDATA\gitlaw-orchestrator\repoint-now"           # run a pass now (within 30 s)
powershell -NoProfile -ExecutionPolicy Bypass -File "$env:LOCALAPPDATA\gitlaw-orchestrator\start.ps1" -Only repoint,pushwatch
python -X utf8 "$env:LOCALAPPDATA\gitlaw-orchestrator\repoint_fast.py"                # dry run: no commit, push or heartbeat
powershell -NoProfile -ExecutionPolicy Bypass -File "$env:LOCALAPPDATA\gitlaw-orchestrator\stop.ps1"
```

They do not survive a reboot: run `start.ps1` after one. A sleep only pauses them. `start.ps1` prints the repoint heartbeat's age and says STALLED past 30 min.

Bash loops are started through `launch_hidden.py` (pythonw, CREATE_NO_WINDOW), so no console window opens for them or their git/python children. To stop only the pointer loop: create `stop-repoint` (it exits within 30 s between passes); `start.ps1` removes the stop file of each loop it starts.

Backups from the 2026-11-04 batching change: `*.bak-batch` beside each edited file (`repoint_fast.py`, `repoint_loop.sh`, `start.ps1`, `stop.ps1`, `pushwatch.sh`, `RESUME.md`).

## In a new Claude session

1. Run `start.ps1` (harmless if they are already running).
2. Re-arm a Monitor on new alert lines: `tail -n0 -F "$LOCALAPPDATA/gitlaw-orchestrator/alerts.log"`.
3. The scraper sessions (gitlaw-scraper-dell, gitlaw-scraper-hp-omen) run their own autopush loops independently; message them by name.
