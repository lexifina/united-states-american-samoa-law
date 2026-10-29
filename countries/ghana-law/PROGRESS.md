# Ghana (gitlaw-NG-GH): progress and handoff, 2026-10-29

Country: Ghana, slug ghana, repo lexifina/ghana-law (private), tz Africa/Accra, lang en, future_branch future.
Remote main at 2026-10-29: 71e071e (scaffold "Ghana: sources, before any law"). Nothing pushed by this agent
(cadence change: autopush's 4-hourly pass publishes). No PROGRESS.md existed before this one; the state was
reconstructed from acts.json, sources.json, constitution.py and .tmp/fetch.log.

## Status
- [x] fetch.py (Peachjam adapter): 4 GhaLII expressions pinned from Internet Archive captures (sources.json).
- [x] constitution.py: fixed the missing articles 195 and 297. Cause: their headings contain "ETC."
      ("195. APPOINTMENTS, ETC. OF PUBLIC OFFICERS.", "297. IMPLIED POWER, ETC..") and both the body-heading regex
      (HEAD) and the arrangement-of-articles regex (toc_titles) rejected a full stop inside a title. Both now allow it;
      all 299 articles are found and the changed-units check (9 articles of Act 527) passes.
- [x] parse.py: corpus.json = the 3 GhaLII acts via peachjam.parse; corpus.d/10-constitution.json = the Constitution
      (constitution.build); verification.json; repo/README.md + LICENSE via peachjam.write_docs, with README.extra.md
      describing the Constitution part. Deterministic.
- [x] acts.json: added a decision on the Renewable Energy Act's commencement ("Commenced" with no date on the 2011
      page; the 2020 page says "Commenced on 31 December 2011").
- [x] Local build (.tmp-build, all parts): 4 acts, 6 versions, check.py 0 mismatches, 0 trailer errors, `--compare`
      identical (main 7830eab). Verified-only build: 3 acts, 4 versions, 0/0 (main 72fe462).
- [x] PUBLISH written (corpus.json). No .PUBLISH for the Constitution part.

| Act | Part | Versions | From | Checks | PUBLISH |
| --- | --- | ---: | --- | --- | --- |
| Data Protection Act, 2012 (Act 843) | corpus.json | 1 | 2012-10-16 (commenced; expression 2012-05-18) | listing ok, nothing after, fidelity 0 | yes |
| Companies Act, 2019 (Act 992) | corpus.json | 1 | 2019-08-02 | listing ok, nothing after, fidelity 0 | yes |
| Renewable Energy Act, 2011 (Act 832) | corpus.json | 2 | 2011-12-31, 2020-12-29 (Act 1045, 13 provisions) | listing ok, nothing after, fidelity 0 | yes |
| Constitution, 1992 | corpus.d/10-constitution.json | 2 | 1993-01-07, 1996-12-31 (Act 527, 9 articles) | 1993 text of changed articles = Audit copy (ratio 1.0 for 7 of 9; 2 differ only by Audit typos) | no |

Why no PUBLISH for the Constitution: both sources are government-hosted but not official prints (OSP's copy is an
Oceana compilation; the Audit Service copy has typing errors and omissions: of 290 unchanged articles, 79 differ from
OSP by one or two words and 34 by more, mostly the Audit copy's omissions and headings caught in the comparison).
Today's text (OSP, "as Amended to 1996") cannot yet be checked against an official expression. To publish: find an
Assembly Press / Ghana Publishing print with a text layer, or a GhaLII capture of /akn/gh/act/1992/constitution.

## Sources and cache
- GhaLII expression pages via Internet Archive id_ captures (20260414022511, 20260218211453, 20241201194147,
  20260419084445), GhaLII listing pages; osp.gov.gh and audit.gov.gh PDFs; GhaLII Act 527 page and source PDF
  (archived; the PDF's OCR layer is used only as a check). Cache .cache/ 7.7 MB, 31 requests logged.

## Next steps
1. Phase 2: more GhaLII acts with every listed expression archived (scripts/africa-law/survey.py ghana --top 40).
   Labour Act 2003 (no AKN text archived) and Criminal Offences Act 1960 (no capture) were ruled out.
2. Official Constitution print (see above), then PUBLISH the part.

## Open issues
- None for peachjam.py (parse.py re-vendors the shared copy when it changes; the copy in this folder was refreshed
  this session).
