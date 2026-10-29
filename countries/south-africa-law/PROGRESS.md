# South Africa (gitlaw-ZA) progress

Repo: lexifina/south-africa-law (private). tz Africa/Johannesburg, lang en, future branch `future`.
Clone (autopush owns it): C:/Users/alany/Documents/south-africa-law. Test builds: `.tmp-build/` (gitignored).

## Checklist
- [x] Probe sources, record terms (2026-10-28)
- [x] fetch.py (curl, sha256 cache, 1 req/s per host; archive.org only through gitlaw_common/wayback.py, shared adaptive rate)
- [x] parse.py -> corpus.json (`--acts a,b` and `--out` for tests)
- [x] Constitution 1996 + all 18 amendment Acts: 21 versions, 253 provisions (constitution.py, constitution_corpus.py, htmlblocks.py)
- [x] POPIA (Act 4 of 2013): 7 versions (parse.py, gazette.py)
- [x] Companies Act 71 of 2008: 9 versions, 230 sections/schedules (companies.py, companies_corpus.py)
- [x] verify.py: Constitution 253/253; POPIA 114/115 (DoJ adds a ";" in s. 112(2)(f)); Companies Act 228/230 (DoJ corrects s. 96(1)(c)(ii) "or" and s. 117(1)(j)(ii) "a[n]" with no amendment; gazette kept)
- [x] check.py on .tmp-build: 0 mismatches, 0 trailer errors; `--compare` rebuild identical
- [x] PUBLISH written by the coordinator (2026-10-28) after the user's decision on source terms; ISSUES.md #1 closed; README Licence section states the terms
- [ ] Criminal Procedure Act 51 of 1977 (plan below)

## State
- corpus.json: 3 acts, 32 laws (Constitution 21, POPIA 7, Companies Act 9 versions); autopush pushes main (see BUILD_STATUS.json).
- Cache: ~45 MB, ~580 requests (.cache/requests.jsonl). WebSearch used: 5 of 10.

## Sources and terms (read 2026-10-28)
| Source | robots.txt | Terms / use |
|---|---|---|
| justice.gov.za | allows (not /admin, /search ...) | /about_web/terms_conditions.htm: "only for non-commercial informational or reference purposes"; commercial needs permission (webmaster@justice.gov.za). Used: Constitution consolidation (today's text), amendments page + poster (dates), 18th Amendment Act, proclamations, POPIA and Companies Act consolidations (Juta exports: today's words, notes with "wef" dates) |
| gov.za | allows /documents, /sites/default/files | same wording (electronic@gcis.gov.za). Used: POPIA gazette GG 37067, Companies Act gazette GG 32121 (both born-digital), proclamations |
| Wayback: gov.za/constitution/1996 (1999-2003), info.gov.za/documents/constitution/1996 (2004-2012) | - | gov.za's own pages; pinned timestamps |
| Wayback: lawlibrary.org.za (Laws.Africa) | - | user allows Wayback of LIIs for gaps. CC BY-NC 4.0, attribution "LawLibrary (lawlibrary.org.za)". Constitution: 11 expressions (constitution.LL_CAPTURES); Companies Act: 2009-04-09, 2014-05-01, 2023-06-01, 2024-12-27 (companies.LL_CAPTURES). Captures can be cut at 1 MiB; LawLibrary's Companies Act text is OCR-derived (live/five, line/fine) |
| lawlibrary.org.za direct | ai-input=no, blocks ClaudeBot | terms s.4 forbid scraping; 403 challenge. Not fetched |
| inforegulator.org.za | allows | no terms page found. Proc. R21 of 2020 |
| SAFLII, commons.laws.africa | - / Disallow all | not used |
| Law text | | Copyright Act 98 of 1978 s. 12(8)(a): no copyright in official texts of a legislative nature |
| ISSUES.md | | #1 closed (user decision); #2 informational |

## How the acts are made
- Constitution: original = gov.za 1999 HTML; credits from amendment notes; intermediate wordings from info.gov.za captures matched by their notes, else LawLibrary expressions, else placeholder; last wording = DoJ consolidation (+18th from its gazette). Gaps: Sch 6 item 26 (1998-10-07..2001-11-21), 8th Amendment's Sch 6A (2002-06-20..2003-03-20).
- POPIA: gazette text; sections added on each commencement; proclamation no-words commits.
- Companies Act: as enacted = gazette (gazette.py); dates and credits = DoJ notes "(wef ...)"; today's words = DoJ consolidation (Juta typography set to the gazette's); intermediate = LawLibrary 2014-05-01 / 2023-06-01 with OCR-pair repair; s. 1 rebuilt definition by definition; s. 11(1)(a)(ii),(iii) from 2014-05-01. Gaps 2011-05-01..2013-06-03: ss. 5, 69, 116, and six s. 1 definitions. Pending Act 16 of 2024 provisions not shown.

## Criminal Procedure Act 51 of 1977: plan (not started)
- The 1977 gazette and pre-2009 amendment Acts are scans (no OCR).
- Government source with history: Wayback captures of justice.gov.za/legislation/acts/1977-051.pdf: 20120523214524 (Juta, "Legislation updated to: 29 October 2010", born-digital, 230 pp.), 20150401005522, 20201029075656, 20201101031042, 20220925204904, 20221001160202, 20221005001633, 20250606200756, plus today's file (cached). Each note has "(wef <date>)".
- Build: first version = 2010 consolidation as "oldest version available" (publisher), then per snapshot the changed units, credited by their new notes and dated by "wef"; generalise companies.doj_units (body start, Part headings) for the CPA.
- LawLibrary (Wayback) has ~100 CPA expressions 1977-2024 (`lawlibrary.org.za/akn/za/act/1977/51/eng@...`) for gaps; check capture completeness (1 MiB cuts, stubs) and OCR quality first.

## Findings worth sharing
- Laws.Africa LIIs block automated readers; Wayback holds their point-in-time expressions, but captures may be cut at 1 MiB or be 30 KB stubs; their old-act texts are OCR-derived.
- DoJ (justice.gov.za/legislation/acts/<year>-<no>.pdf) Juta exports carry a commencement table and "(wef date)" in every amendment note: per-provision in-force dates for DoJ-hosted acts.
- GCIS kept the 1996 Constitution unchanged at gov.za/constitution/1996 until 2003.
