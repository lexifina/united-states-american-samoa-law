# Palestine (gitlaw-PS) progress / handoff (2026-10-29 00:40 UTC, wound down by coordinator)

## Done
- [x] Scaffold check 1: lexifina/palestine-law has only `main` @ 8b40528 "Palestine: sources, before any law". Clone at C:/Users/alany/Documents/palestine-law (untouched; autopush owns it).
- [x] Probe: Al-Muqtafi answers on plain HTTP only (https times out). Open gazette mirror: http://muqtafi.birzeit.edu/pg/ (year pages /pg/YY/, issues getlist.asp?issue=N or special-issue .html, texts getleg.asp?id=N, windows-1256). LegCard/ConsLegSearch (consolidated) need a login. MoJ (moj.pna.ps) and Diwan (dft.gov.ps) did not answer/resolve. No robots.txt. Pages state Birzeit copyright (recorded in licence_note).
- [x] gazette_index.json: all 275 issues 1994-2026, 3,656 texts with ids (index.py).
- [x] Basic Law in corpus.json: 3 versions: 2002-07-07 (id 14094, as enacted), 2003-03-19 (Amended Basic Law, id 14138, 114 units changed incl. renumbering), 2005-08-18 (2005 amendment id 14860 replayed: Arts 36, 47(3), 48, 55, new 47 bis). Test build in .tmp-build: 0 unexplained; check.py ran (output tail showed no mismatch details).
- [ ] PUBLISH not written: today's text not yet compared with an official consolidated text.

## Files
- fetch.py (cached curl, .cache/ + requests.jsonl), index.py (gazette index), parse.py (writes corpus.json atomically).

## Next step to resume
1. Re-run check: `python -X utf8 scripts/gitlaw_common/check.py scripts/palestine-law/.tmp-build --corpus scripts/palestine-law/corpus.json` (one "future_dated: 1" item to look at).
2. Verify 2005 consolidated Basic Law against an official consolidated copy (e.g. Common Crawl/Wayback of the PLC or Diwan site); then scaffold check 2 (`git ls-remote`) and write PUBLISH.
3. Cybercrime: Decree-Law 10/2018 (id 17018, special issue 16, 2018-05-03), amended by 28/2020 (id 17347, 2020-09-24) and 38/2021 (id 17558, 2021-12-23). Same HTML structure; replay amendments; check each one's own in-force clause.
4. Third act: Penal Code 16/1960 base text is not in Al-Waqa'i' (Jordanian gazette); PA amendments ids 16269, 16593, 16680, 17002, 17345, 18814. Alternative with a clean gazette base: Penal Procedure Law 3/2001 (id 13854; amended 15214, 16600, 17021, 17589).
