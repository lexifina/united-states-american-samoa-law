# Africa fan-out: rules for each country agent

Read these first:
- `scripts/africa-law/BRIEF.md`, and everything it tells you to read, including the Wayback rule in `scripts/south-america-law/BRIEF.md`.
- `scripts/africa-law/PEACHJAM.md` and `PROGRESS.md`, to see how far the shared adapter has got.

## Using the shared adapter

- **Read-only.** `scripts/africa-law/peachjam.py` belongs to gitlaw-africa-peachjam. Import it, and never edit it.
- **Your own extensions** go in `scripts/<slug>-law/` (for example `lii.py`), wrapping or subclassing what you need.
- **Fixes the adapter itself needs:** write them, with the exact problem, to `scripts/africa-law/ISSUES-<slug>.md`, and work around them locally meanwhile.
- **Unfinished parts:** if a piece you need is still missing (discovery, units, credits), write it in your own folder. Note in your PROGRESS.md which parts the adapter can adopt later.

## Sources

- **LIIs:** read only archive.org `id_` captures, pinned. Never fetch an LII's own document pages, and never touch its bot challenge.
- **Rate:** at most 1 archive.org request per 3 s per agent, since about 15 agents share archive.org. Fetch only what you build, and cache everything.
- **Uneven coverage:** Wayback has some expressions and not others. Build only expressions that are archived. Every version must be complete and dated, and the README lists what is missing.
- **Government sites:** gazettes and parliament PDFs with a text layer are fine directly, at 1 request per second.
- **No OCR:** scans are left out and named.

## Building

- **Phase 1:** the Constitution plus 2 core acts, chosen by what the archive actually holds.
- **PUBLISH:** write it once today's text equals the latest official or archived expression, and every version comes from its own dated source.
- **Pushing:** autopush pushes within about a minute. Watch `BUILD_STATUS.json`, never push yourself, and never kill processes you didn't start.

## Reporting

Keep `scripts/<slug>-law/PROGRESS.md` current. End with a report of at most 10 lines.

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

- **Arquivo.pt (user-approved 2026-10-29, max speed):** `wayback.pt_captures(url, match="prefix")` lists up to 100,000 captures in one call (5,000 Planalto captures in 1 s), and `wayback.pt_get(rec)` fetches the raw page (40 pages in 7 s from 12 threads, no throttling). It uses host_get's adaptive rate. Try it right after Common Crawl and **before archive.org**, above all for Lusophone and Latin American official sites (Planalto, IMPO, ...). Record it as a source ("Arquivo.pt, capture <ts>").
- **Never publish personal emails (user rule 2026-10-29).** The machine's global git email is personal, so any commit made outside autopush or build.py must set `user.email` explicitly (Lexifina <slug-law@lexifina.com>). Agents still never commit or push.
