# Benin (BJ): progress of gitlaw-BJ

Repo lexifina/benin-law (private scaffold, cloned at C:/Users/alany/Documents/benin-law; untouched). Slug benin,
tz Africa/Porto-Novo, lang fr, future branch `futur`. Stopped by the coordinator's wind-down, 2026-10-29 ~00:42 UTC.

## Status
- [x] Probe sources (below); fetch.py written (curl cache, requests.jsonl, robots crawl-delays honoured)
- [x] Phase 1 inputs cached: 31 requests, 317 MB in `.cache/` (see sources.json for every document and its text quality)
- [ ] parse.py: NOT written. No corpus.json yet, no build, no PUBLISH.
- [ ] Code penal 2018: skipped, no usable text layer anywhere (see below)

## Sources (probed 2026-10-28)
- **sgg.gouv.bj** (robots: allow all). `/doc/<loi-YYYY-NN>/download` gives the promulgated PDF. Text layers are either
  scans or a bad OCR with systematic a->o substitutions ("Lo Cour constitutionnelle"): not usable as legal text.
  No consolidation. `/recherche/?keywords=` lists documents. Code penal 2018-16 is not on SGG (404).
- **legis.cdij.bj** (CDIJ, robots allow all): same PDFs as SGG. Search: `/ressources?word_search=<q>&page=N`, 5 per
  page. Terms forbid reproducing site "elements" without consent (site content; legislation itself is public).
- **courconstitutionnelle.bj** (robots allow all): `/fr/docs/textes-fondamentaux` has a CLEAN consolidated
  Constitution as revised by loi 2019-40 (revised articles marked "(nouveau)", arts 46-47 "(abrogé ...)"), and the
  2025 revised text as a scan only. Decisions PDFs (DCC) have clean text.
- **assemblee-nationale.bj** (Crawl-delay 10): CLEAN 1990 Constitution PDF (retyped; minor transcription differences
  from the CC text, e.g. art. 1 "La capitale du Bénin" vs "La capitale de la République du Bénin").
- **documentation-anbenin.org** (AN Omeka S, Crawl-delay 10, search pages disallowed): `/api/items/<id>`,
  `/api/media/<id>` -> `o:original_url`. Code du numérique 2017-20 (item 227) and loi 2020-35 (item 2170) have a
  usable publisher OCR layer (split words like "Autori té", some missed "Article N"). Code penal (item 2074): bad OCR.
- Wayback CDX for arcep.bj uploads: only ARCEP decisions, no clean Code du numérique.

## Plan for the next agent (exact next step)
1. Write parse.py. Constitution: v1 1990-12-11 from the AN PDF (promulgation date in the law's title; the text sets no
   other date); v2 2019-11-07 from the CC consolidated PDF (loi 2019-40 art. 2: "entre en vigueur dès sa
   promulgation"). Units: `preambule`, `titre-NN`(`titre-10-01`), `art-NNN`(`art-054-01`), heading line
   `# Article N`, "(nouveau)" stripped from the heading and used as the credit to `loi-2019-40`; arts 46/47 removed
   (credited 2019-40); units containing "Forces de défense et de sécurité" credited 2019-40 (its art. 1 al. 1).
   Other differing units stay uncredited (publisher transcription differences) and are listed in decisions.
   pdftotext -enc UTF-8 -layout; normalise spaces before punctuation and around apostrophes, quotes, dashes.
2. Note in decisions/README: the CC text keeps "Forces armées ou de sécurité" in art. 64 although 2019-40 art. 1
   replaces it everywhere; 157-3 applies "à l'occasion de" the 2021/2023 elections (no typed date: `applies` empty).
3. Loi 2025-20 (17 Dec 2025) revision is scan-only (SGG, CDIJ, CC): today's Constitution text is therefore NOT the
   latest; do not PUBLISH the Constitution; README must say the history stops at the 2019 revision.
4. Code du numérique: v1 2018-04-20 (AN OCR), v2 2021-01-06 by replaying 2020-35 (arts 121, 125, 464 new text; art.
   2 renames "ministre (chargé) des Communications électroniques et de la Poste" -> "ministre chargé des
   communications électroniques" everywhere). Check whether the OCR split words make the art. 2 replay unreliable;
   if so, credit only arts 121/125/464 and list the rest as not applied in decisions.
5. Code pénal: find a clean text (none found on SGG, CDIJ, AN documentation); otherwise leave it out, named.

## Open issues
- No ISSUES-benin.md items (shared adapter not used: Benin has no Peachjam LII).
- WebSearch used: 1 of 4.
