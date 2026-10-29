# Qatar (gitlaw-QA): handoff, 2026-10-29 00:40 UTC

Repo lexifina/qatar-law was still the bare scaffold (a4d88d9, "Qatar: sources, before any law") when the run stopped. No PUBLISH yet: the build streams to `preview` only.

## Done
- [x] Probe: almeezan.qa is a React SPA over an open JSON API, https://api.moj.gov.qa/api/v1 (no auth). robots.txt: Allow /.
  - `/Legislation/details-by-key?number=N&year=Y&typeCode=law&sourceCode=general`: the act with its article tree and Official Gazette issue and date
  - `/Legislation/{id}`: the same, by id
  - `/Legislation/{id}/almawad-lookup?pageSize=1000`: every article id; the tree omits some, e.g. Law 13/2016 arts 1-2 and 23-32
  - `/Legislation/{id}/mada/{articleId}`: the article's dated history chain, naming the amending law
  - `/Legislation/{id}/related-legislations-subsequent`: the amending laws
  - `/Legislation/{id}/akoma-ntoso?lang=ar`: AKN XML, but partial (it follows the tree)
- [x] fetch.py: curl, cache in `.cache/` (sha256 of the URL; about 120 requests), at most 3 requests a second. parse.py works offline from the cache. acts.json lists the acts.
- [x] corpus.json written. Today's text equals Al Meezan's current text for all 3 acts (parse.py checks this; 0 mismatches).
  - الدستور: 2 versions (2005-06-09; 2024-11-06 amendments: 15 articles amended, 3 repealed, 75 bis added)
  - قانون العقوبات (Law 11/2004): 8 versions; 7 amending laws (28/2006, 23/2009, 8/2010, 22/2015, 4/2017, 2/2020, 14/2024)
  - Law 13/2016 on personal data: 1 version, in force 2017-01-29; Al Meezan shows no amendment

## Open, before PUBLISH
1. **In-force dates.** They are computed by Constitution art. 142: gazette date + 1 month unless the law fixes its own date. Al Meezan's own "effectiveDate" equals the gazette date for most laws, and is the issue date for 14/2024.
   - Confirm art. 142 is the right reading.
   - Spot-check the gazette PDFs: files.almeezan.gov.qa links are in each law's `officialGazette`.
2. **Draft record of the 2024 amendments.** Al Meezan's record of the draft (69c36fc9, issued 2024-10-29, gazette 16/2024) is mapped to the issued amendments (d8a3673d) through SAME_LAW in parse.py. Verify against both gazette texts.
3. **Constitution art. 1.** One stray history entry was dropped (see decisions).
4. **Repo docs.** repo/README.md, LICENSE and jurisdiction.json are not written yet. Fold in the scaffold's README and SOURCES.md from C:/Users/alany/Documents/qatar-law. Check copyright: Qatar Law 7/2002 is thought to exclude official texts.
5. **Read BUILD_STATUS.json.** Then test-build into `.tmp-build` and run check.py there.

## Resume
    cd scripts/qatar-law; python -X utf8 fetch.py; python -X utf8 parse.py
Then: README/LICENSE, re-check that the repo is still the scaffold, and write PUBLISH. Phase 2: Civil Code (Law 22/2004), same API.
