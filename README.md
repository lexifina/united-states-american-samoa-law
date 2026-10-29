# world-law-max-speed (private)

How the git-for-law pipeline gets law data fast, and the measurements behind it. **Private by the user's rule:** this
material must not go to global-law, the country repos, the coordinator backups or their git history.

- `bench/BENCHMARKS.md`: every speed-up approach tested and measured (2026-10-29); raw results in `bench/*.json`, each
  from the `bench/*.py` beside it; `bench/modeltest/` holds the Sonnet, Haiku and Opus parsers from the model test.
- `rules/`: the agents' speed rules (FORK.md's FETCH RULE, ALT-SOURCES.md, PEACHJAM.md, and the speed sections of
  BRIEF/FANOUT/WAVE in SPEED-SECTIONS.md).
- `code/`: snapshots of the speed-up code as run on 2026-10-29: `wayback.py` (shared archive.org limiter, Common Crawl
  byte-range fallback, per-host adaptive `host_get`) and `autopush.py` (stepped pushes, worker semaphore). The live
  copies are in the lexifina working tree under scripts/gitlaw_common and scripts/south-america-law.
- `tools/`: the fork session's scan and push scripts.
