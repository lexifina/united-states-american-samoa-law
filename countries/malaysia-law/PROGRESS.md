# gitlaw-MY: Malaysia law history

Slug `malaysia`, repo `lexifina/malaysia-law` (PRIVATE). Scaffold checked 2026-10-29 13:10 UTC: only `main`
(ccd3837 "Malaysia: sources, before any law"). Re-checked before PUBLISH (13:45 UTC): `main` unchanged, plus `wip` and
`preview`, which hold only snapshots/builds of this folder. Rules: scripts/world-law/FORK.md -> WAVE.md ->
africa-law/FANOUT.md -> south-america-law/BRIEF.md. Never commit/push. WebSearch used: 0 of 4.

## Source (lom.agc.gov.my, Attorney General's Chambers, direct; no bot challenge)
- robots.txt: HTTP 500. tnc.php: "Copyright 2023 by Attorney General's Chambers, Malaysia, all rights reserved";
  free download; online reprints not the s. 14 Revision of Laws Act reprint; print-out not a copy of the Gazette.
- List endpoints (POST, DataTables body, AES-GCM encoded with the page's published key; fetch.decode):
  `json-amendment-fc-2024.php` (FC amending laws), `json-reprint-fc-2024.php` (FC reprints),
  `json-amendment-2024.php` (414 amending Acts, with RA/publication/commencement), `json-updated-2024.php` (888 updated
  principal Act reprints, with PDF paths). Search parameters are ignored: fetch everything with length=2000 (~30 s).
- `act-detail.php?...` answers "Invalid request" unless reached through its processFile.php token link.
- FC English reprint PDFs: LOM/EN/Federal Constitution (Reprint 2020).pdf; outputaktap/2630992_BI/REPRINT 2025 - BI
  WJW25<U+F022>0908 Teks B5.pdf (the file name has a private-use character; fetch.get percent-encodes it).
- PDPA Act 709: updated "Act 709 (Reprint 2026).pdf" as at 15-09-2026 (outputaktap/3301061_BI/); A1727 RA 09/10/2024,
  pub 17/10/2024, comm 24/12/2024 [P.U.(B) 522/2024].
- Penal Code Act 574: updated reprint as at 04-07-2023 (outputaktap/1841145_BI/WJW23<U+F022>1011 Act 574.pdf); later
  amending Acts A1691 (in force 10/9/2025), A1721 (30/10/2024), A1750 (11/07/2025).
- Interpretation Acts 1948 and 1967 [Act 388] s. 19(1) read from outputaktap/16312_BI/Act 388 (Muktamad).pdf.

## Done
- [x] Federal Constitution: 5 versions (2020-10-15 reprint, 2021-12-15 A1603 s.3 + A1656, 2022-02-11 A1642,
      2022-10-05 A1663, 2025-11-30 reprint), 279 units (articles, part/chapter headings, 13 schedules).
- [x] corpus.json, repo/ (README, LICENSE, jurisdiction.json), verify.py (4,558 checks, 0 misses, 2 expected).
- [x] Scratch build /tmp/my-build (docs-date 2026-10-29): 6 commits, 9 tags; check.py 0 mismatches / 0 trailer errors;
      --compare main_identical true.
- [x] PUBLISH written.

## Phase 2
- [x] PDPA (Act 709) -> corpus.d/20-pdpa.json (pdpa.py), 4 versions: 2013-11-15 as enacted (First Reprint as at
      2023-07-01, sections amended NIL; "Act 709 ori.pdf" answers HTTP 500), A1727 on 2025-01-01 (ss. 67, 136),
      2025-04-01 (57 provisions: general amendment + ss. 4, 5, 9, 21, 48, 129), 2025-06-01 (Div 1A, 12A, 12B, 43A);
      equals Reprint as at 2026-09-15 (asserted). verify.py 2,224 checks 0 misses. Scratch build /tmp/my-build3:
      10 commits, check.py 0 mismatches/0 trailer errors, --compare identical. corpus.d/20-pdpa.PUBLISH written.
- corpus.json (Constitution) unchanged: sha256 f100d134...; its source request count is a fixed time window
  (parse.FC_WINDOW) so later fetches never change it. layout.parse(pdf, 'sec') for Acts (Divisions, NOTE drop).
- FETCH RULE: sources.json lists every URL; `python -X utf8 fetch.py` fetches them all (3 threads, <=3 req/s/host).
  Bulk fetch started 14:10 UTC for the Penal Code files.
- [x] Penal Code (Act 574) -> corpus.d/30-penal-code.json (penal.py, amending.py), 4 versions: updated Reprint as at
      2023-07-04 (oldest available, first_law null), A1721 (2024-10-30: new ss. 424A-D), A1750 (2025-07-11: new
      ss. 507B-G), A1691 (2025-09-10: ss. 305, 306 substituted, s. 309 deleted), applied from each Act's own PDF by
      its stated operations; days from the portal's amending-Act list. 629 units (sections, chapter-NN, xh-NNN
      cross-headings; layout.parse(..., chapters=True)). verify.py 3,186 checks 0 misses. Scratch build
      /tmp/my-build5 (all three acts): 14 commits, 22 tags, check.py 0 mismatches / 0 trailer errors, --compare
      identical. NO 30-penal-code.PUBLISH: no English consolidation after July 2023 is online to check today's text
      against (PUBLISH rule); the coordinator can decide.
- Constitution corpus.json and 20-pdpa.json regenerate byte-identical after every layout change (checked).

## Scripts
fetch.py (curl cache, decode), layout.py (reprint PDF -> provisions), parse.py (-> corpus.json), verify.py.
Run: `python -X utf8 parse.py; python -X utf8 verify.py`, then build.py/check.py into a scratch dir (not the clone).
