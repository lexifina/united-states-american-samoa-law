# Russia (gitlaw-RU) progress — HANDOFF (wind-down 2026-10-29 00:40 UTC)

Slug `russia`, repo lexifina/russia-law (scaffold e9240fe "Russia: sources, before any law", only `main`, checked 2026-10-28), tz Europe/Moscow, lang ru, future branch `budushchee`, on-date tool `deystvuet_na` (not written yet).
Clone: C:/Users/alany/Documents/russia-law (autopush owns it; never build/push into it).

## Source (official, works from this machine)
- pravo.gov.ru and pravo.gov.ru/proxy/ips: no answer (curl 000). No archive needed:
- actual.pravo.gov.ru = the portal's IPS viewer. JSON API http://actual.pravo.gov.ru:8000/api/ebpi/ (calls copied from its js/common.js, js/list.js):
  - `attrsearch/?bpa=ebpi&q=[{AttrId:5,DateFrom,DateTo},{AttrId:999,AttrMode:1,Words:[100,"date","",0,0]}]` search by signing date
  - `redactions/?bpa=ebpi&t={"hash":H,"ttl":3}` ALL editions with date (reddate), caption, reddocrefid (amending act docid)
  - `redtext?bpa=ebpi&t=<redid>&ttl=3` full HTML text of an edition; class P paragraphs = notes "(В редакции ... от DATE № N)"; span.W9 = superscript
  - `card/?bpa=ebpi&t={"docid":N}` amending act: docpassing, docname, adoptions (date, number), publications
- Cache: scripts/russia-law/.cache (487 MB, gitignored), requests.jsonl. FULLY CACHED: Constitution 21 editions, Civil Code part 1 (gk-1) 158 editions, Criminal Code (uk) 367 editions, plus every amending act's card. 0 failed requests.

## Done
- [x] fetch.py (`python -X utf8 fetch.py acts` — resumable; all cached already)
- [x] parse.py -> corpus.json (written atomically 00:38 UTC): Constitution only, 21 versions 1993-12-12..2022-10-05, 140 units, 21 laws (referendum 1993, Ukazy on art. 65, FKZ, popravki 2008/2014/2020). Streams to `preview`.
- [ ] NOT verified: no test build / check.py run yet, so NO PUBLISH.

## Next steps to resume
1. Check BUILD_STATUS.json (autopush preview build) or test-build into .tmp-build with gitlaw_common/build.py + check.py.
2. Inspect suspicious diffs: 1996-01-09 credits art-055 to Указ № 20 (probably note-stripping noise; refine the note regex in paras()). Compare each version's changed units with that edition's notes naming the same law; uncredit noise.
3. Verify last version == today's official text (redid 406785), then write PUBLISH (re-check `git ls-remote` shows only the scaffold first).
4. Add gk-1 and uk to main() in parse.py: unit split needs "Статья 127.1" style numbers (art-127-1), parts/sections/chapters headings, "утратила силу" articles; use `changes` (large acts) instead of full units per version.
5. repo/ docs: README (EN then RU), LICENSE, jurisdiction.json (build: scrape -> api), tools/deystvuet_na.py wrapper around tools/on.py.
