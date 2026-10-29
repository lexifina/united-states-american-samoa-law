UPDATED 2026-10-29 (gitlaw-GY-3): 27 acts / 36 versions; corpus.json + parts 50, 55-companies, 60-chapters, 70-summary-jurisdiction, 75-family, 80-land, each with its .PUBLISH. Nothing committed or pushed by agents (the push loop publishes).

## 2026-10-29 (gitlaw-GY-3): summary jurisdiction, family and land chapters (16 acts, chapters_extra.py)

- **State:** new script `chapters_extra.py` writes three parts (`CHAPTERS_EXTRA_DIR=...` to write elsewhere): `70-summary-jurisdiction` (Caps. 3:04, 3:05, 7:01, 10:02), `75-family` (11:09, 12:02, 12:24, 45:02, 45:03, 46:05), `80-land` (5:01, 5:02, 60:02, 61:01, 62:01, 36:23). One version each. Three kinds (`kind`): `two` (2022 on mola + archived 2012: 3:05, 7:01, 5:02 — all three print the same text in 2022, compared with line breaks as spaces, `same_words`), `mola2012` (mola still serves L.R.O. 1/2012), `only2022` (archived 2012 already lists a 2014 Act: 3:04 lists 13/2014, 5:01 lists 5/2014 -> only the 2022 edition, dated 2022-12-31).
- **Verified:** `verify_chapters.py corpus.d/<part>.json --older` (now also knows chapters_extra; per-chapter `marker` where the text layer puts s. 1 before the long title: 3:05 2012, 46:05): 0 words added in all 16; unaccounted only chapter titles / side refs. Scratch build (scratchpad/gy3/repoB): check.py 27 acts / 36 versions / 0 mismatches / 0 trailer errors; `--compare` identical (main c7a265b). Verified-only build vs full build: the 11 published acts have identical trees and identical commit messages; only the docs commit differs. Parts deterministic (rerun cmp identical).
- **Layout repairs** (in chapters_extra unless stated): `col_heads`/`insert_heads` read form-table column headings set in small or turned type as one line (10:02 Forms 54/55 + s. 38 scale heading; 7:01 Form 10; 11:09 Form 4); 3:05 body size 9.3 (2022 item numbers in 9.4 pt) and "$" put back from the margin (2022); "10.Every" spacing (2012); 10:02 s. 58 "58(1)" split from s. 57 (`split_unstopped`); s. 49 of 46:05 (a section repealing an Act) kept (`REPEALING`; parse.PLACEHOLDER would drop it); dash rules dropped; 5:02 2012 U+2016 read as space; Rent Restriction reviser's NOTE as its own unit `note-1` (kind note); State Lands range to PDF p. 25. **layout.py** (shared): a row "Act, Cap. 3:05, the ..." near the page top is no longer the running head (regex `(?!\d)(?!\s*,)`); regenerating corpus.json + parts 50/55/60 gives identical acts/laws/decisions (parts byte-identical; corpus.json differs only in sources' request counts, so corpus.json was NOT rewritten).
- **Scans, not applied:** Act 13 of 2024 (Matrimonial Causes, Gazette 27 Aug 2024), Act 21 of 2024 (Wills, Gazette 27 Dec 2024): in version notes, decisions, README.
- **Not added (kept in chapters_extra.SKIPPED with `skip` reason):** Summary Jurisdiction (Offences) 8:02 (definition opening quotes go to the margin; 2012 ss. 83/84 glued with words lost across a page; "no t" split; U+201B in 2022; "of 1997.]" fragment) — needs a quote-in-margin repair; Adoption of Children 46:04 (Schedule p. 43 is a turned-page register table; Act 8 of 2021 is a scan). Married Persons (Property) 45:04 (2012 edition lists Acts 11 and 12 of 2014) and Data Protection Act 2023 (scan, not in any edition) not attempted.
- **Next candidates:** 8:02 (above), 46:04 (turned-page table reader), Caps. 3:12, 5:06, 5:11, 12:23, 45:05, 46:06, 59:01-62:09 land chapters (`scratchpad/gy3/mola.txt` lists all 461 chapters with URLs; `sources.mola_chapters()` rebuilds it). Check each front page for post-2012 Acts (`only2022` / skip) and small/turned table headings (spans with 8.5 <= size < body or height > 2 x width inside the text column; verify counts them as margin, so it will not catch them).
- **Note for the coordinator:** this agent's first scratch files were in the shared scratchpad root (its `regen.sh` overwrote another agent's file of that name); all are now in `scratchpad/gy3/`.

## 2026-10-29 (gitlaw-GY-2): cross-heading fix, Companies Act, four more chapters

- **State:** acts constitution (6), civil-law (1), criminal-law-offences (2) in corpus.json; criminal-law-procedure (1), high-court (2), labour (1) in corpus.d/50-chapters.json; companies (1) in corpus.d/55-companies.json; evidence (2), limitation (1), defamation (2), interpretation (1) in corpus.d/60-chapters.json. Last local check (scratch build of the whole folder, docs-date 2026-10-29): check.py 11 acts / 20 versions / 0 mismatches / 0 trailer errors; `--compare` identical (main cb06371). Scratch builds removed afterwards.
- **Task 1, Caps. 6:01/8:01 cross-headings:** `tidy_sections` moved from chapters.py into parse.py (chapters.py aliases it) and `two_editions` now applies it. Unit diff before/after (every unit of every version): only 10 lines removed, all in criminal-law-offences, both versions: sec-031 "Conspiracy", sec-114 "Injury to Growing Things", sec-193 "False Pretences", sec-285 "Counterfeiting Coin", sec-302 "Supplemental Provisions". Cap. 6:01 has none; Constitution unchanged. verify.py counts parse.DROPPED as left out; passes (latest 0 added / 0 unaccounted). Decision added in parse.DECISIONS; PUBLISH has a dated line.
- **Task 2, Companies Act Cap. 89:01** (companies.py -> corpus.d/55-companies.json + .PUBLISH): mola still serves L.R.O. 1/2012 (sha256 4311d05a..., byte-identical to the Wayback capture of 2022-07-30), so 1 version 2012-12-31, 521 sections (1-285, 305-540) + 6 schedules. Parser additions (published outputs checked byte-identical after each): `parse.RANGE_NOTE` ("Sections 286- 304 repealed by Act No. 21 of 1998" carries the numbering; no jump widening), FIFTH/SIXTH SCHEDULE ordinals, a bare "SCHEDULE" inside a schedule (heading continuation) no longer starts a new schedule, `read_all(..., fix=)` hook. companies.py: glued cross-heading "Notices and Documents" cut from s. 471; the Second Schedule Part I form (9 pt, two columns, PDF pp. 422-426) read cell by cell (`form_paras`). verify_chapters.py: 0 added, 0 unaccounted of 111,751 words. Every numbered body paragraph is the next section in order. Post-2012 AML/CFT amendment Acts (8 PDFs) searched for "Companies Act": no hit, but partly scans (stated in decisions/README).
- **Side effect, Cap. 10:01 (part 50):** its Fifth and Sixth Schedules were merged into sch-4 (reader knew 4 ordinals); now sch-5/sch-6, same lines same order (concatenation identical). Decision + dated line in 50-chapters.PUBLISH.
- **Task 3, more chapters** (chapters_more.py -> corpus.d/60-chapters.json + .PUBLISH): Evidence Act 5:03 (2012 + 2022; 2022 lists Acts 1/2014, 13/2018, 15/2021 -> unexplained), Limitation Act 7:02 (1 version, editions equal), Defamation Act 6:03 (2), Interpretation and General Clauses Act 2:01 (1, editions equal). Fixes: layout.py drops the split running foot "1/202"+"2" on the L.R.O. line (Cap. 5:03 2022); parse.PLACEHOLDER now only matches notes <= 100 chars (Cap. 2:01 ss. 14, 51, 52 were being dropped as "repeal notes" AND masked in verify; no published act had a real section dropped, checked across all editions); tidy_sections also splits a lettered next section ("93B In any", Cap. 5:03 2012); chapters_more FIXES: Evidence Schedule table read as rows (`table_rows`), "Short title." glued to s. 1 (7:02 2022), "PART XIII" glued to s. 43 (2:01 2022), missing space "repealed,the". verify_chapters.py --older passes for all four.
- **Skipped:** Sexual Offences Act 8:03: its L.R.O. 1/2012 edition already lists Act 2 of 2013, which is not in the Parliament index, so the 2012 version cannot be dated honestly.
- **Files:** parse.py, layout.py, verify.py, chapters.py, verify_chapters.py (now takes any part, `--older`), fetch_chapters.py (covers parts 50/55/60, all cached), companies.py, chapters_more.py (new). repo/README.md updated (table, checks, what it does not show).
- **Next candidates (same recipe, chapters_more.MORE):** archived 2012 PDFs exist (cached mola CDX, prefix `mola.gov.gy/sites/default/files/Cap`) for Caps. 2:02, 3:01, 3:03, 3:04, 3:05 (8 MB), 3:06, 5:01, 5:02, 5:04-5:09, 6:02, 6:04, 6:05, 7:01, 8:02 (13 MB), 10:02 (7 MB). Check each 2012 front page for amending Acts after 2012 before dating (the 8:03 trap); check 2022 PDFs for new layout slips (glued side notes/headings, split feet) with the unit diff between editions.


## 2026-10-29: further chapters as their own part (corpus.d/50-chapters.json)

- **Acts added (3):** `criminal-law-procedure` Cap. 10:01 (1 version, 2012-12-31, 227 units) · `high-court` Cap. 3:02 (2 versions: 2012-12-31 L.R.O. 1/2012, 2022-12-31 L.R.O. 1/2022, 11 provisions unexplained; the 2022 edition includes Act 9 of 2013) · `labour` Cap. 98:01 (1 version, 2012-12-31, 47 units).
- **Key finding:** for Caps. 10:01, 89:01, 98:01 (and many other chapters with 1695.../1696... URL suffixes) mola.gov.gy still serves the **L.R.O. 1/2012** PDF, byte-identical to the Internet Archive capture (checked live index pages 7, 46, 50 on 2026-10-29). Only chapters with 1785... suffixes (Vols 1-3 so far: Caps 1:01, 2:01, 3:02, 6:01, 8:01, 8:03) are L.R.O. 1/2022. So those chapters have one version, and today's official text = 2012 edition.
- **Not applied (scans, no text layer):** Act 4 of 2023 (Criminal Law (Procedure) (Amendment), Gazette 12 May 2023), Act 11 of 2024 (Paper Committals, Gazette 15 July 2024). No commit (sections and commencement unreadable); named in the version note, decisions and README.
- **[Superseded: built 2026-10-29 by gitlaw-GY-2, see above] Skipped: Companies Act Cap. 89:01** (2012 edition, 668 pp, pages 27-489): section numbers jump 285 -> 305 and parse.segment (shared with the published acts; not changed) accepts a jump <= 12, so all later sections land in s. 285. Would need a local copy of segment with a wider jump, plus care with forms in the schedules; > 45 min.
- **Layout fixes (chapters.tidy_sections, all editions alike):** trailing italic cross-headings ("Gaol Delivery", "(i) Appeals from the Court") dropped; "152 The Court ..." (no full stop) split from s. 151. NOTE: the published Caps. 6:01/8:01 in corpus.json have the same cross-heading slip (e.g. sec-031 ends "Conspiracy"); left unchanged here (published acts stay unchanged); a later pass could apply tidy_sections there too. [Done 2026-10-29 by gitlaw-GY-2, see above.]
- **Verified:** `python -X utf8 verify_chapters.py` (latest version of each vs today's mola PDF, word counts both ways): 0 added; 0 unaccounted for 3:02 and 98:01, 4 (chapter title words on the arrangement page) for 10:01; 2012 High Court version vs its PDF also 0 added. Part deterministic. Stage `.tmp-gy/stage` (corpus.json + part + repo/), repo `.tmp-gy/repo`: 13 commits, check.py 6 acts / 13 versions / 0 mismatches / 0 trailer errors; `--compare` identical, main_identical true. `.tmp-gy/` added to .gitignore.
- **Wayback CDX for parliament.gov.gy (the query that got HTTP 504 before):** retried once without regex via wayback.fetch (prefix `parliament.gov.gy/documents/acts/`, collapse urlkey, limit 5000): 2,752 captures, cached. No Act of 1991 and no Act 5 of 2003 among them (2003 runs 4 -> 6), so the Constitution's missing amenders are not archived either. Common Crawl not needed.
- Files: `chapters.py` (part writer; CHAPTERS_OUT=... to test), `fetch_chapters.py` (mola via fetch.py, archive via gitlaw_common/wayback.py; all cached), `verify_chapters.py`. README: table + "What it does not show" updated for 6 acts.
- **Next candidates:** other Vol 1-3 chapters already in L.R.O. 1/2022 (2 versions each): e.g. Cap. 3:01 Supreme Court, 3:04, 4:01-5:11, 7:01 ff. (archived 2012 PDFs at mola.gov.gy/sites/default/files/Cap%20NNN.pdf, see the cached mola CDX). Summary Jurisdiction Cap. 10:02 (archived) for criminal procedure.

DONE 2026-10-28T18:20Z (pushed main 510f134 by autopush; 3 acts, 9 versions, 10 commits, 12 tags)

# gitlaw-GY: Guyana law history (progress)

Slug `guyana`, repo `lexifina/guyana-law` (PRIVATE, never change), clone `C:/Users/alany/Documents/guyana-law`
(cloned; still only the scaffold commit 65a517a on main). tz America/Guyana, lang en, future branch `futuro`,
on-date tool `repo/tools/in_force_on.py` (thin wrapper around the builder's tools/on.py; not written yet).
Brief: `scripts/south-america-law/BRIEF.md`. Schema: `scripts/gitlaw_common/SCHEMA.md`. Builder is READY.

## Checklist
- [x] Brief, memory/git_for_law.md, SCHEMA, PLAN read
- [x] Scaffold cloned (root 65a517a "Guyana: sources, before any law"; builder wipes it, keeps origin)
- [x] Probe sources (table below)
- [x] Commencement rule found and cited (below)
- [x] fetch.py (curl, sha256(url) cache in .cache/, 1 req/s/host, UA lexifina-watch, .cache/requests.jsonl, spaces -> %20 for curl, key = original URL)
- [x] sources.py: `mola_chapters()` (461 chapters) and `parliament_acts()` (1844 acts: title, page, passed, published, pdf) from cached index pages
- [x] All 52 mola index pages + all 185 parliament index pages (P0..P1840) cached
- [x] Constitution editions cached (3) and 24 amending-act PDFs cached (all have text layers)
- [x] fetch.py now passes `--compressed` to curl (coordinator, 17:25Z; cached bytes unchanged, nothing refetched)
- [x] 2016 Wayback edition fetched: byte-identical (sha256 5550d6b1...) to the LRO 1/2012 PDF captured 2021/2022, so
      LRO 1/2012 was online unchanged by 2016-01-19 (it lists amendments up to 5/2009 only)
- [x] layout.py: PDF -> paragraphs + marginal notes (all 3 editions; footer/header stripped, quotes/dashes normalised
      per edition, line-end hyphens resolved against the corpus vocabulary)
- [x] parse.py -> corpus.json: Constitution, 6 versions (2007-08-28 2010 consolidation; 2009-03-17 +119D Act 5/2009;
      2012-12-31 LRO 1/2012 unexplained (gender-neutral rewrite, 135 provisions); 2015-07-10 Act 2/2015 Sch 3;
      2016-01-11 Act 1/2016 Sch 3; 2022-12-31 LRO 1/2022 unexplained (61 provisions)). 287 units. Revised editions
      dated by their "as at 31 Dec" date (MoLA post; Law Revision Act Cap 2:02 s.9). 1 WebSearch used.
- [x] verify.py: 2022 version vs official PDF, word counts both ways: 0 added, 4 unaccounted (side refs) -> OK
- [x] autopush preview build 7bb0c72: check 0 mismatches (BUILD_STATUS.json 17:43Z)
- [x] repo/README.md, repo/LICENSE, repo/jurisdiction.json, repo/tools/in_force_on.py (tested in .tmp-build)
- [x] --compare determinism: main_identical true (94892dc in .tmp-build); PUBLISH created 17:55Z
- [x] Civil Law of Guyana Act (Cap 6:01): LRO 1/2012 (Wayback Cap%20601_0.pdf, 2022-06-22) == LRO 1/2022 -> 1 version
      2012-12-31. Act 12/2021 (substitutes s.5(1)(b), Gazette 11 Aug 2021) is a SCAN (no text layer) and NOT in the
      2022 edition -> not applied; stated in README, decisions and version note.
- [x] Criminal Law (Offences) Act (Cap 8:01): LRO 1/2012 (Wayback Cap%20801.pdf, 2021-11-23) + LRO 1/2022 -> 2 versions
      (2022: 12 provisions unexplained). Act 10/2025 (Criminal Law Miscellaneous) is a scan -> not applied.
- [x] verify.py covers all 3 acts (latest = 2022 PDFs; --older checks the 2012 versions): all pass (exit 0)
- [x] local build 37b2a9c: check 0 mismatches, --compare identical; tools/in_force_on.py maps numbers to art-/sec-
- [x] PUBLISH updated (18:25Z) for 3 acts. autopush pushed main ebfc60e at 18:11 (Constitution); next run picks up 3 acts
- [x] Data Protection Act 18 of 2023 fetched: Gazette 16 Aug 2023, 125 pp, SCAN with no text layer -> not possible (README says so)
- [x] STOP adding acts: other chapters only have the 2012/2022 editions, and recent amending Acts are scans
- [x] wip branch pushing works: `sh scripts/guyana-law/push_wip.sh` (plumbing, temp index, pushes origin wip; main untouched)

## Sources probed (2026-10-28)
| Source | Status | Format | Dated versions | Amendment notes | robots | Licence |
|---|---|---|---|---|---|---|
| https://www.mola.gov.gy/laws-of-guyana (?page=2..52; 461 chapters) | 200 | HTML index -> one PDF per chapter, LRO 1/2022 revised edition (PDFs made 2025, AES-encrypted but open with pymupdf) | current only | yes: front page "Amended by" list; marginal "[N of YYYY]" per section/article (right-hand column, needs x-position parsing) | `User-agent: * Disallow:` (allows all) | none stated |
| Wayback 2012 capture of legalaffairs.gov.gy Cap 1:01 | 200 | PDF created 2010-10-01, no LRO number | older consolidation: includes 22/2007, NOT 5/2009 | marginal notes | n/a | |
| Wayback 2021 capture of mola.gov.gy/sites/default/files/Cap.101 Constitution.pdf | 200 | PDF, LRO 1/2012 | older edition (includes 5/2009) | marginal notes | n/a | |
| https://parliament.gov.gy/publications/acts-of-parliament/ (+ /P10 .. /P1840) | 200 | HTML table rows: title, "Date Passed", "Published Date", PDF link | Acts as passed, 1928-2025, gaps: 1977-1980, 1991, 2002 missing | n/a | robots.txt 404 | none stated |
| https://officialgazette.gov.gy/ (redirects to officialegazette.gov.gy) | 200 | HTML | not yet probed further | | | |

Exact cached URLs:
- Constitution LRO 1/2022: `https://www.mola.gov.gy/laws/Volume 1 Cap. 1.01 - 3.041785162884.pdf` (338 pp; Schedule = the Constitution starts ~PDF page 26)
- Constitution 2010 consolidation: `https://web.archive.org/web/20121226190242id_/http://legalaffairs.gov.gy:80/information/laws-of-guyana/doc_download/2-chapter-00101.html` (216 pp)
- Constitution LRO 1/2012: `https://web.archive.org/web/20210404214043id_/https://mola.gov.gy/sites/default/files/Cap.101%20Constitution.pdf` (376 pp; the `_0.pdf` 2022 capture is byte-identical size)
- Interpretation and General Clauses Act Cap 2:01: `https://www.mola.gov.gy/laws/Volume 1 Cap. 1.01 - 3.041785164106.pdf`
- Civil Law of Guyana Act Cap 6:01: `https://www.mola.gov.gy/laws/Volume 2 Cap. 3.05 - 6.021785167929.pdf` (not fetched yet)
- Criminal Law (Offences) Act Cap 8:01: `https://www.mola.gov.gy/laws/Volume 3 Cap. 6.03 - 10.071785253947.pdf` (not fetched yet)
- Data Protection Act 18 of 2023: `https://www.parliament.gov.gy/documents/acts/23760-act_no._18_of_2023.pdf` (not fetched yet)
- Amending acts: list of 24 URLs in `scripts/guyana-law/constitution_acts.txt`
  (base `https://www.parliament.gov.gy/documents/acts/`): 8242 (17/1984), 8533 (1/1988), 8503 (23/1990), 5890 (11/1992),
  5939 (21/1993), 6021 (15/1995), 6473 (2/2000), 6481 (11/2000), 6483 (14/2000), 6486 (17/2000), 4458..4560 (3..8/2001),
  4619 (10/2003), 4644 (16/2004 CCJ Act), 4688-act_no_24_of_2006.pdf (24/2006), 2795-act_no_22.pdf (22/2007),
  2938-act_no._5.pdf (5/2009), 5374-5374-act_no._2_of_2015.pdf (2/2015), 5713-act_no._1_of_2016.pdf (1/2016).
  Rebuild that list with `sources.parliament_acts()` (match on pdf file name) if needed.

## Commencement rule (cite in country.default_in_force_rule)
Interpretation and General Clauses Act, Cap. 2:01, s. 15: "Every Act shall be published in the Gazette and shall
come into operation on the date of publication unless it is provided in that Act or some other written law that it
shall come into operation on some other date." s. 16: an Act expressed to come into operation on a particular day comes
into operation immediately on the expiration of the previous day. Source: the Cap 2:01 URL above.

## Constitution (Cap. 1:01): facts verified
- Act 2 of 1980 [20 Feb 1980]; Constitution in operation 6 Oct 1980 (Act s. 4, Procl. 2/1980).
- Amended by (LRO 1/2022 front page): 17/1984, O.38/1987, 1/1988, 23/1990, 1/1991, 12/1991, 35/1991, 36/1991,
  11/1992, 21/1993, 15/1995, 2/2000, 11/2000, 14/2000, 17/2000, 3-8/2001, 5/2003, 10/2003, 16/2004, 24/2006,
  22/2007, 5/2009, 2/2015, 1/2016.
- Not online: the 1980 Act as enacted, the 1991 acts (1, 12, 35, 36 of 1991), 5/2003, O.38/1987. So a forward replay
  from 1980 is impossible, and a backward replay stops at the first whole-text substitution.
- Acts read (gazette text in the PDF; take dates from the PDF, NOT the index, which is wrong for some, e.g. 22/2007
  index says 2007-01-18 but the Gazette/assent is 28 Aug 2007):
  - 24/2006: assent 2 May 2006, Gazette 2 May 2006; "In relation to the Eighth Parliament, article 61 ... shall have
    effect as if for 'three months' the words 'four months' were substituted" -> temporary modification, words unchanged.
  - 22/2007: assent 28 Aug 2007, Gazette 28 Aug 2007; substitutes art. 156(3) with new (3) and (4). Not reversible
    (old 156(3) text not in the act).
  - 5/2009: Gazette 17 Mar 2009 (passed 29 Jan 2009); inserts art. 119D (Parliamentary Oversight Committee on the
    Security Sector).
  - 2/2015: Gazette 10 Jul 2015 (passed 9 Jul 2015); adds 9 entities to the Third Schedule (art. 222A). Two index rows
    point to the same act (5374 and 4034 PDFs, same size).
  - 1/2016: Gazette 11 Jan 2016 (passed 7 Jan 2016); adds "The Parliament Office" to the Third Schedule.

## Decided plan for the Constitution (smaller true history)
1. v1 = the 2010 consolidation, `from` 2007-08-28 (in force of 22/2007, the newest act it includes), `first_law: null`
   (oldest version available), `earlier_laws` = act-2-1980 and every amender through 22/2007.
2. v2 = v1 + art. 119D from 5/2009 (from 2009-03-17); check it against LRO 1/2012 text (record mismatches).
3. v3 = + 2/2015 Third Schedule entries (2015-07-10); v4 = + 1/2016 (2016-01-11); check against LRO 1/2022.
4. Differences between editions that no act explains (LRO 1/2022 formal revision, e.g. "his or her") -> uncredited
   (publisher commit "unexplained"), with the edition named in the version note; find the date the 2022 revised edition
   took effect (mola post `https://www.mola.gov.gy/post/nandlall-presents-2022-revised-edition-of-guyanas-laws-to-parliament`).
5. Unit keys: `art-001`, `art-006a`, `art-119d`, schedules `sch-1`..`sch-4`, preamble `preamble`; the enacting Act's
   sections could be a separate act or `sec-NN` (decide).
6. 24/2006: commit with no word change, `temporary_until` = end of Eighth Parliament (date needed) — or record in decisions only.

## Next 3 steps
1. Write parse.py: extract Constitution articles from the three editions with pymupdf using x-position to drop the
   right-margin notes (marginal "[N of YYYY]" are the credits); normalise quotes/dashes/spaces/hyphenation; diff editions.
2. Write corpus.json (country block, laws, act versions as above), repo/README.md + tools/in_force_on.py; build:
   `python -X utf8 scripts/gitlaw_common/build.py scripts/guyana-law --repo C:/Users/alany/Documents/guyana-law --docs-date 2026-10-28`,
   then check.py, then `--compare` into a temp dir; push main.
3. Fetch and do the Civil Law Act (Cap 6:01) the same way (editions on Wayback: CDX query
   `https://web.archive.org/cdx/search/cdx?url=mola.gov.gy/*&output=json&filter=mimetype:application/pdf&collapse=urlkey&limit=5000`
   is cached; `sites/default/files/` 2021-22 captures are LRO 1/2012 PDFs; legalaffairs.gov.gy 2012 captures `doc_download/<id>-chapter-NNNNN.html`).

## Gotchas
- Use curl only (Python TLS fails). Wayback CDX queries with regex filters are slow (>2 min). Result of the one left
  running at checkpoint: parliament.gov.gy constitution-PDF query got HTTP 504 (not cached; retry without regex, or skip);
  legalaffairs.gov.gy query cached and found one more edition to fetch and compare:
  `https://web.archive.org/web/20160119185919id_/http://legalaffairs.gov.gy/information/laws-of-guyana/410-chapter-101-the-constitution-of-the-co-operative-republic-of-guyana/file`
  (2016 capture; likely LRO 1/2012, check). Nothing older than the 2010 consolidation was found.
- Parliament index dates are unreliable; read the Gazette date and assent date from each PDF.
- Old act PDFs are OCR text layers with noise ("28'" August", "LEGA!."), so never take legal text from them without
  checking against an edition.
- Never commit in the main lexifina repo. WebSearch cap 12 (none used yet).

## Cache
`scripts/guyana-law/.cache/` (gitignored), about 300 files at checkpoint. Requests log `.cache/requests.jsonl`.

## Final state (18:20Z)
- Pushed main 510f134 (autopush, BUILD_STATUS 18:18:23Z): check 0 mismatches / 0 trailer errors; local --compare identical.
- Acts: constitution (6 versions), civil-law (1), criminal-law-offences (2). verify.py passes for all three.
- Open: Act 12/2021 (Civil Law s.5(1)(b)), Act 10/2025 (Criminal Law Misc.), Data Protection Act 18/2023 are scans
  with no text layer (no OCR on this machine; no model may write legal text). Marginal notes (part of the law under
  Cap 2:01 s.57(3)) not included. Dates of LRO 1/2012 and 1/2022 orders not found (used the "as at 31 Dec" dates).
- WebSearch used: 1 of 12.
