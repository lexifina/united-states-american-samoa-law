# Brief for every South American git-for-law country agent

You build one country's law history as a git repository to the Lexifina git-for-law standard and push it to the private repo `lexifina/<slug>-law`. Twelve agents run in parallel, one per country. Move fast, but drop no functionality.

## Read first (about 10 minutes, no more)

- `memory/git_for_law.md`: the standard and every lesson so far. Read all of it.
- `scripts/gitlaw_common/SCHEMA.md`: the only thing you produce is `corpus.json` in this format. A shared builder makes the repository.
- `scripts/south-america-law/PLAN.md`: your country's row and the checklist.
- One model country builder, for parsing ideas only: `scripts/liechtenstein-law/build.py` (functions `read_version`, `build_act`), `scripts/estonia-law/build.py` or `scripts/swiss-law/build.py`.
- `scripts/world-law/register.json`: your country's sources are in `sources[]` where `c` is your country.

## Your folder and repo

- Work only in `scripts/<slug>-law/` in the main repo, plus your local clone. Never edit another country's folder, `scripts/gitlaw_common/`, memory files or the site. Never commit in the main lexifina repo; the user commits it by hand.
- Clone the scaffold with `git clone https://github.com/lexifina/<slug>-law.git C:/Users/alany/Documents/<slug>-law`. The scaffold has one "sources, before any law" commit. Its README, SOURCES.md and jurisdiction.json hold research you should reuse: fold SOURCES.md and the useful README content into your `repo/README.md`, and keep `jurisdiction.json` in your `repo/`, setting `build` to the real status.
- The repo stays PRIVATE. Never change its visibility.

## Steps

1. **Probe** (30 minutes or less). Hit each candidate source once with curl:
   - Record status, format, whether it has dated versions, amendment notes per provision, robots.txt and licence in `scripts/<slug>-law/PROGRESS.md`.
   - Use curl, never Python urllib: TLS chains fail on this machine.
   - If a portal is geoblocked or bot-blocked, try the Wayback Machine (`https://archive.org/wayback/available?url=…`, then the `id_` raw form).
   - Check the prior-art repos listed in PLAN.md for reconciliation only. Never copy their text: we read official text only. Their licences (for example AGPL) don't allow copying.
2. **Choose the Phase 1 acts.** Take the Constitution plus 2 core acts:
   - the Civil Code, and
   - the data protection law or the Penal Code, whichever has the better dated source.

   Choose acts whose history the official source supports. Write the reasons down in `decisions`.
3. **fetch.py.**
   - Use a curl subprocess, cached under `scripts/<slug>-law/.cache/` (add a `.gitignore` there containing `*`), with filenames from the sha256 of the URL.
   - Make at most 1 request per second per host, use the User-Agent `lexifina-watch/1.0 (+https://lexifina.com/watch; corpus@lexifina.com)`, and make it resumable.
   - Log every request to `.cache/requests.jsonl`.
   - Prefer bulk or API endpoints.
4. **parse.py.** It reads only the cache and writes `scripts/<slug>-law/corpus.json`, following SCHEMA.md exactly.
   - **Dates:** use in-force dates, with the country's default rule cited in `country.default_in_force_rule`. A law's own vigencia clause overrides that rule.
   - **Credits:** credit only from the source's own amendment notes ("Redação dada pela…", "Modificado por…", "Texto según…"). Anything unexplained stays uncredited.
   - **Courts:** rulings that strike or condition text are `court` laws.
   - **Temporary measures:** use `temporary_until` and `restores`.
   - **Reconstructing old versions:** if the source has no dated versions, rebuild them from struck-through or "texto original/anterior" annotations or by replaying the amending acts. Then check that replay end to end against today's official text, and record every mismatch.
5. **Build.** Once `scripts/gitlaw_common/READY` exists:
   - Run `python -X utf8 scripts/gitlaw_common/build.py scripts/<slug>-law --repo C:/Users/alany/Documents/<slug>-law --docs-date <retrieval day>`.
   - Run `check.py` until it shows 0 mismatches, or explain each remaining one in `decisions`.
   - Run the `--compare` determinism rebuild.
   - Until READY exists, keep fetching and parsing, and write `corpus.json` early and often.
6. **Push early, then keep pushing** with `git -C <clone> push -f origin main --tags`, plus `futuro` if it exists. The user wants the repos updated continuously.
   - Push as soon as the first act builds and checks clean.
   - Push again after each further act.
   - Nothing pins these repos yet, so force-pushing is fine.
7. **Go deeper (Phase 2).** When the three acts are done and pushed, keep adding acts while the source supports dated history, pushing after each. Priority order:
   - the Penal Code and data protection law (whichever you didn't take)
   - the Commercial Code
   - the Labour Code
   - the Code of Civil Procedure
   - the Code of Criminal Procedure

   Then go on to all national laws if the source offers bulk access. Stop adding acts when about 4 hours of work have passed, or when the source can't give dated history.
8. **Problems in the shared builder.** Write them to `scripts/<slug>-law/ISSUES.md` with the exact error. The coordinator reads these files and fixes the builder. Don't patch the builder yourself; work around it in your data if you can, and note it.

## Limits and rules

- **WebSearch:** at most 12 calls in total. The cap is shared by all 12 agents. Use WebFetch and curl on known URLs instead; neither is capped.
- **Language:**
  - Law text stays in the original language.
  - Commit messages are written by the builder in English, using your law titles.
  - The README is English first, then a short section in the country's language.
- **No model writes legal text.** Disclose any model use in `ai_use`.
- **Facts:** say what you verified. If a source can't give dated history, say so plainly in PROGRESS.md and the README. Don't fake history. A smaller true history beats a larger guessed one.
- **PROGRESS.md:** keep `scripts/<slug>-law/PROGRESS.md` current, with a checklist, the sources, cache size, versions per act, commits, pushed head and open issues. It is how anyone resumes your work.

## Final report

End with a report of at most 15 lines:
- acts built, versions, commits, tags
- pushed head hash
- check results and determinism result
- what was not possible, and why
- any ISSUES.md items
- ideas for making the next country faster

## Known pitfalls (added by the coordinator during the run)
- If GitHub says "Repository not found" for lexifina/<slug>-law, the cause is a transient credential failure. All 12 repos exist. Wait 30 s and retry up to 3 times.
- Planalto (Brazil), SPIJ (Peru), the Gaceta Oficial (Paraguay and Bolivia) and parlamento.gub.uy all block or time out from this machine. Read them through Wayback `id_` raw captures, and pin the capture timestamps in your data so parse stays reproducible.
- The builder is fast: Chile's Constitution (78 versions, 85 commits) builds in 2.4 s with 0 mismatches. Rebuild and push often.

- Always pass `--compressed` to curl. It requests gzip/brotli transfer; curl unpacks before writing, so the cache bytes and sha256s are unchanged.

- **Never kill a process you did not start yourself.** No `kill`, `taskkill` or `Stop-Process` from a `ps` listing. 16 agents and the coordinator's loops share this machine, and one agent's cleanup killed the autopush loop and another agent's fetch (exit 143). Stop only the background tasks you launched, by their own id.

- **No OCR (user decision, 2026-10-28: "prohibitively expensive").** Build only from official texts with a machine-readable text layer. If a needed text is only a scan, don't read it off the page image either. Leave that change out and name it in decisions and the README.

- **Text that appears before its law (coordinator rule, 2026-10-28).** A source version may contain wording whose note names a law that took effect later. Correct only those provisions, only in the versions before that law took effect:
  - if the provision was inserted by the later law, it is absent;
  - otherwise it reads "[La fuente no da el texto vigente en esta fecha.]" (in the act's language), credited to the publisher.
  The wording then arrives in the first version on or after the law's in-force day, credited to that law. List every corrected provision in decisions. Never drop whole versions for this.

- **Sources and Wayback (user decision, 2026-10-28: "scraping wayback is fair game, dont overdo it, we need this data and it is legal").**
  - Reading Internet Archive `id_` captures of any legal source is allowed, including Laws.Africa LIIs and sites whose own terms forbid scraping them directly.
  - Never fetch such a site directly and never touch its bot challenge: go through archive.org only.
  - Don't overdo it: at most 1 archive.org request per 3 s per agent. Fetch only the acts you build, and cache everything so nothing is fetched twice.
  - Record each source's own licence and attribution exactly (for example CC BY-NC 4.0, ZambiaLII) in the README and REPRODUCE.md, and pin capture timestamps.
  - The repos stay private.

## Changed after the restart (2026-10-28, 17:10 UTC): these override steps 5 and 6 above

- **Pushing:** you no longer push anything. `scripts/south-america-law/autopush.py` runs every 3 minutes for all 12 countries and handles both branches:
  - **wip:** it snapshots your whole folder (no .cache) to the `wip` branch.
  - **builds:** whenever your `corpus.json` changes, it rebuilds your clone `C:/Users/alany/Documents/<slug>-law`, runs check.py and pushes. The result is in `scripts/<slug>-law/BUILD_STATUS.json`; read it after each corpus change.
- **Don't build into your clone or push it:** autopush owns it, and two builders at once would collide. To test, build into `scripts/<slug>-law/.tmp-build`, which is gitignored, and run check.py there.
- **Where builds go:** each build goes to the branch `preview` until you create the file `scripts/<slug>-law/PUBLISH`. Create it, with one line saying what you verified, only when the corpus has been checked against the official text: today's text matches the official consolidated text, and every version is sourced. From then on, autopush pushes `main`, the future branch and the tags.
- **Write corpus.json often and atomically:** write to `corpus.json.tmp`, then rename it. Every write becomes a build within 3 minutes, so you stream without doing anything extra.
- **PROGRESS.md:** keep it current after every step, so a restart loses nothing. autopush backs it up.
- **Builder improvements available to you:**
  - Laws can carry a `note` (SCHEMA.md), for referendums or rulings that change no words.
  - Every .py/.sh in your folder, plus sources.json and acts.json, is shipped into the repo's tools/.

## FAST ARCHIVE ACCESS (coordinator, 2026-10-28, 21:45 UTC): use this instead of your own archive.org fetching

archive.org throttles this machine as a whole: all agents share one IP, and it was answering 429 at about 8 requests a second combined. **Common Crawl serves the same kinds of pages about 100 times faster** (30 MalawiLII act pages in 3.2 s), from Amazon's CDN by byte range, across 129 crawls with several captures a year. Use the shared client `scripts/gitlaw_common/wayback.py`:

    import sys; sys.path.insert(0, r'C:/Users/alany/Documents/lexifina/scripts/gitlaw_common'); import wayback
    recs = wayback.cc_captures('malawilii.org/akn/', match='prefix', crawls=wayback.cc_crawls(CACHE)[:12], cache=CACHE)
    body = wayback.cc_get(rec, cache=CACHE)                 # one capture's HTML; parallelise freely (8-16 threads)
    caps = wayback.captures('host/path', match='prefix', cache=CACHE)   # archive.org CDX: one request lists all
    raw  = wayback.get('https://host/path', ts='20240101', cache=CACHE) # archive.org, shared adaptive machine-wide rate

1. **Common Crawl first.** cc_captures gives each capture's crawl and timestamp, and the capture timestamp is your retrieval evidence; pin the crawl id and WARC offset in sources. Index queries are a few seconds per crawl and prefix. The page fetches have no tight limit, so use a thread pool.
2. **archive.org only for what Common Crawl lacks,** always through `wayback.get` / `wayback.captures`. They share ONE adaptive rate for the whole machine: it backs off on 429 and speeds up when allowed. Drop your own sleep and delays for archive.org.
3. **Don't wait on a missing capture.** Build what exists, list what is missing, and move on.
4. **Records:** both clients write `requests.jsonl` in your cache folder. Record "Common Crawl CC-MAIN-…" as a source with its licence (Common Crawl terms of use), alongside the original publisher's attribution.

## SPEED RULE (coordinator, 2026-10-28, 21:55 UTC)

The user asked for more speed.

- **Direct official sources** (LeyChile, InfoLEG, BACN, the Senado basedoc, Planalto, gazettes, parliaments, LIIs' open pages): up to **3 requests a second**, with a parallel fetch of 3 where the server copes. On any 429 or 503, halve your rate and wait 60 s. One exception: IMPO's stated 10 s crawl delay still applies.
- **Common Crawl:** 8–16 parallel threads.
- **Work order:** do Phase 1 for every act before any Phase 2 depth. Skip an act that would take more than 45 minutes to source, note why, and go to the next.

## CADENCE CHANGE (user, 2026-10-29 00:51 UTC): no pushing for hours; at most 10 agents/builders
- Nothing is pushed or committed to any lexifina repo for at least the next few hours. Autopush now runs ONE pass every 4 hours (first at about 04:51 UTC), 2 countries at a time; it no longer pushes within a minute.
- So verify locally yourself: build into an empty scratch repo (`build.py <folder> --repo <empty .tmp-build> --docs-date <D>`), run `check.py` on it (0 mismatches, 0 trailer errors), and `--compare` once for determinism. Write PUBLISH only after that passes. BUILD_STATUS.json will not update until the next pass.
- Never push, commit or `git` write to the country repos or the main lexifina repo yourself.
- check.py now allows the docs commit (last on main) to be up to 2 days ahead, so a same-day build before local noon no longer fails.
- Main is pushed only when the folder-level `PUBLISH` exists AND (with corpus.d) the part has its own `<part>.PUBLISH`. Write both.

## CADENCE CHANGE 2 (user, 2026-10-29 afternoon): frequent pushes again
- The push loop runs a pass about every 5 minutes, 4 countries at a time; agents still verify locally before PUBLISH and never push themselves. Total budget stays 10 agents/builders (fork 2, push 4, coordinator agents 4).

## SPEED RULE 2 (user, 2026-10-29 14:30 UTC): replaces SPEED RULE and per-agent sleeps
The user wants fetching accelerated; agents reading a few files a minute is not acceptable.
- **Official sites:** use `wayback.host_get(url, cache)` from a thread pool of 8-16. One adaptive rate per host, shared by every process on the machine: it starts at 4 requests a second, climbs to 25, and halves with a 30 s pause only when the host answers 429/503 or times out. Drop your own sleeps and fixed rates. Hosts whose robots.txt states a Crawl-delay (IMPO 10 s) keep it, with one thread: get round a slow host through Common Crawl or archive copies, not faster live requests. robots.txt Disallow is always obeyed. LeyChile test: 60 pages in 9 s, no pushback.
- **Common Crawl works again:** index.commoncrawl.org is still down, but `wayback.cc_captures()` now reads Common Crawl's index files from the data host (cluster.idx, cached once per crawl for the whole machine, ~120 MB) and `cc_get()` reads pages by byte range with no rate limit: use 16 threads. Try it before archive.org: 140 MalawiLII records in under 10 s.
- **archive.org** stays at its shared adaptive rate (~2 a second for the whole machine; it answers 429 above that). Use it only for what Common Crawl lacks. Do not rotate IPs or proxies.
- Never get round a bot challenge, login or paywall.
- **Fetch in bulk, in the background:** write the list of URLs first, then run one fetch.py with a thread pool (host_get / cc_get) in the background and parse while it runs. Never fetch a handful of files per tool call; across all agents that averaged about 5 requests a minute today.
- **Bulk and open-data routes first** (dumps, APIs, open data), then Common Crawl, then live pages, and archive.org last.
- **Alternative hosted archives:** read scripts/world-law/ALT-SOURCES.md first. The legalize.dev repos (open-data licences) hold reconstructed histories, e.g. Belgium from Justel. Constitute and FAOLEX are for finding sources only.

## PUSH STOPPED (user, 2026-10-29 ~15:30 UTC)
Nothing is pushed or committed to any remote until the user says otherwise. Keep collecting data locally: verify builds into scratch repos, write PUBLISH when verified. The push loop is off.

- **Arquivo.pt (user-approved 2026-10-29, max speed):** `wayback.pt_captures(url, match="prefix")` lists up to 100,000 captures in one call (5,000 Planalto captures in 1 s), and `wayback.pt_get(rec)` fetches the raw page (40 pages in 7 s from 12 threads, no throttling). It uses host_get's adaptive rate. Try it right after Common Crawl and **before archive.org**, above all for Lusophone and Latin American official sites (Planalto, IMPO, ...). Record it as a source ("Arquivo.pt, capture <ts>").
- **Never publish personal emails (user rule 2026-10-29).** The machine's global git email is personal, so any commit made outside autopush or build.py must set `user.email` explicitly (Lexifina <slug-law@lexifina.com>). Agents still never commit or push.

## SCRAPING STOPPED (user, 2026-10-29 ~16:15 UTC)
"stop scraping even locally". No fetching of any kind until the user says otherwise. Push is also stopped.

## PUSH RULES 3: public repos, no rewrites (coordinator, 2026-10-29 ~18:40 UTC)
The country repos and global-law are now **public**, and the user's rule is: never rewrite, force-push, delete, move or change visibility of a repo without warning and an explicit yes. Pushing is still stopped except for the coordinator's one-repo test. When it resumes it goes only through autopush.py, which now:
- **never uses `-f` or `--prune`.** A fast-forward is pushed plainly. A rewrite is never pushed unasked; that includes the normal case, where a rebuild replaces the documentation commit at the tip. It's recorded in `scripts/world-law/REWRITE-PENDING.json`. The coordinator asks the user, and only after an explicit yes for that repo writes `<slug> refs/heads/<branch> <old> <new>` into `scripts/world-law/REWRITE-APPROVED.txt`. That exact rewrite is then pushed with `--force-with-lease`. Tags only the remote holds are no longer deleted, and a moved tag needs its branch's approval.
- **no longer pushes preview.** Unverified builds are built and checked locally only.
- **sends wip snapshots to the PRIVATE world-law-ops**, branch `wip/<slug>-law`, never to the public country repo.
- **runs `private.audit_push()` over everything a push would add.** It uses the same names and markers as the final privacy audit: private file names, speed tooling, Common Crawl tactics, the home path, bot-challenge notes, the personal email, and identities outside lexifina.com/.invalid. Any finding stops the push.
- `private.is_private()` is widened to match. Build tools (`tools/`) leave out any script that mentions Cloudflare, captchas or Common Crawl hosts, and the playbook files (BRIEF, FANOUT, WAVE, ALT-SOURCES, …).
- Agents: never push. The old per-country `push_wip.sh` / `wip_push.sh` scripts force-pushed to public wip branches and are disabled. Don't write notes about a site's defences (Cloudflare, captchas) or the fetch method into README.md, SOURCES.md or anything under `repo/`: those are published. Keep them in PROGRESS.md / ISSUES.md, which stay private.
- `--dry-run` (`autopush.py --only <slug> --dry-run`) builds, checks and audits one country and prints what would be pushed, pushing nothing.

## RESUMED, MAX SPEED (user, 2026-10-29 ~19:45 UTC: "DO AS IT SAYS ... OVERRIDE")
The user approved the decisions relayed by global-law-main-composer:
1. **Standing approval for two kinds of rewrite.** Both still need a clean check.py and audit_push, and both use --force-with-lease on the old tip. publish() approves them automatically:
   - a replacement of ONLY the final documentation commit of main, when every law commit is byte-identical (old tip's parent == new tip's parent) and every tag is unchanged;
   - a first build replacing a scaffold/placeholder main ("sources, before any law", or an unpaused "Paused, not yet law") or a thin old corpus (at most 3 law commits).

   Anything else (law commits changing, tags moving, deleting branches, visibility) still needs the user's explicit yes per repo.
2. **Push as often as possible.** The per-country autopush loop runs again (--each).
3. **Scrape at max.** Agents resume. Bulk and open data first, then Common Crawl, then Arquivo.pt, then archive.org. Robots Disallow and Crawl-delay are still obeyed. No bot-challenge, login or paywall workarounds, and no IP rotation. PUSH RULES 3 and the privacy rules still hold: nothing about fetching goes into README, SOURCES, repo/ or corpus notes.

## MOVED TO ALAN-DELL, SCALE TO ~90% (user, 2026-10-29, late: "All, ignore SA rule")
- All country folders were restored from world-law-ops `wip/<slug>-law` (the last loop snapshot before the wind-down). **Not restored:** `.cache/` and any `.tmp*` folder. Re-fetch what you need (bulk, background), and redo `.tmp` work your PROGRESS.md mentions (e.g. Colombia batch8/.tmp/99-batch8.json, Argentina batch10/.tmp/92-batch10.json). A few files written in the last minutes on the laptop may be missing. If PROGRESS.md mentions a file that isn't here, rebuild it.
- No fixed agent cap: scale to ~90% CPU/RAM. Each agent runs at most **one fetch process and one build/parse process** at a time: no `&` fan-outs, no pollers, no monitors of its own.
- Politeness is unchanged: robots Disallow, stated Crawl-delay, no bot challenges, Common Crawl ≤ 20/s machine-wide (wayback.py enforces it).

## AFRICA LIIs: ARCHIVE COPIES ALLOWED (user, 2026-10-29 late: "Allow archive copies")
This lifts the 10-29 hold for Common Crawl and Internet Archive captures of LII sites whose robots.txt blocks ClaudeBot (Kenya Law, ulii.org, zambialii.org, GhaLII, SierraLII, NamibLII, botswanalaws.com, TanzLII, MalawiLII, ZimLII …). **Live requests to those hosts stay forbidden.** Read archived captures only, at the Common Crawl pacing in wayback.py. Parts held with `*.held-robots` may be restored to PUBLISH once their text checks pass.

## SPEED RECIPES (speed experiments, 2026-10-29; details in lexifina/world-law-max-speed experiments/SPEED-B.md)

- **Argentina, InfoLEG bulk data (agent B).** Download the three zips linked from `https://datos.jus.gob.ar/dataset/d9a963ea-8b1d-4ca3-9dd9-07a4773e8c23` once (normas, normas-modificatorias, normas-modificadas; one at a time, 10 s apart for the stated Crawl-Delay; `/api/` is Disallowed): 3 requests, 132 s, 429,648 norms and 379,163 amendment links, current to about a month ago. Take dates, numbers and titles from the normas table and never fetch `verNorma.do` (792 of argentina-law's 1,622 requests were record pages parse.py never reads; all 792 are in the table with dates). Take "who amends X" from modificatorias (`id_norma_modificada == X`): it matched 4,918 of 4,922 verVinculos links, the 4 missing being norms newer than the table, so fetch `verVinculos.do` only for that last month. Texts are not in any bulk file: fetch `texto_original`/`texto_actualizado` URLs (https) with `wayback.host_get` from 12 threads (5.7 texts/s measured vs 1/s before). Net: ~27 min of fetching becomes ~4.5 min.
- **Brazil, Arquivo.pt with a length filter (agent B).** List Planalto by directory with `wayback.pt_captures('www.planalto.gov.br/ccivil_03/<dir>/', match='prefix')` (leis/: 21,991 captures in 24 s; constituicao/, decreto-lei/, _ato2019-2022/, _ato2023-2026/: under 2 s each), then **drop records with `int(rec['length']) < 3200`**: those are the "enable JavaScript" bot copies that fill most 2010-2022 captures (21 of 49 sampled). That leaves 12,744 real law-page copies over 3,289 URLs, mostly 2009 and 2023-2025. Fetch with `pt_get` from 12 threads (4.8/s measured, against archive.org's ~2/s for the whole machine; its CDX listing of the Constitution page alone took 54 s). For the original texts of amending laws, `pt_captures('www2.camara.leg.br/legin/fed/', match='prefix')` lists 14,325 clean Chamber captures in 15.5 s, including 2,544 `publicacaooriginal` pages (archive copies only: camara.leg.br's robots has an AI-bot block). Use archive.org only for Planalto states Arquivo.pt lacks (most of 2010-2022). LexML is a catalogue (URN → date and links, Crawl-delay 5, its SRU API is under the Disallowed /busca/), not a text source.
- **Peru, El Peruano discovery (agent B).** Don't list day by day, and don't go to the archives: no archive holds El Peruano's PDFs, and archived norm pages cover only 67% of 2026's laws (Common Crawl 52%, archive.org 47%, Arquivo.pt 0). Instead filter the live search by type (`&tipoDispositivo=LEY`, `DECRETO LEGISLATIVO`, `DECRETO DE URGENCIA`, … for both `tipoPublicacion=NL` and `EX`) and page a quarter or a year 20 at a time. Read `totalHits` and take ops from both `\"op\",\"<op>\"` and `/dispositivo/NL/<op>` (the page data stores repeated strings as references, so one pattern alone misses most cards). Accept a range only when rows == distinct == totalHits, otherwise halve it. Measured on 2026: 10 requests found 142 of 142 laws/D.Legs/DUs in peru-law's day cards with 0 repeats, where day lists take ~500 requests (peru-law used 2,088). Older ranges can still break (LEY 2019: 130 hits, 91 distinct), which the check catches. New issues: `wayback.sitemap_urls('https://busquedas.elperuano.pe/sitemap.xml')` lists today's norms (761) in 3 requests. diariooficial's `/DatosAbiertos/` is Disallowed by its robots.txt.
- **Albania, QBZ API (agent B).** QBZ has no bulk route: no robots.txt or sitemap (both serve the app), page size capped at 100, no all-versions or all-relations endpoint, nothing in Common Crawl or Arquivo.pt. The win is `host_get` from a thread pool instead of a fixed 3/s: 40 list pages (`/api/v1/acts?type=Ligj&size=100&page=N`, 8 threads, 5.6 s) and then `/acts/{id}/versions` + `/relations` only for items with `versions > 0` (383 laws, 766 requests, 12 threads, 47 s, 16/s, 0 throttled). 806 requests took 53 s, against 26 minutes as albania-law ran them. Write the URL list first and fetch in one background run.

## STANDING YES FOR VERIFIED REBUILDS (user, 2026-10-30 ~06:05 UTC)
Any law-history rewrite of a repo this coordinator owns (autopush OWN) is now approved in advance, if every published part has PUBLISH and check.py and audit_push are clean. Before each such push, autopush archives the replaced tip to world-law-ops `archive3/<slug>-law/<branch>/<sha>`, then pushes with --force-with-lease. Deleting branches, changing visibility and other sessions' repos still need an explicit yes.

## COMMON CRAWL PAUSED: robots.txt (hp-omen, 2026-10-31 ~19:00 local)
data.commoncrawl.org/robots.txt is now `User-Agent: * / Disallow: /`. Common Crawl is not one of the user's robots exceptions,
so do NOT fetch from data.commoncrawl.org (cc_get / cc_captures / cluster.idx reads) until the user decides. Use archive.org
(wayback.get / captures) or the official site instead. Arquivo.pt's robots.txt also disallows /wayback with Crawl-delay 5, but
Arquivo.pt is a user-approved exception (2026-10-29), so it stays allowed. Text already fetched and pinned stays usable.

## LIVE-HOST LIMIT (coordinator rule, 2026-11-01 ~09:30 local; supersedes the host_get speed recipe above)
Three hosts blocked another machine after long clean streaks (Sucuri, Incapsula after 92k requests, Imperva). For any
host WITHOUT a stated Crawl-delay: at most 1 request per 3 s and about 5,000 requests per host per day, machine-wide.
Hosts with a Crawl-delay keep it (IMPO 10 s). Spread big pulls over days, prefer bulk/API/archive copies, and STOP FOR
GOOD on any challenge page (captcha, JS check, 403 "request blocked"): record it, never retry or work around it.
`wayback.host_get` now enforces 1/3 s and raises `HostDailyCap` at 5,000/day per host. Fetch scripts that don't use
host_get must apply the same limits themselves.
archive.org (2026-11-01, coordinator): the shared wayback rate is now at most 1 request/s machine-wide, halving on
429/503, and raises `ArchiveDailyCap` at 20,000 requests a day (UTC). Scripts that fetch archive.org without the
shared client must keep the same limits.

## INFOLEG STOPPED (2026-11-01 13:53Z)
servicios.infoleg.gob.ar robots.txt answered HTTP 403 (plain Apache page) at 13:53Z after 404 earlier and 200s up to
13:43Z. Treated as a possible block under the LIVE-HOST LIMIT: NO requests to InfoLEG until the user clears it. Argentina
work continues from cached pages only.

## STF /processos DISALLOWED (coordinator, 2026-11-02)
portal.stf.jus.br robots.txt has `Disallow: /processos`. Make no request to /processos pages, live or via archive copies. Rulings are read only from allowed records (redir.stf.jus.br acórdão/paginador PDFs, Informativos). Earlier parts built from /processos pages (brazil 90-batch3, 80-proc, 70-clt, base corpus.json ADI 7047; possibly 99-batch10/zzn, 99-batch8) are listed for the user; do not change them until the user decides.

## README: WHAT, NOT HOW (composer, 2026-11-02)
A published README (and other repo-level docs, data, tools text) may say what each source is and credit it ("Internet Archive copy of <official page>, captured <date>") and what is left out and why ("not used in this record"). It must not say how anything was fetched: tools (curl), rates/requests per second, caching, build machine, robots.txt or crawl-delay notes, reachability or challenge notes. private.fetch_warnings() reports these (warn-only, logs/fetchwarn.log); it will become blocking once the sweeps finish. Fix forward: docs commit only, law commits and tags unchanged.

## FAST-FORWARD ONLY (Alan, 2026-11-02 ~18:25Z, via composer)
Published history only grows by fast-forward. The standing yes for verified rebuilds is WITHDRAWN: no rebuild-replace, no force-push, no tag moves, anywhere, unless Alan approves that repo in world-law/REWRITE-APPROVED.txt. autopush holds any rewrite and records it in world-law/REWRITE-PENDING.json. Do not reorder history to fit older laws in; corrections to published text must become new labelled correction commits once the append-only builder exists. Until then, keep building and verifying locally and write PUBLISH as before: a part whose publication would need a rewrite simply stays held (that is fine), and say so in your report.
