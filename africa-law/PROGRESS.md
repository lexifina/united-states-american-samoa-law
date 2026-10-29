# Africa (Peachjam LIIs): progress of gitlaw-africa-peachjam (handoff, 2026-10-29 00:40 UTC)

Shared adapter: `scripts/africa-law/peachjam.py` (vendored into each country folder by its fetch.py/parse.py).
How-to for the next LII countries, probe record, dates/credits rules, per-LII quirks: `scripts/africa-law/PEACHJAM.md`.
Coverage tool: `scripts/africa-law/survey.py <slug> --top 40` / `survey.py <slug> <work> ...`.

## Route
LII document pages are behind bot challenges (Cloudflare: ZambiaLII, ULII; AWS WAF: Kenya Law); never fetched.
Every expression is an archived copy (Common Crawl first, then Internet Archive `id_` through
`gitlaw_common/wayback.py`), pinned with sha256 in each country's `sources.json`. User decision (relayed by the
coordinator, 2026-10-28): "scraping wayback is fair game, dont overdo it, we need this data and it is legal". Terms and
licences (CC BY-NC 4.0; Kenya: raw documents only, NCLR licence needed for automated extraction/redistribution) are in
each corpus's decisions, README and LICENSE. Repos stay private.

## Built and published (PUBLISH written; autopush pushed main)
| Country | Acts (versions) | Commits | Pushed main | Cache |
|---|---|---|---|---|
| Zambia | Constitution (4), Data Protection Act 2021 (1), Lands Act (3), Anti-Terrorism and Non-Proliferation Act 2018 (3) | 11 + docs | 9b50a42 | 19 MB |
| Uganda | Constitution (6), Penal Code Act (8) | 14 + docs | bf8a451 | 25 MB |
| Kenya | Constitution 2010 (1), Capital Markets Act (30), Tax Procedures Act 2015 (20) | 47 + docs | 97a16fd | 117 MB |

Each: check.py 0 mismatches, `--compare` rebuild hash-identical, verification.json fidelity clean (every non-heading
character of every version is in a provision file), last version = LII listing's current expression (Zambia,
Uganda) or newest archived page with no later History entry (Kenya; its listing is behind the WAF).

## Dropped (reasons in each decisions list)
Zambia Penal Code (2 of 11 expressions archived), Insurance Premium Levy Act (2 gaps), Companies Act 2017 and
Employment Code 2019 (PDF only); Uganda Data Protection and Privacy Act (current 2023 expression not archived);
Kenya Companies Act 2015 (staged commencement), Employment Act 2007 (2 gaps), Penal Code (3 archived).

## Next steps
1. Fan out the other 9 LIIs with PEACHJAM.md section 2 (copy zambia-law's fetch.py/parse.py/acts.json).
2. Phase 2 candidates, fully archived per survey: Kenya Revenue Authority Act 1995/2 (37/37), Excise Duty Act 2015/23
   (18/18); Zambia Judiciary Administration Act 2016/23 (3/3), Local Courts Act 1966/20 (3/3); Uganda 1969/20,
   1998/15, 1998/16, decree/1971/26 (5-6 archived each; run survey.py first).
3. Optional: `"law_pages": true` to fetch amending laws' assent/publication dates (costly; rarely archived).

## Open issues
- Versions are only as fresh as the newest archived capture (Kenya Tax Procedures: captured 2026-04-19).
- Files are keyed by number: Uganda's Revised Laws 2023 renumbered sections (explained in uganda-law/README.extra.md).
- Peachjam staged commencement (no single "Commenced on" date) is detected but not modelled.
