# Building on WSL's ext4 disk (wsl_run.py + wsl_build.sh)

A build writes tens of thousands of small files and git objects. On NTFS each one goes through Windows Defender and
the NTFS metadata path; on WSL's ext4 disk it does not. `wsl_run.py` runs the unchanged `build.py`, `check.py` and
`push_clean.py` inside WSL (distro `Ubuntu`), with the build repository at `~/gitlaw-builds/<slug>` on ext4. Inputs
(corpus.json, corpus.d/, repo/, the country's scripts and this builder) are read from `/mnt/c`.

## Commands (from Windows, any shell)

    python scripts\gitlaw_common\wsl_run.py setup                         # once per machine
    python scripts\gitlaw_common\wsl_run.py build <slug> --docs-date D    # = build.py scripts\<slug> --repo ~/gitlaw-builds/<slug> --docs-date D
    python scripts\gitlaw_common\wsl_run.py check <slug> [--write]        # = check.py <that repo> --corpus scripts\<slug>\corpus.json
    python scripts\gitlaw_common\wsl_run.py push  <slug> [--main] [--branch futuro]   # = push_clean.py <that repo> <slug>
    python scripts\gitlaw_common\wsl_run.py git   <slug> log --oneline -3 # git in the WSL build repo
    python scripts\gitlaw_common\wsl_run.py path  <slug>                  # repo path, also as \\wsl.localhost\Ubuntu\...

- `<slug>` is the folder name under `scripts\` (e.g. `chile-law`); a folder path also works, and the slug is its name.
- Every other option is passed through (`--compare`, `--site-data`, `--write`, `--main`, `--branch`). Windows paths in
  options (`C:\...`, or relative paths that exist) become `/mnt/c/...`. `--repo DIR` overrides the build folder (a WSL
  path such as `~/gitlaw-builds/.scratch/<slug>`; a `/mnt/c` path works but loses the speed-up).
- Output and exit codes are those of the wrapped script, so a scraper's existing checks (`mismatches`, exit 1/3) work.
- `GITLAW_*` environment variables (`GITLAW_VERIFIED_PARTS_ONLY`, `GITLAW_NO_CHECKOUT`) are passed on.
- `--time` prints wall and CPU time of the WSL side to stderr.
- From Git Bash, set `MSYS_NO_PATHCONV=1` when passing a WSL path such as `/home/...` (Git Bash rewrites it otherwise).

## What setup does

- `~/gitlaw-builds/.venv` (Python 3.14 from Ubuntu). Ubuntu's python has no ensurepip, so setup downloads the pip and
  `tzdata` wheels with Windows pip and installs them from those files. The builders are standard library only; the one
  package is `tzdata==2026.6`, the version the Windows builders use (`PYTHONTZPATH=''` makes zoneinfo read it, as on
  Windows, so commit times come from the same zone data). Bump `TZDATA_VERSION` in `wsl_run.py` with Windows' tzdata.
- `~/gitlaw-builds/gitconfig`, used as git's global config for everything wsl_build.sh starts (`GIT_CONFIG_GLOBAL`;
  `~/.gitconfig` is not touched): `credential.helper` = the Windows Git Credential Manager
  (`/mnt/c/Program Files/Git/mingw64/bin/git-credential-manager.exe`), so no token is copied into WSL or printed;
  `user.name`/`user.email` copied from the Windows `.gitconfig`, because `private.audit_push` asks
  `git config --global user.email` for the personal address it keeps out of pushes. Rerun setup if those change.
- A `git ls-remote` of world-law-ops proves the credential path.

Per build: `build.py` re-inits the repo, then wsl_build.sh sets `gc.auto=0` and `core.autocrlf=false` in that repo's
own config (never global). History is written by build.py's single `git fast-import` stream, as on Windows. Processes
run under `nice -n 10` (about BelowNormal). `PYTHONDONTWRITEBYTECODE=1` keeps `__pycache__` out of the Windows folders.

## Same results

Validated 2026-11-02 on copies of moldova-law, united-states-texas-law and chile-law (scratch builds, no pushes):
every history commit, every tag and the future branch have the same hashes as the NTFS build, and check.py gives the
same result. The one difference is the documentation commit at the tip of main: REPRODUCE.md records the toolchain
that built it (`- Python 3.12.10; git version 2.46.0.windows.1.` on Windows, `- Python 3.14.4; git version 2.53.0.`
in WSL), so that one file, and therefore main's tip hash, differ. Consequences:

- Moving a corpus from Windows to WSL changes the docs commit once, as a builder upgrade does. After that, WSL
  rebuilds of the same corpus and docs date give the same main hash every time.
- Don't mix: build a corpus on one side only, or its main tip flips between the two docs commits.

Measured the same evening, one run each, machine busy with scrapers. Windows side at BelowNormal in a job object
(CPU = python + every git child); WSL side under nice 10, `--time`:

| Corpus | Step | NTFS wall / CPU | WSL ext4 wall / CPU |
| --- | --- | --- | --- |
| moldova-law (3 commits) | build | 133.7 s / 2.2 s | 2.3 s / 3.4 s |
| united-states-texas-law (4 versions) | build | 136.9 s / 7.4 s | 4.0 s / 11.8 s |
| | check | 27.4 s / 0.8 s | 1.7 s / 0.3 s |
| chile-law (127 MB, 4,622 versions, 3,400 commits, 6,931 tags) | build | 175.8 s / 49.7 s | 27.0 s / 30.6 s |
| | check | 56.3 s / 15.7 s | 35.0 s / 23.8 s |

The NTFS builds spend a near-constant ~2 minutes waiting (file creation, Defender, checkout) even for tiny corpora;
on ext4 that goes away. check.py is mostly Python work, so it gains less.

## Adoption steps for a scraper

1. `python scripts\gitlaw_common\wsl_run.py setup` (once per machine; safe to rerun).
2. Replace `python -X utf8 scripts/gitlaw_common/build.py scripts/<slug> --repo C:\Users\alany\Documents\<slug>-build ...`
   with `python scripts\gitlaw_common\wsl_run.py build <slug> ...` (drop `--repo`).
3. Replace `check.py <repo> --corpus ...` with `wsl_run.py check <slug> [--write]`, and
   `push_clean.py <repo> <slug> ...` with `wsl_run.py push <slug> ...` (same fast-forward-only path; pushes go from the
   ext4 repo through the Windows credential manager).
4. Anything else that reads the build repo (append.py, audits, `git log`): use `wsl_run.py git <slug> ...`, or the
   `\\wsl.localhost\Ubuntu\home\alany\gitlaw-builds\<slug>` path from `wsl_run.py path <slug>` (slow from Windows;
   fine for a few reads, not for a build).
5. Leave the old `C:\Users\alany\Documents\<slug>-build` folder alone until the first WSL build is pushed, then delete
   it to free NTFS space.

Notes: the wrapper's PID is `wsl.exe`; stopping it stops the WSL side. The CPU-load pause rule
(`%LOCALAPPDATA%\gitlaw-cpu.log`) still applies to the caller. Free space: `df -h ~` in WSL (the ext4 VHD grows on
demand and does not shrink by itself).
