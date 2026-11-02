# Speed sections copied from the shared briefs (snapshot 2026-10-29)

---

# From south-america-law/BRIEF.md

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

---

# From africa-law/FANOUT.md

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

## CADENCE CHANGE (2026-10-29): read the section of that name at the end of scripts/south-america-law/BRIEF.md. No pushes for hours; verify builds locally.

## SPEED RULE 2 (user, 2026-10-29 14:30 UTC): replaces SPEED RULE and per-agent sleeps
The user wants fetching accelerated; agents reading a few files a minute is not acceptable.
- **Official sites:** use `wayback.host_get(url, cache)` from a thread pool of 8-16. One adaptive rate per host, shared by every process on the machine: it starts at 4 requests a second, climbs to 25, and halves with a 30 s pause only when the host answers 429/503 or times out. Drop your own sleeps and fixed rates. Hosts whose robots.txt states a Crawl-delay (IMPO 10 s) keep it, with one thread: get round a slow host through Common Crawl or archive copies, not faster live requests. robots.txt Disallow is always obeyed. LeyChile test: 60 pages in 9 s, no pushback.
- **Common Crawl works again:** index.commoncrawl.org is still down, but `wayback.cc_captures()` now reads Common Crawl's index files from the data host (cluster.idx, cached once per crawl for the whole machine, ~120 MB) and `cc_get()` reads pages by byte range with no rate limit: use 16 threads. Try it before archive.org: 140 MalawiLII records in under 10 s.
- **archive.org** stays at its shared adaptive rate (~2 a second for the whole machine; it answers 429 above that). Use it only for what Common Crawl lacks. Do not rotate IPs or proxies.
- Never get round a bot challenge, login or paywall.
- **Fetch in bulk, in the background:** write the list of URLs first, then run one fetch.py with a thread pool (host_get / cc_get) in the background and parse while it runs. Never fetch a handful of files per tool call; across all agents that averaged about 5 requests a minute today.
- **Bulk and open-data routes first** (dumps, APIs, open data), then Common Crawl, then live pages, and archive.org last.
- **Alternative hosted archives:** read scripts/world-law/ALT-SOURCES.md first. The legalize.dev repos (open-data licences) hold reconstructed histories, e.g. Belgium from Justel. Constitute and FAOLEX are for finding sources only.

---

# From world-law/WAVE.md

## CADENCE CHANGE (2026-10-29): read the section of that name at the end of scripts/south-america-law/BRIEF.md. No pushes for hours; verify builds locally.

## SPEED RULE 2 (user, 2026-10-29 14:30 UTC): replaces SPEED RULE and per-agent sleeps
The user wants fetching accelerated; agents reading a few files a minute is not acceptable.
- **Official sites:** use `wayback.host_get(url, cache)` from a thread pool of 8-16. One adaptive rate per host, shared by every process on the machine: it starts at 4 requests a second, climbs to 25, and halves with a 30 s pause only when the host answers 429/503 or times out. Drop your own sleeps and fixed rates. Hosts whose robots.txt states a Crawl-delay (IMPO 10 s) keep it, with one thread: get round a slow host through Common Crawl or archive copies, not faster live requests. robots.txt Disallow is always obeyed. LeyChile test: 60 pages in 9 s, no pushback.
- **Common Crawl works again:** index.commoncrawl.org is still down, but `wayback.cc_captures()` now reads Common Crawl's index files from the data host (cluster.idx, cached once per crawl for the whole machine, ~120 MB) and `cc_get()` reads pages by byte range with no rate limit: use 16 threads. Try it before archive.org: 140 MalawiLII records in under 10 s.
- **archive.org** stays at its shared adaptive rate (~2 a second for the whole machine; it answers 429 above that). Use it only for what Common Crawl lacks. Do not rotate IPs or proxies.
- Never get round a bot challenge, login or paywall.
- **Fetch in bulk, in the background:** write the list of URLs first, then run one fetch.py with a thread pool (host_get / cc_get) in the background and parse while it runs. Never fetch a handful of files per tool call; across all agents that averaged about 5 requests a minute today.
- **Bulk and open-data routes first** (dumps, APIs, open data), then Common Crawl, then live pages, and archive.org last.
- **Alternative hosted archives:** read scripts/world-law/ALT-SOURCES.md first. The legalize.dev repos (open-data licences) hold reconstructed histories, e.g. Belgium from Justel. Constitute and FAOLEX are for finding sources only.
