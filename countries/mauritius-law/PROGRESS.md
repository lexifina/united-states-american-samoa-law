# Mauritius: progress

No PROGRESS.md existed when the agent was stopped at the 2026-10-29 wind-down; this file was started by gitlaw-repair
(2026-10-29) from the code, the cache and BUILD_STATUS.json.

## Checklist
- [x] Sources: Attorney General's Office Revised Laws (Constitution PDF, text layer); National Assembly "Acts as passed
      and gazetted" table and Act PDFs (2010-2026); Wayback captures of the AG site. Cache: 273 files in `.cache/`.
- [x] Constitution: 4 versions (2011-12-12 AG consolidation, oldest version available; 2014-07-17 Act 3/2014, no words;
      2015-12-10 Act 30/2015 s. 8; 2016-12-17 Acts 28 and 30/2016 ss. 15, 16). 136 units.
- [x] Build error fixed (2026-10-29): the 04:51 UTC autopush pass failed with "earlier law 'Act 48 of 1991' is not a law
      key" (28 of them). parse.py now registers each law named in the AG amendment notes as a law key
      (`act-1991-48`, `gn-1992-139`, ...; label only, no invented titles or dates) and lists the keys in `earlier_laws`.
- [x] Text fix (2026-10-29): revised.py did not drop inserted-page running heads ("CON — 66 (1)", "[Issue 6] CON — 66 (2)",
      "continued on page CON — 67"). Result: "CON — 66 (1)" sat inside s. 91A(13)(a), and s. 92(3) was swallowed into a
      bracketed note and lost. Both fixed in the running-head filter; s. 91A and s. 92 are the only units that changed.
- [x] Local verification (2026-10-29, scratch repo, --docs-date 2026-10-28): 5 commits, 8 tags, check.py 0 mismatches,
      0 trailer errors; --compare rebuild identical.
- [x] Covid-19 Act check (open at wind-down): the Covid-19 (Miscellaneous Provisions) Act 2020 (Act 1 of 2020; table
      in-force "*", "See Section 58") never mentions the Constitution; s. 58 commences only its own sections. It does
      not amend the Constitution. A scan of all 251 cached Act PDFs 2012-2026 finds no Act that amends the
      Constitution other than those replayed and Act 10 of 2025 (other hits only cite sections of it).
- [ ] Act 10 of 2025 (repeals s. 7(2)): no commencement section; the National Assembly table marks it "*" ("on a date
      to be fixed by Proclamation"). No Proclamation found in the cache, so it is not applied (see decisions). Needs
      the Government Gazette Proclamation, if any.
- [x] repo/README.md, repo/LICENSE and repo/jurisdiction.json written (gitlaw-docs, 2026-10-29), folding in the
      scaffold's README/SOURCES facts. README says s. 7 is unconfirmed until the Act 10/2025 Proclamation is found, and
      that s. 5(3A) is printed though the AG's editorial note says the Privy Council (State v Khoyratty) declared it void.
      Scratch rebuild: check.py 0 mismatches, 0 trailer errors; --compare identical (tip 5f3271d). PUBLISH still unwritten.
- [ ] Phase 1 core acts (Civil Code, Criminal Code / Data Protection Act): not started in corpus (Criminal Code and
      a DPA page are cached / in .tmp).

## PUBLISH
Not written. Remote main is still the scaffold ("sources, before any law", a738f21). Reasons: today's s. 7 depends on
the unresolved Act 10 of 2025 commencement; no official consolidation of today's text exists (the AG text stops at
Act 35 of 2011); repo/ has no README yet.

## Pushes
None by agents (autopush owns pushing; 4-hourly passes since 2026-10-29 00:51 UTC).
