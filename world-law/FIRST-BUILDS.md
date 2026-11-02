# First builds for the empty country repos (2026-10-29, from Alan)

Goal: no lexifina country repo should still be the bare scaffold ("last updated 57 years ago"). Each country gets a small,
real first build: the current constitution, or a few core statutes, with proper dates. Time-box each country to about
15 minutes. Don't aim for completeness.

## For each country `<slug>` (the repo is `lexifina/<slug>-law`)

1. **Check the remote first.** Run `git ls-remote https://github.com/lexifina/<slug>-law.git`.
   - `main` must be the scaffold ("sources, before any law") or a "Paused, not yet law" commit, and there must be no
     other branches. A `wip` branch made by world-law@lexifina.com snapshots is fine.
   - If `main` already holds law, or another session's branch is there, skip the country and report it.
2. **Find an official source fast.** Try, in this order:
   - the country's entry in `scripts/world-law/register.json`;
   - the parliament, the official gazette or the ministry of justice;
   - Common Crawl or archive.org copies of those pages (`scripts/gitlaw_common/wayback.py`: `cc_captures`, `cc_get`,
     `get`; for live sites, `host_get`).
   Rules: never touch a bot challenge or a login; obey robots.txt `Disallow` and a stated `Crawl-delay`; keep Common
   Crawl at no more than 20 requests a second machine-wide (wayback.py paces it); no OCR (text-layer PDFs and HTML only).
3. **Language:** any script is fine for this job; Alan lifted the right-to-left/CJK hold. Use the official language and
   say so in the README, which is English first. Where an official English text exists, prefer it.
4. **Build** in `C:\Users\alany\Documents\lexifina\scripts\<slug>-law\`, following `scripts/gitlaw_common/SCHEMA.md`
   (look at `scripts/norway-law/` or `scripts/new-zealand-law/` for a model):
   - write `corpus.json`;
   - if there's no dated history, use one "oldest version available" version (`first_law: null`), dated from the source's
     own date and credited to the publisher;
   - add `repo/README.md`, `repo/LICENSE` (the source's terms and attribution) and `repo/jurisdiction.json`;
   - build into an empty folder `C:\Users\alany\Documents\<slug>-law-build` (run `git init` first) with
     `python -X utf8 scripts/gitlaw_common/build.py scripts/<slug>-law --repo <build> --docs-date <YYYY-MM-DD>`, which also
     writes REPRODUCE.md;
   - then run `python -X utf8 scripts/gitlaw_common/check.py <build> --corpus scripts/<slug>-law/corpus.json`. It must
     show 0 mismatches and 0 trailer errors.
5. **Publish straight away:** run
   `python -X utf8 scripts/gitlaw_common/push_clean.py C:\Users\alany\Documents\<slug>-law-build <slug>-law --main`.
   It runs audit_push (no private files, fetch scripts, home paths or scraping notes), takes a private snapshot to
   world-law-ops, pushes `main` with a lease, then pushes tags. Alan's standing yes covers replacing a scaffold or
   "Paused" main with a fully checked build. If audit_push reports findings, fix them and push again. Never use `--force`.
6. **If a country is blocked** (only scans, a bot challenge, a login, or no official text online): don't publish law.
   Write `scripts/<slug>-law/PROGRESS.md` (it stays private) saying what you tried and what's missing, and move on.
   For licence-paused countries (marshall-islands, brunei), publish no legal text.

## Never

- Commit to the main lexifina repo.
- Force-push without a lease, delete a branch or repo, or change a repo's visibility.
- Put fetch scripts, PROGRESS notes or speed tooling in a public repo. push_clean's audit enforces this.

## Phase 3: no empty repo (Alan, 2026-10-30)

Every blocked or licence-held country publishes something legally safe today. Try these in order and take everything
that works:

**a) Official texts its copyright law exempts.**
- Many copyright acts exclude laws, decrees and court decisions from protection (Berne Art. 2(4)).
- Read the country's own copyright act. It's often on WIPO Lex, but treat that as a pointer; the official gazette or
  ministry copy is better.
- If laws are exempt, quote the clause in the LICENSE and build those texts as normal acts.
- The copyright act itself is often the first text you can publish.
- Never for the licence-held countries (Marshall Islands, Brunei). Never where the site's own terms forbid reuse,
  unless the national act clearly exempts the laws; if so, record both in LICENSE.

**b) A law catalogue: facts only, no text.**
- Make one act, slug `catalogue`, with one unit per law: title, number, enactment date, gazette citation, official URL.
- Each version adds the laws enacted on one date, dated that day, so the history is real. Credit it to a law key such
  as `catalogue-<date>`. A batch of entries added on the same date is fine.
- Sources: the official gazette's or parliament's index, FAOLEX/NATLEX metadata records, Wikidata.
- Copy facts only, never their descriptive text.

**c) Treaty actions.**
- Make one act, slug `treaties`, with one unit per treaty: name, action (signature, ratification or accession), date,
  depositary.
- Date each version by the action date.
- Sources: UN Treaty Collection, ILO NORMLEX, WIPO-administered treaties.

**d) Open facts.**
- Make one act, slug `legal-system`, from Wikidata (CC0): legal system, courts, official gazette, constitution
  adoption date.
- Date it by the Wikidata fact's own date where there is one, otherwise by the retrieval date as the oldest version
  available.

**e) An English translation by a government or IGO, published under terms that allow reuse.**

Never use Constitute Project (CC BY-NC).

**f) Technical blocks: still try for real text (lexifina-46 for Alan, 2026-10-30).**
- **Scans with no text layer, where the terms allow reuse:** OCR is now allowed for these. Tesseract isn't installed on
  this machine. If you can install it (`winget install UB-Mannheim.TesseractOCR`, plus the traineddata for the
  language you need) within the time box, OCR the scan; otherwise note it as the next step.
  - Mark OCR'd text as such in the README and in `decisions`.
  - Spot-check the OCR against the scan before publishing.
- **A third-party copy of a public-domain official text is fine** where the national copyright act exempts laws.
  - Credit the host as the source of the bytes, and quote the exemption clause in LICENSE.
  - Ethiopia: check Proclamation 410/2004 first.
- **Nepal:** recover the broken legacy font (Preeti or Kantipur) with an open-source Preeti-to-Unicode mapping.
- **WAF, geo-block and Cloudflare blocks:** never get round them. Use (b)–(e) instead, plus any OGL or IGO-hosted copy
  that exists.

The README must say plainly what the repo holds: for example, "metadata only, no law text, because <reason>".

Build, run check.py and publish with push_clean.py --main exactly as in steps 4 and 5. Alan's standing yes covers
replacing a scaffold or "Paused" main. Push each country as soon as it lands.

## Phase 2: core statutes (Alan, 2026-10-30)

Alan wants countries with only a constitution to gain their core statutes: penal, civil and commercial codes, or the
nearest equivalents.

- **Time:** about 15 minutes per statute. Skip any statute you can't source in that time.
- **Where:** add each statute as an act in `scripts/<slug>-law/corpus.json`, with the same dating rules as in step 4.
  Keep the constitution exactly as it is.
- **Publish:** rebuild into an empty build folder, run `check.py`, then publish with `push_clean.py --main`. Alan's
  standing yes lets a fully checked build replace a thin corpus, so the extra law commits are covered. push_clean
  leases on the current main.
- **Order:** publish after each statute is added. Don't wait to batch several statutes together.

global-law picks up each new `main` automatically within about a minute (global-law-main-composer's pointer loop).

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
