---
name: global-law-state-2026-10-29
description: "End-of-day state of global-law and the country-repo privacy cleanup (2026-10-29): what's live, what's stopped, how to resume"
metadata:
  node_type: memory
  type: project
  originSessionId: bf2c37ff-5368-4758-a217-51eee3902b94
  modified: 2026-10-29T20:50:10.279Z
---

State at session end, 2026-10-29 about 20:40 UTC (global-law-main-composer, alan-laptop):

**Repos and visibility**
- lexifina/global-law is PUBLIC. It lost its stars while it was private; GitHub can't restore them.
- Every country and sub-national repo is public.
- Private: world-law-ops, world-law-max-speed, app, publish-test.
- The user decided the licence-flagged repos (Belize, Bangladesh, Pakistan, Newfoundland, NWT) stay public.

**global-law main**
- 143 submodules: 36 were added by a fast-forward commit, 326216d.
- Their laws are NOT yet in the in-force-ordered root history. That needs a full build (scripts/global-law/build.py), which force-pushes global-law: get the user's explicit yes first.
- The pointer loop (repoint_fast.py) is STOPPED.
- To resume, run it from world-law-ops tools/purge-2026-10-29/: `while true; do python -X utf8 repoint_fast.py --push; sleep 20; done`. It uses a persistent clone at C:\Users\alany\gl-repoint.

**The cleanup**
- About 122 country repos plus 91 audit-flagged ones were rewritten to move private files out. Law commits and tags were kept.
- The archive is world-law-ops archive/ and archive2/; some refs are partial.
- Exact pre-cleanup copies of the late repos are bundles at C:\Users\alany\purge-bundles (about 4 GB, alan-laptop only).
- Tools and results are in world-law-ops tools/purge-2026-10-29/ (README there).
- The final audit (audit_final.json) ran before the notes.md fix. Re-run it before trusting it.

**The notes.md bug**
- The old rule's case-insensitive NOTES.md match deleted law notes.md files.
- It's fixed in callback.py and gitlaw_common/private.py (case-sensitive now).
- Restored: pakistan-law wip and australia-western-australia-law wip. Faroe was fixed from alan-dell.
- A confirming re-run of detect_lost.py (bundles first) was NOT done.

**Scrapers**
- gitlaw-scraper-hp-omen (this machine): 10 agents at the cap, push loop `--each 60` with 4 workers.
- gitlaw-scraper-dell: publishing mains in parallel.
- Standing approvals apply (see [[no-destructive-git-without-confirmation]]).
- Bottleneck list NOT yet sent to hp-omen:
  - Brazil planalto at 0 ok (use Arquivo.pt or LexML);
  - Ecuador and Colombia idle;
  - El Peruano throttling;
  - archive.org down to 0.5/s;
  - Austria RIS at 0 ok;
  - the world-law-ops backup push being rejected as non-fast-forward;
  - test InfoLEG bulk dumps.

**Still open**
- Pin global-law on the alan-yahya and lexifina profiles. This is manual; there's no API.
- The Marshall Islands permission email is drafted, not sent.

Related: [[world-law-max-speed-repo]], [[global-law-repo]], [[git-for-law]].
