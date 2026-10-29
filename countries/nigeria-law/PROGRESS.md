# Nigeria (gitlaw-NG-GH): progress and handoff, 2026-10-29

Country: Nigeria, slug nigeria, repo lexifina/nigeria-law (private), tz Africa/Lagos, lang en, future_branch future.
Remote main at 2026-10-29: bbf4208 (scaffold "Nigeria: sources, before any law"). Nothing pushed by this agent
(cadence change: autopush's 4-hourly pass publishes).

## Status
- [x] fetch.py: pins the 3 PDFs (sha256 checked) and writes sources.json.
- [x] get.py: keeps only whole PDFs (`%PDF-` ... `%%EOF`); removed the truncated CAMA capture 20210506145030 from the cache.
- [x] parse.py -> corpus.json (country + `data-protection`), corpus.d/10-constitution.json, corpus.d/20-companies.json,
      verification.json. Deterministic (re-run gives identical bytes).
- [x] repo/README.md, repo/LICENSE, repo/jurisdiction.json (hand-written; not generated).
- [x] Local build (.tmp-build, all parts): 3 acts, 3 versions, check.py 0 mismatches, 0 trailer errors; `--compare`
      rebuild hash-identical (main deabd8c). Verified-only build (GITLAW_VERIFIED_PARTS_ONLY=1, .tmp-build-main):
      1 act, check 0/0, main 379b6af.
- [x] PUBLISH written (corpus.json = NDPA only). No .PUBLISH for either part.

| Act | Part | Versions | From | Units | Words printed = kept | PUBLISH |
| --- | --- | ---: | --- | ---: | --- | --- |
| Nigeria Data Protection Act, 2023 (`data-protection`) | corpus.json | 1 | 2023-06-12 | 66 sections + Schedule | 12,700 = 12,700 | yes |
| Companies and Allied Matters Act, 2020 (`companies`) | corpus.d/20-companies.json | 1 | 2020-08-07 | 870 sections + 15 Schedules | 192,815 = 192,815 | no: BFA 2022 (in force Feb 2023) amended it |
| Constitution of 1999 (`constitution`) | corpus.d/10-constitution.json | 1 | 1999-05-29 | Preamble, 320 sections, 7 Schedules | 64,926 = 64,926 (285->281 renumbered) | no: as promulgated |

## Key finding (changes the handoff's plan)
The FMOJ print "Constitution ... 1999 [With the First, Second and Third Alterations]" is NOT a consolidation: its body
is the 1999 text as promulgated (s. 75 still has "the 1991 census", s. 66(1)(h) present, no ss. 254A-254F, Sixth
Schedule tribunals of "a Chairman and four other members"). The three Alteration Acts follow only as FGP gazettes
(pp. 172-208). So the Constitution is built as one version from 1999-05-29 (first_law `promulgation-1999-24`), not as
a 2011 text. All Alterations (1st-3rd replayable from the same PDF; 4th 2017-18 and 5th 2023: no source) are missing.

## Sources (pinned in sources.json, cache .cache/, ~5.6 MB, requests.jsonl)
- constitution: Wayback 20211015170245 of justice.gov.ng/wp-content/uploads/2020/09/Nigerian-Constitution.pdf, 672,495 B, 209 pp, sha256 e2930538...
- data-protection: https://ncc.gov.ng/media/801/view (FGP Gazette No. 119, 1 Jul 2023), 658,393 B, 43 pp, sha256 5bfb22cf...
- companies: Wayback 20210301095237 of pre.cac.gov.ng/assets/images/CAMA-NOTE%20FINAL-FULL-VERSION.pdf (FGP Gazette No. 124, 10 Aug 2020), 1,269,127 B, 528 pp, sha256 d39745af...
- Probed, not used: NigeriaLII (0 acts), NASS Acts list (scans / clipped printout), judy.legal (JS-rendered), PLAC (unofficial).

## Code
- `gazette.py`: FGP text-layer reader. This session: mixed-case "Part"/"Chapter" at a line start is a heading only with
  a number and dash (wrapped body lines were being dropped as headings); `orphans` report; side notes split at a full
  stop; hyphenated side notes rejoined (`dehyphen`, vocabulary from the body); note window -6/+14 with a -16 fallback;
  `renumber` for misprinted section numbers; `start=None`; `report["words"]` for the word-level fidelity check; a
  line starting in lower case never starts a paragraph by indentation; printer's space before ; : , removed.
- `parse.py`: config per act (pages, running-head band, start/stop, schedule regex); on Constitution schedule pages
  the margin (item numbers, capital cities, paragraph headings) is moved into the body.

## Next steps (Phase 2)
1. Constitution: replay the First, Second and Third Alteration Acts from the gazettes in the same PDF (pp. 176-207;
   each is a list of textual instructions: "Section 66(1)(h) ... is deleted", "inserting immediately after the word
   ... the words ..."); versions 2010-07-16 (First), 2010-11-29 (Second), 2011-03-04 (Third), all assented/gazetted
   Jan-Mar 2011 (retroactive commencement: say so). Then look for 4th/5th Alteration gazettes with a text layer
   (Fifth Alteration No. 17, Act No. 24 of 2023, reportedly at aserc.anambrastate.gov.ng: not fetched).
2. CAMA: find an FGP text of the Business Facilitation (Miscellaneous Provisions) Act, 2022 with a text layer and
   replay its CAMA amendments; then PUBLISH the part.
3. NDPA: re-check for any amending Act before each publish.

## Open issues
- None for peachjam.py (not used: NigeriaLII has no acts).
- Process note: two small edits to gazette.py/parse.py this session were made by script rather than the Edit tool
  (side-note split + note tolerance; one print-field list); both were checked by re-running parse.py.
