# United Arab Emirates (gitlaw-AE): progress and handoff

Repo lexifina/united-arab-emirates-law. The scaffold was confirmed on 2026-10-28: `main` only, with a single commit, f9c01c5 "United Arab Emirates: sources, before any law". The clone is at C:/Users/alany/Documents/united-arab-emirates-law, which autopush owns. Never push it yourself.

## State at wind-down (2026-10-29, about 00:40 UTC)
- [x] Scaffold check and clone.
- [x] `corpus.json` holds the Constitution as 1 "oldest version available" version: 152 articles in Arabic, dated 2023-03-29 (the date the publisher gives for its last update) and credited to the publisher.
  - It comes from the archive.org capture 20250529114023 of `/ar/legislations/1000/`.
  - Test build into `.tmp-build`: 0 mismatches (main 7408150).
  - It streams to `preview`.
- [ ] No PUBLISH yet. The text has not been cross-checked against a second official copy, for example the Arabic PDF `/ar/legislations/1000/download` (captured 20261023183156).
- [ ] Constitution history: earlier wordings and credits to the amendments.
- [ ] Decree-Law 31/2021 Crimes and Penalties (site id 1529).
- [ ] Decree-Law 45/2021 Personal Data Protection (site id 1972).

## Sources (all through archive.org `id_`; the live site gives a Cloudflare 403)
- **Live site.** uaelegislation.gov.ae answers 403 "Attention Required" (Cloudflare) to curl. Its robots.txt is `Disallow:` (empty).
- **Common Crawl.** index.commoncrawl.org was unreachable from this machine (curl 000), so archive.org is the only archive used, through `scripts/gitlaw_common/wayback.py`. Each request took about 45 s at the shared machine-wide rate.
- **Act pages.** The act pages `/ar/legislations/<id>` carry their articles inline in captures up to about March 2026. Later captures load them through `materials-ajax`.
  - Use 20250529114023 for 1000 (Constitution).
  - Use 20260312152646 for 1529 (Penal Code). It has 479 items and 8 "previous texts" links, and says "last update 01 Oct 2025" and "in force 02 Jan 2022".
  - For 1972 (PDPL), the latest HTML capture is 20250512054510.
- **History source.** Each amended article links `/ar/materials/<n>/previous` ("النصوص السابقة"). It is a GET popup that lists each earlier wording, with the name of the act it came from (for example "الدستور المؤقت لدولة الإمارات العربية المتحدة").
  - The Constitution has 21 such articles. All 21 popups are archived, with 7–8 captures each.
  - The material ids are 10, 55, 56, 58, 61, 65, 68, 71, 77, 84, 92, 99, 101, 130, 152, 153, 26340, 26341, 26362, 27048 and 27062.
  - The popups for 10, 55 and 77 are already cached.
- **Constitutional amendment PDFs.** These are archived at `/ar/constitution/modifications/<id>/download`, with ids 1789, 1880, 1996 and 3103 seen so far.
  - The `/ar/constitution/modifications` HTML is captured at 20250618111120. It probably lists every amendment with its id. Read it next.
  - `/ar/legislations/<id>/modifications` loads by POST, so it is not archived.
- **Preamble.** It is at `/ar/legislations/1000/preamble` (JSON, captured 20250529114027). It is not included yet.
- **Caches.** Everything is under `.cache/`: wayback cache files named by sha256, `requests.jsonl`, and `probe/` with copies used while probing. `.cache/pins.json` is not written yet, because fetch.py was stopped during the wind-down.

## Scripts
- `fetch.py`: run as `python -X utf8 fetch.py`, then `python -X utf8 fetch.py laws`. For each act it finds the newest inline-article capture and fetches every previous-texts popup. It pins capture timestamps in `.cache/pins.json`. The `laws` argument also fetches the pages named on related-legislations.
- `parse.py`: for now it builds only the Constitution, from the pinned capture.
- `wb.py`: a small CLI for archive.org (`get URL TS`, `cdx URL prefix`).
- `txt.py`: dumps HTML as plain text.
- `probe_cc.py`: the Common Crawl probe, which returned nothing.

## Exact next step to resume
1. Run `python -X utf8 fetch.py` in the background to fetch the remaining popups for 1000, 1529 and 1972. It takes about 45 s per request.
2. Fetch `/ar/constitution/modifications` (20250618111120) and the amendment PDFs. From them, get each constitutional amendment's date and the articles it changed. The site shows 13 modification entries: 1971 ×1, 1972 ×3, 1976 ×2, and one each in 1981, 1986, 1991, 1996, 2004, 2009 and 2023.
3. In `parse.py`, build the Constitution's versions from 1971-12-02 (Official Gazette No. 1; issued and in force 18 Jul 1971) out of the popups. Credit only the amendments whose text names the article.
4. Cross-check today's text against the Arabic PDF, then write PUBLISH.
5. Do the same for 1529 and 1972. The PDPL appears never to have been amended: if the page shows 0 amendments, use `first_law` = the decree-law, in force 2022-01-02.

The English versions on the site are a reference only, to be noted in the README. Arabic prevails.
