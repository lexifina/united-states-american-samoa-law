# Oman (gitlaw-OM): progress

## Checklist
- [x] Scaffold check (2026-10-29): lexifina/oman-law has only `main` at 01fe763 "Oman: sources, before any law" (git ls-remote; scaffold clone at C:/Users/alany/Documents/oman-law, read only).
- [x] Probe
  - qanoon.om: WordPress, HTML text of every royal decree as issued (`/p/<y>/rd<y><nnn>/`) plus a consolidated "(معدل)" page (`/p/<y>/l<y><nnn>/`) with footnotes naming the amending decree. robots: allow (only /wp-admin disallowed). States texts are public property under Omani copyright law; states it is NOT an official source.
  - mjla.gov.om (Ministry of Justice and Legal Affairs): laws section lists ~190 laws with official PDFs of current texts (InDesign, 2026). Text layer has broken Arabic glyph order (ligatures reversed, extra marks): not usable as text without OCR/heuristics. Licence: Government Open Licence - Sultanate of Oman. robots: allow except /search, /statistics.
  - opendata.gov.om: redirects; not needed.
- [x] fetch.py (curl, .cache/ by sha256, requests.jsonl, <=3 req/s), qpage.py (Qanoon.om page parser), parse.py (cache only -> corpus.json)
- [x] corpus.json written (3 acts, 0 open problems)
  - nizam-asasi (Basic Statute): 4 versions: 1996-11-06 RD 101/96; 2011-10-27 RD 99/2011 (replayed from its 5 items); 2021-01-11 RD 6/2021 (new statute); 2026-09-13 RD 79/2026 ("الادعاء العام" -> "النيابة العامة")
  - qanun-al-jaza (Penal Code RD 7/2018): 4 versions: 2018-01-15; 2022-10-24 RD 68/2022; 2025-01-14 RD 11/2025; 2026-06-29 RD 66/2026
  - himayat-al-bayanat (PDPL RD 6/2022): 2 versions: 2023-02-13; 2026-09-07 RD 68/2026
- [x] verify.py: every article of the current version of all 3 acts matches the MJLA PDF letter for letter (98/98, 397/397, 34/34); verification.json
- [x] repo/README.md (English first, Arabic section), LICENSE, jurisdiction.json
- [x] Scratch build (scripts/oman-law/.tmp-build, a clone of the scaffold; --docs-date 2026-10-29): 10 commits + docs commit, 20 tags, 0 unexplained; check.py 0 mismatches, 0 trailer errors, 0 merges/backwards/future; --compare into .tmp-compare identical (history tip d1165deaab6b, main 355fc5bbe7e2).
- [x] Scaffold re-checked right before PUBLISH: only main at 01fe763. PUBLISH written 2026-10-29.
- Nothing committed or pushed (cadence change). The original session's push pass picks this folder up.

## Numbers
- Cache: 28 requests, 3.8M. Sources: Qanoon.om (13 pages), mjla.gov.om (9 listing pages, 3 show pages, 3 PDFs).
- Laws: 10 royal decrees (rd-1996-101, rd-2011-99, rd-2021-6, rd-2026-79, rd-2018-7, rd-2022-68, rd-2025-11, rd-2026-66, rd-2022-6, rd-2026-68).

## Known limits (also in README / decisions)
- Qanoon.om is unofficial (its own statement); official MJLA PDFs have a scrambled text layer, so they serve only the letter check (alef and word order are invisible to it).
- RD 99/2011 state is a replay of its 5 items (no consolidated 1996-as-amended text exists online).
- Heading changes (Penal Code chapter title by RD 68/2022; Part V bis heading by RD 66/2026) are not commits: headings are not units.
- Penal arts 29, 114, 143: consolidated page differs by transcription only; text as issued kept.

## Phase 2 ideas
- Same Qanoon.om pattern (rd page + l page with footnotes) covers most laws: Civil Transactions Law (RD 29/2013), Labour Law (RD 53/2023), Commercial Companies Law (RD 18/2019). MJLA PDFs exist for all of these for the letter check.

## Resume
    cd scripts/oman-law; python -X utf8 fetch.py; python -X utf8 parse.py; python -X utf8 verify.py; python -X utf8 parse.py   (parse reads verification.json into sources)

## Coordinator (2026-10-29): main held
PUBLISH renamed to .PUBLISH.held. The corpus is in Arabic, and the user's current scope rule is no right-to-left scripts for now (see WAVE.md). Restore PUBLISH only if the user approves.
