# Resuming the South America git-law run

The country agents are background sub-agents of one Claude Code session ("gitlaw-south-america-max-speed"). If that session closes, they stop. Everything they made is on disk, and in GitHub up to their last push. Use this file to restart all 12 from where they stopped.

## 1. Check the state

```sh
python -X utf8 scripts/south-america-law/status.py --remote
```

- The coordinator backup is branch `wip-south-america` on lexifina/global-law. It holds the shared builder, the plan, the brief, and every country's scripts and PROGRESS.md (no caches). If this machine lost files, restore them from it.
- Each country may also have its own `wip` branch on lexifina/<slug>-law.
- Download caches live only on this machine, in `scripts/<slug>-law/.cache`. If they're lost, `fetch.py` refetches them.

## 2. Relaunch every country agent (one prompt each, in parallel)

Use this prompt, filling in the slug and code:

> You are gitlaw-<CODE>, resuming an interrupted run. Read C:/Users/alany/Documents/lexifina/scripts/south-america-law/BRIEF.md (including "Known pitfalls") and follow it. Then read scripts/<slug>-law/PROGRESS.md: it records what was done, the sources, the decisions and the next step. Continue from there.
> - Don't refetch what is already in .cache.
> - Don't redo finished steps.
> - Push `wip` first, then go on to build, check and push `main`.
> - Repo: lexifina/<slug>-law, cloned at C:/Users/alany/Documents/<slug>-law.

| Code | Slug | tz | Language | Future branch | On-date tool |
|---|---|---|---|---|---|
| CL | chile | America/Santiago | es | futuro | on.py |
| UY | uruguay | America/Montevideo | es | futuro | on.py |
| BR | brazil | America/Sao_Paulo | pt | futuro | on.py |
| CO | colombia | America/Bogota | es | futuro | on.py |
| AR | argentina | America/Argentina/Buenos_Aires | es | futuro | on.py |
| PE | peru | America/Lima | es | futuro | on.py |
| PY | paraguay | America/Asuncion | es | futuro | on.py |
| EC | ecuador | America/Guayaquil | es | futuro | on.py |
| BO | bolivia | America/La_Paz | es | futuro | on.py |
| VE | venezuela | America/Caracas | es | futuro | on.py |
| GY | guyana | America/Guyana | en | futuro | in_force_on |
| SR | suriname | America/Paramaribo | nl | toekomst | geldend_op |

The country-specific source notes from the original launch are in each country's PROGRESS.md, and in PLAN.md's country table.

## 3. Restart the coordinator jobs (pushing is owned by these, not by the agents)

- **Auto-push:** `python -X utf8 scripts/south-america-law/autopush.py --loop 180 >> scripts/south-america-law/logs/autopush.log`. Every 3 minutes, for all 12 countries in parallel, it does two things:
  - snapshots each country folder to the `wip` branch;
  - rebuilds and checks each changed corpus.json. Builds go to `main` once `PUBLISH` exists for that country, and to `preview` until then.
- **Coordinator backup, every 5 minutes:** `while true; do bash scripts/south-america-law/backup.sh; sleep 300; done`. It pushes to branch wip-south-america on lexifina/global-law.

### Earlier jobs

- **Backup every 5 minutes:** `bash <scratchpad>/backup.sh`. The script is copied into this folder as `backup.sh`, so a new session can use it with its own scratchpad path.
- **Watcher:** `watch.sh` in this folder. It exits when any corpus, ISSUES.md or main build changes.
- **Builder check:** `python -X utf8 scripts/gitlaw_common/test_build.py` must print OK before agents build.

## 4. Still to do after all countries push

- Add each checked country to `scripts/global-law/common_corpora.json` and rebuild global-law in one go. The new test `test_shared_builder_corpora_match_their_own_on_tool` cross-checks each country against its own `tools/on.py`.
- Write the per-country memories and update `memory/south_america_git_law.md`.
- Build the data-driven /watch reader from `build.py --site-data`. That export is new and must be tested first.
