# peachjam.py issues found by gitlaw-LS (Lesotho), 2026-10-29

1. **Staged commencement is reported but not built.** When a page says "There are multiple commencements" and prints
   `table.commencements-table` (Provisions | commenced on D by <notice>), `parse` keeps the Gazette publication date for
   the whole text and only lists the act under `staged_commencement`. Lesotho's MLPCA 2008 commenced in three stages
   (2009-04-01, ss. 14-15 on 2011-06-10, s. 18 on 2012-07-01). Workaround: `scripts/lesotho-law/lii.py`
   (`commencements()`, `stage()`), which the adapter can adopt as is. It also drops the next version's leftover note
   "Commences. (D)".
2. **Amending laws' pages need Akoma Ntoso text to be pinned.** In `fetch`, law pages go through
   `good_expression_page`, which rejects pages without `akn-akomaNtoso`. Lesotho's amending Acts and legal notices are
   archived, but as PDF-only pages (about 31 KB, coverpage only), so every law got "no archived page" and lost its
   assent/publication dates. A coverpage-only check (track-page-properties or `<h1>` + notice-list) would do for laws.
3. **Non-LII links are queued as laws.** `law_uris` takes any href containing `/akn/`, including the Gazette PDFs on
   `https://commons.laws.africa/akn/.../publication-document.pdf`; they then cost CDX queries. Filter to hrefs starting
   with `/akn/` (or `/<lang>/akn/`).
4. **`Cache.get` does not pass `-g` to curl.** A URL with `[` `]` (e.g. a CDX regex filter) fails with
   "curl: (3) bad range" on every retry. Add `-g` (`--globoff`).
5. **Generic README sentences:** "Against LesLII today ... as named by its own legislation listing" is printed even
   when `"listing": false`, and "How it is built" asserts a bot challenge the country agent may not have tested.
   Lesotho rewrites both in `lii.fix_readme`.
