# Côte d'Ivoire (gitlaw-CI) progress (gitlaw-CI-AO, 2026-10-29 02:20 UTC)

Repo: lexifina/cote-divoire-law (private). tz Africa/Abidjan, lang fr, future branch `futur`, on-date tool
`repo/tools/en_vigueur_au.py`. Clone C:/Users/alany/Documents/cote-divoire-law is owned by autopush (4-hourly pass);
remote main was still the scaffold 0ba4ead at 02:18 UTC. **corpus.json written and PUBLISH written** (Constitution).
WebSearch used: 2 of 4.

## Checklist
- [x] Probe sources
- [x] fetch.py (curl, sha256 cache, per-host delays, requests.jsonl). `--all` reads sources.json, then the signed WIPO
      PDF link from the WIPO record page (the bare PDF URL answers with an HTML page).
- [x] pdftext.py: "blocks" mode (AN Word PDFs); "margin" mode (WIPO) now also breaks at "—" items and 20-pt gaps,
      and joins a lower-case line after a short line
- [x] constitution.py: bugs fixed (art. 165 glued to heading; spaced "P R É A M B U L E"); `repair()` mends AN list
      blocks ("; - " items, mid-sentence block breaks); `split_like()` restores paragraph breaks witnessed by 2016 or
      WIPO HTML; `v2_articles()` builds the 26 "Nouveau" articles
- [x] parse.py -> corpus.json: Constitution, 185 units (preambule + art-001..184), v1 2016-11-08 (Loi 2016-886, as
      enacted), v2 2020-03-19 (`changes`, 24 articles changed, 26 credited to lc-2020-348; 148/149 unchanged ->
      Also-concerns)
- [x] repo/README.md (EN + FR), LICENSE, jurisdiction.json, tools/en_vigueur_au.py
- [x] Local build (scratchpad ci-a): 3 commits incl. docs, 4 tags; check.py 0 mismatches, 0 trailer errors;
      --compare identical (main c7f40d4, docs-date 2026-10-28)
- [x] PUBLISH written 2026-10-29 02:20
- [ ] Code pénal 2019 (AN PDF cached, 565 articles, text layer): in-force date unsourced -> not built (see below)
- [ ] Loi 2013-450: ARTCI PDF is a scan (no text layer), left out (no OCR)

## Verification done
- Every unmarked article: words(AN 2016) == words(WIPO 2020) except WIPO slips in 26, 51, 97, 125, 152 (2016 kept).
  Preamble equal. parse.py asserts all of this.
- Every body word of the AN PDF (préambule to "Fait à Abidjan") is in a unit, only headings left out; same for the
  WIPO PDF against the 2020 state (only headings + the 6 listed slips differ).
- WIPO's HTML rendering (record page) used as a second witness for paragraph breaks only (it drops spaces).
- Art. 177: WIPO "Journal official" -> "officiel" (paragraph otherwise identical to 2016). In decisions.

## Sources (cache: scripts/cote-divoire-law/.cache, about 15 MB)
| Source | Status | Notes |
|---|---|---|
| assnat.ci IMG/pdf/constitution_..._2016-886_du_08_novembre_2016.pdf | used, text layer | v1 |
| WIPO Lex 22491 record page + signed PDF link on it | used, text layer | v2, "Nouveau" credits |
| assnat.ci IMG/pdf/loi_portant_code_penal.pdf | cached, text layer, 139 pp | Code pénal 2019 as voted; not built |
| conseil-constitutionnel.ci constitution_2016.pdf | cached, not used | pre-adoption draft (differs in 16 articles) |
| sgg.gouv.ci (JO) | times out directly | Wayback: 123 PDFs, all older laws |
| artci.ci loi_2013_450.pdf | image scan | left out (no OCR) |
| civlii.laws.africa | not read | see Code pénal below |

## Published
04:51 UTC pass pushed main **d8106d0** (BUILD_STATUS 04:56: 2 versions, 0 mismatches). Any later change must keep
that published version verified (re-run local build + check.py + --compare before touching corpus.json).

## Code pénal (open, skipped under the 45-min rule)
Needs a sourced in-force date (Loi n° 2019-574 du 26 juin 2019, JO publication; CIVLII "Commenced on"). Only add as
its own part (corpus.d/, no PUBLISH until verified) once that date is sourced. 2026-10-29 05:55: archive.org CDX
has 0 captures under civlii.laws.africa/akn/ci/act/ (via wayback.captures); the Common Crawl index timed out again
(110 s, 10 crawls). Retry the CC index when it answers.

## Notes for the adapter
- peachjam.py hard-codes `eng@`; CIVLII expressions are `fra@`. Not needed for the Constitution.
- fetch.py still has its own `cdx()`/`wayback()` helpers from the probe; archive access now goes only through
  gitlaw_common/wayback.py.
