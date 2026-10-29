---
name: lawyers-prompt-engineers-blog
description: "2026-10-18 unfinished blog saas-webpage/app/blog/lawyers-as-prompt-engineers, synthesised from Anthropic's Scion post + its HN thread + our new-unit-of-work post"
metadata:
  node_type: memory
  type: project
  originSessionId: 8f0190c4-bc50-4807-8479-2d2931b3ac8e
  modified: 2026-10-18T15:25:15.858Z
---

On 2026-10-18 the user asked for a deep dive on HN item 50073633 (Anthropic, "Redesigning source control at Anthropic", 13 Oct 2026) and a table of points that apply to Lexifina. They then asked to turn it into a new unfinished blog, "Lawyers as prompt engineers?", synthesised as prose, not as a table.

- Post: `saas-webpage/app/blog/lawyers-as-prompt-engineers/` (dev-only page plus a noindex layout). Its entry sits at the top of `components/BlogOriginalPage.tsx` under Unfinished blogs. Uncommitted ([[commits-by-hand]]).
- Thesis: when agents draft, the lawyer's work becomes reviewing intent, refusing changes, setting structure and owning acceptance. That is a supervising lawyer's judgement more than prompt writing.
- The post marks these as not built: a reason-vs-change verifier, rejection reasons becoming rules, contract lint as gating, dependent-proposal grouping (partial accept breaks the run's atomicity), risk-tiered bulk accept, privilege and retention for the ledger, and a signature-hash chain end.
- HN points are cited as [2] and never attributed in the text ([[blog-concept-over-mechanics]]). Related: [[new-unit-of-work-blog]], [[document-blame-ledger]].
