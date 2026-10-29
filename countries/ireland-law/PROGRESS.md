# Ireland (gitlaw-IE): progress

**Status: stopped on the coordinator's instruction (2026-10-28).** lexifina/ireland-law `main` already holds another
session's build. No corpus.json, corpus.d or PUBLISH was written here, so autopush does not pick this folder up.

## What the existing repo holds (origin/main, head 75f491b, 27 commits; also a branch `sync/main`)

- Two Acts from the Law Reform Commission's Revised Acts PDFs (every current and previous revision listed on
  revisedacts.lawreform.ie/revacts/alpha), built by its own builder, not the shared gitlaw_common one:
  - Data Protection Act 2018 (No. 7 of 2018): 17 revisions, 2018-12-26 to 2026-07-16.
  - Protected Disclosures Act 2014 (No. 14 of 2014): 8 revisions, 2018-06-09 to 2026-06-08.
- One commit per amending law per in-force day, from the F-note annotations; author `<kind>-<year>-<n>@irishstatutebook.invalid`;
  noon Europe/Dublin. Layout-only and two-law changes are publisher commits.
- `tools/build.py` (1102 lines: PDF reader with PyMuPDF, annotation parser), `check_repo.py`, `on_date.py`,
  `reproduce.py`, `test_repo.py`; README, REPRODUCE.md, amendments.csv, corpus.json (its own metadata format, not SCHEMA.md).
- REPRODUCE.md reports 25 revisions checked against the PDFs with 0 mismatches and an identical-hash rebuild.
- Not in it: the Constitution (its README says it is not in the Revised Acts) and the Companies Act 2014.

## Probe findings, for whoever continues (not acted on)

- Revised Acts list has 25 listings for the Companies Act 2014 (eli 2014/act/38), 19 Dec 2018 to 15 Jul 2025, as
  versioned S3 PDFs; the existing builder's reader should handle them with `{'eli': '2014/act/38', ...}` added to ACTS.
- eISB Constitution (`/eli/cons/en/html`, 678 KB) is the current text only (no point-in-time URLs: `/eli/cons/<date>/en/html`
  gives 404); it carries a table of the 32 enacted Amendment Acts with their signing dates (1st 1939 to 38th 2019).
- Amendment Acts are at `/eli/<year>/ca/<n>/enacted/en/html` (XML exists but was 1 KB for the 36th: check it).
- No official 1937 text with a text layer was found yet; a forward replay needs one (or a dated archived official text).
- robots.txt: irishstatutebook.ie has none (404); revisedacts.lawreform.ie disallows nothing.

## Local state

- `.cache/probe/` holds the probe downloads (gitignored). WebSearch calls used: 0.
- A clean clone of origin/main is at `C:/Users/alany/Documents/ireland-law` (made by this session, unchanged).
