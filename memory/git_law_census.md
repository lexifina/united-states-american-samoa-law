---
name: git-law-census
description: Git-for-law census ranked by HN/Reddit attention (2026-10-28) + judgment-overlay feasibility; artifact 7vD8b7fJzEnCumUoLvi5Dh; prior-art passes must sweep HN
metadata:
  node_type: memory
  type: project
  originSessionId: 18e99560-7613-4b15-bc3b-9181848c1694
  modified: 2026-10-28T15:07:05.171Z
---

On 2026-10-28 the user asked why our git-for-law research never surfaced HN 47553798 ("Spanish legislation as a Git repo", legalize-es, 827 pts / 233 comments). That thread carries artirdx's request to overlay judgments on the law at the right points in time. Result: the artifact "Git for Law Census", https://claude.ai/artifact/7vD8b7fJzEnCumUoLvi5Dh.

**Why we missed it.** [[world-law-sources]] was a register of official sources with stars, and it never ran an HN, Reddit or Lobsters sweep or read comment trees. It found legalize.dev and legalize-kr, but missed steeve/france.code-civil (2,687★, HN 453) and JesseKPhillips/USA-Constitution (2,189★, HN 1,198, the biggest thread).
**How to apply:** every prior-art pass runs the hn.algolia.com story search, sorts by points, and reads the top threads' comments.

**Top ranked by attention:**
1. USA-Constitution: about 1,260
2. Open Law Library / DCCouncil law-xml: about 888 (the only official git record)
3. legalize.dev: 827
4. france.code-civil: 458
5. our HN 50268380: 348
6. bundestag/gesetze: 343

legalize-kr (1,544★) has no posts. Its sister repo precedent-kr holds judgments dated by decision date, each with structured 참조조문 (cited provisions), but it isn't joined to the law history.

**Judgment overlay.** We don't do it; the UK README excludes it. Nobody does it in a time-aware way. The proposed design is a sidecar judgments repo per corpus: JSONL per provision, each citation pinned to the `law_commit` in force on the decision date, append-only, with a REPRODUCE.md.

Measured counts:
- UK Find Case Law links section URIs directly: 34 of 43 s.42 CFA citations are linked. Computational analysis needs the free TNA licence.
- Open Legal Data has 18.5M German refs, all pointing to the current GG version, from 2010 on.
- entscheidsuche has 25,521 decisions citing Art. 29 Abs. 2 BV.
- CourtListener has almost no subchapter V opinions.

Effort is about 6–9 weeks; start with the UK. Not started.

Side finding: the agent says a CourtListener key is hard-coded in `src/test_courtlistener_api.py` (see [[leaked-credentials]]).

Related: [[git-for-law]], [[global-law-use-cases]].

**Verdict section (v2, 2026-10-28).** It adds "Is ours the best?" with 17 checkpoints, 10 on faithfulness and 7 on reach.

Our answer is no, not overall. We're the most faithful record (cause per commit, in-force date, author = law, per provision, checked and reproducible), but we trail on reach: tiny coverage, private repos, no API or MCP, no daily updates.

Facts checked in competitors' own commits:
- legalize-dev/legalize-de and -uk commits are "DE-DAILY-…" and "UK-DAILY-…" batches with "Affected articles: N/A", authored "Legalize".
- legalize-uk keeps CFA 2014 as one 843 KB file. Its Coronavirus Act commit only reorders headings.
- legalize-kr dates commits by promulgation (공포일자).

To become clearly the best: go public, cover the whole UK, ship the MCP, update daily, add the judgment overlay.
