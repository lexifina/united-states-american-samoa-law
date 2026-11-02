# fetch_scheduler: one scheduler for every git-for-law fetcher on the machine

`gitlaw_common/fetch_scheduler.py` is the layer above `wayback.host_get`. Both scrapers use it: gitlaw-scraper-dell
and gitlaw-scraper-hp-omen.

**No limits of our own** (Alan, 2026-11-02 21:50 UTC; see "Own pacing caps removed" in
`scripts/world-law/COVERAGE-WAVE.md`). There is no daily cap, no 1-per-3 s floor, no ramp and no worker cap. A host
gets one request in flight, and the next goes out as soon as the last one answers. Only the site's own rules slow it
down:
- robots.txt Disallow and Crawl-delay;
- a rate stated in its terms or API docs (tier A);
- Retry-After;
- halving on 429/503;
- stop-for-good on a challenge;
- a night window the publisher requires.

host_get owns the per-request rules:
- the pace, with the per-host state file and lock that all processes share;
- its in-flight slots: `host_tiers.json` "concurrency", 1–8;
- D6 conditional requests;
- robots Crawl-delay;
- Retry-After;
- halving on a 429/503/time-out, a pause, 1 in flight, then gradual recovery;
- stop-for-good on a challenge (`HostStopped`).

host_get has no daily cap, floor or ramp since hp-omen's change of 2026-11-02.

The scheduler adds the rest:

| What | Where |
|---|---|
| Night windows (allowed hours per host) | `WINDOWS` in the module, a `window` in the registry, or a robots `Visit-time` |
| One shared cache: URL-keyed with ETag/Last-Modified, bodies hard-linked to content-addressed objects, 404/410 remembered | `%LOCALAPPDATA%\gitlaw\fetch-scheduler\cache` and `objects` |
| Hosts registry: tier, pace, cap and their evidence (headers, bot sign, robots excerpt), window, block | `gitlaw_common/fetch_hosts.json` (machine state, not committed) |
| Extra stops: 403 or 429 on robots.txt, a 3xx with no Location, a small captcha-form page, DDoS-Guard | the registry plus host_get's stop file |
| One request in flight per host across all processes; hosts in parallel | leases in host_get's host state, and `fetch_many` |
| Path scope and evidence for more than 1 in flight: only a listed API's paths may use host_get's slots; anything else on the host stays at 1 | `INFLIGHT` in the module, or a `max_inflight` registry field |
| get() retries only while host_get's pause (Retry-After or back-off) is at most 300 s; longer returns None | `RETRY_AFTER_MAX_WAIT` |
| Telemetry: one JSON line per request | `%LOCALAPPDATA%\gitlaw\fetch-scheduler\feed\<UTC day>.jsonl` |
| Status | `python scripts/gitlaw_common/fetch_scheduler.py status [--json \| --jsonl] [host ...]` |

## Adopting it (3 lines)

**A `wayback.host_get` caller** (most of hp-omen's fetchers). `fs.get` takes the same arguments and returns the same
values:

```python
sys.path.insert(0, r'C:/Users/alany/Documents/lexifina/scripts/gitlaw_common')
import fetch_scheduler
host_get = fetch_scheduler.get          # was: from wayback import host_get
```

**A `br_city_get.Host` caller** (the Brazilian city and SAPL fetchers). The Host keeps its cache, `requests.jsonl`,
`.404` markers, STOP file and `Stop` rules. Only its network GETs go through the scheduler:

```python
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'gitlaw_common'))
import fetch_scheduler  # noqa: E402
fetch_scheduler.adopt(H, caller='my_fetcher')   # right after H = Host(...)
```

**Many URLs over many hosts.** Each host runs at its own pace, and a stopped or capped host fails only its own URLs:

```python
for url, res in fetch_scheduler.fetch_many(urls, cache=CACHE):   # workers: one per allowed in-flight request
    ...   # res: bytes, None (403/404/410) or the exception (HostStopped, HostDailyCap, ...)
```

Set `GITLAW_SESSION=gitlaw-scraper-dell` (or `-hp-omen`) in the environment, so the feed shows who made each request.

## Rules for callers

- **`HostStopped`: never retry it.** The host is refused machine-wide from then on.
- **`HostDailyCap`:** comes only from host_get's own cap while that still exists. Resume after 00:00 UTC.
- **`NotNow(at)`:** raised only with `wait=False`. The host is outside its window or busy, so come back at `at`.
- **Leave robots.txt to the scheduler.** It reads robots.txt once a week per host and records the excerpt, so callers
  need not fetch it.
- **`GITLAW_FETCH_DRY=1`:** no network at all. Cached answers are served, and anything else raises `DryMiss`, which says
  what a live run would do. Use it to check a fetcher before a live run.

## Night windows

`WINDOWS` in the module holds the publishers' stated hours:
- RIS and data.bka.gv.at: 20:00–05:00 Vienna, plus weekends. Holidays are not modelled.
- legislation.gov.au and its API: outside 08:00–20:00 at UTC+10.
- consiglioregionale.calabria.it: its robots Visit-time, 06:00–08:44 UTC.

A registry entry can override the hours:

```json
"window": {"tz": "Europe/Vienna", "hours": ["20:00-05:00"], "all_day": ["sat", "sun"], "source": "..."}
```

`"window": {}` removes a window.

## Requests in flight per host

Every host gets 1 request in flight, machine-wide. A documented public API that states no limit and shows no
bot-management sign may have up to 8. host_get grants the slots from the host's `"concurrency"` in
`host_tiers.json`. The scheduler limits them to the API's paths, using `INFLIGHT` in the module (with evidence):
- `www.boe.es` (`/datosabiertos/api/`): 4.
- `data.sa.gov.au` (`/data/`: the CKAN API and its dataset files): 4.
- busquedas.elperuano.pe is not listed: no official API documentation was found.

Both hosts also have `"concurrency": 4` in `host_tiers.json`. A host that is in `host_tiers.json` but not in
`INFLIGHT` gets host_get's value on every path.

A person can set or override the limit in the registry:

```json
"max_inflight": {"n": 6, "paths": ["/api/"], "evidence": "API docs at ... state no limit (checked 2026-11-05)"}
```

`"max_inflight": {}` removes the path scope. Even on a listed host, other paths (crawled HTML) stay at 1. A host stays
at 1 for good once a bot-management sign is seen. host_get drops it to 1 after a 429, 503 or time-out, until its
throttle has recovered. The registry's `inflight_now` shows the current limit and why.

## Lifting a block (people only)

A blocked host stays refused until a person edits its entry in `fetch_hosts.json` and adds a note:

```json
"lift_note": "2026-11-05 publisher allowlisted our IP (email from ...)", "lifted_by": "Alan"
```

On the next call, the scheduler moves the block into `history`. It also renames host_get's stop file to
`*.lifted-<time>`. A `"tier": "stop"` in `host_tiers.json` has to be removed there separately. An entry with no note
stays blocked.

## Contract with wayback.py

The scheduler uses these host_get internals:
- `_host_locked`, `_policy`, `_stop_host`, `_stop_file`, `_note_robots`, `_parse_robots` and `_bot_signal`;
- `_cached`, `_meta_file` and `_host_of`.

It also wraps `_curl_h` to see each response's status and headers. The extra stop rules apply only to calls made
through the scheduler. If wayback.py renames any of these, `test_fetch_scheduler.py` fails.

Tests (local stub servers, no network):

```
python -m unittest scripts/gitlaw_common/test_fetch_scheduler.py -v
```
