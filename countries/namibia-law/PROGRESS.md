# Namibia (gitlaw-NA): progress

Repo: lexifina/namibia-law (private). Autopush builds and pushes it. PUBLISH was written 2026-10-29 00:38 UTC.

## Built (corpus.json)
- Constitution: 1 version, 2014-10-13. This is NamibLII's only expression. It already contains the 1998, 2010 and 2014 Amendment Acts, so it is credited to NamibLII as the oldest version available, with those Acts named in `earlier_laws`.
- Labour Act 11 of 2007: 2 versions, 2012-08-01 and 2023-03-15. NamibLII lists only these 2, and both are archived.
- Companies Act 28 of 2004: 3 versions, 2017-01-16, 2023-03-15 and 2023-07-21. NamibLII lists only these 3, and all are archived.
- Test build in .tmp-build: 5 law commits plus 1 docs commit, 8 tags. check.py: 0 mismatches, 0 trailer errors. Rebuild with --compare: every law commit is identical. Only the docs commit differs, because REPRODUCE.md records the check result.
- The fidelity check finds 0 characters of text outside units. Each act's listing check matches NamibLII's current expression.

## Sources and cache
- Every NamibLII expression page comes from an archive.org `id_` capture, fetched with fetch.py through gitlaw_common/wayback.py. Discovery uses one CDX prefix listing of namiblii.org/akn/na/act/, which covers 4102 URLs.
- Common Crawl was unreachable, and NamibLII's robots.txt disallows CCBot.
- NamibLII itself was asked only for robots.txt, its terms (CC BY-NC 4.0; scraping is prohibited) and 4 listing pages.
- .cache/ holds the 1990 Gazette 2 PDF (gazettes.africa, archived). It is a scan whose OCR layer is garbage, so it is not used: no OCR.
- .cache/ also holds the Constitution's source.pdf. It is a Laws.Africa render of the same 2014 text.

## Not possible
- Constitution history before 2014: the original text and all 3 Amendment Acts exist only as scanned Gazette PDFs. NamibLII's pages for those Acts show only the PDF.
- Criminal Procedure Act 51/1977: every archive copy of the 2023-07-25 expression is truncated at 1 MiB or empty, so the Act was dropped (see decisions). The 2014, 2019 and 2024 expressions are cached.

## Local fixes in parse.py (adapter issues: scripts/africa-law/ISSUES-namibia.md)
- Amending laws on the first expression's own day are added to `earlier_laws`, and the first version's note is corrected. The adapter wrongly said "act as published" (issue 4).
- Units that are only an editorial note on a container are dropped: the Constitution's 'long-title', 'text' and 'text-2' (issue 5).
- fetch.py rejects truncated pages that lack `</html>` (issue 1). It does not fetch amending-law pages, which hold only PDFs (issue 2).

## Next step
- Phase 2 candidates with several archived expressions (.tmp/works.json): Income Tax 1981/24 (7), Customs and Excise 1998/20 (16), VAT 2000/10 (4). For each, compare the expressions NamibLII lists in its History tab with what is archived before adding it.
- Add the act to acts.json, then run `python -X utf8 fetch.py` and `python -X utf8 parse.py`.
