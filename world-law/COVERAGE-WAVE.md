# Coverage wave (Alan, 2026-10-30)

Goal: maximum coverage of the overall global-law repo, as fast as the machine allows. Hold CPU steady at about 90%.

## Ramp, don't jump

- **Shared load signal:** `%LOCALAPPDATA%\gitlaw-cpu.log` is written once a minute by global-law-main-composer. Each line is `<UTC time> cpu1=<1-min avg %> cpu5=<5-min avg %> ram=<%>`. Read the last line; don't run your own pollers.
- **Add load** only while the 5-minute average is under 80%. Add at most 2 agents or workers per session per 10 minutes.
- **Hold** while it's between 80% and 92%.
- **Back off** if the 5-minute average is over 95%, or RAM is over 85%: stop starting new work and let one job finish before starting the next.
- **Priority:** every build, check, OCR or parse job runs at BelowNormal.

## Who does what (to avoid collisions)

- **gitlaw-scraper-hp-omen:** national corpora.
  - First, deepen the thin ones: constitution-only or metadata-only countries get their core codes (FIRST-BUILDS Phase 2).
  - Then the full national corpus with dated history wherever the source has it.
- **gitlaw-scraper-dell:** sub-national.
  - First, the remaining Canadian provinces and territories and the Australian states and territories.
  - Then the other federations, one repo per unit as `<country>-<unit>-law`: German Länder, Swiss cantons, Indian states, Brazilian states, Mexican states and Austrian Länder.
  - Then deepen the thin US states (more titles).
- **global-law-main-composer:** the global-law pointer loop, the CPU log, and any agents it adds itself.

## Claim before you start

- Before working on a repo, create `scripts/world-law/claims/<repo>.txt` atomically (exclusive create, for example `open(p, 'x')`), containing your session name and the UTC time.
- If the file already exists, pick another repo.
- Delete your own claim when the repo is published or blocked.

## Rules that still apply

- FIRST-BUILDS.md and US-STATES.md, including the Processes rule (stop only your own PIDs).
- check.py must report 0 mismatches and 0 trailer errors; publish with push_clean --main.
- Never get round a bot challenge, a WAF, a login or a geo-block. Obey robots.txt and Crawl-delay. Common Crawl stays at no more than 20 requests a second machine-wide.
- Never commit to the main lexifina repo. Never change a repo's visibility.
- New repos are public, created through the API as in US-STATES.md.

## Stream commits (Alan, 2026-10-30, as in the South America run)

- **Work in parts:** agents write `corpus.d` parts (one per constitution, statute or title, or about 50 acts), and drop `<part>.PUBLISH` once a part is verified.
- **Autopush publishes them:** each scraper runs an autopush loop over the repos it has claimed, every 20–60 s at BelowNormal. The loop builds, checks, audits and pushes main within a minute of each new PUBLISH.
  - hp-omen runs `scripts/south-america-law/autopush.py`, with OWN taken from its claims.
  - Dell runs its own copy, with OWN taken from its claims.
- **No hand runs:** don't wait for push_clean by hand, and don't batch up a whole country.

## New hosts: start slow (2026-10-30, after Queensland tripped Imperva)

Open every new host at one request at a time, several seconds apart. Only speed up after about 50 clean responses, and never past its Crawl-delay. Never copy another host's pace or parallelism: a 4-wide burst of about 26 requests in 6 minutes set off a WAF on legislation.qld.gov.au. If a challenge page appears (even with HTTP 200), stop that host for good and record it for a publisher email.

## Cap parallelism (2026-10-31, after one uncapped pool took ~9 cores)

Never start a multiprocessing pool, thread pool or `xargs -P` without an explicit cap: at most 2 workers per agent, at BelowNormal, and pause while cpu5 > 90 (see %LOCALAPPDATA%\gitlaw-cpu.log). Defaults such as `Pool()` use every core.

## Common Crawl paused (2026-10-31 19:00 UTC)

data.commoncrawl.org/robots.txt now reads `User-Agent: * / Disallow: /`. Do not fetch Common Crawl records (cc_get, or any data.commoncrawl.org URL) until Alan decides. CDX index lookups on index.commoncrawl.org are allowed (its robots is empty), but they are useless without the records. Use live official sources, or other archives whose robots allow it.

## Long runs: stay gentle (2026-11-01, after Sucuri/Incapsula/Imperva blocks on azleg.gov, SCJN and QLD)

Three hosts challenged us after long clean runs (SCJN after 92,444 requests). For any host without a stated Crawl-delay:
- keep at most 1 request every 3 s;
- cap each host at about 5,000 requests a day;
- spread big pulls over several days;
- prefer bulk files or APIs.
On any challenge or WAF page, stop that host for good and add it to Alan's held list.
