# gitlaw-FM: Federated States of Micronesia (2026-10-29, Phase 1 done, PUBLISH written)

Repo lexifina/micronesia-law. Before start `git ls-remote` showed only `main` (465bf82 "Paused, not yet law", on
48b9134 scaffold; the coordinator said that is expected). Re-checked before PUBLISH: `preview` (c141069) and `wip`
(b73517e) now exist, both pushed by the push loop from THIS folder (preview history tip f32e4e6 = my build;
BUILD_STATUS.json / .autopush.json here). Never commit/push; the push loop does it.

## User decision
Build from the fsmlaw.org Code of the FSM 2014 Edition (Annotated) and Constitution pages: an unofficial
consolidation published by the FSM Legal Information System under the FSM Supreme Court; not an official
publication. Post-edition public laws applied from the FSM Congress (cfsm.gov.fm, official, text layer).

## Done
- [x] discover.py -> sources.json (pinned IA captures; Congress URLs)   - [x] fetch.py (everything cached)
- [x] layout.py: Code PDFs by font size (12 pt law, 10 pt notes; PyMuPDF); Constitution HTML by FONT SIZE (3 law,
      2 annotations); public laws via pdftotext -layout (line numbers/heads stripped)
- [x] parse.py -> corpus.json   - [x] verify.py -> verification.json: 0 misses (1,451 edition paragraphs vs the LIS
      per-chapter 2014 HTML; 206 PL paragraphs vs PyMuPDF text of the enrolled PDFs)
- [x] local build `.tmp/build` (docs-date 2026-10-29): 10 commits, 17 tags; check.py 0 mismatches, 0 trailer errors;
      `--compare` identical   - [x] repo/README.md, LICENSE, jurisdiction.json   - [x] PUBLISH

## Acts
- constitution: 1 version (2003-06-08, oldest available; 111 units). Newest (2023-24) and oldest (2002-03) captures
  of all 17 pages have identical law text.
- title-11-crimes: 2012-03-16 (2014 ed., dated by PL 17-38) + PL 18-02, 18-19, 18-43, 21-08, 21-149 (6 versions).
- title-07-citizenship: 2012-06-06 (2014 ed., PL 17-54) + PL 19-91, 23-140 (3 versions).

## Open issues
- Constitution: July 2023 referendum amendments (9 proposals; dual citizenship passed per PL 23-140) NOT applied:
  no official text + certified result found (constitution.gov.fm/adopted-proposals etc. 404). gov.fm PIO page
  "all-nine-proposed-amendments..." (cached) describes them only. Next: find certified results/text (Congress
  resolution, Gazette, or IA capture of constitution.gov.fm/adopted-proposals/).
- PL 21-08 § 1141: trailing "(1) Notwithstanding..." outside the quotation not applied (decisions).
- Phase 2: more Code titles (same pipeline: add to TITLES/AMEND in parse.py; search Congress index for amendments).

## Sources
- fsmlaw.org via archive.org only (robots Crawl-delay 30). Tit11 PDF 20260611041125, Tit07 PDF 20190715110226.
  (The 20250119 Tit11 capture is truncated at 1 MiB: not used.)
- cfsm.gov.fm 17th-24th Congress indexes (date per law) and enrolled PL PDFs (direct, <=3 req/s).
WebSearch used: 1 of 4.

## Rerun
python -X utf8 discover.py; python -X utf8 fetch.py; python -X utf8 parse.py; python -X utf8 verify.py; then
build into an empty scratch dir + check.py as in scripts/world-law/FORK.md.

## Constitution held off main (coordinator, 2026-10-29)

The Constitution now lives in `corpus.d/10-constitution.json` with no `.PUBLISH`, so it builds to `preview` only;
`corpus.json` (Titles 11 and 7, verified) keeps `PUBLISH` and goes to `main`. Reason: the July 2023 referendum
amendments are known to be missing (same rule as Ecuador's Código de Comercio and the Sierra Leone, Tanzania and
Mauritius constitutions). To publish it: apply the 2023 amendments from an official text, verify, then write
`corpus.d/10-constitution.PUBLISH`. If parse.py is re-run, it must write the Constitution to that part, not to
corpus.json.
