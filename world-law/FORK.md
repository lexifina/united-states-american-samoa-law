# Fork wave L–Z (worked Z to A): rules for each country agent

Follow `scripts/world-law/WAVE.md`. It points you to `scripts/africa-law/FANOUT.md` and `scripts/south-america-law/BRIEF.md`, including FAST ARCHIVE ACCESS (Common Crawl first) and SPEED RULE. These rules come on top.

1. **Every country gets at least a bit.**
   - If a dated history can't be sourced, first commit the current official text of the Constitution (or the main core act) as one "oldest version available" version. Set `first_law: null`, credit it to the publisher, and source it and date it from the source's own date.
   - Then build outward: amendments, then 2 core acts.
   - A country with no official online law at all (for example North Korea, São Tomé, Yemen): look harder for an official gazette, a parliament or ministry site, an archived copy, or an official UN or embassy deposit. Report honestly if nothing official exists.
2. **Commit early, commit often.**
   - Write `corpus.json` (atomically: write `.tmp`, then rename) as soon as the FIRST act parses, even if unverified. It streams to `preview` within about a minute.
   - Rewrite it after every act.
   - Write `PUBLISH` the moment the first act is verified against the official text.
   - Update `PROGRESS.md` after every step. The coordinator checks every 5 minutes, and an agent with no new file for 15 minutes counts as stuck.
3. **Language and script.** No right-to-left or CJK scripts for now: no Arabic, Hebrew, Persian, Urdu, Chinese, Japanese or Korean text (the user's scope rule, as in WAVE.md). Left-to-right scripts are fine, including Latin, Cyrillic and Vietnamese. If a country's official law exists only in a right-to-left or CJK script, stop and report; don't build it. Where an official English text exists (Sri Lanka, the Pacific states), build the English one and say so. The README is English first.
4. **Before you start, check that your repo is a scaffold.** `git ls-remote https://github.com/lexifina/<slug>-law.git` must show only `main`, and its single commit must be "<Name>: sources, before any law". If not, another session owns the country: stop and report. Check again right before writing `PUBLISH`, because another session's build may have appeared since you started. The push guard also refuses to overwrite another build.
5. **Never push. Never run autopush.** The original session's loop discovers your folder and pushes it. Never kill processes you didn't start.
6. **Budget.** At most 4 WebSearch calls. Skip any act that would take more than 45 minutes to source.
7. **Report:** at most 10 lines.

## FETCH RULE (2026-10-29 14:20 UTC, from the user: "a bunch of agents reading 10 files a minute is useless")

We measured: every agent together logged only about 1,660 requests in 6 hours, roughly 5 a minute. The slow part is agents fetching interactively, a few files per tool call, not the sites' limits. So:

1. **Fetch in bulk, in the background.** Write `fetch.py` once, over the WHOLE list of URLs you need (every version of every act), and start it as a background process with a thread pool. Then write the parser against the cache while it runs. Never fetch a page at a time from the shell.
2. **Common Crawl first, even when index.commoncrawl.org is down.** `wayback.cc_captures(...)` falls back to reading Common Crawl's cluster index from data.commoncrawl.org by byte range, and that path works. Tested at 14:15 UTC: e-seimas.lrs.lt's legal-act prefix gave 4,662 captures in 1.2 s, and legislation.govt.nz answered in 0.9 s. Fetch the captures with `wayback.cc_get` from 8–16 threads.
3. **Bulk and open-data routes before page crawling:** official dumps, open-data portals and APIs. Norway's whole corpus took 6 requests, from Lovdata's bulk tar.
4. **Direct official sites:** fetch through `wayback.host_get(url, cache)` from a thread pool. It keeps one adaptive rate per host for the whole machine, shared with the other session in `%TEMP%/gitlaw-host-rate`. The rate starts at 4 a second and climbs to 25, and on a 429, 503 or timeout it halves and pauses for 30 s. Fetch from several hosts in parallel. Two exceptions, until the user decides otherwise:
   - **robots.txt `Disallow`:** never fetch a disallowed path.
   - **Explicit `Crawl-delay`:** use one thread for that host and sleep for the delay between `host_get` calls. Examples: fsmlaw.org 30 s, IMPO 10 s.
5. **archive.org last.** It is throttled for the whole machine (about 2 requests a second, with roughly 1 in 5 answered 429), so use it only for what Common Crawl and the live site lack. Always go through `wayback.get` / `wayback.captures`, which share one rate. List a whole prefix with one CDX call before fetching anything.

6. **Hosted archives, competitors included:** check `scripts/world-law/ALT-SOURCES.md` before fetching page by page.
   - **legalize.dev repos are open data** (CC0, public domain, CC BY or a national open licence), so you can use them as a text source.
   - When you do, record the repo, the commit hash and its data licence, and credit them in the README.
   - **Re-date every version from the amending law's own in-force clause.** legalize dates by publication, not by in-force day.
   - Check today's text against the official source.
   - Check each repo's first commits, since several start from a 2026 snapshot.
   - **Constitute Project and FAOLEX are non-commercial,** so use them for discovery only and never copy their text.

## CADENCE CHANGE (2026-10-29, from the user)

- **At most 10 agents or builders in total, across both sessions.** The original session runs 8, so the fork runs at most 2.
- **No commits and no pushes anywhere, by anyone, for the next few hours.** Never run `git commit`, `git push`, or `commit-tree`/`update-ref`, in any repo or clone. Write files in `scripts/<slug>-law/` only.
- **The original session's push pass now runs once every 4 hours**, 2 countries at a time; the first is at about 04:51 UTC. So "streams to preview within a minute" (rule 2) no longer holds. Keep writing `corpus.json`, `PUBLISH` and `PROGRESS.md` as before: they go up at the next pass.
- **Verify locally instead.** Build into a scratch clone and run check.py yourself:
  `python -X utf8 scripts/gitlaw_common/build.py scripts/<slug>-law --repo <tmp clone> --docs-date <latest retrieved date>`, then
  `python -X utf8 scripts/gitlaw_common/check.py <tmp clone> --corpus scripts/<slug>-law/corpus.json`.
- **The scaffold check (rule 4) covers every branch, not just `main`.** If `git ls-remote` shows `wip`, `preview` or any branch other than `main`, or if `main` has more than the single "sources, before any law" commit (for example a "Paused, not yet law" commit), another session owns the country: stop and report.
