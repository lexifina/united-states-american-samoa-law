# Arizona (www.azleg.gov): routes faster than Crawl-delay 120 (2026-10-30)

Corpus `us/arizona/statutes` (lexifina/united-states-arizona-law). robots.txt on www.azleg.gov: `User-agent: *`
Crawl-delay 120, no AI-bot rules. Every Constitution and A.R.S. section is its own page, so the live route is one
section per 121 s.

## Tried

| Route | Result |
| --- | --- |
| Official bulk (whole-title page, export, API) | none: arsDetail lists sections only; apps.azleg.gov robots `Disallow: /`; data.az.gov does not answer; AZGeo is GIS only; robotsitemap.xml is a 28-URL legacy list |
| Common Crawl, all 2018-2026 crawls (shared CC limiter, sequential) | distinct pages: const 54, ars/13 557, ars/33 191, ars/10 564. Captured after the 2026 regeneration (2026-09-08): 6 / 81 / 29 / 124 |
| Internet Archive since 2024 (one CDX request per prefix, wayback.py shared limiter, machine rate ~0.65 req/s) | distinct pages: const 286, ars/13 1,069, ars/33 602, ars/10 1,072. After 2026-09-08: 13 / 66 / 30 / 13 |
| Archived 2026 session laws (legtext/57leg/2R/laws) | 163 of 263 chapters readable from IA/CC; 100 queued live |

## Acceptance rules (a copy is used only if it must equal today's text)

- Constitution: only the voters amend it; the Nov 2024 measures took effect at the canvass, the next vote is 3 Nov
  2026. Copies captured on or after 2025-01-15 are accepted.
- A.R.S.: pages carry `<!Creation Date: MM/DD/YY>`; the whole compilation was regenerated 09/08/26 after the 2026
  session. A copy with that creation date is the live page's text. A copy of the 2025 generation (Aug 2025 on) is
  accepted only if no 2026 session law names the section anywhere in its text (list incomplete until the 100 live
  chapters arrive, so none yet).
- Same section: URL path and the page's own heading. Every 15th eligible page is held for the live fetcher, so its
  archive copy can be compared with the live page.
- Provenance per page kept privately (route, capture timestamp, archive URL, sha256).

## Measured

| Part | Pages | From archives | Live left | Live time before | Live time after |
| --- | ---: | ---: | ---: | ---: | ---: |
| Constitution | 323 | 209 (194 IA, 15 CC) | 114 (92 no copy + 22 held) | 10.9 h | 3.8 h (2.9x) |
| A.R.S. Title 13 | 985 | 122 (post-update generation) | 863 | 33.1 h | 29.0 h now; ~533 more candidates wait on the session-law list (+3.4 h live for the laws) |

Archive throughput for this corpus: ~3-6 pages a minute (the machine-wide IA rate was throttled to 0.65 req/s by
other agents), i.e. 6-12x the live 0.5 pages a minute.

## Verdict

No official bulk route. Archive copies help most where the text cannot have changed since the capture (the
Constitution; A.R.S. pages of the current generation). For older A.R.S. copies the session-law list is the gate;
it costs ~100 live requests once and can unlock several hundred sections per title. The live cross-check of the held
pages is pending and will be appended.

## Lesson

Two acceptance runs that each rewrote one provenance JSON from memory lost the other's entries; re-read before
every write (and the provenance was recoverable by matching page bytes to the archive responses).

## Update 12:00 UTC

- Live cross-check of the Constitution: 20 pages held both live and from an eligible archive copy, 20 identical
  (whitespace-normalised text, markup and the `<!...>` header stripped). 4 of the 22 held pages had no eligible copy.
- Each A.R.S. title is regenerated on its own day (2026: Title 13 09/08/26, Title 33 09/09/26; 2025: 09/19/25,
  09/20/25), and pages the regeneration leaves unchanged keep their older creation date. Rule now: current if
  created Aug-Dec 2026, or captured on a day after the title's 2026 regeneration.
- Archive yield with the corrected rule: Title 13 127/985, Title 33 47/544, Title 10 119/595 (post-update only);
  2025-generation copies (526 / 166 / 521) still wait on the 2026 session-law list (184 of 263 chapters read from
  archives with CC at 12 req/s; 85 live).
- Coordinator gave this corpus 12 Common Crawl req/s once ACT and WA finished (federal 8; machine 20).
