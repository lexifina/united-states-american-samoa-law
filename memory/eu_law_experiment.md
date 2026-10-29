---
name: eu-law-experiment
description: "2026-10-21 \"new EU law\" firm-graph experiment + film (scripts/firm-graph-eu): hypothetical 30-day payment regulation, EU overlay rooms 1x/10x, graph wins on effort (10x 12→5 min, 3.3M→0.57M tokens), saas/eu-law-firm-graph.mp4; uncommitted"
metadata:
  node_type: memory
  type: project
  originSessionId: 3b00790a-de3b-4dc0-abce-33e88ecaf379
  modified: 2026-10-26T13:24:48.213Z
---

On 2026-10-21 the user asked for a KG experiment, "How would a law firm react to a new EU law", plus a film to send to Omar Hegazi. They warned that memory was very low.

- **Setup:** `scripts/firm-graph-eu/`.
  - `overlay.py` adds an EU layer to the Calder Wren rooms: EU-established companies, a payment clause on every commercial agreement, and precedent PREC-PAY-01 (60 days), which some clauses follow without stating days. It also adds the firm's own terms of business (45 days).
  - `tasks.py` holds four questions about a hypothetical "Regulation (EU) 2026/2207", a 30-day cap. `stats.py` rescores the answers.
  - Drafts are neutral in scoring, because agents read "live agreements" as signed ones only.
- **Product change (uncommitted):**
  - The graph records each organisation's `country`/`eu` and each clause's `payment_days`, including days inherited from a precedent.
  - `queries.payment_terms` and `firm_graph_clause_facts fact=payment_terms` filter by establishment and min/max days, with compact rows that fit the 24k cap at 10x.
  - `CACHE_VERSION` is 4. There is a new test in `test_firm_graph.py`; all 29 pass.
- **Results (GPT-6 Sol, 3 runs):**

  | | 1x, without → with graph | 10x, without → with graph |
  | --- | --- | --- |
  | Accuracy | 88% → 99% | 97% → 100% |
  | Time | 5.5 → 3.4 min | 12 → 5 min |
  | Input tokens | 0.87M → 0.25M | 3.3M → 0.57M |

  The baseline does well because clauses cite PREC-PAY-01 by code, so search finds them.
- **Running without new containers:** use `docker exec -d` into lexifina-backend-1, with the bench and rooms `docker cp`'d into /tmp/eu.
- **Film:** `film/film.mjs` draws with the Skia canvas (`@napi-rs/canvas` from src/frontend) and pipes raw RGBA frames to ffmpeg. There is no browser; a 50 s 1080p render takes 90 s and about 0.5 GB.
  - Static Manrope cuts come from the fontTools instancer, because Skia registers only the default weight of a variable font.
  - Output: `product-videos/saas/eu-law-firm-graph.mp4` plus a thumbnail.
  - Not sent yet: there was no mail tool, and Omar's address was unknown.

**100x extension (2026-10-21 evening, user: "proper scientific report", EVEN LARGER):**
- 12,000-matter room: `demo_room.py --scale=100` with gated FILLER_MIDDLES_MORE (1x/10x unchanged) → `scripts/firm-graph-bench/rooms-100x/` (gitignored), overlay → `rooms/calder-wren-eu-100x`. The 5-digit refs needed `\d{4,5}` in bench.py/tasks.py.
- Graph build (container, rules): 3.9 s / 52 s / 560 s; 6k / 63k / 626k nodes; cache 2.4 / 25 / 245 MB; peak 1.6 GB. Build it in the container, because Windows file opens cost about 7 ms each. `BENCH_SKIP_LAYOUT=1` is needed because the page layout's circle packing is superlinear.
- `payment_terms` pages: 70 docs and 120 clients per page, with `offset`/`clients_offset`. The 1x/10x graph runs were re-run with paging; the old runs are kept as `results-*-unpaged-tool`.
- Scoring was settled after the first runs (disclosed in the post):
  - drafts and signed agreements on closed matters are neutral;
  - agreements are scored by matter;
  - counterparties and EU clients are neutral in client alerts.
- **100x (partial):** without the graph the agent finds about 15 of 562 agreements (F1 5%); with it, 100%. Neither agent will write lists of 500–1,100 clients, so the next limit is delivering long answers as a file.
- Time is confounded by load when runs overlap, so tokens are the effort metric.
- The container restart at 23:2x killed the run at 15/24. Re-launching the same command resumes it, because existing result files are skipped.
- **Follow-up on 2026-10-22 (split.py, split_stats.py):** the user doubted the 100x "5%" result.
  - The 5% was F1. The share actually found was 2% (10–17 of 562), and the post now says so explicitly.
  - Paged search alone: still 2%.
  - 12 slices × 1,000 matters, one agent each: 96% (510–561 found, 0 wrong), at 7.5M tokens and $3.78, against the graph's 0.21M tokens and $0.27.
  - The misses were precedent-only agreements, from 3 slice agents that never searched for PREC-PAY-01 and stayed silent about it.
  - Slice answers open with their matter range, so the ranges are stripped before scoring.
- **Codex on the same task (codex_runs.py, Codex CLI on GPT-6 Sol via Azure, since its ChatGPT sign-in has no Sol):**
  - Search-only (ripgrep multi-line extraction, no scripts): 562/562 in both runs, 11 min, $0.72.
  - Full freedom (writes a Python script, delivers the list as a linked .md file, which is what gets scored): 562/562 in all three runs, 5.8 min, $0.31.
  - Conclusion in the post: the 2% reflects our agent's tools; the graph is still cheapest and fastest; the synthetic room is regular, which helps regex.
  - Gotchas: Codex's Windows sandbox rejects everything, so runs use the bypass flag in a work dir with a junction to the room. Write scratch scripts with Write, not heredocs (`\n` gets mangled).
- **Post:** `saas-webpage/app/blog/knowledge-graphs-update-firms-for-new-laws/ ("Knowledge graphs update firms for new laws", renamed 2026-10-22 from "Finding what a new law touches")`, unfinished, dev-only, listed. `blog_data.py` writes `euData.ts` from `stats.json` and `graph_stats.json`.
- **Uncapped 120,000-matter re-run (2026-10-25):** the user called the 40-call cap arbitrary. Results are in `results-*-1000x-uncapped`; run `EU_1000X_TAG=uncapped split_stats.py`. `partitioned.py --max-invocations 0`; Codex/Claude Code with no budget and `RUN_TIMEOUT_S=86400`.
  - Graph as the product is: still 64 listed of 5,274. Even with no cap the agent stops after one 70-row page, gives the total and says the list is incomplete; the cap was never the cause.
  - Graph + export: 100%, 4.3 min (≈ Codex's 4.5), 0.07M tokens, $0.05. Most of the time goes on loading partitions from disk (~80 s a query); the model takes under 30 s.
  - Claude Code with scripts now takes about 28 min (it opens all 243k files on Windows). The search-only runs give up on their own.
  - No run at any size ever reached the 40-call limit: reading files at 12k, our agent stopped by itself after 22–32 calls, and 2 of 3 answers gave a partial list as if complete. The post now says so; the title is now "…with a fraction of the tokens Codex and Claude Code use" (2026-10-25).
  - Why the graph's lead on time shrinks at 120k (traces + `time_partition.py`): a firm-wide query spends 101 s loading the 10 partition pickles and 3.9 s querying; node lookups take ~8 s (one partition). The model's own work is ~25 s. At 12k (whole graph in memory) queries take 1–2 s and time goes on the model writing the 562-row reply. Codex runs the same plan at both sizes (read the documents.json index, script over the live agreements only), so its tokens (~0.6M) and time (~5 min) stay flat. The token ratio going from 3× to 9× comes from the export tool, not from size.
  - Graph times without loading (`setup_free_times.py` replays every graph call with the graph in memory → `results-*/setup_free.json`; `blog_data.py` adds `setup_free_s`): 24 s / 1.6 min / 2.2 min at 120 / 1,200 / 12,000 matters (recorded: 25 s / 1.9 / 2.5). At 120k: export 54 s (4.3 min recorded, about 5× faster than Codex's 4.5 min); as the product is, 78 s. The post's tables show only this time (user: readers don't care about load time; the loading detail lives in one short paragraph in the 120k section); captions are divs, because the blog's `[data-blog-content] p` rule (!important) forces body size on every p.
  - Run long jobs detached (Start-Process / `docker exec -d`): Claude Code reaps background shells under memory pressure. backend-1 restarts kill `docker exec` jobs; `scale1000.py` resumes.
- **Post figures (2026-10-26, live in site commit cab35a8):** the user wanted the 120,000-matter graph pictured, not the 1,200, then "duplicated 10 times" = every node drawn: `layout_1000x_full.py part|merge k` (ten passes by id hash, same positions) → `render.mjs calder-wren-eu-1000x-full/k<k>` (~5 min each) → `compose.py` (darker pixel); it sits at the top of the 120k section. `scripts/firm-graph-eu/graph-image/`: `layout_1000x.py part|merge` (one partition per process, because memory is short; the product layout with a sunflower pack, since its greedy pack is O(n³) and takes hours at 12k matters; 1 in 10 of the large kinds drawn), then `render.mjs calder-wren-eu-1000x` → `public/blog-media/eu-law-firm-graph-120k-*.webp`, in the 120k section. Also added `TargetDiagram`, `BigFirmBars` and `TokensBySize` (`ScaleChart.tsx`, a client component with hover), in a palette validated by the dataviz checker.
- **Film v2:** `film/film-v2.mjs` (60 s, adds a three-sizes closing scene) → `product-videos/saas/eu-law-firm-graph-v2.mp4`.

Related: [[firm-graph-film]], [[firm-graph-scale-experiment]], [[low-memory-capture]], [[ad-style-feedback]].
