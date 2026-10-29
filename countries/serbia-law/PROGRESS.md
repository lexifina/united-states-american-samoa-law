# Serbia (gitlaw-RS) — handoff, 2026-10-29 00:40 UTC

Repo lexifina/serbia-law: still the bare scaffold (c51e702 "Serbia: sources, before any law") at start. Clone at C:/Users/alany/Documents/serbia-law (untouched). No PUBLISH yet (not verified word-for-word).

## Done
- [x] Source probe: Pravno-informacioni sistem (PIS) has a clean JSON/HTML API behind its Vue SPA. Text is Cyrillic.
- [x] corpus.json: Constitution, 2 versions (2006-11-08 original; 2022-02-09 Amendments I-XXIX), 207 units, 29 changed articles credited. Built by parse.py from .cache (2 files).
- [ ] Verify against official text, then PUBLISH. Article captions/part headings are currently dropped (heuristic); consider keeping captions.
- [ ] Krivični zakonik, [ ] Zakon o zaštiti podataka o ličnosti 2018 (SG 87/2018; ELI number not yet found).
- [ ] fetch.py (not written; the two cached files were fetched by hand with curl, the same UA, during the probe; probe/ has view JSON for Ustav and KZ).

## The API (all GET, curl --compressed, UA lexifina-watch/1.0; robots allows /eli/rep/*)
1. `https://slgl.pravno-informacioni-sistem.rs/api/prins/eli/rep/sgrs/skupstina/<type>/<year>/<gazette no>/<n>/reg` -> `{lawAdActGuid, eliUrl}`
2. `https://reg.pravno-informacioni-sistem.rs/api/GetLawActViewByLawAdActGuid?lawAdActGuid=G&eliUrl=E` -> `{id (current version), hm (act guid), versionGuid, title, previousVersions[{regId}], links (gazette PDFs), htmlLinks (amending laws)}`
3. `https://reg.pravno-informacioni-sistem.rs/api/GetLawActTimeline?guid=<hm>` -> every version id with `versionApplicationDate` (the in-force dates).
4. `https://reg.pravno-informacioni-sistem.rs/api/viewAct/<hm>?lawActId=<version id>` -> full HTML of that version; per-article notes like `*Службени гласник РС, број 115/2021 (Амандман I)` give credits.
5. `GetEliMetadata?versionGuid=` -> ELI dates (version_date, first_date_entry_in_force). Add `&timestamp=YYYYMMDD` to step 2 for a point-in-time version.
6. Amending law text: `https://slgl.pravno-informacioni-sistem.rs/api/Prins/viewDoc?uuid=<htmlLinks url>` (HTML; final article gives in-force rule, incl. staggered dates, e.g. 121/2012 arts 21, 35 from 2013-04-15).

## Known ids
- Ustav: ELI ustav/2006/98/1, hm f0d72ce3-dad2-4395-a2c1-c3d3226f22c2, versions 408046 (2006-11-08), 433539 (2022-02-09).
- Krivični zakonik: ELI zakon/2005/85/6, hm cfea63a3-cb76-4723-9308-0b071a3f3f78; timeline: 429666 2006-01-01, 429667 2009-09-11, 429672 2010-01-06, 429674 2013-01-01, 429678 2013-12-05, 429679 2014-10-18, 429680 2017-06-01, 429681 2019-12-01, 437844 2024-12-06, 440332 2026-07-18 (63/2026). Oldest version already includes corrections 88/2005, 107/2005.

## Next step to resume
Write fetch.py (cache by sha256(url), log requests.jsonl, 3 req/s), fetch KZ's 10 versions via step 4, extend parse.py to read dates from the timeline JSON and credits from the per-article notes (map gazette no. to law keys), handle staggered in-force articles, then find the ZZPL 2018 ELI (try zakon/2018/87/N) and do the same. Verify latest text vs official, then write PUBLISH (re-check the scaffold with git ls-remote first).
