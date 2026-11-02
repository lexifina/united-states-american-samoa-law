# First builds for US states (Alan, 2026-10-30)

Goal: one public repo per state, `lexifina/united-states-<state>-law`, with a real first build. Spend about 30–45 minutes
per state and don't aim for completeness. Follow `FIRST-BUILDS.md` (steps 2–6 and Phase 3) as well.

## Per state

1. **Check the repo.** Run `git ls-remote https://github.com/lexifina/united-states-<state>-law.git`.
   - If it exists with law on main, skip the state.
   - If it doesn't exist, create it through the GitHub API with the stored git credential, never printing the token:
     POST `https://api.github.com/orgs/lexifina/repos` with
     `{"name": "united-states-<state>-law", "private": false, "description": "<State> law as git history"}`.
     It is public like the other `united-states-*` repos.
   - Push a scaffold first commit, "United States (<State>): sources, before any law", containing README.md and
     SOURCES.md.
2. **Source.** Use the legislature's official code site, or the state's official statute publisher.
   - Check robots.txt and the terms first, and record the licence and attribution in the LICENSE.
   - Statute text itself is not copyrightable (Georgia v. Public.Resource.Org, 2020). Annotations published under a
     state copyright claim are, so take the statute text only and never the annotations.
   - Prefer bulk downloads and XML or JSON APIs (see world-law-max-speed SPEED RECIPES).
   - Never get round a bot challenge, a WAF or a login.
3. **Build.**
   - Start with the state constitution.
   - Then 1–3 core titles: the criminal code, a property, civil or contracts title, and the corporations title.
   - Use "oldest version available" if there's no dated history. Add dated versions where the official site has
     point-in-time or session-law history.
   - Look at `united-states-california-law`, `-utah-law` and `-indiana-law` for the layout.
4. **Check and publish.**
   - Build into an empty folder `C:\Users\alany\Documents\united-states-<state>-law-build`.
   - Run `check.py`: it must report 0 mismatches and 0 trailer errors.
   - Publish with `push_clean.py ... --main` straight after each part.
   - Set `GITLAW_NO_CHECKOUT=1`, and run build.py and check.py at BelowNormal priority
     (`start /belownormal`, or psutil).

global-law adds each state automatically under `united-states/<state>/acts` once main has real content.

## Never

- Commit to the main lexifina repo.
- Force-push without a lease.
- Change a repo's visibility.
- Use Constitute Project.

## Processes (added 2026-10-30, after collateral kills)

Never kill a process you did not start. Record the PID of every background job you launch, and only ever stop those exact PIDs. Never kill by guess, by name, or by working-directory match. Other sessions run fetches and builds on this machine.

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
