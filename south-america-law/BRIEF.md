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
