# Tanzania (lexifina/tanzania-law): progress of gitlaw-TZ (handoff, 2026-10-29 00:40 UTC)

Rules: scripts/africa-law/FANOUT.md (incl. FAST ARCHIVE ACCESS), BRIEF.md, south-america-law/BRIEF.md.
Shared adapter scripts/africa-law/peachjam.py is read-only (parse.py vendors a byte copy here for shipping).

## Constitution (2026-10-29, gitlaw-publisher-fix): built, held on preview
- `constitution.py` (cache only, PyMuPDF text layer, no OCR) writes `corpus.d/10-constitution.json`: act
  `constitution`, 1 version from 2005-04-22 (TanzLII's date for the 14th Amendment, Act 1 of 2005), 167 units:
  title, preamble, art-001..art-152 (162 articles incl. 46A/B, 53A, 59A/B, 107A/B, 110A, 113A, 120A), sch-1, sch-2,
  structure (chapters, parts, sub-headings with the first article under each). first_law null; earlier_laws = the 15
  Acts + 2 G.N. the edition lists (titles from Parliament's Acts list where it gives the number; 2005/1 from TanzLII).
- **Per-act publisher** used: `{"name": "Ministry of Constitutional and Legal Affairs (Tanzania)", "email":
  "nalis@sheria.invalid"}`; the "oldest version available" commit is authored by the Ministry (checked in the build).
  This resolves the open builder issue noted in step 3 below.
- Checks: every 11.7 pt body word of the PDF is in the units (word-multiset compare); 162 article heads in sequence;
  article titles from the margin notes, 33 differ in wording from the Arrangement of Contents (listed in decisions),
  80 and 82 (repealed) take the Contents title; margin amendment references left out of the text.
- Local verification (docs-date 2026-10-29, empty scratch repo): all parts 8 acts, 32 commits, 40 tags; check.py 0
  mismatches, 0 trailer errors; `--compare` identical. Verified-only build (GITLAW_VERIFIED_PARTS_ONLY=1) `--compare`
  against the autopush clone: history identical (main differs only by tools/constitution.py in the docs commit).
  corpus.json is byte-identical to before (parse.py re-run; README.extra.md updated, so repo/README.md changed).
- **No `corpus.d/10-constitution.PUBLISH`:** "no amendment after the 14th" could not be confirmed. TanzLII's history
  (capture 20250918092127) lists nothing after 2005-04-22; Parliament's lists (polis.bunge.go.tz/api/acts/async,
  1,177 Acts; /api/bills/async, 146 Bills; fetched 2026-10-29, logged in `.cache/requests-constitution.jsonl`) have
  no Constitution amendment, but cover only 1964-1995 and 2015-2026 (they lack even the 2000 and 2005 amendments),
  and the CIA World Factbook (one WebSearch, 3 of 5 TZ used) says "last [amended] in 2017". To publish: find an
  official list covering 2006-2014 (or a 2017 amending Act, which would make this a 2-version history), then write
  the .PUBLISH.
- Remote main (read-only `git ls-remote`, 2026-10-29): d8ac513 = our own autopush build (05:05Z), not the scaffold.

## State (2026-10-29, gitlaw-finisher)
- **PUBLISH written.** parse.py now splits: corpus.json = the 4 acts whose last version is TanzLII's current
  expression (Penal Code, Law of Marriage Act, Law of the Child Act, Judiciary Administration Act; 12 versions, 27
  laws); corpus.d/50-unverified.json = ELRA, CPC, BRADEA (8 versions, 20 laws; no .PUBLISH, so preview only). The
  split is the `UNVERIFIED` dict in parse.py, with the reason per act, recorded in decisions of both files. Laws only
  the held acts credit moved to the part; uncredited laws (named in version notes) stay in corpus.json.
- Re-running parse.py re-vendored the shared peachjam.py (one change at line ~1091, which History events count);
  every act's data came out byte-identical to the 00:10 corpus.
- README.extra.md (new) names what is missing: the 3 held acts, the unarchived Marriage 2022-07-15 / Penal 2002-07-31
  expressions, and the Constitution. repo/README.md regenerated (4 acts).
- Local verification (CADENCE CHANGE): verified-only build (GITLAW_VERIFIED_PARTS_ONLY=1) into an empty repo: 14
  commits, 20 tags, 3 unexplained; check.py 0 mismatches, 0 trailer errors; --compare identical. Full (preview)
  build: 7 acts, 20 versions, 31 commits, check.py 0 mismatches.
- verification.json fidelity flags penal-code@2023-12-31 sec-050..054, 367, 368: repealed-section placeholders that
  carry a footnote shared by several sections ("Sections 51, 52... were re-enacted in the Newspapers Act"); the
  heuristic counts the shared footnote against each one. No operative text involved.
- Remote main was still the scaffold (2f5b208) when PUBLISH was written; the next 4-hourly autopush pass publishes.
- To publish a held act later: verify it (archived copy of the expression TanzLII names as current), remove it from
  UNVERIFIED, rerun parse.py, rebuild and check.

## State at handoff (2026-10-29 00:40 UTC)
- corpus.json written (parse.py, cache only): 7 TanzLII acts. **No PUBLISH**: builds go to `preview` only.
- Not yet verified for PUBLISH; see "Listing check" below.

| Act | Work | Versions built (archived) | LII listing today names | OK |
| --- | --- | --- | --- | --- |
| Penal Code | ord/1930/11 | 2019-11-30, 2023-12-31 (LII also lists 2002-07-31, not archived) | 2023-12-31 | yes |
| Employment and Labour Relations Act | 2004/6 | 2004-06-11, 2023-12-31 | 2025-03-14 (not archived) | no |
| Law of Marriage Act | 1971/5 | 2019-11-30, 2023-12-31 (2022-07-15 has no good capture) | 2023-12-31 | gap |
| Law of the Child Act | 2009/21 | 2019-11-30, 2023-12-31, 2024-10-11 (all) | 2024-10-11 | yes |
| Civil Procedure Code | 1966/49 | 2019-11-30, 2021-01-18, 2021-10-22, 2024-10-04 (LII History also lists 2020-02-21, not archived) | 2021-10-22 (!) | no |
| Basic Rights and Duties Enforcement Act | 1994/33 | 2019-11-30, 2025-03-14 (2020-06-19 no good capture) | 2023-12-31 (!) | no |
| Judiciary Administration Act | 2011/4 | 2012-03-01 (commencement), 2015-07-01, 2016-07-01, 2020-06-19, 2023-12-01 (all) | 2023-12-01 | yes |

## Next step (exact) — steps 1 and 2 DONE 2026-10-29 (see State above); step 3 DONE (Constitution built, held on preview: see the Constitution section at the top); 4 remains
1. Drop or move the non-matching acts so the published set is verified: either remove ELRA, CPC and BRADEA from
   acts.json (record why in `decisions`) and rerun `python -X utf8 scripts/tanzania-law/parse.py`, or split them into
   corpus.d parts without .PUBLISH. CPC/BRADEA: TanzLII's listing today names an OLDER expression than the newest
   archived one (expressions withdrawn?); bare-work 302 captures (CDX cached) could show the redirect target.
2. Check BUILD_STATUS.json (preview build + check.py), then write PUBLISH for Penal Code, Law of the Child Act,
   Judiciary Administration Act (+ Law of Marriage Act if the 2022-07-15 gap is accepted and listed).
3. Constitution (Phase 1): TanzLII has the Constitution in Kiswahili only (1977/1 swa@2002-07-31). The official English
   text is cached: `.cache/nalis/katiba_ya_jamhuri_ya_muungano_wa_tanzania__english_version__2009_1.pdf`
   (sha256 ba2f319f..., 519,926 B, text layer, 91 pages), from nalis.sheria.go.tz/en/constitution (Ministry of
   Constitutional and Legal Affairs; signed S3 URL via a server action, downloaded with Playwright, script
   `.tmp/nalis_dl.py`). It is the "official Revised version in English ... up to the 14th Amendment of 2005" (Cap. 2,
   G.N. No. 150 of 2005). TanzLII's archived History (Kiswahili page, capture 20250918092127) lists the 14th Amendment
   on 2005-04-22 and nothing later, so one version dated 2005-04-22. Layout (PyMuPDF): margin notes x<155 at 9.7 pt
   (article titles + "Act No.15 of 1984 Art.6" refs), body x>=160, paragraphs start x=195, items "(a)" at 195 with
   text at 230; headings centred. To do: constitution.py -> corpus.d/10-constitution.json.
   Open builder issue: the first version of an act with first_law=null is authored by the country publisher (TanzLII),
   which would be wrong for the Ministry PDF; needs a per-act publisher in gitlaw_common (write ISSUES.md) or keep
   the part unpublished.
4. Phase 2 candidates with every listed expression archived (survey, `.tmp/survey.jsonl`): Public Audit Act 2008 (7),
   Law School of Tanzania Act (4), Anti-Money Laundering Act (3), National Prosecutions Service Act (3), Legal Aid Act
   (3), Land Registration Act (3), Cotton Industry Act (3). Land Act 3/4, Companies Act 2002 listing mismatch.

## Sources probed (2026-10-28)
- **TanzLII** is `tanzlii.org` (`tanzlii.go.tz` does not resolve). Works `/akn/tz/act/<year>/<num>`, ordinances
  `/akn/tz/act/ord/...`; pages also under `/en/akn/...` (path_prefixes `["", "/en"]`; listing `/en/legislation/?years=Y`).
  robots.txt: Allow /, Crawl-delay 5, Content-Signal ai-train=no, search=yes, ai-input=no. Terms: project of the
  Judiciary of Tanzania; "Scraping and bulk downloading from this website is strictly prohibited"; law content
  CC BY-NC 4.0 crediting TanzLII. No TanzLII document page fetched; only Internet Archive `id_` captures (pinned in
  sources.json) plus 7 open listing pages.
- Wayback: ~2,440 TanzLII works archived, mostly one expression (2002-07-31 / 2019-11-30 Revised Editions); list in
  `.tmp/archived_works.json`.
- **Common Crawl**: index.commoncrawl.org refused connections from this machine all session (21:55 to 00:35 UTC).
  All fetching went through gitlaw_common/wayback.py (archive.org, shared adaptive rate).
- Government: parliament.go.tz (Acts as passed, polis.bunge.go.tz PDFs, mostly Kiswahili), oag.go.tz (robots allow
  all; no law list found), sheria.go.tz -> nalis.sheria.go.tz (official Constitution PDFs; Kiswahili PDF is the 2000
  edition, older than the English 2005 one). agctz.go.tz does not resolve.

## Files
- fetch.py (archive.org via wayback.py -> sources.json), parse.py (peachjam.parse -> corpus.json, verification.json,
  repo/README.md, repo/LICENSE), survey.py, probe.py, cc_index.py (Common Crawl index; unused, CC unreachable).
- Cache: `.cache/` (archive.org CDX + captures, listings, `nalis/` PDFs). WebSearch used: 2 of 5.
