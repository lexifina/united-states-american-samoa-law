# Malawi (MalawiLII via Wayback): progress of gitlaw-MW

Rules: `scripts/africa-law/FANOUT.md`, `scripts/africa-law/BRIEF.md`, `scripts/south-america-law/BRIEF.md`.
Adapter: `scripts/africa-law/peachjam.py` (read-only; fetch.py/parse.py vendor a copy here). Repo lexifina/malawi-law
(private); autopush builds and pushes; nothing is pushed by hand.

## Sources (probed 2026-10-28, all through archive.org)
- MalawiLII terms (Wayback 20261012174416): hosted by the Gender and Justice Unit; content CC BY-NC 4.0, credit
  MalawiLII; "Scraping and bulk downloading from this website is strictly prohibited". robots.txt (Wayback
  20261012174559): Allow /, Crawl-delay 5, Content-Signal ai-train=no, ai-input=no. So no MalawiLII page is fetched,
  not even the listing (`"listing": false`); every page is an archive.org `id_` capture.
- Wayback CDX of malawilii.org/akn/mw/act/: 807 works archived, nearly all only at their 2014-12-31 expression (the
  2014 revised edition). Works with 2+ archived expressions include the Constitution 1994/20 (2014-12-31,
  2017-12-31, 2020-11-03), Land Act 2016/16, Courts Act 1958/1, Electoral Commission Act 1998/11, Parliamentary and
  Presidential Elections Act 1993/31, Presidential, Parliamentary and Local Government Elections Act 2023/10.
  Penal Code 1929/22, Employment Act 2000/6: only 2014-12-31 archived.
- Titles from the archived listing https://malawilii.org/legislation/ (Wayback 20231004172807), in .tmp/listing2023.txt.

## Archive access (coordinator 21:45Z: FAST ARCHIVE ACCESS)
- lii.py replaces peachjam.fetch: Common Crawl first, archive.org via gitlaw_common/wayback.py for gaps; pins in
  sources.json in peachjam.parse's shape (CC key `cc:<warc>:<offset>:<length>`). index.commoncrawl.org times out from
  this machine (21:55-22:10Z); lii.cc_records then falls back to archive.org alone.
- listing.py: current-expression check from archived /legislation/ listing pages (JSON rows `"date", "work_frbr_uri"`).

## Survey (History tab of each act's newest archived expression)
- Constitution 1994/20: LII lists 2017-12-31 (consolidation, Fifth Revised Edition L.R.O. 1/2018) and 2020-11-03
  (Constitution (Amendment) (No.5) Act, 2020); 2014-12-31 also archived (an earlier MalawiLII expression no longer
  listed). All archived: TAKE.
- Electoral Commission Act 1998/11: LII lists 2014-12-31 (consolidation) and 2018-11-02 (Electoral Commission
  (Amendment) Act, 2017); both archived: TAKE.
- Land Act 2016/16: LII has 2022-07-01 (Land (Amendment) Act 2022), not archived: not taken (today's text unknown).
- Courts Act 1958/1: LII has 2026-02-20 (Courts (Schedule) (Replacement) Notice 2026), not archived: not taken.

## Checklist (handoff, 2026-10-29 00:44 UTC)
- [x] Probe terms, robots, Wayback coverage; survey (above)
- [x] lii.py (CC first, archive.org via wayback.py; CC index unreachable all run), listing.py (archived listing check)
- [x] fetch: Constitution 2017-12-31 + 2020-11-03; Electoral Commission Act 2014-12-31 + 2018-11-02; PPLGE Act 2023
      2025-09-05 only (2023-02-21 copies are PDF-only). All in .cache (archive.org); sources.json pinned.
- [x] corpus.json written (3 acts, 5 versions, laws act-2018-32, act-2020-13, act-2025-32); listing check: all 3 current
      (archived listings 2026-04-19..06-10); fidelity 0 text outside units.
- [x] PUBLISH written 2026-10-29 (gitlaw-finisher). Local verification of the 00:43Z corpus (CADENCE CHANGE: no
      pushes; next autopush pass publishes): build into an empty scratch repo (docs-date 2026-10-28) -> 5 commits,
      7 tags, main b66c56c; check.py 0 mismatches, 0 trailer errors, 0 backwards/future; --compare rebuild identical.
      Currency: listing_check.json all 3 ok; the newest cached expression pages' own History tabs list no later
      expression (Constitution capture 20260807, EC Act 20260215, PPLGE 20260517). A fresh archive.org CDX query
      for newer expressions timed out (archive.org 429) and index.commoncrawl.org still times out, so nothing newer
      than Aug 2026 was checked. Remote main was still the scaffold (ccc439d) when PUBLISH was written.
- Next: retry Common Crawl (index.commoncrawl.org) to survey Penal Code 1929/22, Employment Act 2000/6, Companies Act
  2013/15 for later expressions.

## Open issues
- scripts/africa-law/ISSUES-malawi.md: 3 adapter issues, worked around locally (parse.py, lii.py, acts.json skip).
- index.commoncrawl.org connection timeouts from this machine (21:55Z-00:40Z).
