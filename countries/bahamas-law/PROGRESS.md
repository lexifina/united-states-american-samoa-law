# gitlaw-BS: The Bahamas law history (progress)

Updated 2026-10-29 ~06:40 UTC by gitlaw-BS-2. **Phase 1 done and verified locally; PUBLISH written.** Nothing pushed or committed (cadence change: the 4-hourly autopush pass publishes).

Slug `bahamas`, repo `lexifina/bahamas-law` (PRIVATE), clone `C:/Users/alany/Documents/bahamas-law` (owned by autopush; not touched).
Remote checked read-only before writing PUBLISH: `main` = bd4c6c7 "Bahamas: sources, before any law" (the scaffold), plus `wip`.
tz America/Nassau, lang en, future branch `future`, docs-date 2026-10-29 (retrieval day).

## Checklist
- [x] Scaffold check; rules read (WAVE, BRIEF incl. CADENCE CHANGE, SCHEMA incl. per-act publisher)
- [x] fetch.py (curl, sha256 cache, 3 req/s, requests.jsonl, POST forms); `fetch.py --plan` fetches `sources.PLAN`
- [x] Dated-index route confirmed (see Source facts); Constitution, Penal Code and Data Protection Act found
- [x] Text layers checked: all three consolidations have one; the Constitution (Amendment) Act 2017 PDF is a scan (6 chars in 7 pages), left out
- [x] Copyright page read and recorded (README, LICENSE, licence_note)
- [x] pdftext.py (PDF layout reader) + parse.py -> corpus.json (country, shared sources) + corpus.d/10-constitution, 20-penal-code, 30-data-protection
- [x] repo/README.md, repo/LICENSE, repo/jurisdiction.json
- [x] Local build into an empty scratch repo: check.py 0 mismatches, 0 trailer errors; `--compare` identical; verified-only build (GITLAW_VERIFIED_PARTS_ONLY=1) checks clean too; parse.py is byte-deterministic
- [x] PUBLISH + corpus.d/{10-constitution,20-penal-code,30-data-protection}.PUBLISH

## Result (local build)
| Act | Versions | Span | Latest = current consolidation |
| --- | ---: | --- | --- |
| constitution | 1 | 1973-07-10 | LRO 1/2006 (1973-1080_1.pdf) |
| penal-code | 7 | 2009-10-01 .. 2016-12-31 | LRO 1/2017 (1873-0015_2.pdf) |
| data-protection | 1 | 2007-04-02 | LRO 1/2008 (2003-0003_1.pdf) |

10 commits, 17 tags, 62 laws in the record, 1 unexplained (publisher) commit (9 Penal Code provisions on 2016-12-31). Local main c8df7e5 / history tip b71a66e (scratch build; the real one is autopush's).

## Source facts (verified 2026-10-29)
- laws.bahamas.gov.bs answers curl directly, no bot challenge; robots.txt allows /cms/images/LEGISLATION/.
- **The point-in-time field is `pointintime_post`**, not `pointintime_post_alpha` (that hidden field is ignored: the earlier cached C/D/P pages all say "Current Legislation for 29 October 2026"). Body: `pointintime_post=YYYY-MM-DD+00%3A00%3A00&submit4=<LETTER>`.
- The dated index gives distinct dated consolidations only where the publisher made more than one edition. Penal Code: `_1` = LRO 1/2010 listed up to 2016-12-30, `_2` = LRO 1/2017 from 2016-12-31 (bisected). `_2` has no lower bound (it is listed beside `_1` on every earlier date). Constitution and DPA: only `_1` exists (`_2` 403).
- "amended by..." rows under a listing are the amending Acts made after that consolidation, with "Date Commenced". Acts by Year (`POST year=YYYY`, rows rowMain/rowAmd) gives title + commencement for others.
- PDF layout: body 10-12 pt, marginal notes 8 pt (heading roman, amendment notes italic "34 of 2011, s. 2."), bold section numbers, centred Part/Book/Title headings, the act's list of laws as a margin column on the title page, arrangement of sections at 9 pt (used for headings).
- Copyright page (article 115): "The legislation contained on this website is subject to Government of The Bahamas Copyright protection. Any reproduction shall ensure its accuracy, and the source and copyright status of the material is made evident to users. The website may only be used for informational non-commercial purposes and must not be used in a derogatory or defamatory manner." The `rights` meta naming the Isle of Man is iLAWSSYNC template text.
- The site search (ilaws-search) is an iframe; not used.

## Penal Code method
v1 = LRO 1/2010, dated 2009-10-01 (commencement of Act 1 of 2007, the last law its list names), publisher "oldest version available". Then each provision whose words differ and whose LRO 1/2017 marginal note names a law not in LRO 1/2010's list gets its 2017 text on that law's commencement: Act 20/2010 (2011-01-04, 7), Act 1/2011 (2011-06-01, 1), Act 19/2010 (2011-10-04, 33), Act 34/2011 (2011-11-04, 3), Act 15/2014 (2015-11-12, 5). Act 28/2008 (3 provisions) has no date on the site: dated 2016-12-31 with a law `note` saying so. 9 other differing provisions -> publisher, unexplained, 2016-12-31. Same-words provisions take the 2017 paragraphing everywhere. parse.py asserts the last version == LRO 1/2017.

## Not built (named in decisions + README)
- Penal Code (Amendment) Acts 2018 (2018-12-31), 2020 (2020-12-09), 2024 (2024-08-01): in no consolidation the site serves.
- Constitution (Amendment) Act 2017 (2018-05-10): scan only, no OCR; current consolidation still LRO 1/2006.

## Cache
`.cache/`: 60 logged requests, ~43 MB (5 point-in-time index pages + earlier probes, 7 year pages, copyright, 5 PDFs, bisection pages).

## Next (Phase 2 ideas)
- Other acts with more than one edition (`_2`, `_3` PDFs) give real dated history the same way: probe `_k` per act from the index; the Civil-law-type acts here are many separate Acts (no Civil Code).
- Find Act 28 of 2008's commencement (Official Gazette 2008 via gazettes-by-year) to date it properly.

## Open issues
None in the shared builder.
