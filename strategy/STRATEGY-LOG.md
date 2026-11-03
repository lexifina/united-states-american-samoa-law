# Global law: strategy log

This is the paper trail of the coordinated push to widen lexifina/global-law. Each entry gives the decision, what was done, who did it, and the measured effect. The figures come from the orchestrator's speedwatch (`speed-history.jsonl`, sampled every ~6 min), the per-repo GitHub API, and `strategy/census-*.tsv`. If something wasn't measured, the entry says so.

The repo is private. Fetch methods and rates stay here, never in public repos.

## Who does what

| Role | Session | Lane |
|---|---|---|
| Coordinator | global-law-main-composer (alan-dell) | global-law pointer loop, speedwatch, its own build agents, cross-session direction |
| National scraper | gitlaw-scraper-hp-omen | Latin America, NL, NO, GR, JP, CA, BR federal, BE, NZ |
| Sub-national scraper | gitlaw-scraper-dell | states, provinces and cities; fetch_scheduler owner |
| Tools | gitlaw-mcp | law.py / MCP server over global-law |

## Baseline (2026-11-02, before this push)

- **Rate:** about 700 commits/h across all repos, and pushes to global-law were sometimes 50 minutes apart.
- **Pacing caps of our own:** daily request caps per host, a 3 s floor, slow-start ramps and an IA cap, all on top of the publishers' own limits.
- **Held work:** about 3.3k verified commits, plus every non-fast-forward build, were held behind the no-rewrite rule.
- **CPU:** the box ran at about 80%, but no one measured how much of it was law work.

## Measured result

Commits added across all law repos, by hour (UTC):

| Hour | Commits | Mean CPU (5-min) |
|---|---:|---:|
| 19:00 | 38 | 79% |
| 20:00 | 741 | 85% |
| 21:00 | 8,089 | 78% |
| 22:00 | 10,572 | 79% |

From 20:00 to 22:00 the rate rose about 14×, while CPU stayed the same. The gain came from doing less waiting, not from using more machine.

## Decisions and their effects (2026-11-02)

**D-1. Stream instead of batch (from the south-america-law precedent).**
- **Done:** every lane publishes a part every 10–20 minutes, and the global-law pointer loop moves submodule pointers as each push lands.
  - The repoint loop caches its probes, keyed on `pushed_at`.
  - When the API quota runs out, it falls back to `ls-remote`.
  - It re-asks "no law yet" probes every 30 min.
- **Effect:** the gap between global-law pushes fell from about 50 min to minutes. The probe cache cut API calls per pass from about 40 to only the repos that changed. Five Argentine city repos that stale probes had hidden were added.

**D-2. Remove our own pacing caps (world-law-ops ab5429e, then 98d6922).**
- **Removed:** daily caps, the 3 s floor, the ramp, the IA cap and the scheduler's 2-worker clamp.
- **Kept:** each publisher's stated rate, Crawl-delay, Retry-After, halving on 429/503 and stopping on any challenge.
- **Added:** a per-host concurrency semaphore. It gives 6 slots to e-Gov, LexML, BWB and api.lovdata.no; 4 to BOE `/datosabiertos/api/` and data.sa.gov.au `/data/`, path-scoped; and 1 to everything else.
- **Effect:** together with D-3 and D-4, the rate went from 741/h to 8,089/h. The biggest single runs were eCFR (up to 4,349 commits per run), EU, Romania, Colombia/Marche/Dubai and the D9 releases. The effect of concurrency alone has not been isolated.

**D-3. Bust the held-rewrite pile without rewriting history.**
- **No force-pushes anywhere** (Alan, 2026-11-02). `push_clean.py` holds anything that isn't a fast-forward, and tags are never moved.
- **Held work ships as:**
  - **end blocks:** commit-tree grafts onto the published tip (Dell's `append_onto`, D12);
  - **append-only builds:** `tools/append-only/append.py`;
  - **labelled `Kind: correction` commits,** with In-force, Corrects, Supersedes and Reason trailers. Readers resolve each provision by the greatest In-force date on or before the date asked for.
- **Effect:** Dell's held cities (Muriaé, Cáceres, Almirante Tamandaré, Lavras) were published, and Brandenburg was re-claimed. Corrections for Belgium, Brazil, NZ and Bremen are being built. hp-omen's future branches (CO 1,613, NO 1,098, UY 616 commits) are being moved to `append_future.py`.

**D-4. Dedicated build agents on the biggest uncovered corpora.**
- **US eCFR:** lexifina/united-states-cfr-law, 10,078 commits after 6 titles, with 44 titles left on a detached loop. It is built from GovInfo bulk data with no new requests.
- **EU:** lexifina/european-union-law, 91 acts and 462 commits, with a loop adding about 175 more. The source is Cellar; eur-lex.europa.eu is a WAF stop.
- **Poland:** Sejm ELI API. **Taiwan:** LY and MOJ open data.

**D-5. Populous-country sprint.** India, China, the Philippines, Nigeria, Egypt, Vietnam and Ukraine, followed by a second wave: Morocco/Algeria, Saudi Arabia/Iraq, Thailand/Myanmar, Iran, Sri Lanka/Ghana.
- **Effect so far:** all of these repos have first official texts.
- **Ukraine is blocked:** Rada and NAIS are geo-blocked, and data.gov.ua and golos.com.ua disallow ClaudeBot in robots.txt. Whether Internet Archive copies may be used is a decision for Alan.

**D-6. Make CPU effective, not just busy.**
- **Done:** speedwatch now measures what share of busy CPU goes to law work.
  - **Found:** 11–13% at first. Defender took about 5.7 cores, WMI about 1.1, and svchost, WSL and the indexer took the rest.
  - **Removed WMI polling** from cpu_log.ps1, br_city_resume.ps1, arch_loop.sh, indonesia-regencies/stop.ps1 and NL fetch_pipeline.
  - **Paused** the idle lexifina-frontend container.
  - **Cleaned up** about 370 orphan tail and grep processes.
- **Effect:** the law share rose from 11–13% to 25% (22:51Z sample).
- **Biggest remaining win:** a Defender exclusion. It needs an admin step by Alan.

**D-7. Breadth before depth (22:45Z).**
- **Model:** Norway round 14, where Lovdata NLOD dumps gave 561 acts in one append, and 2,821 regulations are queued for the next pass.
- **Rule:** every lane first publishes all remaining acts as current text ("oldest version available"), in appends of 500 or more, then adds history behind them.
- **Applied by hp-omen:** JP (about 10.3k), CA (971 Acts and 4,897 regulations), NL (46.6k BWB inventory), NO (145 laws and 615 regulations left), BR, CO, MX and UY.
- **Applied by Dell:** about 60 SAPL councils, D9 regions, LexML states SC and AM (MG's ~30k next, via the ALMG API) and South Australia.
- **Why:** a country with every act in its current text answers more questions than one with five acts and their full history. Breadth also needs about one request per act, where history needs one per version.
- **Effect:** measure acts per repo against `census-2026-11-02.tsv` at the next census.

**D-8. Census-driven targeting (23:10Z).**
- **Census:** 712 lexifina/*-law repos. 267 are under 0.5 MB, 299 under 5 MB and 146 are substantial (`census-2026-11-02.tsv`).
- **Wave 3** goes to empty national repos with official open-data routes:
  - UK (legislation.gov.uk, OGL);
  - Austria (RIS OGD);
  - Estonia, then Czechia;
  - Luxembourg, Slovakia, Slovenia;
  - Croatia, Latvia, Bulgaria;
  - Qatar, Oman, Bahrain, Kuwait, Jordan;
  - Albania, Montenegro, Moldova, North Macedonia, Bosnia.
- **Brief:** `world-law/WAVE3-BRIEF.md`. Each agent skips any jurisdiction with a recorded terms, robots, WAF or geo stop, and starts the next one while it waits on a fetch.

**D-9 (Dell). Scheduler slots for documented APIs (98d6922, 23:2xZ).**
- **What:** `fetch_scheduler` dropped its own daily cap, `GITLAW_CAP_SHARE` and the 2-worker clamp. `_claim` now leases `wayback._policy(host)['concurrency']` slots per host, machine-wide. Extra slots apply only to API paths: www.boe.es `/datosabiertos/api/` and data.sa.gov.au `/data/` get 4 each; their HTML stays at 1.
- **Before:** every host got 1 slot through the scheduler, so Japan e-Gov, LexML, the BWB hosts and api.lovdata.no ran at 1 in flight despite host_get allowing 6.
- **After:** 6 in flight for those hosts and 4 for the BOE and data.sa.gov.au APIs. A 429, 503 or time-out drops a host to 1; a bot sign drops it to 1 for good. 44/44 tests pass.
- **Effect:** measure requests/h and commits/h on those hosts at the next speed sample.

**D-10 (Dell). Breadth lanes started (22:50–23:20Z).** Baselines, to compare at the next census:
- **SAPL:** about 60 councils, publishing their cached laws (up to 400 each) in appends of 500 or more. Before: most cities held a Lei Orgânica plus 0–225 laws.
- **LexML states:** brazil-santa-catarina-law (20,825 laws via IA copies, D2) and brazil-amazonas-law (11,402 Leis via SAPL). Before: no repo. The first 500-act parts are about 2 h and 11 h away.
- **brazil-minas-gerais-law:** about 30k ordinary Leis via the ALMG open-data API. Before: Constitution, ADCT and 173 LCs.
- **South Australia (data.sa.gov.au XML):** before, partial main c974b4b (about 360 of 1,390 Acts).
- **Claims janitor:** restart or release the about 38 stalled dell claims. Before: autopush_dell showed "waiting 38"; the after count goes in this entry when it reports.

**D-11 (Dell). Scheduler stall fix and time split (7d168e5, 00:2xZ 11-03).**
- **What:** when every slot was busy, `fetch_many` had parked the host until the earliest lease expired (about 3 min). It now rechecks within 0.5 s and serves other hosts meanwhile. The feed now splits `wait_ms` (queue, scheduler, host_get) from `fetch_ms`, records slot and attempt, and logs cache hits as `event: hit`.
- **Before and after:** e-Gov through `fetch_many` went from 5.1/min (with a 3-min stall) to 21.5/min. Serial callers stay at about 6/min, because they use 1 of 6 slots.
- **Remaining limits, outside the scheduler:**
  - host_get starts a curl process per request: about 4.1 s at BelowNormal on the loaded machine, against 0.22 s server time;
  - hp-omen's serial e-Gov fetcher;
  - no refetches, so D6 304s don't happen; e-Gov sends no validators.

**D-10 update (Dell), SAPL lane closed (low yield, D-8 rule).**
- 38 cities on main: about 2,680 laws plus 16 dated Lei Orgânica histories. The largest are Campinas 361, Divinópolis 346 and Muriaé 329.
- Before the breadth sweep, the build loop had already published the whole cache.
- 165 tier-3 councils passed robots and terms but were dropped unfetched. 222 claims released.

### Goal run, 2026-11-02 23:26Z → 2026-11-03 06:35Z (composer)

Alan's goal: a meaningfully finished global-law as fast as possible. Progress is measured every 20 minutes by `tools/orchestrator/goal_tracker.py` (snapshots, census, steps) and shown in `~/Documents/html-reports/global-law-goal.html`.

| | 23:26Z | 06:35Z | Change |
|---|---:|---:|---|
| Law repos holding law (>0.5 MB) | 447 | 480 | +33 |
| Substantial repos (>5 MB) | 146 | 167 | +21 |
| Nearly empty repos | 265 | 243 | −22 |
| Law data (GitHub size, lags) | 7,042 MB | 8,297 MB | +1,255 MB |
| Law commits, all repos | 642,892 | 735,908 | +93,016 |
| Peak commits/h | 2,700 | 31,408 | ~12× |
| Requests per 20 min | 749 | 7,849 | ~10× |
| Request error share | 3% | 0% | |
| Held rewrites | 7 | 1 (Chile, terms) | |

**D-12. Build on WSL ext4, not NTFS.**
- **Measured:**
  - Japan, 500 laws: 80+ min → 2.5 min.
  - Canada gate, 500 Acts: 100+ min → 6 min.
  - Uruguay: 1,162 s → 140 s; Colombia 892 → 231 s; Chile 840 → 148 s.
  - São Paulo: 279 → 87 s.
- **Tools:**
  - `wsl_run.py` and `wsl_exec.py` (fetching stays on Windows; `GITLAW_FETCH_DRY` makes WSL cache-only).
  - A `.wsl-only` marker in each repo's scripts folder.
  - The shared WSL gitconfig carries no identity (`useConfigOnly`), so a commit without an explicit identity fails instead of leaking.

**D-13. In-process keep-alive HTTP in host_get (f6e812a).**
- Each request used to start a curl process: 0.8–4 s each on this box.
- **Measured:** e-Gov 6.1 → 0.9 s per request (with `fetch_many`, 51.7/min against 7.8–12.2), Santa Catarina 4.5×, Algeria 9×.

**D-14. Correction commits (append.py --corrections, b8d0b10).**
- **Format:** Kind, In-force, Corrects, Supersedes, Reason, Act-path, and one Files: line per path.
- **Readers:** the MCP reader follows the same rule (global-law a9fcd6b). The shared check.py and on.py follow via reader-support-dell, under review.
- **Effect:** Belgium (240), New Zealand (41) and Brazil (557) published, Czechia (127), and held rewrites 7 → 1.

**D-15. Breadth first, everywhere (with the dating rule).**
- An amended act's current text is dated by its latest amendment, else by the retrieval day; never by its original start.
- **Largest gains:** Japan (~8,980 laws), Canada (all Acts plus most regulations), Colombia (1,700+), Portugal (2,098), Albania (1,004), Qatar (704), Kyrgyzstan (2,331), Croatia, Taiwan, Philippines, Vietnam, US state codes (WA 51k sections, VA 33k, MO 30k; MN, IA, GA, FL, PA, TX running), UK (685+), Sri Lanka (229) and China (173).

**D-16. Cost fixes found by measuring.**
- **Runaway tree-wide greps:** about 1.3 cores. A `grep -rx` bug in a status loop is fixed, and speedwatch now alerts on any recursive search older than 10 minutes.
- **Wasted requests:** the India gazette guesser was 76% 404s, so it was stopped.
- **Future-dated docs commits:** they blocked appends, so all three writers are now capped at min(build, now).
- **Nightly-slot starvation** stalled hp-omen's loop between 01:00 and 05:00Z; fixed.
- **Metric fix:** the WSL VM now counts as law work, so the law share reads about 35–44%, not 6%.

**D-17. Blocked, not bypassed.**
- Indonesia (BPK Cloudflare), Estonia (riigiteataja challenge), Ukraine and Iraq (geo), Myanmar, Ethiopia, Zimbabwe, Malawi, Jordan, Moldova, Morocco, Senegal, Tajikistan and seven Canadian provinces.
- Terms holds: Austria (needs the RIS notice), Latvia, Uzbekistan, Zambia, Bahrain, Kuwait, Mauritius, Tonga, Uganda (paywall) and Iran.
- All recorded in each repo's PROGRESS.md; the decisions are listed below.

## Hard limits (not traded for speed)

- No bypassing bot challenges, CAPTCHAs, WAFs, logins or geo-blocks. Obey robots.txt and Crawl-delay, and respect publishers' terms.
- No PacLII, AustLII, Constitute or Laws.Africa accounts.
- No force-pushes. Published history only grows.
- Commit identity is always a lexifina.com bot address.
  - **Audit, 2026-11-02:** 15 world-law-ops commits and 10 world-law-max-speed commits carry a personal address. Both repos are private, and the commits are left as they are, because removing them needs a force-push.
- Stop only PIDs we started.

## Open decisions for Alan

1. A Defender exclusion for the build folders (about 5.7 cores).
2. Lovdata: does the 10-30 exception cover all NLOD bulk sets?
3. Ukraine: may Internet Archive copies of the geo-blocked Rada site be used?
4. Bremen: CC BY-NC-ND on the edited and earlier-version views.
5. eCFR: robots.txt disallows `/api/versioner/v1/full/`; keep obeying (recommended).
6. California: fill 2019–2024 by in-force date with correction commits (recommended), or use a side branch.
7. Chile (LeyChile terms), Italy (IPZS WAF, email), Lithuania (FortiWeb), law.resource.org (robots names ClaudeBot; Alan: no permanent stop).

### gitlaw-scraper-hp-omen, 2026-11-03 01:30Z: breadth first, WSL, future branches

- **Canada federal.** The pipeline moved to WSL ext4 and switched to breadth first (current-text acts, 500 per push). The repo had 147 commits, then C-46 with full history (ba44487); now +482 Acts (1536829, 822 tags), 46 of them single-file and 18 held on parser mismatches. Timing per 500-act block: NTFS check_xml was still only half done after 100 min; WSL takes 6 min 14 s for the whole block (C-46 check alone: 7:55 on NTFS against 1:50 on WSL). Next: about 470 more Acts, then 4,897 regulations.
- **Norway.** Breadth from the cached Lovdata NLOD dumps. Repo went from 29 acts to 590 by append (bc84ad0, 561 acts in one append); a further 2,821 central regulations plus 592 more acts (322 single-file) are verified, for 4,004 acts and 4,608 versions in the staged build. 167 are held on undated in-force days. The detached runner (run_bulk.py) adds only new acts.
- **Japan.** Batch 1 (the six codes with full e-Gov history, 130 commits plus 16 future) went from 9d587c5 to 959dcff, with tags 66 to 198. The first 1,000-law breadth append is running.
- **Netherlands.** BWB per-act zips through fetch_many with 6 slots; credits taken from amendment-record labels cut requests from about 690 to 60–100 per 50 laws. Parts 66–68 (98 formal laws, full history) are published, and breadth parts 001–002 (990 current-text acts) are verified. About 500 zips per 12.5 min.
- **Uruguay.** Went from 262 to 269 acts. 303 more cached Leyes are being re-dated by in-force day before they go out.
- **Future branches.** append_future (Dell's append_onto, vendored) was switched on 01:05Z. Dry runs: colombia futuro +16, norway fremtidig +4,013, uruguay futuro +24, all fast-forward, check 0.
- **host_get.** Own caps removed, and concurrency 6 for documented APIs (ab5429e). The in-process keep-alive path is in progress.
- **Held for Alan.** Chile: BCN LeyChile terms forbid bulk replication (CC BY-NC-ND), so it is on hold. Uruguay: IMPO open-data licence read as governing the JSON route (to confirm).

## Next census

Re-run the census command (see `strategy/README.md`) every 6 h. Add a dated row to the table below and a delta for each wave.

| Census | Repos | <0.5 MB | <5 MB | Substantial |
|---|---:|---:|---:|---:|
| 2026-11-02 23:10Z | 712 | 267 | 299 | 146 |
