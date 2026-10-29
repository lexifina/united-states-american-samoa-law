# Palau (gitlaw-PW): progress

Owner: gitlaw-PW (fork session), 2026-10-29. Repo lexifina/palau-law (private). At start `git ls-remote` showed only
`main` (0f2f770 "Paused, not yet law" on c76324a scaffold); the user decided to resolve the pause. Before PUBLISH
(13:3x UTC) it also showed `wip` (a01bde6) and `preview` (5c1588f): both are the push loop's own snapshots of THIS
folder (wip = "Work in progress: scripts/palau-law"; preview history tip f5cf5aa = my local build's). Never commit,
never push. Local scratch build: `scripts/palau-law/.cache/tmp-build` (inside the ignored cache).

## Status: PUBLISH written (Phase 1 done)
- Constitution: 5 versions (1981-01-01 Preamble + Articles; amendments 1992-11-04, 2004-11-06, 2008-11-19,
  2020-11-17), 140 units.
- PNC Title 17 Penal Code: 6 editions (1994-09-30 1st Ed, 2021-05-14 15th, 2021-05-26 16th, 2022-06-02 17th,
  2023-04-25 18th Supp, 2026-09-30 current), 627 sections now.
- PNC Title 1 General Provisions: same 6 editions, 64 sections.
- Local build: 60 commits, 61 tags, 50 laws, 7 unexplained commits; check.py 0 mismatches / 0 trailer errors;
  `--compare` identical, main_identical true. verify.py: 22,968 / 22,971 paragraphs found in pdftotext
  (verification.json; 3 layout misses explained in decisions).

## THE SOURCE: the Code Commission's own publication channel
- palaulaw.gov.pw = "Palau Legal Information Access website, a project of the Republic of Palau Code Commission ...
  free, open ... the official digital repository" (About page in its JS bundle). Live JS app (Zite).
- Its document store: PALAU Office (Publication And Law Access Unit, under the Code Commission per EO 413) public
  Google Drive, folder `1o9b7uIAaNl7qj_yfILpbgstBp6nW90Ox`. Provenance: its "Disclaimer" file (Judiciary website
  disclaimer + 1 PNC s. 1002 + PALAU Law Search CD), its "Palau Law Website Link" file (-> palaulaw.gov.pw), and the
  2020 PALAU Office transition report on palaugov.pw (PNCA supplements are put on Google Drive).
- Listing `https://drive.google.com/embeddedfolderview?id=<id>`; files `https://drive.google.com/uc?export=download&id=<id>`
  (fetch.py `drive_folder`, `drive_file`). Folder/file index cached in `.cache/drive/index.json`.
- Holds: Constitution (EN + Palauan), current PNC titles 1-42 (PDF + Word), RPPL, regulations, Archives/Former
  Supplements: 1st Edition (9/30/94, full titles), 1st (8/15/96) and 2nd (12/1/97) Supps (pocket parts), 15th-18th
  Supps (full titles). Supplements 3-14 are not in the Drive. All PDFs have a text layer.
- Copyright (front matter): "Copyright (c) Republic of Palau, Publication And Law Access Unit". No reuse licence:
  repo stays private.

## Method notes
- Constitution: Code Commission prints the original articles + appended amendments (US style); kept as is.
  First Amendment's date (1992-11-04) is from the public referendum record (the note names only RPPL 3-76).
- PNC: versions dated by edition "through" dates (not in-force days); credits = RPPLs newly named in a section's
  "Sources" note; else unexplained (e.g. 2022 "Minister of Health" -> "... and Human Services", 2026 restyle).
- Paragraphs split only at enumerators after clause ends (layout-independent across typeset vs Word exports).

## Next (Phase 2 ideas)
- More titles: same code path, add to pnc.TITLES (all 42 titles exist in every archived edition).
- Pocket parts (1st/2nd Supps 1996/1997) could add two dated versions for the sections they reprint.
- RPPL texts with a text layer on the Drive could date changes to their enactment.

## Scripts
- fetch.py (curl, cache, Drive helpers), layout.py (PyMuPDF lines; header/footer/annotation split; paragraphs),
  parse.py (corpus.json; Constitution), pnc.py (PNC titles), verify.py (word check), sources.json, probe.py
  (archive.org CDX probe). Run: `python -X utf8 scripts/palau-law/fetch.py; python -X utf8 scripts/palau-law/parse.py;
  python -X utf8 scripts/palau-law/verify.py`. The PNC PDFs are fetched on first use through fetch.drive_file
  (cached; parse.py itself only reads the cache).

## Probe results (for the record)
- palausupremecourt.net (archive.org CDX, 6168 URLs): cases, rules, digests; no PNC or Constitution. Its rules page
  links "Palau Code Commission Publications" (never archived). palaujudiciary.org: 0 captures. palauoek.org: 2026 site
  only. palaugov.pw: PNCA Title 24 (2015) and Title 40 (2018) PDFs; RPPLs there are scans. Common Crawl index
  unreachable from this machine.

WebSearch used: 4 of 4.
