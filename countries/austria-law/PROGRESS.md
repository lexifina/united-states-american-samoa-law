# Austria (gitlaw-AT): PROGRESS

**Status: stopped on the coordinator's instruction (2026-10-28, about 22:40 UTC).** lexifina/austria-law `main`
already holds a complete build by another session, and autopush won't overwrite a main it didn't make. No
corpus.json, corpus.d or PUBLISH was written here, and nothing was pushed.

## What the existing repo holds (checked 2026-10-28 against origin)

- **Head:** `main` = `4cc372aef9323b9fb5b0478ba4d925e8dcb21863`, "Dokumentation, Tabellen, Werkzeuge und REPRODUCE.md",
  on top of the scaffold `59b5c5f` ("Austria: sources, before any law", which is also `sync/main`).
- **Size:** 301 commits on main and 246 tags (one per law, e.g. `bgbl-i/2024/70`). The README says the `future`
  branch has no commits after 2026-10-28.
- **Acts** (RIS Bundesrecht konsolidiert, OGD API v2.6, retrieved 2026-10-28):
  - **B-VG** (10000138): 241 provisions, 1262 versions, from 1930-01-03.
  - **DSG** (10001597): 90 provisions, 282 versions, from 2000-01-01.
  - It has no ABGB and no StGB: its REPRODUCE.md names ABGB 10001622, StGB 10002296, UGB 10001702 and ZPO 10001699
    as next, "appended in later commits".
- **How it was built:** its own builder, `tools/build.py` in that repo (lxml, its own git fast-import; it does not
  use gitlaw_common). It credits each version to the law in RIS's per-version Kundmachungsorgan ("zuletzt geändert
  durch"). Commits are dated noon Vienna, and dates before 1970 are clamped. It ships the tools `stand_am.py`,
  `check_repo.py`, `test_repo.py` and `reproduce.py`. REPRODUCE.md records 0 mismatches over 1544 versions, a
  word-for-word check, and an identical-hash rebuild.
- **RIS OGD terms it records (binding; stricter than the general speed rule):**
  - at most 0.5 requests a second, over one connection;
  - only between 20:00 and 05:00 Vienna time, or at weekends and on public holidays;
  - bulk use must be announced in advance to ris.it@bka.gv.at, which the user did for that build.
- **Its cache** (`scripts/austria-law/.cache` per its REPRODUCE.md) is not in this checkout, so a rebuild must refetch.

## What this session left here

- `fetch.py` is a curl fetcher for ABGB, StGB, DSG and B-VG that keeps the RIS hours and the 2-second pause, ready
  for whoever appends ABGB and StGB.
- `.cache/` holds 65 RIS responses, 9.3 MB, gitignored: every search page of all 4 acts (B-VG 14, ABGB 26 = 2566
  documents, DSG 4, StGB 12) and 8 B-VG XML documents. The fetch was stopped by its own task id.
- WebSearch used: 0 of 4.

## Next, if the coordinator wants Austria deepened

Append ABGB and StGB with the existing repo's own `tools/build.py` (add them to its `acts_extra.json`), in a RIS
night window, rather than replacing main with a gitlaw_common build. The search pages are already cached here: about
2566 ABGB and roughly 1150 StGB XML documents at 2 s each, about 2 hours.
