# peachjam.py issues found by gitlaw-NA (Namibia), 2026-10-28

1. **Truncated archived pages pass `good_expression_page()`.** Some Internet Archive copies are cut off at exactly
   1 MiB (1048576 bytes). Example: `https://web.archive.org/web/20240617051143id_/https://namiblii.org/akn/na/act/1977/51/eng@2023-07-25`
   ends mid-section (`...chp_23__sec_197__para_d__p_1...</span></section>`), with no `</html>`. The page still has
   `class="akn-akomaNtoso"` and `track-page-properties`, so the adapter accepts it and every provision after the cut
   would read as repealed in that version. Suggested fix: also require `b.rstrip().lower().endswith(b"</html>")`.
   Workaround: `scripts/namibia-law/fetch.py` applies that check itself (`complete()`).

2. **Amending laws shown only as a Gazette PDF give no dates.** On NamibLII most amending Acts' expression pages carry
   no coverpage notices and no Akoma Ntoso text, only the PDF viewer and a History timeline ("Assented to",
   "Published in Government Gazette N", "Commenced by ..."). `good_expression_page()` rejects them (no
   `akn-akomaNtoso`) and `law_meta()` reads only coverpage notices, so each costs two archive.org requests for
   nothing. Suggested fix: accept a law page on `expression_frbr_uri` alone, and let `law_meta()` fall back to the
   timeline's "Assented to" / "Published in" / "Commenced" items. Workaround: Namibia does not fetch law pages
   (`fetch_law_pages` unset), so its laws carry no enacted/published dates.

3. **Rate:** `Cache` spaces archive.org at its own 3 s stamp; the coordinator now asks for
   `scripts/gitlaw_common/wayback.py` (shared adaptive rate). `scripts/namibia-law/fetch.py` is a drop-in fetch that
   uses `wayback.captures` (one CDX prefix listing for every work) and `wayback.get`, writing the same
   `sources.json` shape, with the same cache file names, so `peachjam.parse()` reads it unchanged. The adapter can
   adopt it.

4. **Same-day amendments on the first expression.** When the oldest expression's own date carries an "Amended by"
   event, `parse()` (a) labels the first version "the act as published" (the else branch only checks consolidations)
   and (b) leaves that law out of `earlier_laws` (`t["date"] < first_day` should be `<=`). Namibia: Constitution
   2014-10-13 (Act 8 of 2014), Labour Act 2012-08-01 (Act 2 of 2012), Companies Act 2017-01-16 (Act 8 of 2016).
   Workaround: `scripts/namibia-law/parse.py`, `same_day_amendments()`.

5. **Container units that are only an editorial remark.** The Constitution's preface holds only a commencement
   remark, and Chapters 10A/10B only "[Chapter 10A ... is inserted by ...]". `units_of()` keeps the remark as the
   unit's body (meant for repealed provisions), producing 'long-title', 'text', 'text-2' with no law text.
   Suggested fix: keep a remark-only body only for basic units. Workaround: `editorial_only()` in Namibia's parse.py.
