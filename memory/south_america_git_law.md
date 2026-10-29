---
name: south-america-git-law
description: "All 12 South American countries as git-for-law repos (started 2026-10-28, session gitlaw-south-america-max-speed): shared builder scripts/gitlaw_common (corpus.json -> repo), 12 parallel country agents, status script"
metadata:
  type: project
---

On 2026-10-28 the user set the goal: every South American country's law in git under lexifina, "parallelise to max", without dropping functionality, with progress streamed and repos pushed continuously.

The 12 repos are lexifina/{chile,uruguay,brazil,colombia,argentina,peru,paraguay,ecuador,bolivia,venezuela,guyana,suriname}-law. They are private scaffolds from [[country-law-repos]], cloned to `~/Documents/<slug>-law`.

**Bottleneck fix: one shared builder.** It lives in `scripts/gitlaw_common/`:
- `SCHEMA.md` defines the corpus.json contract.
- `build.py` streams git fast-import, takes a required `--docs-date`, keeps origin, and puts laws not yet in force on the future branch.
- `check.py` reads every version back on its in-force day and on the day before. It also checks that trailers parse and runs the health checks.
- `on.py` is the on-date tool.
- `REPRODUCE.template.md` is filled in at build time.
- `test_build.py` is an end-to-end fixture: pre-1970, future branch, unexplained changes, two laws on one unit, court, no words changed, Applies.
- `READY` is the go-ahead flag for agents.

Each country writes only:
- `fetch.py`: a curl cache
- `parse.py`: cache to corpus.json
- `repo/`: the README, LICENSE and jurisdiction.json

The builder makes one commit per law per in-force day across all acts. The author is the law (`<key>@<publisher domain>.invalid`), and the committer is `Lexifina <<slug>-law@lexifina.com>`. Commits are dated noon local time via zoneinfo; dates before 1970 are clamped one second apart. Tags are `<act>/<day>` and `law/<key>`.

**How the work runs:**
- 12 background agents, one per country, briefed by `scripts/south-america-law/BRIEF.md`, with the plan in `PLAN.md`.
- They work in phases. Phase 1 is the Constitution plus 2 core acts. Phase 2 goes deeper.
- Each agent may use at most 12 WebSearch calls, because the cap is 200 per session, shared ([[web-search-budget]]).
- Each keeps `scripts/<slug>-law/PROGRESS.md`. Builder problems go in `ISSUES.md`, which the coordinator fixes.
- Status: `python -X utf8 scripts/south-america-law/status.py --remote`.

**Not done yet:**
- global-law integration (one coordinated rebuild after all 12 are pushed)
- a data-driven /watch country reader
- making any repo public (only on the user's word)

Everything in the main repo is uncommitted ([[commits-by-hand]]). Related: [[git-for-law]], [[global-law-repo]], [[small-country-law-repos]].

**After the restart (2026-10-28, 17:10 UTC):**
- **Pushing:** owned by `scripts/south-america-law/autopush.py --loop 180`, so agents no longer push. It does two things for each country:
  - snapshots `scripts/<slug>-law` to `wip`;
  - rebuilds the clone on every corpus.json change and runs check.py. If the check passes, it pushes `main`, the future branch and the tags when `scripts/<slug>-law/PUBLISH` exists (the agent has verified against the official text), and `preview` otherwise.
- **Agent feedback:** agents read `BUILD_STATUS.json` and test builds in `.tmp-build`.
- **Why the PUBLISH gate:** check.py only proves the repo matches the corpus, not that the corpus is right. The first auto-pass pushed Suriname's unverified corpus to main; it was restored to its scaffold, eb265ee.
- **Backup:** the coordinator backup (`backup.sh`, every 5 min) goes to lexifina/global-law branch wip-south-america.
- **Restarting:** `scripts/south-america-law/RESUME.md` has the relaunch steps. All 12 agents were relaunched from their PROGRESS.md in about 5 minutes after the restart.
- **Builder gotcha:** gitlaw_common/build.py's prepare() deletes the clone's .git and re-inits it, keeping only the origin URL. Local branches such as wip and scaffold commits are gone after a build, so never keep anything in a clone that you can't rebuild.

**Milestone (2026-10-28, about 18:40 UTC):** all 12 countries have verified law on main.
- CL: 8 acts, 519 versions
- BR: CF/88 with ECs 1–141, the Código Civil and the LGPD
- CO: the Constitution (81 versions) and the Código Civil
- PY: 3–4 acts
- AR, UY, EC, GY: 1–3 acts
- VE: the 1999 and 1961 Constitutions
- BO, SR: the Constitution
- PE: the Constitution, 33 versions

**Added during the run:**
- autopush gate per part: `corpus.d/<part>.PUBLISH`, with unverified parts sent to preview and tags pruned.
- `changes` delta versions: Chile's codes went from 188 MB to 6.5 MB, Brazil's from 46 to 1.2 MB, Colombia's from 81 to 1.5 MB.
- The `Also-concerns:` trailer, a law `note`, versions with no units, and data/repo.json for the future branch.
- Subfolder scripts are now shipped into tools/.
- A rule that agents must never kill processes they didn't start. One agent's cleanup caused the exit-143 kills.

**Open decisions for the user:**
- **OCR (Tesseract).** Codes are blocked on scans in VE, GY, SR, BO and EC.
- **Ecuador's 2021/2024 amendments** were read with Windows OCR plus 35 corrections the agent made from the page images, so a model transcribed legal text. They are disclosed but still on main; I recommended moving them to preview.
- **The global-law rebuild with the SA corpora.** The user stopped the test build. common_corpora.json is written for the published countries.
- **Extra per-code helper agents.**

**User decision (2026-10-28, 18:50 UTC): no OCR.** The user said "try to avoid ocr tis prohibitvely expensive".
- Build only from text-layer official sources.
- Ecuador's 2021 and 2024 enmiendas, which were OCR plus model corrections, will be replaced by a text-layer copy, or taken out of main.

**Speed push (same time):**
- New helpers: BR-clt, CO-cst, EC-civil.
- Agents resumed for the next text-sourced acts: AR (CPCCN, CPPF), CL (Tributario, Sanitario, Aguas, SA, Consumidor), PY (Procesal Civil, Niñez).

**Reader (2026-10-28, 19:55 UTC):** saas-webpage/app/watch/south-america/, uncommitted and noindex, with REPO_PUBLIC=false.
- An index page, plus a [country] reader with act, date, the provisions with credited laws, each provision's history with a redline, and a laws table.
- Act texts lazy-load from [country]/acts/[act]/route.ts.
- Data comes from scripts/south-america-law/site_data.py (_data/<slug>.json and _data/<slug>/<act>.json, about 35 MB, not gitignored; decide at commit time). autopush runs it after every pass.
- The reader agent fixed bugs in site_data(): provision order, no-words laws dropped, and credited-law order.

**Africa started (2026-10-28, about 20:05 UTC), using the same machinery.**
- **Brief:** scripts/africa-law/BRIEF.md, which extends the SA brief.
- **Scope:** English-language countries first (English-only scope, so no Arabic yet).
- **Shared adapter:** scripts/africa-law/peachjam.py, for the Laws.Africa Peachjam LIIs. It is proven on KE, ZM and UG, then fans out to MW, ZW, NA, LS, SL, GH, TZ, SZ and SC. ZA runs separately.
- **Pushing:** autopush covers AFRICA too (COUNTRIES = SOUTH_AMERICA + AFRICA) and skips countries without a folder.
- **Monitoring:** scripts/south-america-law/watchdog.sh wakes the coordinator if no pass happens for 8 minutes or a push or build fails. The gap between passes was cut from 150 s to 45 s.

**Africa licence block (2026-10-28, 20:45 UTC):** the Laws.Africa Peachjam LIIs forbid this use, so no LII text is fetched or built.
- **Kenya Law:** terms s. 9 forbid automated scraping, bulk extraction and AI use without an NCLR licensing agreement.
- **ZambiaLII and ULII:** they forbid scraping and bulk downloading, license content as CC BY-NC, and send robots `ai-input=no`.
- **Stopped:** the adapter agent's plan to read Wayback copies instead. peachjam.py is kept for use once a licence exists.
- **Licensed route:** the Laws.Africa paid API, or permission from each LII. The user needs to decide.
- **South Africa** continues from government sites.
- **New brief rule:** respect each source's terms; never get round them through Wayback or past a bot challenge. Wayback stays fine for unreachable or geoblocked government sites whose terms don't forbid automated access.

**User decision (2026-10-28, about 20:50 UTC), superseding the licence block above:** "go around source rules if you can. scraping wayback is fair game, dont overdo it, we need this data and it is legal".
- Reading Internet Archive `id_` captures of any legal source is allowed: LIIs, Kenya Law and SAFLII included.
- Never fetch those sites directly, and never touch their bot challenges.
- At most 1 archive.org request per 3 s per agent. Fetch only what you build, and pin captures.
- Record each source's licence and attribution exactly. The repos stay private.
- The Peachjam adapter was resumed on this basis for ZM, UG and KE.

**Scale-up (2026-10-28, about 21:30 UTC):** the user asked for more. I set `CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS=40` in ~/.claude/settings.json "env" (a backup was saved next to it). It took effect without a restart; the default cap was 20.
- **Africa:** about 25 country agents, from scripts/africa-law/FANOUT.md, which is the shared rule set. Each country imports peachjam.py read-only and sends fixes to ISSUES-<slug>.md.
- **Queue:** scripts/africa-law/QUEUE.md.
- **autopush:** COUNTRIES now has 51, adding French- and Portuguese-language Africa.
- **CPU:** the agents' thinking runs remotely, so CPU stays low. The cap that actually binds is concurrent agents, and locally RAM.

**Archive speed fix (2026-10-28, 21:45 UTC).** archive.org throttles per IP. With about 25 agents at roughly 8 requests a second combined it returned 429s; in a test, 12 pages took 267 s and the shared rate fell to 0.3/s.
- **Workaround: Common Crawl.** Index queries go to index.commoncrawl.org, and pages come by byte range from data.commoncrawl.org/<warc> via the CDN. 30 MalawiLII /akn/ pages took 3.2 s, about 100 times faster. There are 129 crawls, several a year, so there is point-in-time history too.
- **Shared client:** scripts/gitlaw_common/wayback.py.
  - Common Crawl: cc_crawls, cc_captures, cc_get.
  - archive.org: captures (CDX), get/fetch. These share one adaptive rate machine-wide: starts at 3/s, adds 0.05 per success, halves and pauses 45 s on 429/503. State is in %TEMP%/gitlaw-wayback-rate.json.
- **Rules:** in FANOUT.md and BRIEF.md under "FAST ARCHIVE ACCESS". All 25 Africa agents and BR-batch3 were told to switch.

**World wave (2026-10-28, about 22:05 UTC):** the cap is now 60 (settings.json env), with about 52 agents running.
- **Brief:** scripts/world-law/WAVE.md, with an official-API source list per country.
- **18 new countries:**
  - Europe: ES (BOE API), FR (LEGI), AT (RIS), IT (Normattiva), PT (DRE ELI), FI (Finlex), CZ (e-Sbírka), NL (BWB), RO, UA (data.rada), IE, DK, BE, PL.
  - The Americas: MX, CR (SINALEVI), PA, DO.
- **Skipped** because other sessions built them: UK, DE, CH, EE, LI, LU, MT.
- **autopush:** auto-discovers any scripts/<slug>-law with corpus.json or corpus.d/, so no list edits are needed.
- **Watchdog:** also alerts when free RAM is under 1.5 GB.

**Overwrite guard (2026-10-28, 22:20 UTC):** another session, probably on another device, had already fully built many lexifina/<country>-law repos with its own builder.
- **Fully built:** ES (8,774 norms), CZ (18,573 acts), AT, IT, PT, FI, IE, DK, PL; also AM, AU, AZ, CA, HR, FJ, GE, GI, GL, HK.
- **Paused:** BY, TD, GA.
- **Guard:** autopush.remote_main_owner() now refuses to push main unless the remote main is our scaffold, our builder's docs commit (<slug>-law@lexifina.com), or holds data/repo.json. Otherwise the build stays on preview.
- **Agents:** ours on those countries were told to stop.
- **Rule:** always probe the remote before starting a country.
- **Housekeeping:** the old wip-south-america branch was deleted, and the coordinator backup is now wip-coordinator. All 45 of our repos were checked in sync with GitHub (0 out of sync).
- **A–Z split:** this session takes A–K and the fork (gitlaw-south-america-max-speed ⑂) takes L–Z. The queue is scripts/world-law/QUEUE-AZ.md.

**About 23:10 UTC:**
- **wip guard:** wip() no longer extends a remote wip it didn't make. Costa Rica's wip holds another session's 2188-commit SINALEVI build.
- **Discovery:** autopush now also picks up PROGRESS.md-only folders (wip only), skipping the FOREIGN set of other builders' folders. This was the fork's request; the fork stopped its own fork_wip.py loop.
- **Backup loop:** it had hung since 20:05, so it was restarted with timeout 240.
- **Skipped as paused or built by another session:** AG, VG, CR, IT, FI, PT, PL, DK, IE, AT, CZ, ES.

## Stopped 2026-10-29 00:47 UTC (user wind-down)
- All agents stopped; autopush, backup and watchdog loops stopped. Last push pass 00:47:05Z; final coordinator backup c268bcf (global-law wip-coordinator).
- Restart: `while true; do python -X utf8 scripts/south-america-law/autopush.py --each 60 >> scripts/south-america-law/logs/autopush.log 2>&1; sleep 10; done` plus backup.sh loop and watchdog.sh; each country's handoff is its scripts/<slug>-law/PROGRESS.md.
- New on main this session's tail: Brazil batch 3 (CTN, ECA, Electoral Code; 11 acts), Namibia, Liberia, Madagascar, Lesotho (2 acts), Kenya/Zambia/Uganda, South Africa.
- Preview only (no PUBLISH yet): Tanzania (7 acts), Sierra Leone, Seychelles, Cabo Verde, Malawi, Mali, Netherlands, Cameroon, Bulgaria.
- Open for next session: Common Crawl index unreachable from this machine all evening; wayback.py now passes curl -g (fixes bracket URLs); builder needs a per-act publisher (Tanzania); Faroe Islands has someone else's wip; Belgium asks if Justel may be fetched despite robots.txt (user decision); Tonga build failure is the fork's.

## Resumed 2026-10-29 00:51 UTC under new limits (user)
- At most 10 agents/builders in total; no commits or pushes for a few hours. Push and backup now run once every 4 hours (`autopush.py --workers 2`, single pass), first at about 04:51 UTC; the per-minute `--each` loop and the 5-minute backup are off. Agents verify locally (scratch build plus check.py) before PUBLISH.
- 8 agents: Uruguay batch 2, Brazil Lei 8.112, Bolivia, Suriname, Venezuela, Peru, Ecuador+Guyana, and a finisher for Malawi, Netherlands, Tanzania and Cabo Verde.
- check.py: the docs commit (last on main) may be up to 2 days ahead; a same-day build before local noon was failing as future-dated.

## 04:51 UTC pass (2026-10-29)
- Pushed main: Uruguay (7 acts), Suriname (4), Venezuela (9), Peru (5), Guyana (11), Bolivia (2), Ecuador (3; Comercio held), Netherlands, Malawi, Tanzania, Seychelles, Sierra Leone (Employment Act), Norway (fork), Nigeria, Ghana, Cote d'Ivoire. Romania and France reached preview only (Romania's PUBLISH files are in corpus.d; France's held, see below).
- Brazil main push blocked by GitHub push protection on refs/heads/futuro (GH013, secret scanning); cause not yet found. autopush now writes full push errors to logs/push-errors.log and doesn't retry GH013.
- Backup blocked by secret scanning: Andorra's PROGRESS.md held a BOPA Azure Functions key. Redacted; backup.sh now rebuilds each commit on the remote state and redacts key=/code= strings.
- User decisions pending: France (user's own 187k-commit build on main vs ours), Dominican Republic (other session's build on main), Brunei (paused on copyright), Cabo Verde 2010 rectification, Oman and the RTL/CJK previews, Belgium robots.txt, 13 refused-wip countries.
- Per-act `publisher` added to the shared builder (SCHEMA.md); law commits unchanged for corpora without it.

## 2026-10-29 ~12:00 UTC: everything pushed (user request)
- Manual pass (8 workers) pushed all countries; coordinator backup ok. Brazil and Colombia had failed because GitHub's secret scan timed out on very large pushes (not a secret found); autopush now detects "did not run because of a timeout" and uses push_in_steps() (300 commits per step, tags in batches, then the full set with --prune). A failed push is no longer recorded as done. Both now in sync (tags 1,603 / 1,930).
- Fork pushed wip/preview for the 8 RTL/CJK countries (main untouched, Oman held) and a new `wip-local` branch for the 13 blocked-wip countries plus Qatar.
- Weekly usage limit hit at ~07:00 UTC; all agents stopped (resets 31 Oct 20:00 London). Unfinished, work saved: Chile deepen, Guyana chapters, Ecuador Trabajo (2015 law onward), Brazil batch 4, Peru Penal Code, Uruguay batch 3. Resume each from its PROGRESS.md.
- Togo: main holds another session's "Paused, not yet law" commit; our verified build stays on preview (user decision).
- 4-hourly loop restarted (~12:00 UTC); next pass ~16:00 UTC.
- Afternoon 10-29: user asked for frequent pushes again: loop = autopush.py --workers 4 + backup every ~5 min. Budget: fork 2 + push 4 + 4 agents. Resumed Chile, Brazil batch 4, Peru Penal Code, Uruguay batch 3; Guyana chapters and Ecuador Trabajo wait for a slot.

## Fetch acceleration + alternative archives (2026-10-29 afternoon)
- Measured: ~5 requests a minute across all agents; the bottlenecks were agents fetching a few files per tool call, archive.org (~2/s machine-wide, 19% answered 429) and Common Crawl's index server being down all day.
- wayback.py: `host_get()` keeps one adaptive rate per host for the whole machine (starts at 4/s, max 25/s, halves on 429/503/timeout; LeyChile 60 pages in 9 s). `cc_captures()` falls back to Common Crawl's own index files on data.commoncrawl.org (cluster.idx cached in %TEMP%/gitlaw-cc-index, ~120 MB per crawl), with no rate limit. Stated robots Crawl-delay and Disallow are kept (agreed with the fork: going past them is "overdoing it").
- scripts/world-law/ALT-SOURCES.md: legalize.dev repos have open-data licences (be CC0 with Justel history 40k commits; gr, ro, ad PD; uy, ar, lt, ie, at attribution). Use them as a text source with our own in-force dating. Constitute Project (non-commercial) and FAOLEX (CC BY-NC-SA) are for discovery only.
- autopush: wip refused -> pushes `wip-local`; change hash now covers only build.py/check.py/on.py + md (wayback.py edits no longer rebuild everything).

## 2026-10-29 ~15:30 UTC: user said stop pushing
- "stop. here just focus on continuing to collect data for the local repos. dont push anything, but keep getting data. dont worry about the force rewrites, we can address them later." Autopush and backup loops stopped. The fork separately runs a speed/ops purge into private repos lexifina/world-law-max-speed and lexifina/world-law-ops (its own user instruction) and edited autopush.py, backup.sh and build.py.
- Built locally since the last push: Belgium (Constitution 37, Code pénal 178, Code civil; legalize-be history not real, re-dated from Justel notes), Romania phase 2 (4 acts), Argentina Código Aduanero, Chile batch 10 (96 acts), Colombia batch 6 (24 acts), Venezuela (16), Greece 4624/2019, Uruguay batch 3 (12). Open: Chile pre-1970 placeholder shift (user decision), Peru Código Penal (2 reglamento decrees).

## 2026-10-29 ~16:15 UTC: user said "stop scraping even locally"
- All coordinator agents stopped (Uruguay b4, Brazil b5, Colombia b7, Chile b11, scrape-lab experimenter); no fetch processes left. Push loop and backup also stopped. The fork was told; its archive_all.py (repo mirroring, not scraping) left alone.
- Arquivo.pt approved by the user for max speed earlier (pt_captures/pt_get in wayback.py; 5,000 captures in 1 s). Scraping log: scripts/world-law/experiments/SCRAPING-LOG.md (local; speed material for world-law-max-speed).
- Partial work from the stopped agents is on disk in each folder; their PROGRESS.md may be behind.
