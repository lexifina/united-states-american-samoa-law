# Cyprus (gitlaw-CY-2): progress / HANDOFF

Rules: scripts/world-law/WAVE.md, scripts/south-america-law/BRIEF.md (CADENCE CHANGE: no pushes; verify locally),
gitlaw_common/SCHEMA.md. gitlaw-CY (probe) 2026-10-28 22:40 to 10-29 00:42; gitlaw-CY-2 10-29 ~01:20 to ~06:40 UTC.

## Status: all three parts built, verified locally and marked PUBLISH (nothing pushed or committed)
- [x] fetch.py: CyLaw read only via Internet Archive (`wayback.py`), never cylaw.org; Gazette issues from the
      Printing Office (`--gpo`, direct, 1 req/s). Pins in sources.json. Cache .cache/ 75 MB, 505 requests logged
      (164 direct to mof.gov.cy).
- [x] parse.py -> corpus.d/ (country block in every part; no corpus.json). Deterministic (re-run gives same bytes).
- [x] 10-data-protection: Law 125(I)/2018, 2 versions: 2018-07-31 as enacted; 2022-03-11 N.26(I)/2022 (arts 2, 3).
- [x] 20-constitution: 15 versions, 2013-07-17 (oldest available, after 68(I)/2013) to 2025-11-07, plus 67(I)/2025
      on `mellon` (2027-07-01).
- [x] 30-criminal-code: Cap. 154, 15 versions, 2017-04-07 (oldest available, after 31(I)/2017) to 2025-12-12.
- [x] Scratch build of all parts (session scratchpad): 34 commits, 32 versions, 0 mismatches, 0 trailer errors,
      0 unexplained; --compare identical. Last version of each act == newest archived consolidated page.
- [x] Remote main = scaffold 5c5b2a0 (git ls-remote, read-only, rechecked just before PUBLISH). PUBLISH +
      corpus.d/{10,20,30}-*.PUBLISH written. The next 4-hourly autopush pass publishes.

## Method (parse.py docstring has the detail)
Per section, CyLaw's history on the newest full.html lists its instruments; wording "as left by" instrument e comes
from (1) the newest full page, (2) the archived old-wording page (`-ln...` or `-ai...` links), (3) any archived full
copy whose list ended where the section had the same last instrument (sections CyLaw re-created under a new id are
matched by number). Versions = the act on each in-force day; a section whose chain is not a prefix of the laws in
force is unrepresentable. A law with no sourced day makes the window between its neighbours' publication days
unknown. History starts at the first day after which no day is missing. Every archived full copy is compared with
the rebuilt version for its list (`parse.py --report`).

## Dates
- Cap. 1 s. 7: a law takes effect on Gazette publication unless it provides otherwise.
- Gazette issue/date from CyLaw extract /nomoi/arith/*.pdf (text layer), else the Printing Office issue.
- Own commencement: 95/1989 s.5 -> 1990-01-01; 67(I)/2025 s.3 -> 2027-07-01; 134(I)/2020 s.3 -> 2020-10-01.
  103(I)/2022 s.7: deferred parts (Art. 144 para 1(3),(4); Art. 155(2) repeal) shown from publication (listed).
- Printing Office archive (gazette.nsf): years 2026=1..2004=23, month y.m, annexes y.m.2. First Annex Part I is
  listed only for recent years (found 186(I)/2025 -> Αρ. 5060 2025-11-07; 212(I)/2025 -> Αρ. 5065 2025-12-12).

## Left out (listed in README and decisions)
- Constitution: 1960 text (no sourced commencement day) and 1990-2002 versions (127(I)/2006, 51(I)/2010 undated).
- Cap. 154: everything before 2017-04-07 (36 laws + ΑΝΑΚ.3309 undated, latest 43(I)/2016 whose PDF text is garbled).

## Ideas to go deeper
- Constitution back to 1960 needs the Gazette dates of 127(I)/2006 and 51(I)/2010 (and a sourced 1960 date):
  another archived copy of the Gazette issues, or a non-retyped CyLaw extract.
- Cap. 154 earlier: dates for the 1999-2016 laws; the Printing Office has no Part I issues online for those years.
- Common Crawl index was unreachable from this machine all session (cc_crawls returned []).
- Build scratch repos in the session scratchpad, NOT in this folder (.tmp-build is not gitignored in lexifina).
