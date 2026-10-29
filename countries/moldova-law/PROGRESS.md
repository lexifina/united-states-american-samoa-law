# Moldova (gitlaw-MD): progress / handoff

Repo `lexifina/moldova-law` (private). Scaffold checked 2026-10-29 12:18 UTC: `git ls-remote` shows only `main` 9aba2b5, single commit "Moldova: sources, before any law". No commits or pushes by this session.

## Checklist
- [x] scaffold check (start)
- [ ] probe sources (legis.md, monitorul.gov.md, archives)
- [ ] Constitution 1994 + amendments
- [ ] Law 133/2011 personal data protection
- [ ] Criminal Code 985/2002

## Probe (12:18-12:30 UTC)
- **legis.md**: Cloudflare managed challenge (403 "Just a moment") on / and robots.txt. Not touched again. Page `getResults?doc_id=N` is a JS shell; content comes from `/cautare/showdetails/N` (found in archived `justicejs`). Constitution = doc_id 145723 (republished MO 466, 13.11.2024; linked by constcourt.md "Baza legală"); doc 136084 = Law 52/2023.
- archive.org: only 108 `showdetails/` captures in total (none for 145723); `getResults` captures are shells only.
- **monitorul.gov.md**: robots `Disallow:` empty; issues as FlowPaper viewers per issue/part (ids to 3366); subscription site. Not yet used.
- constcourt.md: no own text of the Constitution (links legis.md). parlament.md: Cloudflare challenge (not touched again).
- Next: old register lex.justice.md (pre-legis.md) in archives; Common Crawl prefix search for legis.md running.
- WebSearch 1/4.

## Constitution findings (12:35 UTC)
- Old register lex.justice.md (Ministry of Justice), archived: Constitution id 311496, 22 distinct captures 2008-2024 (frozen after 2016; last change HCC7 notes). MODIFICAT list: RMO 1994 (x2), LP957/1996, LP1115/2000, LP351/2001, LP1469/1470/1471/2002, LP344/2003, LP185/2006, HCC7/2016. Amending acts archived as lex.justice.md/document_rom.php?id=... and md/363742 (HCC7).
- HCC7/2016: the register did NOT change words, only added "Notă: ... declarate neconstituționale" to art. 78, 85, 89.
- Captures from 2015 on carry markup corruption in art. 35, 75 (to 2017), 129 (escaped tags inside words). Clean: 2013-05-27 / 2013-06-20.
- **Current text**: presedinte.md hosts the Moldpres edition "Cu modificări și completări la data de 20 octombrie 2024" (PDF, text layer, PyMuPDF; lists LP256/2016, LP70/2017, LP255/2018, LP120/2021, LP52/2023, HCC8/2024, Legea 244/2024). No per-article notes. New orthography (â, sunt) throughout.
- ustav.py parses both (174 vs 182 units). Plan: oldest-available (2006 text) -> HCC7 note version (words unchanged) -> 2024 edition (diff uncredited: the sources give no per-article attribution).

## Status 12:45 UTC
- parse.py + ustav.py write corpus.json: constitutia, 3 versions (2006-07-14 oldest available from register 2013 capture; 2016-03-04 HCC7 applied from its point 8 b)/3; 2024-10-20 Moldpres edition, uncredited diff of 111 units). HCC7's art. 89 equals the 2024 edition word for word (cross-check).
- Core acts skipped (decisions): 133/2011 repealed 23.08.2026 by 195/2024; Criminal Code; current texts only on legis.md.
- Next: repo/ docs, fetch_all.py, local build + check + compare, PUBLISH.

## Status 12:53 UTC (local verification done)
- fetch_all.py (pinned IA captures + presedinte.md PDF), parse.py, ustav.py; repo/ README (English + Română), LICENSE, jurisdiction.json (build: built).
- Local build `.tmp-build` (docs-date 2026-10-29): 3 law commits + docs commit, 4 tags, main 9c62e36 (history tip 0388856); check.py 0 mismatches / 0 trailer errors / 0 backwards; `--compare` into `.tmp-build2`: identical.
- PUBLISH written 12:53. Remote re-checked 12:52: main 9aba2b5 only; a `wip` branch exists, but it is the autopush snapshot of THIS folder (commits "Work in progress: scripts/moldova-law", 12:41-12:48 UTC, holding my PROGRESS.md/fetch.py/ustav.py).
- No commits, no pushes by me. WebSearch 1/4.

## Resume ideas
- The 2016-2024 lump (111 units, uncredited) splits if the texts of LP256/2016, LP70/2017, LP255/2018, LP120/2021, LP52/2023 (archived: web.archive.org/web/20230403213420id_/https://www.legis.md/cautare/showdetails/136084), HCC8/2024 and Law 244/2024 can be read: constcourt.md publishes HCC8/2024; the others are only on legis.md (`/cautare/showdetails/<doc_id>` is the text endpoint) or the paid Monitorul Oficial download.
- Core acts need legis.md: Law 195/2024 (doc 144681), Criminal Code; Law 133/2011 is repealed from 23.08.2026.
- 12:55: stopped my own Common Crawl probe (0 legis.md records in 16 crawls); one archive.org probe died on a wayback.py lock PermissionError (ISSUES.md).
