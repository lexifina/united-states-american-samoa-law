# Turkmenistan (gitlaw-TM): handoff

Repo lexifina/turkmenistan-law: confirmed bare scaffold (single commit b1e0a19 "Turkmenistan: sources, before any law"). Clone at C:/Users/alany/Documents/turkmenistan-law (untouched). Never push; autopush builds `preview` from corpus.json. No PUBLISH yet.

## Done
- [x] Probe. mejlis.gov.tm is live, robots allows all, serves full HTML texts in Turkmen (tk), ru/en pages partial or empty.
  - JSON lists: `https://mejlis.gov.tm/codes?lang=tm&ajax=true` (22 codes), `https://mejlis.gov.tm/laws?lang=tm&ajax=true` (371 laws).
  - Constitution: `single-law/107?lang=tm` = 2016 revision (Kons. kanun № 448-V, 14.09.2016), consolidated with 617-V (09.10.2017), 297-VI (25.09.2020), 531-VI (21.01.2023). Repealed articles shown as red notes (art. 75). Superscript articles flattened ("61-njy madda" = 6¹).
  - Civil Code: `single-code/6?lang=tm` = NEW code, Kanun № 162-VII of 28.06.2025, in force 2026-01-01 (as enacted; no amendment notes).
  - Criminal Code: `single-code/27?lang=tm` = revised edition, Kanun № 456-VI of 17.04.2022, in force 2023-01-01. Has a MAZMUNY (table of contents) before the text.
  - minjust.gov.tm: Next.js, API `https://minjust.gov.tm/api/front/legislation/<slug>?locale=tm` (slugs unknown yet). law.minjust.gov.tm ("Adalat" EMTP) needs a login: not usable.
  - Common Crawl index timed out tonight (index.commoncrawl.org); archive.org CDX worked (shared client).
- [x] fetch.py (curl, sha256 cache in .cache/, requests.jsonl). parse.py (cache only) -> corpus.json.
- [x] corpus.json written: Constitution 1 version (144 units, "oldest version available", from 2023-01-21, first_law null, credited to publisher) + Civil Code 1 version (1344 units, from 2026-01-01, first_law kanun-162-vii).

## Not done / open
- Criminal Code left out: parser stops with "duplicate article art-070" (likely a heading/reference line starting "70-nji madda" or the ToC; the body starts at the 2nd "UMUMY BÖLEK"). Fix `criminal_code()` / `split_units` in parse.py.
- Constitution `from` 2023-01-21 is assumed (date of 531-VI); confirm 531-VI's own in-force clause before PUBLISH.
- No dated history yet. Leads found in archive.org CDX (not yet fetched):
  - `https://mejlis.gov.tm/maglumat/turkmenistanyn-konstitusiyasy` captured 20211027005957 (19 KB): likely the 2020 text (Milli Geňeş). List all its captures with `wayback.captures(..., match='exact')`.
  - `https://mejlis.gov.tm/constitutional-law?lang=tm` 20230929193441.
  - Need: 2016 as adopted, the amending laws 617-V (2017), 297-VI (2020), 531-VI (2023); 2008 Constitution (26.09.2008) for the oldest layer.
- Not checked: the build output (BUILD_STATUS.json after autopush), verification vs official text, README in repo/.

## Resume
1. `python -X utf8 scripts/turkmenistan-law/fetch.py` (cached; re-fetches nothing).
2. Fix the Criminal Code split, then `python -X utf8 scripts/turkmenistan-law/parse.py` (writes corpus.json atomically).
3. Test build: `python -X utf8 scripts/gitlaw_common/build.py scripts/turkmenistan-law --repo scripts/turkmenistan-law/.tmp-build --docs-date 2026-10-28`, then check.py.
4. Fetch the archived Constitution captures above via `wayback.get`, add them as dated versions, then write PUBLISH.
