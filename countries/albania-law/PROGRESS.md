# Albania (gitlaw-AL): progress

Country: Albania · slug `albania` · tz Europe/Tirane · lang sq · future_branch `e-ardhme` · on-date tool `tools/ne_fuqi_me.py`.
Repo `lexifina/albania-law` (private). Remote main checked read-only on 2026-10-29 ~06:09 UTC and again before PUBLISH: still the scaffold 4993e04 ("Albania: sources, before any law"). The local clone `C:/Users/alany/Documents/albania-law` belongs to autopush: never build into it.

## Status (2026-10-29, gitlaw-AL-2)

- [x] Probe of qbz.gov.al (open JSON API, see below)
- [x] fetch.py (curl, sha256-of-URL cache, requests.jsonl, ≤3 req/s; archive.org via gitlaw_common/wayback.py)
- [x] qbzpdf.py: reads QBZ / Assembly PDF editions of the Constitution into units (text layer, no OCR)
- [x] parse.py → `corpus.d/10-kushtetuta.json` (country + Kushtetuta), deterministic, cache only
- [x] repo/README.md (English, then Albanian), repo/LICENSE, repo/jurisdiction.json, repo/tools/ne_fuqi_me.py
- [x] Local build in an empty scratch repo: 8 law commits + docs commit, 16 tags, 0 unexplained, 0 future
- [x] check.py: 0 mismatches, 0 trailer errors, 0 merges/backwards/future; `--compare` rebuild: identical
- [x] PUBLISH + corpus.d/10-kushtetuta.PUBLISH (today's version equals QBZ's consolidated edition, unit for unit)
- [ ] Kodi Civil: skipped, no official copy of the 1994 text found (see below)
- [x] Publication dates checked against each gazette issue's masthead (all 7 match)
- WebSearch used: 1 (found the INSTAT/QBZ 2016 edition; WIPO only had an English text and a 2008 Albanian PDF behind signed URLs).

## Kushtetuta: what was built

| Version (in force) | Law | Changes | Words from |
| --- | --- | ---: | --- |
| 1998-11-28 | ligji 8417 (as enacted; promulgated by decree 2260, art. 183) | 215 units | Assembly's PDF (Internet Archive 20060525195849); never-amended provisions as in QBZ today |
| 2007-01-14 | 9675/2007 ("menjëherë"; FZ 2/2007 of 14.1.2007) | 3 | replay (no edition of this state) |
| 2008-05-22 | 9904/2008 (FZ 61/2008 of 7.5.2008 + 15) | 12 (incl. Part 12 repealed) | QBZ edition 2008 |
| 2012-10-26 | 88/2012 (FZ 132/2012 of 11.10.2012 + 15) | 3 | QBZ edition 2012 |
| 2015-12-21 | 137/2015 ("menjëherë"; FZ 219/2015 of 21.12.2015) | 4 | QBZ edition 2015 |
| 2016-08-11 | 76/2016 (FZ 138/2016 of 27.7.2016 + 15) | 57 (incl. Annex A–G) | QBZ edition 2016 |
| 2020-09-08 | 115/2020 (FZ 153/2020 of 24.8.2020 + 15) | 2 | today's QBZ edition |
| 2022-03-24 | 16/2022 (FZ 37/2022 of 9.3.2022 + 15) | 1 | today's QBZ edition |

Verification (printed by parse.py, recorded in decisions):
- Replay vs the official words of each state: 82 provision changes (73 provisions); all match ignoring whitespace and word-division hyphens, except 3 typographic points in the 2016 law's own text (arts. 125, 136: final period lost at “dh””; art. 131 ë) "kushtetutshmerinë" → "kushtetutshmërinë" in QBZ 2016).
- Credits vs QBZ's notes in today's edition: 0 discrepancies.
- Law-text quirks handled and logged: 76/2016 adds 179/b "after 179/a" (no such article; placed after 179/1); 16/2022 quotes "funksionimit të tyre" where the text reads "funksionimit tyre"; 76/2016 art. 20 has a stray closing quote after art. 141 para. 1.
- Assembly 1998 copy vs QBZ words for never-amended provisions: 15 provisions differ in typography (capitals, accents, quotes, commas), 7 only in spacing; the QBZ words are used, and the list is in decisions.

Default in-force rule: Kushtetuta art. 84(3) "Ligji hyn në fuqi me kalimin e jo më pak se 15 ditëve nga botimi i tij në Fletoren Zyrtare" (verified in today's QBZ edition). Each amending law's own clause sets its day.

Final local result (2026-10-29 ~06:50 UTC): corpus sha256 3a705d67…, parse deterministic (two runs identical); scratch build main f703c1cd, history tip beeaab7d, 8 commits + docs, 16 tags; check.py 0 mismatches / 0 trailer errors / 0 merges / 0 backwards / 0 future; `--compare` identical (also with GITLAW_VERIFIED_PARTS_ONLY=1). Nothing pushed or committed; the 4-hourly autopush pass publishes.

## Sources (all cached in .cache/, ~70 MB incl. 7 Fletorja Zyrtare issue PDFs used to check publication dates)

- qbz.gov.al API `https://qbz.gov.al/api/v1`: `/acts/{id}` (word.url = free .docx), `/acts?q=`, `/gazettes/{y}/{n}` (publishDate), `/publications?type=kushtetuta` (today's consolidated PDF, free, text layer, created 2026-02-09). Act ids: 9675→5051, 9904→6511, 88/2012→8604, 137/2015→12702, 76/2016→15530, 115/2020→22000, 16/2022→24124. Copyright law 35/2016 → 62751 (neni 12/1/b excludes legal acts).
- API `date` is a day early for 88/2012 (17.9 vs 18.9) and 16/2022 (9.2 vs 10.2); parse uses "Miratuar në datën" from each docx.
- Internet Archive: Assembly PDF `parlamenti.albaniaonline.net/menu/foto/Kushtetuta%20e%20RSH.pdf` @20060525195849 (also at parlament.al/graphics/foto/ 2011–2013, same digest); its HTML twin `parlament.al/dokumenti.asp?id=855&kujam=Kushtetuta` @20060510020112. QBZ editions: `qbz.gov.al/Kushtetuta-2008.pdf` @20160828082331 (state after 9904), `Kushtetuta%202012.pdf` @20150514023034, `Kushtetuta%202015.pdf` @20160828081555, `kushtetuta%20me%20pjese/Kushtetuta%202016.pdf` @20161231232216 (= INSTAT copy), `Kushtetuta-2017.pdf` @20181123131026 (same as 2016 plus an index; not used).
- `qbz.gov.al/Kushtetuta me pjese/Kushtetuta 1998,varianti 1.pdf` exists but was only archived after it became an SPA fallback (no PDF capture).
- Common Crawl index was unreachable (timeouts) on 2026-10-29 ~06:20 UTC; not needed.

## Kodi Civil / Kodi Penal

- Kodi Civil: ligji 7850, 29.7.1994; amending laws in qbz: 8781/2001 (808), 17/2012 (7855), 121/2013 (9465), 113/2016 (15921), 82/2026 (34057). Consolidated: `/publications?type=kode` id 79. NOT BUILT (per brief: only if the original is found). 8781/2001 rewrites ~12 articles on associations (arts. 39–46+), so the 1994 wording is needed. Archive.org CDX searches (filters "kod", "kodi civil", "dokumenti") on parlament.al, parlamenti.albaniaonline.net and qbz.gov.al found no Civil Code copy at all; the Assembly's 2006 site (dokumenti.asp) listed the Constitution, electoral code and rules but no codes. Common Crawl starts too late for pre-2001 text.
- Lead for later: parlament.al/Files/ProjektLigje/7905-date-21.3.1995-Kodi-iprocedures-penale-i-RSh.pdf (Internet Archive 20190917030631, 594 KB): a Code of Criminal Procedure PDF on the Assembly site; not checked (whether original or consolidated).
- Kodi Penal: ~25 amending laws incl. Constitutional Court rulings; original 1995 text also missing.

## How to rebuild

    python -X utf8 scripts/albania-law/fetch.py
    python -X utf8 scripts/albania-law/parse.py
    python -X utf8 scripts/gitlaw_common/build.py scripts/albania-law --repo <empty scratch> --docs-date 2026-10-29
    python -X utf8 scripts/gitlaw_common/check.py <scratch> --corpus scripts/albania-law/corpus.d

## Open issues

None in the shared builder.
