# Sri Lanka (gitlaw-LK) progress: handoff, 2026-10-29 00:40 UTC

## Done
- [x] Scaffold confirmed: lexifina/sri-lanka-law had only `main` with "Sri Lanka: sources, before any law". Clone at C:/Users/alany/Documents/sri-lanka-law (autopush owns it).
- [x] Probe: parliament.lk is good. robots allows everything except /api, /adminpanel and /preview. It has text-layer PDFs (no OCR needed) of the consolidated Constitution as amended up to the 17th (2001-10-03), 18th (2010-09-09), 19th, 20th and 21st (2022-10-31) Amendments, the Acts of the 18th-22nd Amendments (5807, 5974, 6176, 6261, 6433), and the 1980 LRE "1978ConstitutionWithoutAmendments.pdf", which is two-column with OCR-like errors and already includes the 1st and 2nd Amendments. The 17th-Amendment page lists amendments 1-17 with their certification dates and articles. documents.gov.lk and lawnet.gov.lk did not answer (curl 000/404).
- [x] corpus.json written and built into .tmp-build; check.py gives 0 mismatches. It holds 2 versions:
  - 2022-10-31: the 21st edition, 267 units (preamble, articles, Schedules 1-9), first_law null, credited to the publisher;
  - 2026-09-25: the Twenty Second Amendment (certified 25 Sep 2026), replayed onto Art. 107(5) and Art. 137.
- [ ] PUBLISH is NOT written: the text has not been proof-read against the official PDF yet.

## Files
- fetch.py: curl cache in .cache/ (sha256 of the URL), with requests.jsonl. All 20 parliament.lk URLs are cached.
- constitution.py: edition parser (EDITIONS config: header y-cutoff and minimum body font size; footnote markers become credits).
- parse.py: writes corpus.json. .work/: scratch dumps (t1.py dumps editions to .work/edNN.txt; diffed.py diffs two of them).

## Known parser issues
- The 20th-edition PDF's text layer lacks some justified words (e.g. Art. 18(4) "Parliament shall ... law provide the"). Don't take unaffected units from it.
- The 21st edition sometimes lacks a final period (source typesetting, e.g. Art. 8).
- Paragraph splitting is heuristic (TOKEN_RE plus the punctuation that ends the line before).

## Next step to resume
1. Proof-read about 20 units of corpus.json against the 21st-edition PDF. If they match, write PUBLISH.
2. Add earlier versions backwards: version k = version k+1 for every unit the Amendment k+1 did not touch. A unit counts as touched if its edition-k footnotes name that Amendment (constitution.parse_edition already returns them) or if the Amendment Act's text mentions the article. For touched units only, take edition k's text. Dates: 17th 2001-10-03 (oldest), 18th 2010-09-09, 19th 2015-05-15, 20th 2020-10-29, 21st 2022-10-31; confirm each against "[Certified on ...]" in the Act PDF.
3. Then the Personal Data Protection Act No. 9 of 2022 and the Penal Code: no source yet (documents.gov.lk and lawnet did not answer). Try Common Crawl via gitlaw_common/wayback.py.

## Verifier sweep 2026-10-29: NOT published (no PUBLISH written)
- Compared all 267 units of version 1 (and the 2 replayed units of the 22nd Amendment, which match the Act text exactly) against an independent pdftotext reading of the 21st-edition PDF (word-level diff; 73,484 of 73,813 corpus tokens matched).
- Fixed in parse.py `fixup()` (corpus.json rebuilt, 35 units changed): lost "(1)" in Art. 18 and "(3)" in Art. 156E; 40+ line-end hyphen splits (Commis-sioner, Parlia-ment ... in Arts 154-170, Schedule 9); chapter headings glued to the end of 11 units (Arts 29, 41J, 53, 61F, 69, 81, 106, 136, 156, 156A, preamble); text cut at a page break (Art. 17 "Chapter.", Art. 111F "Chapter comes into operation."); Secretary-General in Art. 41D; oath wording (Art. 63, Schedules 4 and 7: "solemnly declare and affirm/swear") and the dropped Colombo District row in Schedule 6.
- Build into a scratch repo: 0 mismatches, 0 trailer errors.
- Still open, so no PUBLISH: (a) the 21st Amendment's section 30/31 transitional provisions that Parliament prints in the edition are not built and no decision records that; (b) the check was word-level, not layout-level, so Art. 63 / Schedule 4 / Schedule 7 oath wording and Art. 5 / Art. 8 missing final periods need a human look at the page image; (c) the dating of the 22nd Amendment and the single-edition history (earlier editions not built) are unchanged.
