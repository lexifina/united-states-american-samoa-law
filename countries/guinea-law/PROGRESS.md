# Guinea (GN): progress

Repo: lexifina/guinea-law (private). Clone: C:/Users/alany/Documents/guinea-law (autopush owns it). Agent: gitlaw-CD-GN (resumed the stopped session on 2026-10-29).

## Status (2026-10-29, ~07:30 UTC)

- [x] Source: Journal officiel numérique (journal-officiel.sgg.gov.gn), launched 2025; every issue as a PDF, robots.txt allows all; no consolidation, no dated versions. Index pages cached (1624 issue PDFs listed, up to n° 2026-07).
- [x] Constitution 2025 (1 version, 2025-09-26) and Charte de la Transition 2021 (1 version, 2021-09-27). Built locally: check.py 0 mismatches / 0 trailer errors, --compare identical (main df82862, docs-date 2026-10-28).
- [x] repo/ README.md (English, then French), LICENSE, jurisdiction.json, tools/en_vigueur_au.py.
- [x] PUBLISH written 2026-10-29 (remote main confirmed read-only to be the scaffold d9deb76 "Guinea: sources, before any law").
- [ ] Phase 1 asks for 2 core acts besides the Constitution: the Charte is one act but not a code (see Next).
- Not pushed by me; the next 4-hourly autopush pass builds and pushes. BUILD_STATUS.json still shows the old preview 8023ec7.

## Work done on 2026-10-29 (resume of "inspecting PDF column layout in layout.txt")

The preview build (8023ec7) passed check.py but its text was badly wrong. Fixed in parse.py:
1. **Charte art. 1 and art. 84** held a prison-release table and decree text: the signature "Conakry, le 27 Septembre 2021" sits inside art. 84's paragraph, so the stop never matched and parsing ran into the following decrees (whose "Article 1er" overwrote the Charte's). The stop now cuts mid-paragraph.
2. **Constitution preamble** started with ~40 sommaire lines: the start now needs a paragraph equal to "PRÉAMBULE".
3. **Constitution art. 61 was missing:** the JO prints it inside art. 60's paragraph ("… de ses biens. Article 61. Les écarts …"); it is split out, and ART accepts "Article 61." as well as "Article 61:". Article numbers must now run without a gap (the parser raises otherwise).
4. **Heading second lines** ("SÉCURITÉ", "DROITS FONDAMENTAUX", "TRANSITION", "INTERNATIONAUX") leaked into articles: an all-caps short paragraph right after a heading is dropped with it.
5. **Paragraphs split mid-sentence** (Constitution art. 16, art. 72): a short line no longer ends a paragraph when the next line continues the sentence (lower case or "("); a gap of 13.5 pt or more ends a paragraph after closing punctuation.
6. **Ordinary line-end hyphens** in the Charte (96 breaks: "na- tionales", "RASSEM- BLEMENT") are joined; compounds written with a hyphen elsewhere, or in a short list (bien-être, soixante-douze), keep it.

Verification (`verify.py`, plus a scratch pdftotext comparison):
- Word multiset vs pdftotext of the same pages: corpus has no word that is not in the PDF (3 apparent extras are pdftotext splitting words around running headers); everything missing is headings, running headers, page numbers, sommaire. Paragraph order checked where the two extractions differ: ours follows the sentences, pdftotext's content order does not.
- Charte vs the site's HTML copy (journal-officiel.sgg.gov.gn/fr/textes-officiels/constitution.html): equal word for word apart from headings, 2 printed slips the site corrects ("I ‘Etat", "gouvemance") and 3 bracketed numbers the site omits.
- 14 JO issues after the Constitution (n° 2025-12-12-sp to 2026-07, all text-layer) searched: no revision of the Constitution, no amendment or repeal of the Charte.
- PDFs are born-digital InDesign with visible text (no OCR anywhere).

Also added: `fetch.py` (drives gncache over `sources.json`), `sources.json`, `verify.py`.

## Cache

.cache/: ~423 MB (index pages, ~150 issue PDFs fetched while probing for the 2020 Constitution and codes, the 14 later issues). requests.jsonl logs every request (167 lines).

## Next (open)

- The Charte has no end commit: Constitution art. 196 keeps the transition organs until the new institutions are installed, and no JO text found dates that. If a JO text (e.g. installation of the Assemblée nationale) is found, add a `note` law or decide how to mark the lapse.
- 2020 Constitution: the 2020 issues are scans (no text layer) - left out (no OCR).
- Codes: the site has a "Codes en vigueur" page (fr/textes-officiels/les-codes-consolides.html), not yet probed. `.tmp/cs_cp.pdf` (200 pages, ilovepdf, 2016/2018 dates, origin not recorded) looks like a Code pénal copy; not official-sourced, not used.
