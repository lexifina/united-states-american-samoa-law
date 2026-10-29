# Brunei (BN) git-for-law: progress

Agent gitlaw-BN, 2026-10-28/29. Stopped at the coordinator's wind-down (00:44 UTC). **No corpus.json yet, no PUBLISH.**

## STOPPED 2026-10-29 (gitlaw-BN-2): the remote is no longer the scaffold
`git ls-remote` showed two branches, neither the scaffold commit 2422157:
- `main` = d8e7bb6 "Brunei: paused, not yet law" (In-force: 2026-10-28; README only). Its README says another
  session paused Brunei **at the terms gate**: the AGC Terms of Use (www.agc.gov.bn/terms_use/) s. 2.2 forbid
  reproducing or re-using site material without the Government's express written permission, and the Copyright
  Order, 1999 (S 14/2000) s. 168 gives His Majesty copyright in every Act and every s. 83(3) Order (50 years from assent).
- `wip` = a1e7165 "Work in progress: scripts/brunei-law at 2026-10-29T00:38:43Z" (wip/PROGRESS.md, fetch.py, sources.json).
No parse.py was written and nothing was built. Needs a coordinator decision: does the terms-gate pause stand?
If it does, the cached PDFs should not be published.

## Checklist
- [x] lexifina/brunei-law main is still only the scaffold: one commit 2422157 "Brunei: sources, before any law". Cloned read-only to C:/Users/alany/Documents/brunei-law (untouched; autopush owns it).
- [x] Probe of the AGC portal (below)
- [x] fetch.py + sources.json; every Phase 1 PDF cached (18 requests, ~22 MB, .cache/requests.jsonl)
- [x] Text layers checked with PyMuPDF: all 15 PDFs have one (no OCR needed); dumps in .tmp-probe/ (scratch)
- [ ] parse.py -> corpus.json (NEXT STEP)
- [ ] test build in .tmp-build, check.py 0 mismatches, --compare determinism
- [ ] repo/README.md (fold scaffold README + SOURCES.md), repo/jurisdiction.json (build -> real status), PUBLISH

## Source probe (www.agc.gov.bn, Attorney General's Chambers)
- Site is WordPress (rebuilt 2026). robots.txt: 404 (none). Old `AGC Site Pages/*.aspx` URLs are dead (404).
- Index: `https://www.agc.gov.bn/services_brulaw-2/?agc_letter=<A-Z>` lists every law with status chip.
- Each law has a page `https://www.agc.gov.bn/documents/<slug>/` with: the latest PDF, an **Amendment** table (citation, S number, commencement date, PDF link), a Subsidiary Legislation table, and a **Version** list of every revised edition PDF. `?agc_tab=sl` returns the same page.
- Licence: no open licence stated on the site; record "Attorney General's Chambers, Brunei Darussalam" attribution and that the text is official legislation. Still to check: any copyright/terms page.
- History support: dated revised editions (point-in-time snapshots) + amending Orders with commencement dates on the page. The scaffold's "pit: no" is too pessimistic.

## Phase 1 acts and what is cached (sources.json)
1. **Constitution of Brunei Darussalam (CONST. I, S 97/1959)**: editions 1984, 2004, 2011, 2022 (B.L.R.O. 2/2022); Orders S 22/2021 (commenced 4 Sep 2021 per AGC page) and S 42/2024 (21 Oct 2024). The 2022 Ed. cover lists every amending instrument per edition: 1984 Ed. after S 121/1961, E 2/1963, E 4/1964, E 6/1967, S 59/1970, S 7/1983, S 32/1983, S 8/1984, S 11/1984; 2004 Ed. after S 20/1985, S 32/2004, S 47/2004, S 65/2004, S 69/2004; 2011 Ed. after S 14/2006, S 15/2006; 2022 Ed. after S 22/2021. S 42/2024 is after the 2022 Ed., so today's text = 2022 Ed. + S 42/2024 replayed (must be applied by parse.py from the Order's text).
2. **Penal Code (Cap. 22)**: editions 1984, 2001, 2016, 2021 (5/2021); Orders S 61/2017 (24 Jul 2017), S 60/2018 (30 Oct 2018), S 71/2018 (17 Dec 2018), S 38/2021 (AGC page says "3 October 2011": an obvious typo; take the date from the Order itself). Also N 1 (s. 277A prescribed period, 4 Aug 2009), not fetched.
3. **Personal Data Protection Order, 2025 (S 1/2025)**: one PDF, as enacted, no amendments. Commencement date still to read from the Order / a commencement notification (not on the AGC page).

## Plan for parse.py (next step)
- Split each edition into units by Article/section headings (Constitution: `art-NNN[-a]`, plus Parts as headings; Penal Code: `sec-NNN[-a]`). Strip running headers ("LAWS OF BRUNEI", page numbers, "B.L.R.O. x/yyyy", "CONST. I", "CAP. 22").
- Versions: oldest edition credited to the publisher ("oldest version available", earlier_laws = the pre-1984 instruments above). Each later edition's changed units are credited only where the edition's own margin/source notes name the amending S/E number; dates from the commencement dates in those instruments (or in the AGC Amendment table). Where one unit was changed by more than one instrument between editions, put it at the last instrument's date with all named, and say so in decisions; unexplained diffs go to the publisher ("unexplained", dated at the edition date). Revised-edition editorial changes: credit only if the edition says so.
- Post-edition Orders (Constitution S 42/2024; Penal Code changes after the 2016 Ed. are already in the 2021 Ed.) are replayed and checked against the next edition where one exists.
- Default in-force rule: still to source (Interpretation and General Clauses Act, Cap. 4: commencement on publication in the Gazette unless the law says otherwise). Verify the section number from the AGC PDF before citing.

## Open issues
- None filed against the shared builder.
- The C:/Users/alany/Documents/brunei-law clone holds the untouched scaffold; the builder replaces it on first build.

## WebSearch used: 0 of 3.
