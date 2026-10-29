# Lesotho (gitlaw-LS): progress

Repo lexifina/lesotho-law (private). Folder scripts/lesotho-law/. Shared adapter scripts/africa-law/peachjam.py
(read-only), own extensions in lii.py (staged commencement, unapplied-amendment decisions, README fixes) and
constitution.py (Constitution 1993 from LesLII's earlier website). Adapter issues: scripts/africa-law/ISSUES-lesotho.md.

## Status (2026-10-29 00:40 UTC, run stopped)
- [x] Probe: LesLII terms (CC BY-NC 4.0, credit LesLII; scraping prohibited) and robots.txt read from Wayback copies.
      No lesotholii.org page fetched directly. Common Crawl index (index.commoncrawl.org) was unreachable all session.
- [x] Wayback coverage: CDX of lesotholii.org/akn/ls/act/ gives 142 works with an archived expression page; only
      2008/4 (3 expressions) and 2011/1 (2) have more than one. No Peachjam page of the Constitution is archived.
- [x] corpus.json: Money Laundering and Proceeds of Crime Act 2008 (5 versions: 2009-04-01, 2011-06-10, 2012-07-01
      staged commencements from LesLII's table; 2013-03-28 LN 30/2013; 2015-09-25 LN 112/2015) and Anti-Trafficking in
      Persons Act 2011 (2 versions: 2011-01-11, 2021-01-14 Act 1/2021). All changes credited, 0 unexplained.
- [x] corpus.d/10-constitution.json: Constitution as it came into operation 1993-04-02 (166 sections + 3 schedules),
      from Wayback copy 20230326214103 of lesotholii.org/ls/legislation/num-act/1993/1. NO amendments applied ->
      no .PUBLISH, preview only.
- [x] Test build (.tmp-build): 8 commits, 16 tags, check.py 0 mismatches, rebuild hash-identical.
- [x] PUBLISH written for corpus.json (the two acts). Autopush last reported preview pushed 2e2e27e.
- Cache: .cache/ 4.0 MB, 39 files, 52 logged requests (sources.json pins every expression capture).

## Not applied / missing
- MLPCA: Money Laundering and Proceeds of Crime (Amendment) Act 2016 (2017-02-06) and Amendment of Schedule Notice 2017
  (2017-06-30): LesLII itself had not applied them; text after 2017-02-06 is not the law in force (README says so).
- Constitution: every amendment (2nd 1997, 4th 2001, 5th 2004, 6th and 7th 2011 listed by the old page; others later,
  incl. a Tenth Amendment Act No. 15 of 2022 and Tenth Amendment Act 2025 per web search, unverified).

## Next step
1. Constitution amendments: the old site holds PDFs of the amending Acts (lesotholii.org/ls/legislation/act/1996/1,
   1997/7, 2001/4, 2004/8, 2011/13, 2011/15 ... .pdf, all in Wayback CDX, see .tmp/cdx1.txt). Fetch them via
   gitlaw_common/wayback.py, check for a text layer (no OCR), and only if every amendment up to today has one and a
   current official consolidated text exists to check the replay against, rebuild the history; otherwise leave it.
2. Retry Common Crawl (cc_index in peachjam.fetch) once index.commoncrawl.org answers: it may hold LesLII expressions
   the Internet Archive lacks (Constitution AKN page, more multi-version acts).
3. Commencement-notice laws (ln-2011-68, ln-2012-82) have no enacted/published dates; the amending laws' pages are
   PDF-only (ISSUES-lesotho.md item 2).
