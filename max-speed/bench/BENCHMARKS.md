# Git for law: ways to get more data faster, tested and measured (2026-10-29)

The user asked for every approach to be tested and quantified. Each test below has its script and raw results in this
folder (`bench_*.py` writes `bench_*.json`). Tests used small samples, under each source's shared adaptive rate
(`gitlaw_common/wayback.py`). Robots.txt `Disallow` and stated `Crawl-delay` were obeyed; no bot challenge was touched.

## Headline

1. **Fetching isn't the bottleneck; agents are.** Agents fetched 0.1–10 requests per agent-minute. A script fetches
   1.4–30.8 pages a second from Common Crawl, 3.4 a second from a live official site, or 779 versions a second from an
   official API.
2. **Best source, by a long way: official bulk dumps and APIs.** Spain's BOE API returns an act's whole history in one
   request (269 versions per request on average). Lovdata gave all 754 Norwegian laws in 1 request.
3. **Common Crawl is the fast fallback for blocked or slow sites.** It is about 120 times archive.org's speed, and has
   captures of 152 of the 159 official law sites of countries not yet on main.
4. **Sonnet does the same parsing work as Opus,** with the same correctness and in 61% of the time.
5. **Unverified `preview` text has real errors.** A Sonnet verifier found and fixed 35 bad provisions out of 267 in Sri
   Lanka, and 1 out of 224 in Tuvalu, in 5–8 minutes each.

## 1. Fetch methods, same official pages (`bench_fetch.py`, `bench_bulk.py`)

| Method | Threads | Requests | Success | Time | Rate |
|---|---|---|---|---|---|
| Common Crawl byte-range (`cc_get`) | 1 | 20 | 20 | 14.2 s | 1.41 pages/s |
| Common Crawl byte-range | 8 | 60 | 60 | 5.2 s | 11.6 pages/s |
| Common Crawl byte-range | 16 | 60 | 60 | 2.0 s | **30.8 pages/s** (4.2 MB/s) |
| archive.org (`wayback.get`, shared limiter) | 1 | 10 | 10 | 36.4 s | 0.27 pages/s |
| archive.org | 8 | 20 | 20 | 79.5 s | 0.25 pages/s (threads don't help: one machine-wide limit) |
| Live official site via `host_get` (Spain BOE HTML) | 1 | 8 | 8 | 10.2 s | 0.78 pages/s |
| Live, via `host_get` | 4 | 16 | 16 | 13.1 s | 1.22 pages/s |
| Live, via `host_get` | 12 | 24 | 24 | 7.2 s | 3.35 pages/s |
| Live, via `host_get` (Lithuania e-seimas) | 1–12 | 85 | **0** | – | Cloudflare 403 challenge: live is impossible, Common Crawl is the only fast route |
| **Official open-data API (Spain BOE, whole history per act)** | 1 | 12 | 12 | 29.9 s | 134 versions/s |
| **Official open-data API (Spain BOE)** | 6 | 24 | 24 | 8.3 s | **779 versions/s**, 269 versions per request |
| **Official bulk dump (Norway Lovdata)** | 1 | 1 | 1 | 2.7 s | **754 laws in one request** (5.8 MB) |
| Official API (Austria RIS OGD) | 1 | 1 | 1 | 1.2 s | 100 documents per request |

Index lookups:
- **Common Crawl:** 2.4 s per site (median of 159 hosts). An e-seimas legal-act prefix gave 4,662 captures in 1.4 s.
- **archive.org CDX:** the same prefix gave 218,364 captures in 117 s.

The archive.org shared limiter sat at 2.2 requests/s, with 714 of 3,883 requests (18%) answered 429.

## 2. Agents' real fetch rate (request logs, this session's agents)

| Country | Requests | Agent minutes | Requests per agent-minute | Source |
|---|---|---|---|---|
| Norway | 6 | 54 | 0.1 | Lovdata bulk dump: the whole corpus in 6 requests |
| Palau | 73 | 56 | 1.3 | Code Commission Drive PDFs |
| Oman | 28 | 19 | 1.5 | qanoon.om |
| Malaysia (phase 2) | 34 | 17 | 2.0 | AGC portal PDFs |
| Moldova | 85 | 34 | 2.5 | archive.org |
| Micronesia | 105 | 40 | 2.6 | archive.org (robots crawl-delay 30 s on the live site) |
| Montenegro | 38 | 14 | 2.7 | Official Gazette PDFs |
| New Zealand | 373 | 87 | 4.3 | archive.org (live site has an AWS WAF challenge) |
| Lithuania | 96 | 19 | 5.1 | archive.org (live site has a Cloudflare challenge) |
| Latvia | 302 | 29 | 10.3 | archive.org (likumi.lv refuses HTTPS from this machine) |

All agents together logged about 1,660 requests in 6 hours, or about 5 a minute. Fetching only dominates where a site
forces archive.org; elsewhere, agent time goes on parsing and checking.

## 3. Output per agent (completion reports; tokens and wall time)

| Country | Versions built | Tokens | Wall time | Versions per 100k tokens | On main |
|---|---|---|---|---|---|
| Latvia | 103 (Satversme 17, Criminal Law 83, data law 3) | 373k | 29 min | 27.6 | yes |
| New Zealand | 91 (4 acts) | 330k | 87 min | 27.6 | yes |
| Norway | 42 (4 acts) | 505k | 54 min | 8.3 | yes |
| Palau | 17 | 383k | 56 min | 4.4 | yes |
| Oman | 10 | 239k | 19 min | 4.2 | held (Arabic, out of scope) |
| Lithuania | 12 | 338k (resumed run) | 19 min | 3.6 | yes |
| North Macedonia | 12 | 340k | 15 min (resumed run) | 3.5 | yes |
| Micronesia | 10 | 337k | 40 min | 3.0 | yes (Constitution held to preview) |
| Malaysia | 5 + 8 | 336k + 444k | – + 17 min | 1.7 | yes (Penal Code awaiting a decision) |
| Montenegro | 4 | 295k | 14 min | 1.4 | yes |
| Moldova | 3 | 306k | 34 min | 1.0 | yes |

The yield depends on the source, not the agent: sites that publish dated versions or amendment notes (likumi.lv notes,
NZ "as at" versions, Lovdata) give 8–28 versions per 100k tokens. Gazette-only countries give 1–4.

## 4. Model choice: the same parsing task three times (`modeltest/`)

The task: turn the BOE XML of the Spanish Constitution into a corpus, build it and pass check.py. The right answer is 5
versions (1978, 1992, 2011, 2024, 2026) and 210 provisions.

| Model | Time | Tokens | Tool calls | Result |
|---|---|---|---|---|
| Sonnet | **59 s** | 64.8k | 11 | 5 versions, 210 units, 0 mismatches |
| Haiku | 76 s | 71.7k | 8 | 5 versions, 210 units, 0 mismatches |
| Opus | 97 s | 75.3k | 11 | 5 versions, 210 units, 0 mismatches |

Sonnet's and Opus's text agree in 209 of 210 provisions, ignoring heading marks and whitespace; one paragraph break
differs. All three got the task right. On a well-specified task the cheaper models match Opus and use the usage limit
more slowly. Hard sourcing and judgement calls weren't tested.

## 5. Verifier sweep: taking `preview` countries to `main` (Sonnet)

| Country | Provisions compared | Errors found and fixed | Tokens | Time | PUBLISH |
|---|---|---|---|---|---|
| Sri Lanka | 267 | **35**: lost clause numbers, ~40 line-end hyphen splits, chapter headings stuck to units, page-break cuts, a missing schedule row | 127k | 7.3 min | no: 21st Amendment transitional provisions not yet built |
| Tuvalu | 224 | 1: a schedule table row with its columns interleaved | 87k | 5.5 min | no: main holds a "Paused: copyright" commit; the user decides |

32 countries are on `preview` without PUBLISH (258 versions), 8 of them held as right-to-left or CJK. Unverified text
can carry about 1 error per 8 provisions, so the sweep is a quality fix as well as a route to main.

## 6. Coverage across countries not yet on main (`bench_coverage.py`)

- **Official sources in register.json:** 223. For countries not yet on main, 32 offer an API, 50 give point-in-time
  versions and 23 give amendment data.
- **Common Crawl, newest 3 crawls:** 152 of 159 official law hosts have captures, 114 have at least 100, and 68 have
  at least 1,000. Lookups took 131 s in total, 6 at a time.
- **Shared platforms named in the register:** XML 43, API 39, LII 30, ELI 22, Akoma Ntoso 17, JSON 15, Laws.Africa 13,
  SPARQL 5, PacLII 4. One parser per platform would cover many countries.

## 7. Common Crawl history depth (`bench_cc_depth.py`)

Prefix lookups across the 24 newest crawls (2024–2026):

| Page | Captures (200) |
|---|---|
| Latvia Satversme | 10, over 3 years |
| Spain Constitution | 52, including dated `&p=` versions |
| New Zealand Constitution Act | redirects only |

An exact-URL match found nothing, because of URL forms; use `match='prefix'`. A bug turned up here and was fixed: older
crawls sometimes return an XML error page, which crashed `cc_captures`. `wayback._cc_captures_files` now skips those
blocks. The 128-crawl result is in `bench_cc_depth.json` when the run finishes.

## 8. Hosted reconstructed archives (legalize.dev)

| Repo | Metadata clone | Full clone | Commits | Law files | Real history? |
|---|---|---|---|---|---|
| legalize-lt | 37 s | 95 s | 73,023 | 16,174 | **No**: starts 2026-09-24, and the Lithuania agent found its data-protection text differs from the official one |
| legalize-lv | 15 s | 40 s | 16,511 | 16,307 | **No**: starts 2026-10-21 (a snapshot) |

Fast to get and broad, but for these two countries it gives today's text only, and not always correctly. Other repos
(legalize-be with 40k commits of Justel versions, legalize-ar) look deeper. Check each one's first commits.

## 9. Not testable here, or tested negative

- **Cloud agents** (`isolation: remote`): the test agent reported Windows, Git Bash and this machine's git credentials.
  It ran locally, so there is no extra RAM or network from that route here.
- **Asking publishers for keys or permission:** sent and answered in days, not minutes. The Marshall Islands request
  is drafted (`scripts/marshall-islands-law/PERMISSION_REQUEST.md`) and not yet sent.
- **Spreading requests over extra IP addresses to beat archive.org's limit:** not tested on purpose. It evades a
  nonprofit's capacity limit, and approaches 1–3 make it unnecessary.

## What to do with this

1. Find official bulk dumps and APIs first. Use Common Crawl (16 threads) for blocked or slow sites, and archive.org last.
2. Download from a script in the background and parse from the cache. Agents should never fetch interactively.
3. Use Sonnet for fetch, parse and verify work, keeping Opus for hard sourcing and judgement.
4. Run a verifier sweep over the 24 in-scope `preview` countries.
5. Write one parser per shared platform (ELI, Akoma Ntoso/Laws.Africa, PacLII-style, Commonwealth revised editions).
