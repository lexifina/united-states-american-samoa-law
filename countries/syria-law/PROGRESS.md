# Syria (gitlaw-SY) progress: handoff (run stopped 2026-10-29 00:44 UTC)

- [x] Scaffold check: lexifina/syria-law has only main, one commit 510faec "Syria: sources, before any law"
- [x] Clone at C:/Users/alany/Documents/syria-law (untouched; autopush owns it)
- [x] Probe: parliament.gov.sy, presidency.sy, pministry.gov.sy do not answer from here; sana.sy and moj.gov.sy answer (moj has no legislation database)
- [x] corpus.json: 2012 Constitution, 1 version (preamble + arts. 1-157), "oldest version available", from 2012-02-27 (Decree 94/2012 art. 1)
- [ ] PUBLISH: not written. The text equals the People's Assembly page, but that Constitution is no longer in force (replaced in 2025), so "today's text = official" is not met until the Declaration is added
- [ ] 2025 Constitutional Declaration: no official text fetched. sana.sy search finds only news; try presidency.sy captures (CDX run for presidency.sy/sana.sy from 2025 was started: .cache/cdx_presidency.sy.txt, .cache/cdx_sana.sy.txt)
- [ ] Civil Code (LD 84/1949), Penal Code (LD 148/1949)

## Sources
- People's Assembly constitution page: http://parliament.gov.sy/arabic/index.php?node=5518&cat=423& (cp1256). Captures pinned in sources.json: 20150428001050 and 20241207201658; both give identical units. 166 captures exist 2015-2026.
- People's Assembly legislation DB: node=200 (search), node=201&nid=N (one law per page, title, number, date, status "نافذ", full text). >8,672 nids archived (CDX lists in .cache/cdx_arabic_*.txt, truncated at 50,000 rows). "قوانين أساسية" menu: node=5518&cat=399.
- WIPO Lex has the Civil Code PDF (sy012ar.pdf, details/10917); text layer not checked.

## Scripts
- fetch.py: reads sources.json, fetches through gitlaw_common/wayback.py into .cache/
- parse.py: cache only -> corpus.json (atomic). Arabic ordinal article headings parsed; asserts 157 articles.

## Next step
1. Find the nids of LD 84/1949 and LD 148/1949 in node=201 (search node=200 captures with Key1=القانون المدني, or fetch nid pages from the CDX list and read titles); add them to sources.json; parse articles the same way.
2. Find an official Declaration text (presidency.sy capture or Official Gazette); add it as act constitutional-declaration-2025 from 2025-03-13; then decide PUBLISH.
