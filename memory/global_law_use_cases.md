---
name: global-law-use-cases
description: "Use-case + literature research for global-law (2026-10-28): artifact 'Global Law Use Atlas' with 67 uses, prior art, design gaps, ~120 sources; top bets ranked"
metadata:
  type: project
---

On 2026-10-28 the user asked for every use case of [[global-law-repo]] beyond knowledge graphs and an MCP, researched in depth across the literature. Result: the artifact "Global Law Use Atlas", https://claude.ai/artifact/RpySk6gJwapyYhLxRbnkBm (local copy in that session's scratchpad).

**Ranked bets (my recommendation):**
1. A point-in-time MCP where every answer carries provenance (commit hash).
2. LawCommitPack: verified (old, instruction, new) triples. Prior best is 908 German pairs at 50% exact match (Prior et al., NLLP 2025).
3. Statute change → impact on contracts, policies and rules-as-code (no CLM tool found that does this).
4. A live temporal benchmark.
5. A data paper replicating Coupette et al. 2021 from open data.
6. A change feed for regulatory-change-management (RCM) vendors.
7. Commit-hash citations plus a Memento (RFC 7089) TimeGate.
8. "Lobby text that survived into force".

**Design gaps the literature raises:**
- Ex tunc annulment rewrites the past, which an append-only log can't show.
- Validity, efficacy and application dates differ.
- The omnibus act that carried a change is not the bill it came from (Casas 2020).
- Line-level blame misses 16% of co-authors.
- Renumbering.
- The Data Foundation 2020 objection that "law is instructions, not versions".
- Source licences differ (AustLII bans AI use).

**Closest competitors:** legalize.dev (dates commits by publication; calls itself "not verified"), FiscalQA Pro (2026), and the TUM Grabmair group.

Related: [[world-law-sources]], [[git-for-law]].
