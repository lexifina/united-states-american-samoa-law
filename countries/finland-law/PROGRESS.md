# Finland (gitlaw-FI): stopped by the coordinator

Status, 2026-10-28 ~22:30 UTC: **stopped before building.** lexifina/finland-law already holds another session's build. The coordinator said not to write corpus.json, corpus.d or PUBLISH. This folder deliberately has none of them, so autopush ignores it.

## What lexifina/finland-law holds (read-only clone, 2026-10-28)
- main `86af6a1` ("corpus.json: history \"replayed\""), 9 commits. Branches: `sync/main` 97138bb, `wip` e2a58ce. Not built with the shared gitlaw_common builder: it has its own build.py, check_repo.py and test_repo.py, and the README tool is `tools/finlex.py`.
- One act: Perustuslaki 731/1999, with one file per section (`perustuslaki/pykala-NNN.md`). There are 5 law commits, each at noon Helsinki time: 731/1999 (2000-03-01), 596/2007 (2007-06-01), 802/2007 (2007-10-01), 1112/2011 (2012-03-01) and 817/2018 (2018-10-15). Tags `perustuslaki/<year>-<num>`; also amendments.csv, README, REPRODUCE.md.
- The intermediate versions are **replayed**: they start from the original statute and apply each amending act. Only the end state is checked against Finlex's consolidation (dated 2018-10-05), 131/131 sections.
- The `wip` PROGRESS.md says: Vaalilaki 714/1998 not built; an "expansion to all statutes" is in progress; main goes out only after gitlaw-global confirms REWRITES_AGREED.
- Rikoslaki 39/1889 and Tietosuojalaki 1050/2018 (my Phase 1 brief) are not in the repo.

## Probe notes for whoever owns Finland (not acted on)
- API: `https://opendata.finlex.fi/finlex/avoindata/v1/akn/fi/act/{statute|statute-consolidated}/{year}/{num}/{fin|swe}@{version|latest}`. A User-Agent header is required. The OpenAPI file is `/Finlex_avoin_data_v0_4_0.yaml`. `statute-consolidated/.../fin@` (no version) returns 404, but `fin@latest` works.
- The consolidated Akoma Ntoso XML has `contains="multipleVersions"`, and `finlex:amendedBy` gives each amending act's `dateEntryIntoForce` and an editorial note ("muutt. 10 §:ää"). Amended subsections carry `finlex:originalVersion="@20111112"` in eIds like `subsec_3v20111112`. That records which act wrote each subsection, which could support credits. I did **not** check whether older `fin@<version>` expressions can be fetched.
- WebSearch calls used: 0 of 4.
