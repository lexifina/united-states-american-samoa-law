# global-law orchestrator: what runs here and how to resume

Everything here runs outside any Claude session, so closing or reopening a session loses nothing.

| Loop | Script | What it does | Log |
|---|---|---|---|
| repoint | `repoint_loop.sh` → `repoint_fast.py --push` | Every ~30 s: add new country repos to lexifina/global-law and repin changed ones; pushes main and preview | `repoint_loop.log` |
| pushwatch | `pushwatch.sh` | Appends a line to `alerts.log` if global-law hasn't pushed for 15 min or the loop logs an error | `alerts.log` |
| cpulog | `cpu_log.ps1` | One line a minute (cpu1, cpu5, ram) to `%LOCALAPPDATA%\gitlaw-cpu.log`, which the scrapers read to pace themselves | `..\gitlaw-cpu.log` |

State that persists between runs: the global-law clone `%LOCALAPPDATA%\gl-repoint`, plus the caches `gl-repoint-tips.json`, `gl-repoint-names.json` and `gl-repoint-probes.json` beside it. Each pass is stateless beyond these, so a killed pass just reruns.

## Start / check / stop

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "$env:LOCALAPPDATA\gitlaw-orchestrator\start.ps1"   # idempotent
Get-Content "$env:LOCALAPPDATA\gitlaw-orchestrator\repoint_loop.log" -Tail 4
Get-Content "$env:LOCALAPPDATA\gitlaw-orchestrator\alerts.log" -Tail 5
powershell -NoProfile -ExecutionPolicy Bypass -File "$env:LOCALAPPDATA\gitlaw-orchestrator\stop.ps1"
```

They do not survive a reboot: run `start.ps1` after one. A sleep only pauses them.

## In a new Claude session

1. Run `start.ps1` (harmless if they are already running).
2. Re-arm a Monitor on new alert lines: `tail -n0 -F "$LOCALAPPDATA/gitlaw-orchestrator/alerts.log"`.
3. The scraper sessions (gitlaw-scraper-dell, gitlaw-scraper-hp-omen) run their own autopush loops independently; message them by name.
