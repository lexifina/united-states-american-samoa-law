---
name: global-law-mcp
description: "MCP server for lexifina/global-law (2026-10-28, session global-MCP): tools/mcp_server.py, stdlib JSON-RPC over stdio, 15 read-only tools; 31 tests; five blind rounds all correct; aliases.json + .mcp.json"
metadata:
  node_type: memory
  type: project
  originSessionId: 3aeca1a1-581e-4c88-900a-8bc3cbe73b0c
  modified: 2026-10-28T15:36:05.433Z
---

Built on 2026-10-28 by the session "global-MCP", forked from gitlaw-global. The user's goal: "make an MCP server for using our gitlaw-global repo, as useful as possible, keep running, iterating and testing it."

**Files:** all under `scripts/global-law/repo/`, which ships in lexifina/global-law on the next build:
- `tools/mcp_server.py`. It imports `tools/law.py`.
- `tests/test_mcp.py`
- `MCP.md` (setup and the tool table)
- An "MCP server" section in `CHANGELOG.md`

gitlaw-global owns `law.py`, `build.py` and the README; they agreed to keep law.py's function names stable.

**Design:**
- Standard library only: newline-delimited JSON-RPC over stdio. Protocol versions 2025-06-18, 2025-03-26 and 2024-11-05. Tools, plus 4 resources (README, REPRODUCE, CHANGELOG, manifest).
- Each tool returns text plus `structuredContent`. A `UserError` (or law.py's SystemExit) becomes `isError`, so the model can correct itself.
- `law.timeline` and `law.manifest` are wrapped in a cache keyed on HEAD.
- The provision index uses `names_of` (`ls-tree`), plus headings read with `git cat-file --batch` only for the folder asked about. This keeps it fast for all-UK and full-SR scale.

**The 14 tools:**
- finding things: `list_jurisdictions`, `find_provision`, `list_provisions`
- reading the law: `read_law` (with sources), `world_on_date`, `who_wrote`, `compare_dates`
- history: `provision_history`, `laws_between` (with provisions per law), `changes_between`
- search: `search_law`, `search_changes`
- cases and records: `applies_to_case`, `law_details`

Details:
- `search_law` runs git grep across submodules at the world commit. Plain queries match typographic dashes and quotes.
- `find_provision` falls back to a text search when headings are only numbers.
- `applies_to_case` parses `Applies: <prov> | cond; cond | set-by …`. When there's no data, it falls back to the scope stated in words for that provision's message block.

**Testing:**
- Test clone: `C:/Users/alany/Documents/global-law-mcp`. Copy the server, law.py and the tests in, then run `python -m unittest tests.test_mcp`. After global-law is force-pushed, use `git fetch` and `reset --hard origin/main`, not pull.
- Blind runs: `C:/Users/alany/Documents/global-law-mcp-blind`, using `claude -p --mcp-config mcp.json --strict-mcp-config --allowedTools mcp__global-law --disallowedTools Bash,…,PowerShell --model sonnet < /dev/null`. Three rounds: questions*.txt and answers*.txt.

**Open:** `applies_to_case` needs the US `Applies:` trailers, which come with the full-Code rebuild. Install with `claude mcp add` is documented only; it wasn't added to the user's config.

Related: [[global-law-repo]], [[git-for-law]].

**Round 4 (adversarial):** 6/6. Fixes from it:
- `applies_to_case` parses worded scopes (`conditions_from_words`): "commenced … on or after <Month D, YYYY>", "before, on, or after". The verdict then says "read from the record's words".
- `explain()` maps law.py hints to tool names.
- `num()` validates numeric arguments, and `date_arg` accepts 8-digit integers.

**Open:** topic search by popular names.

**Round 5 (research memo, 2026-10-28):** correct. Added in response:
- `phrase_history`: `git log -G` pickaxe per corpus, counting added versus removed lines that match. It shows when words entered or left the law at any date.
- A `search_law` miss now falls back to the change notes.

**Coordination:** gitlaw-global is adding `law.py case`. I offered to move applies_groups, group_holds, scope_in_words and conditions_from_words into law.py, or have it import them from mcp_server. Awaiting its answer.

The test clone is at fb679cf. Update with `git fetch`, `reset --hard origin/main`, `submodule update` and `submodule foreach git fetch --force --tags`.

**After the stop-hook review (2026-10-28):**
- Added `repo/aliases.json`: popular names mapped to paths. An exact name gets weight 100; a name inside a longer query gets 4.
- Added `repo/.mcp.json`, which runs `python tools/mcp_server.py` from the clone root.
- Added `read_law` "beyond_the_words":
  - reach-back from later Applies data or worded scope
  - `Modifies:` effects, indexed by trailer (`modifies_in`, `git log --grep`): latest open effect per provision and kind, `ended` closes, `Curated: yes` is noted
- UK and US now emit `Modifies:` (empty commits).
- 31 tests pass. Delivery waits on gitlaw-global's build. I asked it to build, or to let me build and force-push, and subscribed to its idle notice.

