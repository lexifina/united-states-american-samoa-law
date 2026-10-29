# gitlaw-BT: Bhutan law history (progress, handoff 2026-10-29 00:42 UTC)

Slug `bhutan`, repo `lexifina/bhutan-law` (PRIVATE), tz Asia/Thimphu, lang en (build English; Dzongkha exists), future_branch `future`.
Rules: scripts/world-law/WAVE.md -> scripts/africa-law/FANOUT.md -> scripts/south-america-law/BRIEF.md.

## State
- [x] Scaffold confirmed: lexifina/bhutan-law main = only c8c32ec "Bhutan: sources, before any law". Cloned to C:/Users/alany/Documents/bhutan-law (autopush owns it; do not build into it).
- [x] fetch.py (curl, sha256(url) cache, 3 req/s/host, requests.jsonl). Cache: .cache/ 40 MB, 20 files.
- [ ] parse.py / corpus.json: NOT STARTED (run stopped by coordinator). No PUBLISH.
- WebSearch used: 0 of 3.

## Sources probed
| Source | Status | Notes |
|---|---|---|
| www.nab.gov.bt (National Assembly) | TLS cert is *.systems.gov.bt (SEC_E_WRONG_PRINCIPAL); with -k it serves an unrelated "Call Center System" SPA | Site is misrouted. Use Wayback `id_` captures (CDX: 19,851 URLs, 1,400 PDFs). |
| oag.gov.bt (Attorney General) | 200, WordPress REST API works | "Depository of Laws" = `?rest_route=/wp/v2/pages/7854`, 232 PDFs (acts as passed, no consolidation). robots.txt 404. |

## Phase 1 PDFs cached (all with text layer unless noted)
- Constitution 2008: OAG `wp-content/uploads/2026/08/Constitution_of_Bhutan.pdf` (75 pp) == Wayback NAB 20151006145515 `assets/templates/images/constitution-of-bhutan-2008.pdf` (same 2,343,010 bytes). Never amended (verify): 1 version, from 2008-07-18 (adoption).
- Penal Code 2004 English: OAG `Penal-Code-of-Bhutan-2004_English-version_.pdf` (79 pp, text). NAB copy not archived (only an error page).
- Penal Code (Amendment) Act 2011: OAG copy is a SCAN (0 chars). Text copy: Wayback 20160706002053 `nab.gov.bt:80/assets/uploads/docs/acts/2014/The_Penal_Code(Amendment)_Act_of_Bhutan_2011eng7th.pdf` (19 pp, text).
- Penal Code Amendment Act 2021: OAG `Penal_Code_Amendment_Act_of_Bhutan_2021.pdf` == Wayback 20210311190821 NAB copy (same 3,645,967 bytes, 53 pp, text).
- ICM Act 2018: not on OAG (only the 2006 Act). Wayback 20190905002039 `nab.gov.bt/assets/uploads/docs/acts/2018/ICMActofBhutan2018.pdf` (349 pp, 412,886 chars; likely English + Dzongkha, split by language).
- Also cached: ICM Act 2006 English (OAG, 237 pp), OAG depository page JSON, Wayback CDX listing.

## Exact next step
1. parse.py: Constitution (Article N headings -> `art-NNN`, Schedules), one version, first_law `constitution-2008`. Find the in-force rule (acts state their own commencement; check each Act's final section).
2. Penal Code: 2004 version (in force per its own commencement section), then replay 2011 and 2021 amendments section by section; no consolidated official text exists, so record the replay as reconstruction in decisions; check whether any 2021 change needs OCR (none expected).
3. ICMA 2018: English pages only; check NAB captures for any later ICM amendment.
4. Build into .tmp-build, check.py to 0 mismatches, --compare, then PUBLISH.

## Open issues
- nab.gov.bt misrouting (wrong vhost) means no live NAB access; everything NAB comes from Wayback.
