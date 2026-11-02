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

## Next census

Re-run the census command (see `strategy/README.md`) every 6 h. Add a dated row to the table below and a delta for each wave.

| Census | Repos | <0.5 MB | <5 MB | Substantial |
|---|---:|---:|---:|---:|
| 2026-11-02 23:10Z | 712 | 267 | 299 | 146 |
