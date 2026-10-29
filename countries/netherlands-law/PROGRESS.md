# gitlaw-NL: Netherlands (lexifina/netherlands-law), handoff 2026-10-29 00:43 UTC; PUBLISH written 2026-10-29 by gitlaw-finisher

## Status
- [x] Source probed: BWB repository (CC0). Per act: `manifest.xml` (all dated toestanden), toestand XML per version, `.WTI` (amendments per in-force day). Per-article `bron="Stb.YYYY-N"` + `inwerking` gives the crediting law.
- [x] fetch.py (curl, cache by sha256, 3 req/s, requests.jsonl) — all versions cached for 4 acts (~465 MB), plus 329 Staatsblad metadata.xml (titles) from zoek.officielebekendmakingen.nl.
- [x] parse.py -> corpus.json: Grondwet 11 versions (2002-), BW Boek 1 58 (2002-), Wetboek van Strafrecht 119 (2002-), UAVG 6 (2018-); 248 laws; 14 unexplained unit changes (mostly inhoud/editorial, plus Sr 2024-07-01 arts 240a-c/248a-f and BW1 2015-01-01 arts 263a-b vanished with several laws that day).
- [x] first_law: UAVG = stb-2018-144 (as enacted); the other three start at the BWB's oldest toestand (publisher). Confirmed in corpus.json.
- [x] repo/README.md (English, then a Dutch section), repo/LICENSE (CC0 source + Auteurswet art. 11), repo/jurisdiction.json (from the scaffold, `build` set to the real status), repo/tools/geldend_op.py (wrapper around tools/on.py: DD-MM-YYYY dates, gw/bw1/sr/uavg, Roman additional articles -> add-art-NN, "Artikel 23"). Tested in the scratch build.
- [x] verify.py (new): reads https://wetten.overheid.nl/<BWB id> (in force today, via fetch.py cache + requests.jsonl) and compares word for word with the last version of each act; writes verify.json. Result 2026-10-29: page in-force date = our last version for all 4 (2023-02-22, 2025-07-05, 2026-07-01, 2026-09-01); 1,396 articles, 0 unmatched, 0 unexplained page entries (only "Vervallen" placeholders and UAVG art. 23a, which the BWB marks nogniet). To re-check on a later day, delete the 4 cached pages (sha256 of the URL) and rerun.
- [x] Fresh manifests (2026-10-29, read into scratch, not the cache) list exactly the cached toestanden: nothing newer.
- [x] Local verification (CADENCE CHANGE): build into an empty scratch repo, docs-date 2026-10-28: 281 commits (4 first, 272 law, 5 unexplained), 442 tags, 0 on toekomst; check.py 0 mismatches, 0 trailer errors, 0 backwards/future; --compare identical.
- [x] PUBLISH written 2026-10-29. Remote main was still the scaffold (d8c9fb4) at the time. The next 4-hourly autopush pass publishes main.
- [ ] Phase 2: Boek 6 BW (BWBR0005289), Sv, Rv, WvK — just add to acts.json and run fetch.py then parse.py (then update repo/README.md's table and jurisdiction.json, and rerun verify.py).

## Open points
- Grondwet tekstplaatsing besluiten (Stb.2006-240, 2008-348, 2019-33) are the BWB's bron for the wording; a law `note` names the revision laws the WTI lists for that day. Grondwet 2018-12-21 is credited to Stb.2019-33 (signed 2019-01-16): in-force before signature, as the BWB gives it (decision recorded).
- Article without number (Gw "Algemene bepaling") is key art-000.
- wetten.overheid.nl shows a "Toekomstige wijziging(en) voorzien met ingang van 01-01-2027" banner on Sr art. 71; the BWB has no toestand for it yet, so nothing is on `toekomst`. A later fetch with --refresh will pick it up once the BWB publishes it.
- README states counts (versions per act, 5 unexplained commits, 1,396 articles): update them if acts are added.
- No background processes running.
