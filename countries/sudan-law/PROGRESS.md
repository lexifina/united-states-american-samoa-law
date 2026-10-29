# Sudan (gitlaw-SD) progress / handoff (stopped 2026-10-29 00:40 UTC, coordinator wind-down)

Repo lexifina/sudan-law: scaffold confirmed (only `main`, single commit 4e9800e "Sudan: sources, before any law"). Clone at C:/Users/alany/Documents/sudan-law (autopush owns it; never build into it or push).

## Done
- [x] scaffold check
- [x] probe sources (below)
- [x] fetch.py (curl, cache .cache/<sha256(url)>, requests.jsonl; `get(url, key=)` caches signed URLs under a stable key)
- [x] parse.py + corpus_meta.py -> corpus.json: **Criminal Act 1991 only**, 218 units (185 articles + part/chapter headings + 2 schedules), 0 parse problems, one version `from 2015-03-30`, first_law null (oldest version available, credited to the publisher).
- [ ] NOT verified against the official text by eye beyond spot checks (art. 5, 7) -> **no PUBLISH**.
- [ ] Civil Transactions Act 1984: parses 566 units but 31 problems (report in .cache/parse-report.json). Cause: from Part 16 on the article sequence breaks (a skipped/odd article number, and some articles laid out in `<table>` rows "head | 532ـ | text"). Excluded from corpus via `ONLY` in corpus_meta.py.
- [ ] Constitutional Charter 2019 (+2020, 2025 amendments): **not buildable without OCR.** Official gazette PDFs moj.gov.sd/files/download/144 (2019, 28 pp, scanned pages 4-28), /226 (2020 amendment, scan), /425 (2025 amendment, HP Scan, no text). WIPO Lex details/19705 has the same Arabic scan plus an English text that is an International IDEA translation (constituteproject.org), not official.

## Sources
- MoJ ebook https://www.moj.gov.sd/sudanlaws/ = 9th Revised Edition of the Laws of Sudan (laws in force to 30 March 2015 per its intro, xhtml/sibyrw.html). Unpacked EPUB: /sudanlaws/epub/EPUB/package.xml, nav xhtml/contents.html (full act -> chapter file list, ~400 acts). Criminal Act = xhtml/s53c19.html, Civil Transactions Act = xhtml/sr6vg1.html, Criminal Procedure Act 1991 = scjmfu.html, Civil Procedure 1983 = sjwkt5.html, Evidence 1994 = sev7da.html. Footnotes name amending laws (no dates).
- MoJ gazette list https://moj.gov.sd/files/index/28 (2015-2026 issues; e.g. DL204 = issue 1904 of 13/7/2020, likely the 2020 Miscellaneous Amendments Act affecting the Criminal Act; text layer not yet checked).
- No robots.txt on moj.gov.sd (404). WebSearch used: 1 of 4.

## Resume
1. `python -X utf8 scripts/sudan-law/parse.py --dry` and fix the Civil Transactions Act problems (handle `<tr>` article rows: cells "head | N- | text"; find where the sequence breaks after Part 15), then add its slug to `ONLY` in corpus_meta.py.
2. Read the Criminal Act corpus against s53c19.html end to end; then write PUBLISH.
3. Phase 2: check gazette DL204/DL198-205 (2020) for a text layer to add a 2020 Criminal Act version.
