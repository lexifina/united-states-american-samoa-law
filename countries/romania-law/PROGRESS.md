# Romania (gitlaw-RO): progress and handoff

Phase 2 (four more acts) added 2026-10-29 by gitlaw-RO-2, see below. Repo lexifina/romania-law (private scaffold, cloned to C:/Users/alany/Documents/romania-law, untouched; autopush owns it). Phase 1 done 2026-10-29 ~02:30 UTC. Nothing pushed or committed by this agent; the 4-hourly autopush pass publishes.

## Checklist
- [x] Probe: legislatie.just.ro (and its SOAP service) closes every TLS connection from this machine. Read only via archive.org `id_` captures (gitlaw_common/wayback.py). Common Crawl index unreachable on 2026-10-28.
- [x] fetch.py: 201 cache files (248 MB); forms.json pins every form's id, date and capture. 2026-10-29: added `pins` (Civil Code 03.05.2026 form = act page 109884 @20260625171643) and `base_capture` override (civil 2009 text @20250413082055; the newer capture is cut at 5 MiB). Both fetched via wayback.get; fetch.py carries the same pins.
- [x] parse.py -> corpus.d/10-constitutia.json (holds country + sources), 20-codul-civil.json, 30-codul-penal.json. Deterministic (two runs byte-identical), ~30 s.
- [x] Scratch build (scratchpad, --docs-date 2026-10-28): 64 commits, 118 tags, 57 laws, 4 unexplained commits; check.py 0 mismatches, 0 trailer errors, no merges/backwards/future; --compare identical (also with GITLAW_VERIFIED_PARTS_ONLY=1).
- [x] Independent check: the newest form of each act, parsed afresh, equals the built repo's main article by article (156, 2674, 458).
- [x] repo/README.md (English, then Romanian), LICENSE, jurisdiction.json, tools/in_vigoare_la.py
- [x] corpus.d/10-constitutia.PUBLISH, 20-codul-civil.PUBLISH, 30-codul-penal.PUBLISH (remote main confirmed still the scaffold a8f2bf2 via ls-remote, read-only)

## Corpus
- Constituția: 2 versions (1991-12-08 as adopted; 2003-10-29 republished text, 146 articles credited to Legea 429/2003).
- Codul civil: 13 versions, 2011-10-01 (2009 text, then same-day republished text: 665 changes, Legea 71/2011 + OUG 79/2011) ... 2026-05-03 (Legea 57/2026). 1 unexplained (art. 253 "1)"->"(1)", 2018). Cross-check: the 03.05.2026 form from two captures (109884, 130143) identical in all 2674 articles.
- Codul penal: 45 versions, 2014-02-01 (2009 text, then same-day first in-force form: Legea 187/2012, 63/2012, 27/2012) ... 2026-04-26 (Legea 53/2026). 12 unexplained (10 diacritic fixes 2014-05-20; arts. 194 and 378 line breaks only).
- Credits: amendment notes (dated "(la DD-MM-YYYY, ...)" from ~2017; undated after a dash rule before). CCR decisions: 732/2014 and 603/2015 from amendment notes; 601/2020 (civil art. 164) from the editorial note, effect day in the interval. parse.py stops if any note is dated after its form or a change's note date differs from its form date (none).
- Newest form in any capture (every cached page's "istoric consolidări"): civil 03.05.2026 (capture 2026-07-07), penal 26.04.2026 (2026-07-03), constitution 2003 only (2026-06-04). Later amendments may be missing (README says so).

## What the portal gives (verified on cached captures)
- Each consolidated form is its own page `/Public/DetaliiDocument/<id>`; the act page lists all forms under "istoric consolidări". The base form (as published) is `/Public/DetaliiDocumentAfis/<base id>`. The act's own page (109884, 109855, and 130143) shows the newest form.
- Markup: S_ART (TTL/DEN/BDY), S_ALN, S_LIT, S_PCT, S_LIN, S_PAR (black text incl. marginal titles; blue "(la ..." = amendment note), S_NTA = editorial notes. Older forms: alineate as S_LIT with "(1)" in the body; notes black after "---------".
- Quirks handled in parse.py: thousands separators in titles ("1 074", "1.000", "2357."), footnote markers "*)", leaked "<LLNK ...>", trailing "NOTĂ:" blocks and adoption/signature blocks, § headings nested in articles, marginal titles nested in the previous article or between articles, 2009 civil text with articles printed as loose paragraphs (ART.1.251, Art. 2.367, ART 2.655; art. 2.448 left run into 2.447), two HP holdings printed as text in penal art. 183 (2019+, dropped).

## Phase 2 (gitlaw-RO-2, 2026-10-29): done, verified locally, nothing pushed or committed
- [x] Four new parts, each with its own .PUBLISH: 40-codul-procedura-civila (28 versions, 2013-02-15 .. 2025-12-14), 50-codul-procedura-penala (61, 2014-02-01 .. 2026-06-13), 60-codul-muncii (61, 2003-03-01 .. 2025-12-18), 70-legea-190-2018 (2, 2018-07-31, 2019-12-01).
- [x] fetch.py: `python -X utf8 fetch.py phase2` (or slugs). Common Crawl first: one prefix query per crawl (40 crawls, 2022-2026) over legislatie.just.ro/Public/DetaliiDocument*, cached in .cache/cc-listing.json (260,510 records); archive.org only for the rest. A capture counts only if complete and it shows its form: the act page marks its shown form; a past form's page lists only the later forms up to the next republication, so the next form's date must be listed. Republications whose own page shows the newest form are read from DetaliiDocumentAfis/<id> (CPC 167140, CM 128647); never-captured newest forms from an act-page capture made while each was newest (CPP 309218, 310617). forms.json pins each (`cc`, `afis`, `pins`, `captures`, `base_cc`); Phase 1 entries unchanged.
- [x] parse.py: `python -X utf8 parse.py [slug ...]`. Phase 2 additions, all no-ops for Phase 1 (its three parts re-parse byte-identical): articles wrapped in their marginal-title paragraph or in an unclosed heading (S_PAR > S_PCT/S_CAP > S_ART); articles of other acts quoted in notes (Roman numbers, "NOTĂ: Reproducem") skipped; a duplicate article number between N-1 and N+1 read as N (CPP "Articolul 158" = art. 518); "Art. 518. -" run into art. 517 split off; portal notes printed as text dropped (gazette in capitals); the act-page id's republication link skipped; Codul muncii has no marginal titles (`titles: False`); republication credits (CPC 2015 -> Legea 138/2014, CM 2011 -> Legea 40/2011, from the portal's own note).
- [x] Cross-check: each act's newest form from a second capture equals the corpus's latest version (1143, 641, 297, 16 articles).
- [x] Scratch build (--docs-date 2026-10-29): 232 commits, 376 tags, 174 laws, 50 unexplained commits; check.py 0 mismatches, 0 trailer errors, no merges/backwards/future; --compare identical; GITLAW_VERIFIED_PARTS_ONLY=1 build gives the same main.
- [x] Phase 1 acts vs a Phase-1-only build: every law commit has the same author, date and act tree, and the act folders (READMEs included) are identical. Commit messages differ only on 15 shared law-days, where the commit now also holds Phase 2 provisions: Codul civil with CPC on Legea 138/2014 (2014-10-19), OUG 1/2016 (2016-02-04), Legea 17/2017 (2017-03-24), Legea 140/2022 (2022-08-18, also CPP and CM); Codul penal with CPP on OUG 18/2016 (2016-05-23), Legea 151/2016 (2016-07-23), Legea 49/2018 (2018-04-01), Legea 217/2020 (2020-11-02), Legea 228/2020 (2020-11-05), Legea 146/2021 (2021-05-21), Legea 207/2021 (2021-07-25), Legea 219/2021 (2021-08-27), Legea 214/2023 (2023-07-14), Legea 217/2023 (2024-01-01), Legea 53/2026 (2026-04-26). The docs commit also changes (README table, docs date 2026-10-29: autopush takes the newest `retrieved`).
- Unexplained changed articles: CPC 213 (portal typesetting flip-flops 2013-2014), CPP 80, CM 307 (form of 22.04.2007 without diacritics, 271), Legea 190/2018 0. CPP form 02.03.2017 (186645) has no text on the portal: its changes arrive 03.03.2017.
- Cache now 1.3 GB, 562 files, 560 logged requests (Phase 2: ~360, mostly Common Crawl byte ranges). legalize-ro checked: holds none of the four acts.
- Scratch: scratchpad/ro2 (tools/cmp_acts.py, xcheck.py, summ.py, wdiff.py).

## Next
- Retry for forms newer than the newest captures (Common Crawl's next crawl; archive.org).

## Open issues
- legislatie.just.ro unreachable directly; Common Crawl index unreachable at the time.
- WebSearch calls used: 0. No AI wrote legal text. No ISSUES.md items (the builder needed no workaround).

## Coordinator (2026-10-29)
Added the folder-level PUBLISH (autopush pushes main only when it exists); the 04:51 pass had pushed preview only.
