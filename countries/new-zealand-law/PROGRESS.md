# gitlaw-NZ: New Zealand law history (fork wave, started 2026-10-29 ~02:25 UTC)

Slug `new-zealand`, repo `lexifina/new-zealand-law` (PRIVATE). Rules: scripts/world-law/FORK.md (CADENCE CHANGE: no commits,
no pushes; verify locally) -> WAVE.md -> africa-law/FANOUT.md -> south-america-law/BRIEF.md.

## Checklist
- [x] Scaffold check 1 (02:25 UTC): `git ls-remote` shows only `main` = 8e62ce6 "New Zealand: sources, before any law" (single commit).
      Scaffold copy cloned to `.tmp/scaffold/` (read-only reference).
- [x] Probe (02:30 UTC):
  - www.legislation.govt.nz: HTTP 202 + `x-amzn-waf-action: challenge` (AWS WAF bot challenge) even for robots.txt.
    NOT touched again (rule: never touch a bot challenge).
  - api.legislation.govt.nz: `/v0/works` -> 401 {"error":"API key is required"} (key by email to PCO; we have none).
  - Common Crawl index (index.commoncrawl.org): connection refused/timeout from this machine at 02:30; CDN data.commoncrawl.org OK.
  - archive.org CDX via shared `wayback.captures`: works (slow, shared 429 backoff). Constitution prefix
    `legislation.govt.nz/act/public/1986/0114/` = 2313 captures, all under `latest/` (DLM*.html, whole.html, versions.aspx, PDF).
  - Old-site layout: `/act/public/<yyyy>/<nnnn>/latest/whole.html` (whole Act, header "as at <date>"), `versions.aspx`
    (list of versions + "List of amendments incorporated in this version").
  - Constitution versions.aspx (capture 2024-03-20): ONE version only, "as at 17 May 2005", amendments incorporated:
    Constitution Amendment Act 2005 (2005 No 48), Public Finance Amendment Act 2004 s 37(1), CDEM Act 2002 s 117,
    Constitution Amendment Act 1999, Electoral Act 1993 s 271, Constitution Amendment Act 1987.
- [x] Sources settled (resumed ~11:45 UTC after the rate-limit pause):
  - Common Crawl does not hold legislation.govt.nz (CDX block for CC-MAIN-2025-08 jumps lawcom -> linz); index.commoncrawl.org
    was unreachable, so `ccindex.py` reads cluster.idx/cdx-*.gz from the CDN by byte range (works; kept as a tool).
  - Internet Archive holds the site well: old site `/act/public/Y/NNNN/latest/whole.html` + numbered `<k>.0/whole.html`,
    new site (2026) `/act/public/Y/N/en/latest/` and `/en/<as-at date>/`. Same body markup (div.prov, p.history-note).
  - `fetch.py`: CDX listing + bisection over `latest` captures by stated "as at" date -> `captures.json`.
  - `parse.py`: units = long title, sections, schedules; history notes -> (in-force date, amending Act) credits.
- [x] Constitution Act 1986: 4 versions 2005-05-17 (oldest archived, publisher) / 2025-11-13 (s 25 repealed, Parliament
      (Repeals and Amendments) Act 2025) / 2026-07-10 (ss 6, 8, Constitution Amendment Act 2026; dated by notes) /
      2026-09-04 (s 18, new s 18A, Emergency Management Act 2026). 1 unexplained: s 22 "or." -> "or" (PCO correction).
      The "as at 03 Sep 2007" page (2009-11 captures) is an older rendering of the re-issued 17 May 2005 consolidation.
- [x] NZBORA 1990: 3 versions 1994-02-01 / 2013-07-01 (s 24(e), Criminal Procedure Act 2011) / 2022-08-30 (ss 7A, 7B,
      NZBORA (Declarations of Inconsistency) Amendment Act 2022). 2026 new-site captures still state 30 Aug 2022.
- [x] Privacy Act 2020: 26 versions 2020-12-09 .. 2026-05-01 (20 archived consolidations + 6 days dated by history
      notes), 229 units, 24 amending Acts/Orders + `pco-editorial` (PCO editorial changes, kind publisher).
      Pre-commencement consolidations (as at 2020-08-01, 2020-08-07) and as-enacted pages (69.0, 72.0) excluded (in force
      1 Dec 2020). 5 placeholders (sch-04 2023-11-01; s 138 2024-06-30; ss 22, 44, 49 2025-09-24), 1 unexplained (sch-02
      2023-12-06). Built from cache (`fetch.py privacy-act --cached-only`): archive.org congested, the uncached captures
      lie inside runs whose ends state the same date or in the Mar-May 2026 gap (dated by notes anyway).
- [x] Truncation guard (12:50 UTC): some Wayback captures are cut at exactly 1 MiB (no </html>); parse.py skips them
      and logs it. Only pre-commencement Privacy pages were affected; published versions unchanged, verify OK.
- [x] Parser fixes: site chrome (slInfoAlert, link-to-sl-button), PCO editorial notes dropped; SL/LI/SR citations;
      bilingual citations (English half); "editorial change made by the PCO" -> pco-editorial.
- [x] (stretch) Crimes Act 1961 (fetched 12:37-13:08 UTC, built by 13:14): 58 versions 2007-09-03 .. 2026-08-08, 590
      units today, 63 amending Acts/Orders credited; 455 unexplained provision changes on 8 days (PCO reprint restyling,
      esp. 2009-12-08, 2013-08-19, 2015-11-07); 1 placeholder (s 244, 2009-10-17). 21 truncated (1 MiB) captures skipped.
      Old reprints' appended amending-Act provisions (div.skeletons) excluded. Commencement Orders named beside an Act
      are not credited; "pursuant to"/old "by section N X Act" note forms handled. verify.py OK.
- [x] verify.py: both acts OK (replayed corpus == newest archived page, captured 2026-10-05, unit for unit; exact text).
- [x] Local build (.tmp-build, docs-date 2026-10-29): 8 commits, 12 tags, 1 unexplained; check.py 0 mismatches / 0 trailer
      errors; --compare identical (main 496fc50).
- [x] Scaffold check 2 (~12:00 UTC): main = 8e62ce6 only scaffold commit; `wip` b2c4ab8 exists but is the coordinator's
      autopush snapshot of THIS folder (05:03 UTC, contains this PROGRESS.md + ccindex.py), not another session.
- [x] PUBLISH written (Constitution + NZBORA), rewritten 12:40 UTC to cover the Privacy Act.
- [x] Final local build (13:14 UTC): 4 acts, 91 versions, 112 commits, 181 tags, 10 unexplained commits; check.py 0
      mismatches / 0 trailer errors; --compare identical (main 1ba5552). Remote main 3369a03 (coordinator push of the
      4-act corpus); next pass picks up label fixes + README. Scaffold check 3 (13:14): only main + wip (our snapshots).
- [x] PUBLISH rewritten 13:15 UTC for all 4 acts.
- [x] Coordinator push pass pushed main 5e83e8d at 12:36 UTC (3 acts, check clean, BUILD_STATUS.json). Latest local
      build 37 commits / 62 tags / 2 unexplained, main b2d5ce4 (README update), --compare identical. repo/README.md, LICENSE, jurisdiction.json written.
- Licence (legislation.govt.nz/copyright/, capture 20260712): no copyright in NZ legislation (Copyright Act 1994 s 27);
  other site content Crown copyright, CC BY. Recorded in licence_note, LICENSE, README.
- NOTE: never add an act to corpus.json unless verify.py passes for it (PUBLISH is live).

WebSearch used: 0 of 4. Cache: see .cache/requests.jsonl (archive.org id_ + CDX, CC CDN index probes).
