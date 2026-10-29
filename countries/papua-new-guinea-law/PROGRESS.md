# Papua New Guinea (gitlaw-PG): progress / HANDOFF (wound down 2026-10-29 00:40 UTC)

Owner: gitlaw-PG. Repo lexifina/papua-new-guinea-law (private), still the bare scaffold (main 9d4cbff,
"Papua New Guinea: sources, before any law"). Clone at C:/Users/alany/Documents/papua-new-guinea-law (untouched).
Rules: scripts/world-law/FORK.md -> WAVE.md -> africa-law/FANOUT.md -> south-america-law/BRIEF.md. Language: English.

## Status
- [x] Scaffold check (only main, single scaffold commit).
- [x] Probe done (below). No parser yet, so NO corpus.json and NO PUBLISH.
- [ ] Constitution, [ ] Criminal Code Act (Ch. 262), [ ] Companies Act 1997.

## Sources found
- PacLII direct (paclii.org) answers a Cloudflare challenge (403 "Just a moment"): do NOT fetch directly. Use archive.org
  via scripts/gitlaw_common/wayback.py. Common Crawl index (index.commoncrawl.org) was unreachable from this machine
  at 00:00 UTC (connect timeout), so archive.org was used.
- **Best Constitution source:** PacLII "original PDF" `https://www.paclii.org/pg/legis/consol_act/cotisopng534.pdf`,
  archive.org capture 20260906195625 (1,702,450 bytes, md5 50602a75...). Office of Legislative Counsel consolidation
  **"As at 16 May 2025"**, text layer OK (pdftotext -layout -> 11,468 lines). It lists Constitutional Amendments
  No. 1-47 with "in operation" dates (front matter lines 1-97) and has per-provision footnotes naming the amending law
  (e.g. "Subsection (2) amended by Constitutional Amendment No. 47 (Court Restructure) Law 2024, s.1"), incl. No. 48
  and No. 49 (Christian Country) of 2025, which are not in the front list. Body section headings match
  `^\s*\d+[A-Z]*\. [A-Z ...]+\.\d*$` (331 hits, s.1 at line 1025 .. s.349 at 10445). Footnote markers are glued
  to words ("be2", "PRIVACY.78") and footnote text sits at page bottoms (lines starting "<n> Added by/Amended by/...").
- Older PacLII snapshots: HTML 2004 and 2015-2025 = a stale undated text (has Amdt 16 of 1995, lacks Amdt 22 of 2001);
  HTML 2009-2013 and PDF 2017 = OLC text "Certified on / /20" with notes "No. 880-886 of 2006". The PDF that
  parliament.gov.pg hosts (wp-content/uploads/2026/04/PNG-CONSTITUTION.pdf) is byte-identical to the 2017 PacLII PDF
  (that older OLC text), so it is NOT current. parliament.gov.pg WP media API has no Acts.
- Criminal Code: `paclii.org/pg/legis/consol_act/cca1974115/` captures 2005-2025 (+ PDF 20220119142203, RTF 2016/2022).
  Companies Act 1997: slug not yet found (not ca1997108); look in `consol_act/toc-C.html` captures (latest 20180901094204).

## Cache
- `.cache/` (gitignored), wayback client cache + requests.jsonl; working copies in `.cache/x/`:
  const2026.pdf/.txt (target), const2017.pdf/.txt, const2018.pdf/.txt, toc*.html (HTML snapshots), parl_const.pdf.
- Scripts: `ia.py <url> <ts> [out]` (one archive.org id_ capture via wayback.get), `cc_probe.py <prefix> [n]`.

## Exact next step
1. Write parse.py: read const2026.pdf (the cached capture), pdftotext, cut body from line ~1000 (Preamble) on, drop page
   headers/footers and footnote blocks, strip trailing footnote digits after words/headings (map each to its note),
   one unit per section (`s-001` ... `s-349`, preamble, schedules), one paragraph per line.
2. corpus.json: one version, `first_law: null`, from = 2025-05-16 (the source's "As at" date), credited to the publisher
   (Office of Legislative Counsel / PacLII), earlier_laws = Constitutional Amendments 1-49 with in-operation dates.
3. Verify a sample of sections against the PDF, then (repo still scaffold) write PUBLISH. Then Criminal Code, Companies Act.
