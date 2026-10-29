# gitlaw-BM: Bermuda law history (progress, handoff 2026-10-29 00:42 UTC)

Slug `bermuda`, repo `lexifina/bermuda-law` (PRIVATE), clone `C:/Users/alany/Documents/bermuda-law`.
tz Atlantic/Bermuda, lang en, future branch `future`. Rules: scripts/world-law/WAVE.md.

## Status: probe done, fetch.py written, NO corpus.json yet (run wound down by coordinator)
- [x] Scaffold verified: main = one commit 1e488be "Bermuda: sources, before any law"; cloned.
- [x] Probe of bermudalaws.bm (below). 1 of 3 WebSearch calls used.
- [x] fetch.py written (live PDFs + archive.org CDX/id_ captures + Common Crawl, writes snapshots.json). First run
      was stopped at wind-down after ~13 cache files (index queries); rerun it, it resumes from .cache.
- [ ] parse.py (layout -> units per section, snapshot diff, notes -> credits/dates)
- [ ] corpus.json, build in .tmp-build, check.py, --compare, repo/README.md, PUBLISH

## Probe findings (verified 2026-10-28)
- bermudalaws.bm is a Blazor Server app; robots.txt 404. Documents are PDFs (Antenna House, text layer, no OCR needed).
- Live URL: `https://www.bermudalaws.bm/Laws/Consolidated%20Law/<year>/<title>` returns the current consolidated PDF
  (e.g. 1907/Criminal Code Act 1907, 1968/Bermuda Constitution Order 1968, 2016/Personal Information Protection Act 2016).
  Annual (as enacted) laws: `/Laws/Annual%20Law/Acts/<year>/<title>` and `/Laws/Annual%20Law/Statutory%20Instruments/<year>/<title>` (1993+).
- **The live site has NO point-in-time versions** (WebSearch + site pages: only current consolidations; "Amended by"
  list at the end). The task brief's claim of PIT versions did not hold. Crown Copyright, all rights reserved.
- Per-provision notes give the amending instrument and in-force date, e.g.
  `[Section 4 subsection (4) amended by 2023 : 23 s. 3 effective 1 January 2025]`,
  `[Section 2 amended by UK SI 2579/2001 effective 21 August 2001]`. Use these for credits and `from` dates.
- Dated history source = archived consolidations: Wayback has ~11 distinct Criminal Code PDFs
  (2013-05-12, 2015-12-23, 2016-09-14, 2018-02-09, 2019-03-30, 2020-10-28, 2021-09-22, 2022-06-22, 2022-08-03 under
  old URL `/Laws/Consolidated%20Laws/<title>.pdf`; 2024-11-02, 2025-08-08 under the new URL). Constitution/PIPA CDX not yet listed.
- PIPA 2016: assent 27 Jul 2016; ss.1,2,26-29,35,36,51,52 in operation 2 Dec 2016; rest later (2023:23 effective
  1 Jan 2025); amended by BR 115/2017, 2023:23, BR 100/2025. Annual Act could serve as the enacted first version.
- Constitution: Order (ss.) + Schedule (Constitution sections 1-105 + 1st/2nd Schedules); amended by UK SIs 1968-2003
  and BR 89/2010 (eff. 9 Nov 2012), BR 122/2017 (eff. 21 Aug 2020) replacing the 2nd Schedule (constituencies).

## PDF layout notes (for parse.py)
- pymupdf: body font BookmanOldStyle 9pt; page header "CRIMINAL CODE ACT 1907" Bold 10pt at y~107; page number
  Bold 12pt at y~683. TOC lines: section numbers at x=108, headings at x=148 (skip TOC: before the first body section).
- Notes are bracketed lines starting `[Section ...`; end matter `[Assent Date: ...]`, `[Amended by: ...]`.

## Exact next step
1. `python -X utf8 scripts/bermuda-law/fetch.py` (resumable; archive.org is the bottleneck, shared rate).
2. Write parse.py: units per section (keys `s-001`, `s-001a`; Constitution `order-s-NNN` + `s-NNN` + `sch-N`),
   diff consecutive snapshots, date each changed unit by its newest note's effective date after the older snapshot,
   credit the named instrument; unexplained diffs -> publisher at capture date; multi-law gaps -> placeholder text
   per the "text before its law" rule. Base version = oldest snapshot, `first_law: null`.
3. Build into .tmp-build, check.py to 0 mismatches, then PUBLISH.

## Open issues
- None filed. Cache: scripts/bermuda-law/.cache (2.1 MB, gitignored).
