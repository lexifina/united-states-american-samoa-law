# gitlaw-PH: Philippines law history (progress / handoff)

STOPPED 2026-10-29 00:36 UTC (coordinator wind-down). Preview built and pushed by autopush: 3b5988e (BUILD_STATUS.json).
**No PUBLISH yet** (see "Next step"). No repo/README.md yet.

Slug `philippines`, repo `lexifina/philippines-law` (PRIVATE; never push, autopush owns it), clone `C:/Users/alany/Documents/philippines-law`.
tz Asia/Manila, lang en (English is an official language and the language of the statutes), future branch `future`.
Rules: scripts/world-law/FORK.md -> WAVE.md -> africa-law/FANOUT.md -> south-america-law/BRIEF.md.

## Done
- [x] Scaffold check 2026-10-28: ls-remote showed only main 275d245 "Philippines: sources, before any law". Re-check before PUBLISH.
- [x] Sources probed (table below)
- [x] fetch.py: pinned Wayback `id_` captures via gitlaw_common/wayback.py (PLAN dict). All 4 cached in `.cache/` (861 KB).
- [x] parse.py -> corpus.json (atomic): Constitution (307 units, 1 version from 1987-02-02, first_law constitution-1987, kind referendum)
      and Data Privacy Act RA 10173 (45 units sec-01..sec-45, 1 version from 2012-09-08, first_law ra-10173). Decisions + ai_use filled.
- [x] verify.py: word-sequence cross-check against Lawphil (cross-check only; output in verify.out).
  - Data Privacy Act: matches except "SEC."/"Section" labels, chapter headings (left out on purpose) and one Lawphil typo ("rides of court"). Effectively verified.
  - Constitution: ~40 real wording differences between the Official Gazette page (source "CDAsia") and Lawphil. Most are Lawphil typos
    ("personages", "article v1"), but some look like Official Gazette errors, e.g. Art. XIII s. 9 OG "public sector" vs Lawphil "private sector",
    Art. XIII s. 7 OG "local marine" vs "communal marine", Art. VIII s. 11 OG "reached the age" vs "reach", Art. XII s. 2 Lawphil lacks "sixty".
    UNRESOLVED: needs a third official witness before PUBLISH.

## Sources probed (2026-10-28)
| Source | Status from this machine | Notes |
|---|---|---|
| officialgazette.gov.ph | 403 Cloudflare challenge (even robots.txt) | read through archive.org `id_` captures only; footer: "All content is in the public domain unless otherwise stated" |
| elibrary.judiciary.gov.ph | homepage 200; RA list is a DataTables POST behind a Radware WAF ("Unauthorized Activity Detected") | not touched further |
| congress.gov.ph | robots.txt: Cloudflare managed, `Content-Signal: ai-train=no`, ClaudeBot disallowed | not used |
| comelec.gov.ph constitution pages | 403 / "Maintenance" page; no Wayback captures of the ?r= URL | candidate third witness, not reached |
| lawphil.net | 200 | cross-check only, never a text source |
| Common Crawl | `wayback.cc_crawls` returned [] (collinfo fetch failed) | archive.org used instead |

Pinned captures (fetch.PLAN):
- Constitution: OG `/constitutions/1987-constitution/` at 20231009121845 (newest 200 of 105 distinct captures)
- RA 10173: OG `/2012/08/15/republic-act-no-10173/` at 20230930155155
- Act 3815 (Revised Penal Code, original 1930 text): OG `/1930/12/08/act-no-3815-s-1930/` at 20230608093131 (cached, not parsed)
- EO 200 (default rule, Civil Code art. 2 as amended): OG `/1987/06/18/executive-order-no-200-s-1987/` at 20230717000612

WebSearch used: 1 of 4 (DPA published 24 Aug 2012 -> in force 8 Sep 2012, Bloomberg Law; no official page gives the publication day).

## Revised Penal Code: not built
No official consolidated text exists (OG and Lawphil both print the 1930 Act as enacted). Today's text would need a replay of
roughly 100 amending Acts, PDs, BPs and RAs (RA 7659, 8353, 10592, 10951, 11648, ... including implied amendments such as RA 9344),
with no consolidation to check the result against. That is well over the 45-minute limit; skipped. A fallback is the Civil Code (RA 386).

## Commands
    python -X utf8 scripts/philippines-law/fetch.py     # resumable; everything is cached already
    python -X utf8 scripts/philippines-law/parse.py     # writes corpus.json atomically
    python -X utf8 scripts/philippines-law/verify.py    # Lawphil cross-check

## Next step (to resume)
1. Settle the Constitution discrepancies with a third official copy (an older OG capture with a different text, a COMELEC or
   Senate page through Wayback, or an official PDF). If OG is wrong somewhere, keep the OG text and record it, or switch source; never patch by hand.
2. Write repo/README.md (standard sections; fold in the scaffold's SOURCES.md), repo/LICENSE, and keep repo/jurisdiction.json with `build` set.
3. Re-check ls-remote is still the scaffold, then write PUBLISH (or split the DPA into corpus.d/ with its own .PUBLISH if the Constitution stays unresolved).
