# gitlaw-TO: Tonga law history (handoff, 2026-10-29 00:37 UTC, run stopped by coordinator)

Slug `tonga`, repo `lexifina/tonga-law` (PRIVATE; scaffold b609a93 "Tonga: sources, before any law", checked: only main).
Clone `C:/Users/alany/Documents/tonga-law` (autopush owns it; never push). tz Pacific/Tongatapu, lang en (Tongan versions
exist; English built), future branch `future`. Rules: scripts/world-law/FORK.md -> WAVE.md -> africa-law/FANOUT.md -> south-america-law/BRIEF.md.

## State
- corpus.json written (2 acts): Constitution 17 versions (1988-12-31 .. 2020-12-04), Criminal Offences Act 18 versions.
- Shared build into `.tmp-build` passes (docs-date 2026-10-28): 64 tags, 29 laws, check.py clean. Earlier autopush failure
  (units were strings) is fixed.
- NO PUBLISH yet: the latest versions are not yet word-verified against the 2020 Revised Edition PDFs (write verify.py).
- WebSearch used: 0 of 4.

## Sources (all direct, ago.gov.to, open; PacLII is behind Cloudflare and was not touched)
- Index: POST `https://www.ago.gov.to/cms/legislation/current-revised-edition/by-title.html?view=acts_alpha` with
  `submit4=<LETTER>&pointintime=2026-10-28+00%3A00%3A00` (sources.py `history(letter, title_re)` parses each act's
  "Legislation History Table": v1 = 1988 Revised Edition, v2 = 2016 RE, v3 = 2020 RE, with "Date Commenced", plus the
  amending Acts since 2020 with PDFs and commencement dates).
- PDFs (text layer, base https://www.ago.gov.to/cms/images/LEGISLATION/PRINCIPAL/):
  Constitution 1988/1988-0002/ActofConstitutionofTonga_1.pdf, ConstitutionofTonga.pdf_2.pdf (2016; not in the modal but live),
  ConstitutionofTonga.pdf_3.pdf (2020); Criminal Offences 1924/1924-0010/CriminalOffencesAct_{1,2,3}.pdf;
  Land Act LandAct_{1,2,3}.pdf (history fetched, PDFs not yet); Interpretation Act 1903/1903-0006/InterpretationAct_{1,2,3}.pdf.
- Commencement rule: Interpretation Act Cap. 1.02 s. 3(1) (Gazette publication day; cl. 79 Acts on the King's signature);
  s. 21: the Tongan version prevails.
- Acts by year (titles + PDFs of amending Acts): POST `https://www.ago.gov.to/cms/legislation/acts-by-year.html?view=acts_by_year`
  (select field name not yet identified).
- Cache: `scripts/tonga-law/.cache/` (sha256(url or url+' POST '+data)), log `.cache/requests.jsonl`.

## Scripts
- `fetch.py` (curl, cached, <=3 req/s), `sources.py` (index parsing), `layout.py` (PDF -> provisions, endnotes, parts;
  drops 1988 inline italic notes and superscript markers), `parse.py` (versions; method in its docstring).
- Run: `python -X utf8 scripts/tonga-law/parse.py`, then build into `.tmp-build` and check.py as in SCHEMA.md.

## Next steps (in order)
1. parse.py: strip trailing "." from 1988 titles; treat changes in spacing/punctuation only as no change (2020 text layer
   has "s hall" in cl. 19); build the commencement table from ALL editions plus the Interpretation Act 2016/2020 endnotes
   (Acts 42 and 46 of 2010, commenced 24 Nov 2010, explain many Criminal Offences changes now "unexplained");
   detect "THE SCHEDULE" in the 1988 COA (it is now absorbed into s. 200).
2. Resolve the source conflict: COA 2020 endnotes say "Act 6 of 2020" for ss. 126-127, the table says "Act 6 of 2016, 16 June 2020".
3. verify.py: latest version vs the 2020 RE PDFs word for word; then write PUBLISH.
4. amendments.py (parse.py already imports it if present): replay post-2020 Acts from the history-table PDFs:
   Constitution Act 10/2018 (cl. 31B, in force 2021-08-11), Act 2/2021 (cl. 31C, 2021-08-11), Act 2/2025 (2025-05-22),
   Acts 14/2025 and 24/2025 (2025-12-19); COA Acts 2, 3, 7, 10 of 2022 (2023-02-06), 6/2025 (2025-09-04), 20/2025 (2025-10-01).
5. Third act: Land Act (LandAct_{1,2,3}.pdf; v3 dated 2020-10-31), add to ACTS in parse.py.
6. Known source limits: per-clause changes made by several Acts between editions get a placeholder between the first and
   last Act (listed in decisions); the Taione v Kingdom [2005] ruling on cl. 7 changes no printed words (endnote only).
