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
