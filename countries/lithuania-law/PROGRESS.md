# Lithuania (gitlaw-LT): progress

Agent: gitlaw-LT (fork wave L–Z). Rules: scripts/world-law/FORK.md, WAVE.md, africa-law/FANOUT.md, south-america-law/BRIEF.md.

## Checklist
- [x] Scaffold check (2026-10-29): `git ls-remote` showed only `main` = 4517d9ac "Lithuania: sources, before any law". Re-checked before PUBLISH: `wip` (9 snapshots of scripts/lithuania-law) and `preview` (tip fb43692 = my local build's history tip) are the push loop's copies of this folder, as expected.
- [x] Probe sources (see below)
- [x] Constitution 1992 + every amendment to 2022: 12 versions, 16 commits + docs, 15 laws/court acts + the referendum
- [x] corpus.json, local scratch build (.tmp-build), check.py: 0 mismatches, 0 trailer errors, 0 merges/backwards/future; `--compare` main identical
- [x] PUBLISH written (Constitution verified)
- [ ] Core act 2 (personal data law / Civil Code / Criminal Code): see "Core acts" below

## Constitution: how it was built
- Version 1 (1992-11-02): e-TAR rs/legalact/TAR.47BB952431DA, capture 20180626074019 (the 2015 and 2017 captures carry two transcription slips the Register later fixed).
- 1996-07-21 … 2006-05-26 (7 versions): e-TAR editions for these years are not archived; each amending law's e-TAR text (I-1390, VIII-32, IX-959, IX-1305, IX-1378, IX-1379, IX-2343, IX-2344, X-572) is replayed by a checked rule in parse.py.
- 2013-11-16 (KT president's notice, suspension of X-572) and 2014-01-24 (ruling KT2-N1/2014): versions without units, credited to art-125, with notes.
- 2019-09-01 and 2022-05-22: e-TAR rs/actualedition texts (LZjyKYDgoo, vkzKUoOclO).
- In-force days: e-TAR's edition list (portal/lt/legalActEditions, capture 20250622024316).
- Checks (all pass, see corpus decisions "Check:"): replay = lrs.lt Jan 2006 (170/170 units); 2006 text = e-TAR 2014 edition and lrs.lt 2007/2008/2014/2016; 2019 = lrs.lt 2020; today = lrs.lt live 2026-10-29 and Wayback 2026-10-20; e-TAR act page 2026-10-23 names the 2022-05-22 edition as current. The 2022-06-27 lrs.lt capture still shows the 2019 text (the page lagged) and is checked against that.
- Decision: IX-1378's point 11 ends with "." in the law; consolidated texts keep ";", which this record follows.

## Source probe (2026-10-29)
| Source | Result |
|---|---|
| www.e-tar.lt (TAR, official publication) | 403 Cloudflare challenge. Not touched. Read through Wayback `id_` captures only. |
| e-seimas.lrs.lt | 403 Cloudflare challenge. Not touched. |
| data.gov.lt / get.data.gov.lt (dataset 2613, Spinta API `datasets/gov/lrsk/teises_aktai/{Dokumentas,Suvestine}`) | WAF "Web Page Blocked" (Attack ID 20000018) for this IP. Not worked around. Licence not readable from here. |
| www.lrs.lt/home/Konstitucija/Konstitucija.htm | 200, windows-1257; current consolidated Constitution with per-article notes. robots.txt allows, Crawl-delay 20. 1 direct request. |
| www.lrkt.lt (Constitutional Court) | 403 Cloudflare challenge. Not touched. |
| Wayback: e-TAR act pages, rs/legalact, rs/actualedition, legalActEditions | Good coverage for the Constitution; amending laws archived except XIV-1028/XIV-1030/XIII-2004/the 2013 notice (not needed: their editions are archived). |

Cache: scripts/lithuania-law/.cache (requests.jsonl). Licence: legal acts are not objects of copyright (Law on Copyright and Related Rights, art. 5).

Prior art (reconcile only, never copied): github.com/Yiin/lt-teises-aktai (built from get.data.gov.lt).

## Core acts (not built: today's official text unreachable)
- Personal data law (ADTAPĮ, TAR.5368B592234C): e-TAR editions list (capture 20260310) has 20 editions 1998-2025; archived texts exist for 2025-01-01, 2024-07-01, 2021-12-01 (+ several older ids). BUT the act page captured 20261009 names a newer edition in force from 2026-06-30 (id kqEdQJIjKX, Law XV-904 of 2026-05-12), and neither that edition nor XV-904 is in Wayback or Common Crawl, so today's text cannot be verified. Skipped after ~25 min.
- Criminal Code (TAR.2B866DFF7D43): ~45 archived editions, newest text 2026-03-04 (cLtIOQKxTp); no 2026 editions list to show it is current. Civil Code (TAR.8A39C83848CB): editions lists only, no edition texts archived. Skipped.
- legalize-lt (github.com/legalize-dev/legalize-lt, data CC BY 4.0, HEAD 76c1b579 of 2026-09-25): commits are dated by e-TAR edition (in-force) day, but its ADTAPĮ 2025-01-01 text differs from e-TAR's archived edition: 674 vs 452 paragraphs, repealed articles (36, 10¹) kept, articles 7¹/14¹/19¹/32¹ missing, superscripts lost. Not used as text. It also lacks the 2026-06-30 edition.
- Next step for whoever resumes: find Law XV-904's e-TAR id (e.g. a Common Crawl prefix scan of e-seimas.lrs.lt/portal/legalAct/lt/TAD/) and replay it on the 2025-01-01 edition; the parser in lt_common.py now keeps superscript article numbers (7¹).

## Publish state
- PUBLISH written; the push loop has pushed main (b5bfe7a) with tags konstitucija/1992-11-02 … 2022-05-22 matching the local build hash for hash (history tip fb43692). Later local rebuild after sources.json cleanup: main f025643 (docs commit only differs), check 0 mismatches, --compare identical.

## Open issues
- none
