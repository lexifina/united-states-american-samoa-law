---
name: global-law-repo
description: "Private superproject lexifina/global-law (2026-10-28): jurisdiction tree (iso/level/corpus) with each law repo as a submodule, root history in in-force order; builder scripts/global-law; 22 tests; /watch/global-law page"
metadata:
  node_type: memory
  type: project
  originSessionId: 6c10e21b-396e-4a16-8949-2d713ab370b0
  modified: 2026-10-28T13:35:11.310Z
---

On 2026-10-28 the user asked for a "global law" repo, with sub-repos per country and sub-repos within them (Germany → federal law…), plus the optimal design, a private repo and dummy tests.

**Design chosen:** one superproject. Intermediate levels are folders holding `jurisdiction.json`, not repos. Each corpus is a submodule at `country/level/corpus`:
- `de/bund/grundgesetz`
- `gb/uk/send`
- `us/federal/usc`

Country uses ISO 3166-1 codes. Sub-national levels use ISO 3166-2 codes (for example `us/ca`), and devolved UK legislatures sit beside `gb/uk`. `manifest.json` lists the corpora and which trailer holds each one's in-force date.

**Root history:**
- Commit 1, dated 1970-01-01, holds the jurisdiction tree and no law.
- Then one root commit per corpus commit, k-way merged by in-force date while keeping each corpus's own order. Each moves exactly one gitlink. Author = the law. Trailers: Corpus, Corpus-commit, Law, In-force, Kind.
- Commit dates are clamped so they never go backwards; the `In-force` trailer is authoritative, which handles pre-1970 Grundgesetz changes.
- Each corpus's tags are copied as `<path>/<tag>`, 133 in all.
- The last commit adds the README, `tools/law.py` and `tests/`.

**Files:**
- Builder: `scripts/global-law/build.py` in the main repo. The repo's README, tools and tests are copied from `scripts/global-law/repo/`. Run `python scripts/global-law/build.py ~/Documents/global-law --date YYYY-MM-DD`, which rebuilds from scratch, then force-push.
- `tools/law.py` (standard library): world / show / blame / diff / log / laws on any date. It reads pinned commits through `git ls-tree` and `git show` without checking anything out.
- `git add -A` would drop the gitlinks, because the corpus folders aren't checked out. Git objects are read-only on Windows, so rmtree needs a chmod handler.

**Local testing:** point `submodule.<path>.url` at the local checkouts and run `git -c protocol.file.allow=always submodule update --init`.

**Status:** the repo is private and pushed, 121 corpus commits. A fresh clone with `--recurse-submodules` from GitHub passes all 14 tests. The builder is uncommitted in the main repo ([[commits-by-hand]]).

**Retained vs the US reader:**
- Retained: on-date, blame by law (line-level, where the reader is word-level), diff between dates, log per file, and three dates via trailers.
- Not in git: "what else changes" (relies-on) and follow notifications. These would need data files per corpus.
- Retroactive application is a trailer only, as in the reader.

Related: [[us-code-history]], [[grundgesetz-watch]], [[uk-law-history]].

**Moved 2026-10-28** to the lexifina org at the user's request; README clone URL updated, rebuilt and force-pushed (2aa687c). The user then moved the three corpus repos to lexifina too (all private).

**Builder reads published repos by default (2026-10-28):** it bare-clones each corpus URL into `.git/corpus-cache`. `--local DIR` reads checkouts, but never publish that build. A local-checkout build once pinned an unpushed us-code-history rebuild (6ed9a1a), which broke fresh clones. Submodule URLs are lexifina/{grundgesetz,uk-law-history,us-code-history}. Head is e48204d, verified by a fresh `--recurse-submodules` clone with 14 tests passing.

Shared rules for every git-for-law corpus, including the REPRODUCE.md requirement: [[git-for-law]].

**2026-10-28, later the same day:**
- **Tests:** 22. They include cross-checks against each corpus's own tools:
  - Grundgesetz `tools/stand_am.py`: 6 articles at 7 dates.
  - UK: every version in `data/history.json`, rendered with `ukhistory.render` and placed with `provision_path`.

  Other tests cover tags, three dates through `law.py history`/`log`, plain `git ls-tree`/`show`, and laws in a date window. The US has known readings only.
- **REPRODUCE.md** is generated. `scripts/global-law/repo/REPRODUCE.md` holds `{{PINS}}` `{{COMMITS}}` `{{BUILD_BLOB}}` `{{LAW_BLOB}}` `{{TEST_BLOB}}`, filled at build time. `build.py` ships itself as `tools/build.py`. Two builds gave identical hashes.
- **Pins:** GG b0d346e, UK e295f45, US c9591a6. Head 3cc7e22 is pushed.
- **Peers:** gitlaw-UK, gitlaw-GER and gitlaw-US each message before a force-push. Their pending rebuilds (UK data fixes; GG 104c/143e–g and the 63rd–69th amendments) will need a global-law rebuild.
- **Site:** `saas-webpage/app/watch/global-law/` is uncommitted and noindex.
  - `_data/global.json` comes from `build.py --site-data`. `_data/load.ts` maps each event to its corpus reader's label and link.
  - `_components/WorldOnDate.tsx` is the client: a date input, lanes with a tick per change and a pin, a card per corpus, and a list filterable by country.
  - The page also shows the jurisdiction tree and the method. There's a rail item on /watch.
  - Ticks close together overlap; the list below covers that.
- **Video:** internal walkthrough at product-videos/ordinary/208-global-law-repo-test-walkthrough.mp4 (3:11). Recorder is the scratchpad `vid/record.mjs` with `stage.html`.
- **Verdict:**
  - Works: on-date, blame, diff, follow with dates, laws in a window, tags, agreement with each corpus's tools.
  - Not in git: relies-on, word-level authorship, retroactive reach, follow alerts.

**Swiss corpus, not added yet (gitlaw-SWISS answers, 2026-10-28):**
- Repo: lexifina/swiss-law. `In-force:` trailer; publisher corrections carry `Corrected:` instead of In-force.
- Tags: `<act>/<date>` (bv, dsg, schkg) and `as/<year>-<n>`.
- Branches: `main`, plus `kuenftig` for changes adopted but not yet in force. Build from main.
- CLI for a cross-check test: `python tools/stand_am.py DATE bv|dsg|schkg [art]`.
- Files: `bv/art-NNN.md`, dated noon Zurich.
- Suggested path: `ch/bund/swiss-law`.
- Main was at 431b779c, then force-pushed to 965d882f the same day.
- First-version commits carry `Consolidated:` instead of `In-force:`. The builder would treat them as baseline, so read `Consolidated` as their date.

**Scaling options (gitlaw-global-research, 2026-10-28; the register is in [[world-law-sources]]):**
- legalize.dev has about 31 countries, one repo each, and could be wrapped as submodules for countries we don't build.
- Its commits are dated by publication, not in-force, so its corpora must go in with a different date rule: manifest `date_rule: published` and `Kind: published`. Never interleave them silently as in-force.
- Respect licences: AustLII bans AI use, and FAOLEX is non-commercial (NC).

**Later on 2026-10-28:**
- Head is a150ef0, with 23 tests. Pins: GG b0d346e, UK 9ed31ef, US c9591a6.
- `law.py words DATE PATH`: word-level authorship. It diffs each file version against the one before; islands of fewer than 3 matching words inside a rewrite are credited to the rewriting law.
- REPRODUCE.md and README.md fill in `{{TESTS}}` (the count of `def test_`) at build time. `--date` is now required.
- Site timeline: marks closer than 0.6% are grouped into one button that steps through its laws on each click.
- **Pending US:** a full-Code rebuild and force-push, adding `tools/uscode.py on DATE PATH` and `Applies:` trailers. Format: `Applies: <provision> | cond; cond`. Groups are OR'd, conditions AND'ed; no Applies line means all cases. Conditions: commenced-on-or-after, commenced-before, commenced-after, commenced-on-or-before, pending-on, any-commencement. Then add `law.py case` plus tests.
- **Pending UK:** all UK law, about 200k documents. The layout changes to one file per document (`ukpga/2014/6.md`). Tools: `gitwrite.render(uri, title, items, meta)` and `uklaw.py on`. Trailers: In-force, Enacted, Made, Text-as-at, Temporary-change-ended. Don't pin until UK messages. I asked them to choose one repo per legislature (gb/uk, gb/sct, gb/wls, gb/nir) or a single repo at gb/legislation, and how many commits to expect. Past a few hundred thousand, switch to one root commit per corpus per day.

**Deep test (2026-10-28, evening).** Results are in CHANGELOG.md, section "This tree (global-law): deep test of real use". The internal video is product-videos/ordinary/209-global-law-real-usage.mp4 (2:22, recorded live from a fresh clone).

Fixed in `law.py`:
- dates are now validated (they used to be compared as text, so `2022-5-1` read as December 2022)
- each corpus has `record_to`/`record_note` in the manifest, with notes on stderr
- `explain_missing` tells a typo from a date before the record, not yet in force, or removed-and-back (Art. 143h: 2020-10-08 to 2020-12-31, then from 2025-03-25)
- paths may be written `./` or with backslashes
- diff from before a record's start, a reversed `laws` window, and missing-argument tracebacks
- `words` was 16 s on 17 U.S.C. §115 and is now 1.3 s (line match first, then line-pair large rewrites)

Also fixed:
- `.gitignore`; tests set `dont_write_bytecode` (a pycache in the UK submodule had blocked checkout)
- the German test force-fetches tags (stale tags survive a corpus force-push)
- new Pins test (every pin is an ancestor of its published main) and GitReadsTheDates test (`%(trailers)` finds the in-force date)
- README now covers plain-git pitfalls: use a worktree for time travel, no dates before 1970, no blame from the root, and fetch --force --tags after a rebuild

Open: the root chronology starts with doc commits; scale for all-UK/full-SR (one root commit per corpus per day; shallow submodules); `Modifies:`/`Applies:` trailers need indexing; `test_words_is_fast` (under 8 s) is flaky under load.

**Coordination:**
- global-MCP (my fork) owns `tools/mcp_server.py`, `tests/test_mcp.py`, `MCP.md`, `.mcp.json` and `aliases.json`. Case applicability lives there, not in law.py.
- Take turns building: message before each build. The builder now empties the out folder rather than deleting it, because other sessions may sit in it.
- Germany's repo is now lexifina/germany-law. It will become all German law (`bund/gg/...`, `bund/gesetze/...`), so its path should move to `de/...`.
- gitlaw-global-research is making 205 placeholder `<iso>-law` repos plus scripts/world-law/countries.json. The builder should read countries.json, and corpora stay "pending" until they have a law commit.
- Estonia, Liechtenstein and Luxembourg repos are done but not in global-law yet. Pushed head: 6a7bb70 (61 tests).

