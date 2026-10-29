# Sierra Leone (gitlaw-SL): progress

Repo lexifina/sierra-leone-law (private), clone C:/Users/alany/Documents/sierra-leone-law (autopush owns it).
PUBLISH + corpus.d/20-sierralii.PUBLISH written 2026-10-29: main gets the Employment Act only; the Constitution part
(10-constitution, no .PUBLISH) stays on `preview`.

## Finished (gitlaw-finisher-2, 2026-10-29 ~02:00 UTC)
- Common Crawl tried once (CC-MAIN-2026-43 index, curl -m 30): connect timeout on port 443. acts.json keeps
  "common_crawl": false. Added lii "listing": false so fetch.py never requests a SierraLII page directly (the listing
  had not been cached; only archive.org copies are read). requests.jsonl: no direct SierraLII request.
- fetch.py (archive.org only): **Employment Act 2023** (2023/15) 1/1 expression, 2023-05-11, capture 20260711081915.
  **Cyber Security and Crime Act 2021** (2021/7): all 18 archived captures (2023-06..2026-05) are SierraLII's PDF
  viewer only (source.pdf, 11.5 MB), no Akoma Ntoso text, so it cannot be built from SierraLII. Moved from acts.json
  `acts` to `left_out` (with reason) + a decision; peachjam.parse crashed on the unpinned act (KeyError), filed in
  scripts/africa-law/ISSUES-sierra-leone.md. Next for it: Parliament has "THE CYBER SECURITY AND CRIME ACT, 2021.pdf"
  (667 KB, archived 20220301205224, in .tmp/probe/parl_pdfs.txt); check its text layer (no OCR) and write a parser.
- parse.py (run twice: identical bytes): 20-sierralii = Employment Act, 1 version, 118 units; fidelity 0 differing
  units, 0 chars outside units; SierraLII History lists nothing after 2023-05-11; Parliament's archived PDF index has
  no amending Act for either act. README line on "listing names as current" corrected (listing not read).
- Local verification (scratch repos, --docs-date 2026-10-28): main mode (GITLAW_VERIFIED_PARTS_ONLY=1) 1 act,
  1 version, 2 commits, tags employment/2023-05-11 + law/act-2023-15, check.py 0 mismatches, 0 trailer errors,
  --compare identical; preview mode 2 acts, 6 versions, 0 mismatches, --compare identical.
- Remote main checked read-only (fetch into a scratch bare repo): 347e501 "Sierra Leone: sources, before any law"
  (world-law@lexifina.com) = the scaffold. Nothing pushed or committed; the next 4-hourly autopush pass publishes.
- Known gap: repo/README.md (written by parse.py) describes the Constitution too and its example commands use
  constitution/; main will not hold that folder until the Constitution part is published.

## Status (2026-10-29 00:41 UTC, run stopped; kept for history)
- [x] Probe: SierraLII robots.txt (Allow /, Crawl-delay 5, Content-Signal ai-train=no, ai-input=no) and terms
      (s. 4 no scraping/bulk; s. 9 CC BY-NC 4.0 crediting SierraLII). Recorded in acts.json decisions.
- [x] SierraLII holds ~80 acts (2026 listing, 2 pages), each ONE expression (as published). No 1991 Constitution,
      no point-in-time consolidations. Archive.org CDX: 115 /akn/sl/act/ works, 1 expression each.
- [x] parliament.gov.sl: invalid TLS (Traefik default cert), so read via archive.org id_. CDX list of 4,665 PDFs is
      cached (.tmp/probe/parl_pdfs.txt). Constitution 1991 + amending Acts with text layers found.
- [x] constitution.py: parses the 1991 Constitution (Sierra Leone Web transcription Parliament publishes; 197 units,
      fidelity check: every body character kept, chapter/part headings dropped) and replays 4 amending Acts:
      No. 15 of 2001 (2002-02-07: s.38A, s.43), No. 9 of 2008 (2008-07-31: ss.64, 66), No. 5 of 2013 (2014-01-09:
      ss.79, 80), No. 10 of 2016 (2016-06-16: s.38). Dates from each Act's PDF (commencement, else Gazette, s.106(3)).
- [x] parse.py writes corpus.d/10-constitution.json + 20-sierralii.json (country block; acts empty until fetch),
      repo/README.md, LICENSE, jurisdiction.json. Test build .tmp-build: 5 versions, 0 mismatches.
- [ ] SierraLII acts (Employment Act 2023 = 2023/15, Cyber Security and Crime Act 2021 = 2021/7) configured in
      acts.json, NOT fetched: the Common Crawl index hung for 2 h; I killed my fetch. acts.json now has
      "common_crawl": false so peachjam uses archive.org CDX only.

## Why the Constitution is not publishable
Missing: Act No. 22 of 2022 (Gazette 22 Dec 2022, ss.34-35; scan with garbled OCR layer only) and a 2022 Act on
s.32(2),(8) (unnumbered, undated print, no sourced date). 1996 reinstatement / 1997 decree are scans. Bills 2017,
2018, 2021, 2022 (s.76) not enacted texts. So the last version (2016) is not today's text.

## Exact next step
1. `python -X utf8 -u scripts/sierra-leone-law/fetch.py > scripts/sierra-leone-law/.tmp/fetch.log 2>&1` (background;
   archive.org CDX + 1 page per act + listing pages; ~10 requests).
2. `python -X utf8 scripts/sierra-leone-law/parse.py`; check verification.json listing ok; test build + check.
3. If clean: write corpus.d/20-sierralii.PUBLISH and PUBLISH (one line each: what was verified). Constitution part
   stays unpublished.
4. Phase 2: more SierraLII acts (cheap: one page each); Companies Act 2009 + Companies (Amendment) Act 2014 from
   parliament PDFs (check text layer) as a replayed history.

## Cache
.cache/ 22 MB, 34 files (Constitution PDFs, CDX listings, parliament PDF CDX). requests.jsonl logs every request.

## Open issues
- None for the shared adapter. CC index (index.commoncrawl.org) was unusably slow 22:15-00:20 UTC.
