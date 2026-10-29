---
name: uk-law-history
description: Git for UK law (2026-10-28) — /watch/uk-law reader + public repo alan-yahya/uk-law-history built from legislation.gov.uk by scripts/uk-law-git/ukhistory.py; SEND provisions only so far
metadata:
  node_type: memory
  type: project
  originSessionId: e5d01b16-6536-4761-940c-8c544987e055
  modified: 2026-10-28T13:24:45.767Z
---

On 2026-10-28 the user's goal was: UK law only, a new /watch category page, prior art such as c3e/grundgesetz researched in depth, a public git repo carrying our design, using the data we already have.

**Built**

The data is the SEND provisions we already use (send_law_sources): Children and Families Act 2014 ss. 19, 21, 36, 37 and 42, and SEND Regulations 2014 regs 6, 11, 12 and 13. That is 26 versions and 11 law commits.
- `scripts/uk-law-git/ukhistory.py` uses only the standard library. Commands:
  - `build` reads every point-in-time version and the /changes/affected register into history.json.
  - `repo` writes the commits.
  - `check` re-fetches every version and compares it.
- Alongside it: `test_ukhistory.py` (13 tests on fixtures), `README.md` and `LICENSE.md` (the public repo's), and `RESEARCH.md`, which holds the prior-art findings and decisions.
- Repo: https://github.com/lexifina/uk-law-history (moved from alan-yahya), **made PRIVATE on the user's ask 2026-10-28 ("for now")**, local checkout at ~/Documents/uk-law-history. It follows us-code-history's conventions:
  - Author is the instrument, at `<uri>@legislation.invalid`.
  - Commits are dated the in-force date at noon London time.
  - Committer is `Lexifina <uk-law-history@lexifina.com>`.
  - The last commit adds the README, the tools and data/history.json.
  - Rebuilding means re-running `repo` into a fresh directory and force-pushing; the output is deterministic.
- The site is `saas-webpage/app/watch/uk-law/`: an overview, a page per instrument or provision through `[...path]`, a UkReader reusing the US watch.module.css, and the rail entry on /watch. It is noindex. **Released 2026-10-28** in site commits 474ecb3 + 4964ccb, pushed to main. The user chose "commit everything", so the release also shipped other sessions' Grundgesetz, rules-as-code and US reader work. While the repo is private, `REPO_PUBLIC = false` in `_data/load.ts` hides every repo link on the site; flip it when the repo is made public again.

**Gotchas**
- GitHub push protection takes legislation.gov.uk keys (`key-` plus 32 hex digits) for Mailgun keys. The build strips the prefix, through `effect_id()`, in every output and fixture. Never bypass the block.
- The publisher tidies punctuation between versions, so reversion matching ignores trailing punctuation.
- Another session builds /watch/grundgesetz and edits /watch/page.tsx at the same time; leave its entries alone.

Shared rules for all corpora: [[git-for-law]]. Repo now also has REPRODUCE.md + RESEARCH.md (commit b188f3f, appended, not force-pushed, because global-law pins `gb/uk/send`). A rebuild must pass `--extra REPRODUCE.md=… RESEARCH.md=…` (sources in scripts/uk-law-git/).

Related: [[us-code-history]], [[git-for-the-us-code-blog]], [[global-law-repo]].

**Deep test (2026-10-28).** The findings are in [[git-for-law]] under "Testing findings". Appended commits since then: e295f40 (`on` command, non-empty guard) and 9ed31ef (org move, README notes).

**Pending, and needs the user's go-ahead plus a force-push coordinated with gitlaw-global:**
- extent read at every level
- no `In-force:` trailer on Royal Assent or made commits
- reversion: an "expired" line and a `Restores:` trailer
- parent-scope effects (Pt. 3 modified by S.I. 2015/62; Act applied by S.I. 2014/2270)
- cross-referenced provisions (reg. 10, ss. 24, 33, 71)
- savings and transitional conditions as data, not only note text (gitlaw-contracts' finding)
- a warning or labelled layer for the s. 42 Coronavirus notices (May–July 2020)
- shorter subjects and structured trailers
- generating REPRODUCE.md in the builder

More UK sources to check before scope grows (from gitlaw-global-research):
- i-dot-ai/lex, a government API over legislation.gov.uk
- MattLynchPCO/uk-akn-model
- the Crown dependencies: jerseylaw.je, legislation.gov.im, guernseylegalresources.gg

**ALL-UK rebuild (goal set 2026-10-28: "run to completion, get all UK law in here").** In progress. Resume from here.
- **Scope:** every non-EU UK document on legislation.gov.uk, about 200k. Listing counts matched the site's own facets (ukpga 17,560, ukla 20,171, uksi about 109k, …).
- **Store:** `C:/Users/alany/Documents/uk-law-data/uk.sqlite`, with PROGRESS.md, list.log, fetch.log and harvest.pid alongside.
  - Tables: docs (state listed/done/error), versions (zlib JSON items), effects.
  - Detached run: cmd `harvest.py list && harvest.py fetch --workers 3 --rate 6`, with keep_awake.ps1 watching the pid.
  - **Resume:** `python scripts/uk-law-git/harvest.py fetch --db <store>`. It skips docs already done and retries errors. A fetch loads harvest.py at start, so restart it after code edits.
- **Strategy per document:**
  - not revised: one fetch
  - revised, with versions × size ≤ 40 MB: the whole document at each version
  - otherwise: provision by provision, assembled per date. Before a provision's first dated version use its earliest revised text; a provision inserted later is absent before it; a prospective-only provision reads as now.
  - Checked against whole-document text for CFA 2014: 0/34 versions differ in words. 9/34 differ only in the in-force marker of s. 130, which can't be determined; REPRODUCE reports the sampled rate.
- **Writer:** `gitwrite.py` (fast-import, one file per document `<type>/<year>/<n>.md`, bold provision labels). `--verify` checks every version at the end of its day. On the 5-doc test, 101/101 matched.
- **Release:** `release.py --db --repo NEW --data-date D [--push]` builds, verifies, samples the provision-built docs against whole text, generates STATS.md and REPRODUCE.md with tool blob hashes, and pushes to lexifina/uk-law-history in 20k-commit steps.
  - The test store is at `.tmp/uk-all/test.sqlite`.
  - Tell gitlaw-global before the force-push. They pin gb/uk/send, and their test must switch to gitwrite.render and uklaw.py.
- **Corpus README** is in `scripts/uk-law-git/repo/README.md`, and the date tool in `repo/tools/uklaw.py` (`on`/`log`, chosen by trailers).
- **Estimates:** ukpga averages about 19 versions and 0.6 MB per Act, so the harvest takes days. SIs are mostly one version.
