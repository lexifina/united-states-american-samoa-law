# Rwanda (gitlaw-RW): progress

Owner: gitlaw-RW (resumed 2026-10-29 by gitlaw-SZ-RW). Not a Peachjam country: RwandaLII is not used. Source is the
Rwanda Law Reform Commission's open API behind amategeko.gov.rw (robots.txt allows all), serving the trilingual
Official Gazette PDFs (Kinyarwanda | English | French); the English column is read from the text layer (no OCR).

## Files
- `fetch.py`: API metadata + signed PDF URL per file id, cached by sha256 of a stable URL; `.cache/requests.jsonl`.
- `extract.py`: the English column as structure (running heads by content, two gutters, line pitch paragraphs).
- `parse.py`: corpus.json (whole texts, replay of amending laws, two Supreme Court rulings from the RLR).
- `verify.py`: column check, replay check, today's-text check -> verification.json.
- `repo/`: README.md (English, short French section), LICENSE (no licence; RLRC terms quoted), jurisdiction.json
  (from the scaffold, build line filled in). Written 2026-10-29: earlier builds had no README or LICENSE.
- `.gitignore` (.tmp/, .tmp-build/, .cache/), added 2026-10-29 so the stale .tmp-build clone stays out of wip.
- `.cache/prior-amategeko-build.bundle`: backup of the remote main as found on 2026-10-28 (see "Remote main").

## Built (corpus.json, docs date 2026-10-29; 44 requests, cache 87 MB)
| Act | Versions | From |
| --- | ---: | --- |
| constitution | 2 | 2015-12-24 (2015 revision), 2023-08-04 (2023 revision, whole text) |
| penal-code (Law 68/2018) | 5 | 2018-09-27, 2019-04-24 (Re Mugisha), 2019-11-29 (Law 69/2019), 2022-05-20 (Re Byansi), 2023-12-05 (Law 059/2023) |
| data-protection (Law 058/2021) | 1 | 2021-10-15 |
| public-servants (Law 017/2020) | 4 | 2020-10-08, 2020-11-20 (Law 019/2020), 2024-06-19 (Law 052/2024), 2026-04-24 (Law 017/2026) |

## Checklist
- [x] fetch, extract, parse (deterministic: re-parse 2026-10-29 byte-identical)
- [x] verify.py: column check 0 words missing; replays restated_equal and only_named_changed; today's text OK
- [x] 2026-10-29: the open item ("gutter return"): the 2023 Constitution's column check reported 50 file words out
      of order. Cause: words at the right edge of the English column (e.g. "from" in "Article 16: Protection from
      discrimination", x 500-525 with the gutter at 527) sit in the PDF block of the French column, so PyMuPDF's
      clip text in block order placed them after the next English line. extract.py was right (it orders by
      position). verify.py now orders the clip's lines by position (baseline, then x); result 0 out of order for all
      four texts, and `ok` now also requires 0 out of order.
- [x] repo/ README.md + LICENSE + jurisdiction.json
- [x] Local verify 2026-10-29: empty scratch build (main 92001ab, history tip 46b5c0d = preview's parent), check.py
      0 mismatches, 0 trailer errors; --compare rebuild identical; tools/on.py commands in the README tried.
- [x] 2026-10-29 (gitlaw-RW-2): Law n° 017/2020 + amendments added in parse.py (no corpus.d here): files 4423, 4193,
      6109, 11115 re-fetched by fetch.py (8 requests) and pinned in acts.json; their sha256 equal the old build's.
      Replay grammar generalised by base law (LAW68 / LAW017); unquote also strips a closing mark printed before the
      final full stop. constitution, penal-code and data-protection in corpus.json are byte-identical to before.
      verify.py extended: column check of 4423 (8035 words, 0 missing, 0 out of order), replay check of 4193, 6109,
      11115 (restated_equal, only_named_changed), today's text = 2020 text changed only by named articles. OK.
- [x] Local verify 2026-10-29 (after the statute): empty scratch build, docs date 2026-10-29: 12 law commits, 24 tags,
      main 4120447, history tip f495849 (superseded: with enacting formulae, main 5a22f50, tip ce0185c); check.py 4 acts, 12 versions, 0 mismatches, 0 trailer errors, 0 missing
      in-force; --compare rebuild identical. tools/on.py tried on public-servants.
- [ ] PUBLISH: **not written** (user decision: replacing remote main). The comparison below says nothing is lost
      in law text or dates; see the three format differences.

## Remote main (checked read-only 2026-10-29)
- `main` = 121603e, NOT the scaffold and NOT a build of this corpus: an earlier Lexifina build (author
  rwanda-law@lexifina.com, own tools/on_date.py and build.py) of the Constitution plus Law n° 017/2020 (public
  servants statute, with 019/2020, 052/2024, 017/2026 replayed), with tags constitution/2015, constitution/2023,
  law-2020-017/*. The scaffold is on `sync/main` (cd9cc49). `preview` = 411fddb (our build).
- Per the run rules PUBLISH is not written while main holds another build. 2026-10-29: Law 017/2020 and its three
  amendments are now folded into this corpus (`public-servants/`), so publishing no longer drops the statute; see
  "Comparison with the old build" for what differs. Replacing main stays the user's decision (the bundle in .cache
  keeps the old history). preview/BUILD_STATUS predate the statute until autopush's next pass.

## Open issues
- PUBLISH: user decision on replacing remote main (comparison below). Nothing else blocks it.
- Public servants statute: amendments after Law n° 017/2026 (24/04/2026), if any, were not searched for (the old
  build had these three; the API's document for 017/2026 names parent 4252, the base law's document id).
- Penal Code: no official consolidation exists, so "today's text" is the replay, checked against each amending law's
  restated text; amendments after Law 059/2023, if any, were not searched for on 2026-10-29.

## Comparison with the old build (remote main 121603e), 2026-10-29 (re-run after adding enacting formulae)
Old build read read-only from `.cache/prior-amategeko-build.bundle` (cloned to the scratchpad). Script and full result:
`.tmp/compare_old.py`, `.tmp/compare-old-build.json` (args: old clone, this folder, output). Same sources: all six
PDFs the old build used (5144, 3939, 4423, 4193, 6109, 11115) have the same sha256 in our cache.

| Old tag | In force (old = ours) | Units compared | Byte-equal | Equal after our normalisation | Text differences |
| --- | --- | ---: | ---: | ---: | ---: |
| law-2020-017/2020-017 | 2020-10-08 | 94 (93 arts + enacting) | 69 | 94 | 0 |
| law-2020-017/2020-019 | 2020-11-20 | 95 | 70 | 95 | 0 |
| law-2020-017/2024-052 | 2024-06-19 | 91 | 67 | 91 | 0 |
| law-2020-017/2026-017 | 2026-04-24 | 91 | 67 | 91 | 0 |
| constitution/2015 | 2015-12-24 | 179 (177 arts + preamble + enacting) | 161 | 179 | 0 |
| constitution/2023 | 2023-08-04 | 178 (176 arts + preamble + enacting) | 150 | 178 | 0 |

Every version of the old build is in ours, on the same in-force day, with the same set of files (no file only in
one build, enacting formulae included) and the same words. The differences, all of form:
1. **Typography (the non-byte-equal units above).** Our parse.py normalises once (SCHEMA rule): curly apostrophes
   and quotes and U+201F become ' and ", "Nº" becomes "N°". The old build kept the PDF's characters. Statute: 25
   units, only ’ and º. Constitution: 18 (2015) and 28 (2023) units, only quotes/apostrophes. No word differs.
2. **Chapter/Section/Subsection lines.** Old files carried `Chapter:`, `Section:`, `Subsection:` lines under the
   heading (49 distinct headings); ours start with "Article N: heading" then the paragraphs (the README says so).
   The structural headings are not in our corpus. Adding them would change every unit of every act: a corpus-wide
   choice, not made here.
3. **Enacting formula: now a unit (coordinator request, 2026-10-29).** `enacting-formula` in every act (title,
   promulgation formula, the Parliament's sittings and citations), equal to the old `enacting-formula.md` after
   normalisation in all 6 old versions. Also added for the Penal Code and data protection law (old build had
   neither act). Law 68/2018's trailing "PART ONE"/"TITLE ONE" headings are left out, like Chapter lines. Only the
   2023 revision changes the Constitution's (credited to it); amending laws leave their act's unchanged. All other
   units are byte-identical to the corpus before this change. verify.py OK (column check now orders
   enacting-formula, preamble, articles); rebuild: main 5a22f50, history tip ce0185c, check.py 0 mismatches, 0
   trailer errors, --compare identical.
Other, non-text: the folder is `public-servants/` (old `law-2020-017/`); tags are `public-servants/<day>` and
`law/<key>` (old `law-2020-017/2020-017`, `constitution/2015`); the old `Takes-effect: 2020-10-08` trailer of Law
019/2020 is a version note in the commit body here; old `tools/on_date.py` is `tools/on.py`; author names differ
slightly ("Revision of 2023 of the Constitution" vs "Revision of the Constitution (2023)"). Both builds keep Article
21's enacted heading "Incidental leave" although Law 052/2024 heads its amending article "Circumstantial leave", and
Article 4's enacted heading although Law 017/2026's amending article is headed differently.

**Verdict:** replacing main loses no law text and no date. It drops only the Chapter/Section/Subsection context
lines (item 2, kept out by decision), and adds the Penal Code (5 versions) and the data protection law. Decision for
the user: approve replacing main (write `PUBLISH`).
