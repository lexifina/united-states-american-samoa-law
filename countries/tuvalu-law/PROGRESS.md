# Tuvalu (gitlaw-TV) progress / handoff (wound down 2026-10-29 00:41 UTC)

Repo lexifina/tuvalu-law was the bare scaffold (only `main`, 7705352 "Tuvalu: sources, before any law"). Clone: C:/Users/alany/Documents/tuvalu-law (untouched; autopush owns it). Never pushed.

## Done
- fetch.py: curl, cache `.cache/` (sha256 of URL, or URL+"\n"+POST data), `.cache/requests.jsonl`, POST support.
- discover.py: POSTs the alphabetical act list (`submit4=<letter>`) and prints each act's history table (PDF per version, commenced, superseded). `python -X utf8 discover.py C P`.
- layout.py: Revised Edition PDF reader (headers/footers, Part/Division heading units, section units `s-NNN[-x]`, schedules `sch-NN`, 7 pt footnote refs kept per unit, endnotes parsed).
- parse.py -> corpus.json: Constitution, 2 versions: 2007-08-03 (2008 RE PDF v1, oldest available, first_law null) and 2023-10-01 (Constitution of Tuvalu Act 2023, Act 7 of 2023, 203 units credited). Test build in .tmp-build: check.py 0 details.
- No PUBLISH yet: text not yet word-checked against the PDF body.

## Sources found
- Constitution: 1986-0001_{1,2,3}.pdf (v2 == v3 at unit level). Penal Code: 1965-0007_1.pdf (2008 RE, consolidated to Act 4 of 2009, 6 Jul 2009) and _2.pdf (2022 RE). 2022 RE endnote 1 lists Acts 12/2009 (2009-12-03), 4/2014 (2014-07-22), 5/2016 (2016-06-03), 18/2017 (2017-11-24), 14/2017 (2018-10-05), 5/2020 (2020-07-22); per-section endnotes name the act. Diff p1->p2: 57 units, mostly "Her"->"His Majesty" (unexplained, revision).

## Next step to resume
1. Fix layout.py paragraph joining across pages: odd/even pages have different left margins (105/133 vs 65/93), so normalise x per page before comparing (see starts_paragraph). Recheck with .tmp/t1.py p1 p2 then .tmp/t4.py p1 p2 (only real wording diffs should remain).
2. Add the Penal Code to parse.py: v1 2009-07-06 (oldest available), one version per later act at its commencement applying units whose 2022 endnotes name only that act (multi-act units: placeholder rule), final 2022-12-31 version for the uncredited Her->His revision.
3. Word-check units vs PDF body text, then write PUBLISH. Third act still to choose.

## Verifier sweep 2026-10-29 (no PUBLISH)
- Constitution v2023-10-01 word-compared with pdftotext of the cached Act 2023 PDF: all provisions match; only diff was Schedule 6 row TVBP00180-181 (merged cell, columns interleaved), fixed in parse.py and corpus.json rewritten. Scratch build + check.py: 0 mismatches, 0 trailer errors.
- PUBLISH NOT written: `git ls-remote` shows main = b42d612 "Paused, not yet law: copyright notice forbids redistribution without permission" (after the 7705352 scaffold commit), so main is not a scaffold (FORK.md rule 4). Text is correct; the blocker is the copyright/redistribution pause, which needs the user's decision.
