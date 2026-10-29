# Seychelles (gitlaw-SC): progress (updated 2026-10-29 ~01:30 UTC: PUBLISH written)

Owner: gitlaw-SC. Repo lexifina/seychelles-law (private). Clone (autopush owns it): C:/Users/alany/Documents/seychelles-law.
Rules: scripts/africa-law/FANOUT.md, BRIEF.md, PEACHJAM.md.

## Finished (gitlaw-finisher-2, 2026-10-29 ~01:30 UTC): PUBLISH written; Licences held back
- **PUBLISH** covers corpus.json = Constitution (14 versions) + Civil Status Act (4 versions). The next 4-hourly
  autopush pass builds main from it (nothing pushed or committed by me; BUILD_STATUS.json updates only then).
- **Licences Act moved to corpus.d/50-licences.json, no .PUBLISH** (preview only). SeyLII's 2024-04-29 text differs
  from Act 2 of 2024 as gazetted (.tmp/gz/5c466b219bb1.txt): "fixed penalty" reads "regulation made" / "by payment"
  where the Act has "regulations made" / "on payment"; "Minister ... responsible for investment and;" where the Act has
  "Investment; and". All else the Act inserts matches. Reason in acts.json `held_back` and in the part's decisions.
  To publish it: source those words from the Gazette PDF inside parse.py (cache it via fetch.py) or wait for a corrected
  SeyLII expression, then write corpus.d/50-licences.PUBLISH.
- **Verified against Gazette text-layer PDFs** (token alignment, scratch script, not shipped): Civil Status s.2
  definitions, ss.15, 18A, 22A, Part III (ss.31-39C), Part V (ss.80-89), s.107A, amended ss.6, 20, 110-116, repeals of
  ss.7, 90-91, 117, 120, 157-161 = Act 45/2021 word for word (Gazette prints a stray "rs." in s.36; s.87(3) lacks the
  final full stop). Constitution Acts 13/2022, 14/2024 (arts. 52, 55, 59, 66A, 79, 81, Sch. 3 para. 4/4A), 6/2025: match
  (Sch. 3 para. 4(4) has a full stop the Gazette lacks). Not checked: the Constitution's other articles have no official
  consolidation to check against (e.g. art. 79(13) reads "Whereon ... one or more of them the before the day of
  election" in SeyLII, wording not touched by any recent amendment).
- **parse.py now** (steps 4-6 in its docstring): drops remark-residue lines (bare "(8)", "14.", '"interment"'),
  maps unspaced en dashes to em dashes (removed 2 typesetting-only Licences changes wrongly credited to Act 2/2024),
  and splits acts with acts.json `part` into corpus.d. Adapter issues filed: scripts/africa-law/ISSUES-seychelles.md.
  README.extra.md added (country notes in repo/README.md); repo/jurisdiction.json copied from the scaffold.
- **Local verification** (scratch repos, --docs-date 2026-10-28): main mode (GITLAW_VERIFIED_PARTS_ONLY=1) 2 acts,
  18 versions, 20 commits, 33 tags, check.py 0 mismatches, 0 trailer errors, --compare identical; full/preview mode
  3 acts, 22 versions, 0 mismatches, --compare identical. parse.py run twice: identical bytes.
- Remote main checked read-only 2026-10-29 (fetch into a scratch bare repo): 6776c39 "Seychelles: sources, before any
  law" (world-law@lexifina.com), i.e. the scaffold.
- Still open: law 2025/6 enacted/published dates empty (Gazette PDF says assent 4 July 2025, published 4 July 2025;
  fill only if parse.py reads that PDF from cache). Phase 2 candidates below unchanged.

## Earlier status (handoff 00:41 UTC, kept for history)

## Built (corpus.json, 2026-10-29 00:30; test build .tmp-build: 24 commits, check.py 0 mismatches, 0 future)
| Act | SeyLII work | Versions | Notes |
|---|---|---|---|
| Constitution of 1993 | si/1993/38 | 14 (1993-06-21 to 2025-07-04) | all 15 SeyLII expressions archived; 2020-06-01 left out on purpose (acts.json "skip": separately keyed 2020 consolidation, 97 articles reworded, reverted in 2022). Every change credited (First to Twelfth Amendment). |
| Civil Status Act | 1883/4 | 4 (2015-12-31 to 2022-11-01) | 1 of 41 changes on 2021-07-01 uncredited |
| Licences Act, 2010 | 2010/23 | 4 (2017-07-05 to 2024-04-29) | all credited |

Verified: the Constitution's last 3 amendments against the official Gazette text-layer PDFs (gazette.sc: Act 13/2022,
Act 14/2024, Act 6/2025, in .tmp/gz): no "Defence Forces of Seychelles" left after 2022; arts. 113 and 114 carry the
2025 wording. gazette.sc Acts lists 2020-2026 show no Constitution, Civil Status or Licences amendment after the last
archived expression (title search only; Statute Law Revision / miscellaneous acts not checked).

## Sources (probed 2026-10-28)
- **SeyLII left Peachjam in 2026** (now Lexum Decisia/Norma, `/seylii/en/nav.do`); its Peachjam pages exist only in
  the Internet Archive (terms archived 2026-03-01: CC BY-NC 4.0 crediting SeyLII; scraping prohibited). No SeyLII
  document page fetched directly. robots: Content-Signal ai-train=no; ClaudeBot etc. disallowed.
- **SeyLII renumbered works in 2024/25:** Constitution is si/1993/38; /akn/sc/act/1994/7 was the Constitution in
  2023-24 captures but is the First Amendment Act in 2025 ones (likewise 1996/14). fetch.py accepts an amending law's
  page only if its title matches the History link title.
- **Common Crawl index** (index.commoncrawl.org) did not connect from this machine (ports 443 and 80); all pages via
  archive.org through gitlaw_common/wayback.py.
- **Official Gazette** www.gazette.sc: open, Drupal, PDFs with text layer, Acts/SIs/Gazettes 2020-2026 (`/v/act/<y>?page=N`).
- **National Assembly** nationalassembly.sc: HTTP 500 on 2026-10-28.

## Files
- fetch.py (wayback.py-based; same sources.json + cache layout as peachjam.fetch; `--probe WORK` lists History;
  acts.json `skip`) - the adapter can adopt the wayback-based fetch, the title check and `skip`.
- parse.py: peachjam.parse + post(): skip reasons, law dates from History tab when coverpage absent, Constitution kind=law.
- Cache: .cache (archive.org CDX + pages for 3 acts and 19 laws, plus probes of ~14 other works); .tmp/gz gazette lists/PDFs.

## Next steps
1. Check Civil Status and Licences final text against gazette.sc amendment PDFs (Act 45/2021, Act 2/2024 cached in
   .tmp/gz), then write PUBLISH.
2. Law 2025/6 (Twelfth Amendment) has no archived SeyLII page: its enacted/published dates are empty; fill from the
   Gazette PDF (assent 4 July 2025) only if parse.py reads that PDF from cache.
3. Phase 2 candidates whose latest SeyLII expression is archived: Trusts Act 2021 (but Act 14 of 2026 amends it, not
   archived), Financial Consumer Protection Act 2022, Public Enterprises Act 2023. Not complete in the archive:
   Penal Code (2024-10-01, 2025-12-23 missing), Employment Act (2022, 2023 missing), IBC Act 2016, Pension Fund Act, VAT Act.
4. README (repo/README.md, generated by peachjam.write_docs) should name the left-out 2020 consolidation (it is in decisions).

## Open issues
- Common Crawl index unreachable from this machine.
- archive.org throttling (wayback.py rate fell to 0.3/s).
