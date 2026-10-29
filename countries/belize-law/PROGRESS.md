# gitlaw-BZ: Belize law history (progress / handoff, 2026-10-29 00:42 UTC, wound down by coordinator)

Slug `belize`, repo `lexifina/belize-law` (PRIVATE), clone `C:/Users/alany/Documents/belize-law`.
tz America/Belize, lang en, future branch `future`. Rules: scripts/world-law/WAVE.md -> africa-law/FANOUT.md -> south-america-law/BRIEF.md.

## Status: NOT BUILT. No corpus.json, no PUBLISH.

## Checklist
- [x] Scaffold confirmed: lexifina/belize-law main = 283e182 "Belize: sources, before any law" (only commit). Cloned.
- [x] Rules, memory/git_for_law.md, SCHEMA.md read; Guyana (scripts/guyana-law) chosen as the model (edition + amending-Act replay).
- [x] Probe: agm.gov.bz/laws works (JS page; data comes from a POST API, below). nationalassembly.gov.bz is a
      suspended hosting page. belizelaw.org gives no response (connection fails) -> old editions only via Common Crawl / archive.org.
- [x] fetch.py (curl, --compressed, UA, 3 req/s/host, sha256 cache, .cache/requests.jsonl; POST listings cached under key "POST <url> <body>").
- [x] All listings cached: R.E. 2020 volumes 1-18 (`action=1000&volume=N`), annual Acts lists (`action=1001&volume=<YYYY>_act`): only 2021-2026 exist (55/31/54/40/25/24 Acts); 1981-2020 return rc=2 (empty).
- [x] PDFs cached (7): Cap 4 Belize Constitution Act (upload 6aa0784753c95, uniqid => uploaded ~Sept 2026, so likely consolidated past R.E. 2020),
      Cap 101 Criminal Code (R.E. 2020, upload Dec 2022), Act 6/2021 Constitution (Ninth Amendment), Act 25/2022 Constitution (Tenth Amendment),
      Act 45/2021 Data Protection Act, Act 34/2023 Criminal Code (Amendment), Act 8/2024 Criminal Code (Amendment) (No. 2).
- [ ] Text-layer check of those PDFs (not done; use PyMuPDF without `-I`, or pdftotext at /mingw64/bin/pdftotext).
- [ ] Older dated editions (R.E. 2000 / 2003 / 2011) from old belizelaw.org via Common Crawl first (gitlaw_common/wayback.py), e.g. prefix `belizelaw.org/web/lawadmin/`.
- [ ] parse.py, corpus.json, repo/README.md, repo/LICENSE, repo/jurisdiction.json, verify, PUBLISH.

## Exact next step
1. Check text layers of the 7 cached PDFs; read the Cap 4 PDF's front matter for its "as at" date and the list of amending Acts it includes
   (it decides whether the Ninth/Tenth Amendments are already in the current text).
2. Phase 1 plan: Constitution = R.E. 2020 edition (or the 2026 upload, if newer) as `first_law: null` "oldest version available",
   then replay Act 6/2021 and Act 25/2022 if the base predates them; and check end to end against the latest upload.
   Criminal Code = R.E. 2020 + Acts 34/2023 and 8/2024 (the "No. 2" title implies a 2024 No. 1 Act not in the portal list: check).
   Data Protection Act 45/2021 = one version as enacted; find its commencement (the Act's own commencement section / SI).
3. In-force rule: cite the Interpretation Act (Cap 1, R.E. 2020 volume 1, cached listing) on commencement at publication in the Gazette.

## Sources
| Source | Status | Notes |
|---|---|---|
| https://agm.gov.bz/laws (Attorney General's Ministry) | 200 | R.E. 2020 consolidated PDFs (18 vols) + annual Acts 2021-2026 PDFs. Listing API: POST https://agm.gov.bz/api-laws/ (no CSRF token needed). No dated versions; no robots.txt (returns HTML). Licence not stated on the site. |
| nationalassembly.gov.bz | suspended | cgi-sys/suspendedpage.cgi |
| belizelaw.org | no response | old R.E. editions; try Common Crawl / Wayback |

Cache: 1 + 18 + 46 listing responses and 7 PDFs (~3.3 MB) in .cache/. WebSearch used: 0 of 3.

## Open issues
None in the shared builder (not run yet).
