# gitlaw-GD: Grenada law history (progress)

STOPPED 2026-10-29 00:42Z at the coordinator's wind-down. No corpus.json and no PUBLISH yet; nothing built or pushed.

Slug `grenada`, repo `lexifina/grenada-law` (PRIVATE, never change), clone `C:/Users/alany/Documents/grenada-law`.
Scaffold verified 2026-10-28: only `main`, one commit f8427e1 "Grenada: sources, before any law" (ls-remote HEAD = refs/heads/main = f8427e1).
tz America/Grenada, lang en, future branch `future`. Rules: scripts/world-law/WAVE.md (+ africa-law/FANOUT.md, south-america-law/BRIEF.md).

## Checklist
- [x] Scaffold check + clone (still only the scaffold; RECHECK with `git ls-remote` before writing PUBLISH)
- [x] fetch.py (curl, sha256(url) cache, 3 req/s/host, UA lexifina-watch, .cache/requests.jsonl)
- [~] Probe laws.gov.gd (done for the structure; see below)
- [ ] Find the Constitution Order 1973 on laws.gov.gd (not a numbered chapter; try the "map-of-folders/legislation-folder" page or the site search)
- [ ] Find the Data Protection Act 2023 (the /index.php/acts year list only shows 2011-2022; check acts-folder for 2023)
- [ ] parse.py, corpus.json, test build in .tmp-build, check.py, then PUBLISH

## Probe findings (laws.gov.gd, 2026-10-28/29, 8 requests)
- Joomla + eDocman. robots.txt allows all (`Allow: /`), has a sitemap.xml (cached).
- Revised laws by chapter: /index.php/chapters/<letter range>/<id>-chapter-..., each page links a PDF at `.../<docid>-capNN-.../download`.
- Criminal Code: Cap. 72A, page /index.php/chapters/c-39a-75d/119-chapter-72a-criminalcode, PDF
  /index.php/chapters/c-39a-75d/1107-cap72a-criminal-code/download (1.02 MB, posted 3 July 2024). HAS A TEXT LAYER (pdftotext works).
  Header lists its history: Act No. 76 of 1958, amended by 23/1962, 32/1962, 1/1963, 7/1964, 5/1966, 10/1966, 45/1972, 18/1973,
  35/1973, 36/1973, 12/1974, 3/1980, 16/1993, 36/1993, 34/1994, 9/2004, 11/2007, 15/2007.
- Annual Acts 2011-2022: /index.php/acts/<id>-<year>, each act a PDF download (e.g. Act No. 1 of 2022). S.R.&O. folder too.
- Source gives one consolidated text only (no dated versions, register pit=n). History has to come from replaying amending acts;
  pre-2011 amending acts are not on the site (likely gazette scans or absent). Realistic Phase 1: current text as "oldest version
  available" (first_law null) + any post-2011 amending acts that have text layers, verified by replay against the consolidation.

## Exact next step
1. Fetch /index.php/map-of-folders/legislation-folder and acts-folder to locate the Constitution and 2023 acts.
2. pdftotext -layout the Criminal Code PDF (cached as .cache/b0b48d00...ad27) and write parse.py (sections from the
   "ARRANGEMENT OF SECTIONS" body; drop running headers/page footers).
3. Check whether the chapter PDFs give a revision date ("revised edition as at ...") for the version `from` date.

## Cache
.cache/: 8 responses (home, robots, sitemap, chapters C page, acts index, acts 2022, legislation index, Criminal Code PDF). WebSearch used: 0.
No background processes were started.
