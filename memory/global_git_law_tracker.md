---
name: global-git-law-tracker
description: "Dashboard artifact tracking global git law (countries, commits, MB, country repos, US titles, UK docs) vs forecast and target at 30-min snapshots; collector script in session scratchpad"
metadata:
  type: project
---

Built 2026-10-28 at the user's request: "Global Git Law Tracker", https://claude.ai/artifact/KiqJgRjPMc88zFvbvDoFMr (Dashboard type, owner john@lexifina.com, shared with Anyone at Lexifina).

- Metrics: countries with law in git (target 193 UN states), law commits, provision files, law MB (no target), country scaffold repos (target 209 from scripts/world-law/countries.json), pushed repos, US Code titles built (target 53, from src/backend/.us_code_history/logs/status.txt), UK docs fetched (target = docs listed in ~/Documents/uk-law-data/uk.sqlite).
- Predicted = straight-line fit over the last 3 h of snapshots; "predicted for now" is the forecast made at the snapshot before.
- Collector: `collect.py` in session 0c08570e's scratchpad (`gitlaw-tracker/`), appends snapshots.jsonl, writes out/{metrics,series,corpora}.json, uploaded as dataset files. Refresh was a session-only cron (every 30 min); when that session ends, the dashboard goes stale until someone reruns it.
- Points before 15:46 UTC 28 Oct are reconstructed from .git birth times (= last rebuild), so early history understates.
- New corpora: add to CORPORA in collect.py (stub repos in ~/Documents/world-law-repos are picked up automatically once they have ≥2 commits).

Related: [[git-for-law]], [[global-law-repo]], [[small-country-law-repos]].
