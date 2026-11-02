# Speed experiments C (2026-10-29, 23:05 to 00:10 UTC)

Three questions: why the machine-wide fetch rate fell after the afternoon peak, whether a fetch/parse pipeline helps,
and whether `host_get` halves the rate of hosts that are slow but healthy. Nothing in `gitlaw_common/wayback.py` or
any agent's files was changed. Everything here is a proposal plus measurements.

## 1. The rate drop (`rate_drop.py`, `rate_drop.json`; read-only over every `scripts/**/requests.jsonl` and `%TEMP%/gitlaw-host-rate`)

Logged requests per minute, whole machine, in 10-minute buckets (logs record finished requests only, not failures):

| UTC | req/min | Who |
|---|---|---|
| 21:30 | 609 | re-fetch after the move to alan-dell: netherlands 1,582, chile 898, tanzania 853, argentina 843, paraguay 467, peru 410 |
| 21:40 | 369 | peru, tanzania, belgium, argentina |
| 21:50 | 259 | belgium, colombia, peru, guinea |
| 22:00 to 23:10 | 36 to 113 (about 80) | peru, albania, ACT, mexico, uruguay |

**Cause: the big queues ran out, and the agents moved on to building and checking; nothing broke.** The 21:30 to 22:00 peak (about 410/min
averaged over the half hour) was eight agents refilling their `.cache` from bulk sources (raw.githubusercontent.com
1,412, InfoLEG 1,256, LeyChile 1,171, officielebekendmakingen 893, BACN 733, Senado CO 696) after the restore. These
hosts all sat at host_get's 25/s cap with almost no pushback. Once those lists were done, the same agents went on to
build and check (`check.py`, `test_corpus.py` and `push_clean.py` are what's running now). What's left is
fetching that is slow by nature:

Last 30 minutes (22:43 to 23:13), per host:

| Host | req/min | Why it is slow |
|---|---|---|
| qbz.gov.al (albania) | 23.3 | own fetcher; fine |
| data.commoncrawl.org | 15.7 | well under the 20/s cap: few agents use it now |
| web.archive.org | 13.0 | **shared limiter at its floor: rate 0.30/s, 900 throttles against 2,402 ok (27%)**; mexico pulls 1 to 2 MB PDFs through it |
| busquedas.elperuano.pe (peru) | 11.9 | finished at 23:02 (3,560 ok, 251 throttles, rate 21/s) |
| www.impo.com.uy (uruguay) | 4.9 | robots `Crawl-delay: 10` (6/min at most): obeyed |
| www.legislation.act.gov.au (ACT) | 4.6 | robots `Crawl-delay: 10`: obeyed |
| www.lexml.gov.br | 0.4 | rate 1.0 with 14 throttles out of 57. Robots says `Crawl-delay: 5`, which host_get does not read (see below) |

Per agent, last 30 minutes: albania 23.3, peru 21.4, ACT 9.2, mexico 8.9, uruguay 4.9, cyprus 3.8, latvia 1.2,
tanzania 0.9, bolivia 0.6, brazil 0.4.

Throttled or paused hosts in the state files: archive.org (0.30/s, paused in bursts), arquivo.pt (0.50/s, 10
throttles out of 35), lexml (1.0/s), gacetaoficial.gob.ve (0.78/s, 13 out of 391), a dozen Sierra Leone and Ghana
ministry hosts at 2.0/s after one failure each (probes of dead hosts). Nothing was in an active pause at 23:13
except archive.org.

**Idle between fetch and parse** (last 60 minutes; gaps over 60 s between an agent's logged requests):

| Agent | Requests | Idle (s of 3,600) | Longest gap |
|---|---|---|---|
| cyprus | 116 | 3,116 | 1,600 s |
| latvia | 50 | 2,978 | 812 s |
| bolivia | 34 | 2,618 | 1,967 s |
| tanzania | 67 | 2,150 | 273 s |
| brazil | 51 | 2,088 | 758 s |
| romania | 118 | 1,136 | 643 s |
| sierra-leone | 14 | 939 | 414 s |
| mexico / ACT / uruguay | 396 / 584 / 305 | 383 / 377 / 200 | under 200 s (continuous fetchers) |

The agents that fetch little do so in bursts with 5 to 30 minutes of silence between them: fetch, stop, parse, think,
fetch again. That is the gap `pipeline.py serve` is for (section 2).

Two side findings:
- **host_get does not read robots.txt.** lexml.gov.br states `Crawl-delay: 5`, but host_get starts every host at 4/s, and
  lexml's state shows 1.0/s after 14 throttles: five times the stated delay or more. Any agent that calls host_get directly on a Crawl-delay host breaks
  the rule. `pipeline.py` reads robots.txt once per host and spaces requests to the stated delay for the whole machine.
- **archive.org's limiter has the same timeout rule** (`fetch()` counts curl code 0 as pushback, with a fixed 120 s
  `--max-time`). Mexico's 1 to 2 MB PDFs at archive.org's usual 20 to 100 KB/s can pass 120 s, so some of the 900
  "throttles" are probably slow downloads, not 429s. The logs record no failures, so this wasn't measured: the
  `classify()` rule from `hostget2.py` would apply to `fetch()` unchanged.

## 2. Pipelining (`pipeline.py`, `bench_pipeline.py`, `bench_pipeline_*.json`)

`pipeline.py` has two forms:
- `stream(urls, fetch, threads)`: a generator that yields `(url, body)` as each fetch lands, while the pool keeps
  fetching.
- `serve CACHE` / `enqueue()` / `ready()`: an agent's one background fetch process. It fetches every URL appended to
  `CACHE/queue.txt`, from any later tool call, and writes `ready.jsonl`. It obeys robots Disallow and Crawl-delay,
  uses one lane per Crawl-delay host, sends archive.org through `wayback.fetch`, and exits after 10 idle minutes.

Benchmark: 150 consolidated Canadian Acts per mode from raw.githubusercontent.com (justicecanada/laws-lois-xml; about
10 MB per mode; sets are disjoint and size-balanced). Parse is a real ElementTree parse of every Section, hashed and
written out. "Heavy" repeats the parse 12 times, standing in for PDF or HTML clean-up. 12 threads. Wall seconds per run:

| Mode | Light parse (≈1 s CPU) | Heavy parse (≈8.5 s CPU) | First doc parsed at |
|---|---|---|---|
| serial (fetch one, parse it, next) | **82.1** | – | 0.4 s |
| batch (fetch all, then parse all) | 12.5, 10.2 | 16.2, 21.2, 21.1 | 8 to 12.6 s |
| `stream()` in one process | 10.0, 9.7 | 20.2, 19.0, 13.2 | 0.3 to 0.8 s |
| `serve` process + `ready()` | 10.9 | 13.8, 19.5 | 1.6 to 2.3 s |

(The machine was busy with other agents' builds, hence the spread.)

- **The big gain is serial to background: 82 s down to about 10 s, 7 to 8 times faster.** That is the pattern of an
  agent fetching a few files per step.
- Overlapping parse with fetch saves at most the parse time: about 1.5 s of 11 for light parsing (13%), and
  2 to 3 s of about 19.5 on average for heavy. It's noisy.
- **With CPU-heavy parsing, `stream()` in the same process can lose:** parse CPU went from 8.5 to 12 to 14 s because
  12 fetch threads (curl spawns, file writes) share the GIL with the parser. For heavy parsing use the `serve` process.
- The first result arrives in under a second, against 8 to 12 s for batch. An agent can start writing its parser on
  real data at once.

The lever for agents isn't the in-process overlap but section 1's idle gaps. Start `pipeline.py serve` once in the
background, enqueue URLs the moment they're known, and parse from `ready()`. Fetching then runs through the 5 to 30
minutes the agent spends thinking.

## 3. Timeouts on slow-but-healthy hosts (`hostget2.py`, `bench_timeout_sim.py`, `bench_timeout_real.py`)

`host_get` counts `code == 0` (any curl failure, timeouts included) as pushback, and curl runs with a fixed `--max-time 90`.
With 16 threads on a host whose total bandwidth is low, each download gets 1/16 of it. Big files pass 90 s, curl kills
them and the bytes are lost. host_get halves the rate, pauses everyone for 30 s, and downloads the same file again.

`host_get2` (same state files, cache and log):
1. curl aborts on a **stall** (`--speed-limit 1024 --speed-time 60`, `--connect-timeout 30`, a 1,800 s ceiling), not on total time.
2. Pushback = 429/503 (honouring Retry-After), a refused, reset or empty connection (curl 7/35/52/55/56), or no first
   byte before the stall limit. A transfer that was receiving bytes is "slow": no halving, no pause.

Local simulation (a healthy server sharing 1 MB/s across all downloads, never 429; 12 files of 4 MB and 20 of 150 KB;
16 threads; times scaled 4.5x down: 20 s max-time, 13 s stall):

| Policy | Wall | Useful MB/s | Bytes thrown away | curl tries | "Throttles" | Final rate |
|---|---|---|---|---|---|---|
| current | 166.5 s | 0.31 | **48.4 MB of 99.4 sent (49%)** | 54 | 22 (all false) | 12 → 1.44 |
| proposed | **53.4 s** | **0.96** (the link's cap) | 0 | 32 | 0 | 12 |

**3.1 times faster, with half the host's bandwidth no longer wasted.** At 2 MB/s with 10 big files neither policy
timed out, and the two were the same (22.0 vs 22.3 s). Under real pushback (the server answers 429 above 4 open downloads)
both back off alike: current 90.5 s and 12 throttles, proposed 89.6 s and 13 throttles. The fix keeps the politeness.

Real host, the Greek ΦΕΚ store (16 threads, production timeouts, 40 PDFs per policy): tonight it served
**2.6 MB/s** (the lab measured 0.5 MB/s this afternoon), so no download came near 90 s. Both policies gave 0
throttles and 40 of 40 files, and host_get2 cost nothing extra (40 tries for 40 files). The failure needs
`threads × file size / bandwidth > timeout`. It shows up whenever such a host slows down (as this afternoon),
and on archive.org PDFs.

**Proposed change to wayback.py (for the owner to apply):** use `hostget2._curl2` and `classify()` in `host_get` and
in `fetch()`. Optionally, have `host_get` call `robots_rules()` once per host and turn a stated Crawl-delay into the
host's spacing.
