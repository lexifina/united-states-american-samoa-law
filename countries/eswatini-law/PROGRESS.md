# Eswatini (gitlaw-SZ): progress

Owner: gitlaw-SZ (resumed 2026-10-29 by gitlaw-SZ-RW). Rules: `scripts/africa-law/FANOUT.md`. Adapter:
`scripts/africa-law/peachjam.py` (read-only; this folder vendors an exact copy through fetch.py/parse.py, as Zambia
does). Local extension: `lii.py` (dates of the PDF-only amending Acts from their History tabs; the adapter could adopt
it: accept a law page without akn text for law_meta when the History tab is present).

## Sources (probed 2026-10-28)
- EswatiniLII (eswatinilii.org), the Judiciary of Eswatini on Laws.Africa Peachjam.
  - robots.txt: `User-agent: *` Allow / with Crawl-delay 5; disallows /api/, /search/, /judgments/, /gazettes/,
    /akn/*/provision/*, /akn/sz/judgment/, /akn/sz/officialGazette/. Content-Signal search=yes, ai-train=no,
    use=reference. Named AI crawlers: Disallow /.
  - Terms (/terms-of-use/): content CC BY-NC 4.0, crediting EswatiniLII; "Scraping and bulk downloading from this
    website is strictly prohibited". So: no LII document page is fetched; only archived copies (Internet Archive
    `id_`, Common Crawl).
  - Listing pages /legislation/?years=Y are open (200); 7 fetched at 5 s spacing to choose acts and check currency.
- Wayback: one CDX prefix query found 361 works with archived expression pages, only 48 with more than one expression.
  Common Crawl: 105 works (crawls 2022 to 2026). swazilii.org: no /akn/ captures.

## Findings
- EswatiniLII's history is thin: most acts have one expression. Many expressions are dated 1998-12-01 (a placeholder
  "Consolidation" date, even for 2009 Acts), so the Employment Act 1980 and Companies Act 2009 were left out.

## Built (corpus.json, docs date 2026-10-28)
| Act | Versions | From |
| --- | ---: | --- |
| constitution (Act 1 of 2005) | 1 | 2006-02-08 (commencement) |
| suppression-of-terrorism (Act 3 of 2008) | 2 | 2008-05-11, 2017-08-25 (Act 11 of 2017) |
| money-laundering (Act 6 of 2011) | 2 | 2012-03-23, 2016-09-28 (Act 5 of 2016) |

## Checklist
- [x] Probe robots, terms, listings, Wayback coverage
- [x] fetch (sources.json, law_pages.json pinned)
- [x] parse; verification.json: listings ok, history_after_last [] for all, fidelity 0/0
- [x] 2026-10-29: parse.py had a broken string literal (literal newlines inside "\n## How it is built"); fixed with
      Edit. Re-parse gives byte-identical corpus.json; README now carries "What is missing".
- [x] repo/: README.md (English), LICENSE, jurisdiction.json (from the scaffold, build line filled by write_docs)
- [x] Local verify 2026-10-29: empty scratch build (main 660046d, 5 law commits + docs), check.py 0 mismatches,
      0 trailer errors; --compare rebuild identical (history tip f29df3c, matches preview e0d5b67's parent)
- [x] Remote main checked read-only 2026-10-29: 6c7e832 "Eswatini: sources, before any law" (the scaffold)
- [x] PUBLISH written 2026-10-29 (no corpus.d, so no part .PUBLISH needed)

## Pushed
- preview e0d5b67 (autopush 2026-10-29 04:58 UTC). main waits for the next 4-hourly pass now that PUBLISH exists.

## Open issues
- None. Phase 2 candidates are limited by the archive (most acts have one expression or the 1998 placeholder date).
