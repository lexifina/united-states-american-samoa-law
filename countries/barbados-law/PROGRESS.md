# gitlaw-BB: Barbados law history (progress)

Stopped at the coordinator's wind-down (2026-10-29, about 00:40 UTC). **Probe only: no corpus.json, no PUBLISH, no build.**

Slug `barbados`, repo `lexifina/barbados-law` (PRIVATE, never change). Clone at `C:/Users/alany/Documents/barbados-law`.
On 2026-10-28 main was still only the scaffold commit 88aff25 "Barbados: sources, before any law".
tz America/Barbados, lang en, future branch `future`. Rules: `scripts/world-law/WAVE.md`, then `scripts/africa-law/FANOUT.md`, then `scripts/south-america-law/BRIEF.md`.
WebSearch calls used: 0 of 3.

## Checklist
- [x] WAVE/FANOUT/BRIEF, memory/git_for_law.md and SCHEMA read
- [x] Scaffold confirmed and cloned
- [x] fetch.py: Guyana's fetcher with per-host delays. barbadoslawcourts.gov.bb gets 10.5 s (its robots.txt says Crawl-delay: 10); other hosts 0.34 s.
- [x] Probed 4 sources (table below)
- [x] 4 law-courts PDFs cached (below)
- [ ] Wayback CDX for barbadosparliament-laws.com, the CloudFront host and the old law-courts PDFs. This was started and then stopped at wind-down, so some CDX responses may be cached partially.
- [ ] Find and fetch the amending acts: Constitution amendments after L.R.O. 2002, including the 2021 republic amendment; Data Protection Act 2019-29
- [ ] layout.py/parse.py: model them on `scripts/guyana-law/layout.py` and `parse.py`, which handle the same L.R.O. layout with marginal notes and "[N of YYYY]" citations
- [ ] repo/README.md, LICENSE, jurisdiction.json (`build` status)

## Sources probed (2026-10-28)
| Source | Status | Format | Dated versions | Notes |
|---|---|---|---|---|
| barbadoslawcourts.gov.bb/laws/consolidated-laws/statutes-of-barbados/ | 200 | HTML list of 543 PDFs under `assets/content/pdfs/statutes/` | No: one L.R.O. edition each, mostly L.R.O. 2002 (PDF mod dates 2011–2015) | robots: Crawl-delay 10. Has no Data Protection Act. |
| barbadosparliament-laws.com (the "laws portal": Consolidated Statutes, Acts, Gazette) | 200 shell | JS app; its data comes from `/api/BrowseAct` etc. | unknown | The API answers `{"type":"legal_error","message":"Api BrowseAct Access Forbidden"}` unless the request sends a `Secret-Code-Key` header that its JS generates (front-custom.js getSecretCode). **This is an anti-automation gate, so I did not bypass it.** Next step: read it only through Wayback or Common Crawl captures. Assets are on d3rjznhzn844vx.cloudfront.net. |
| barbadosparliament.com | 200 | HTML; bills at /bills/details/N with PDFs at uploads/bill_resolution/*.pdf | bills only | robots disallows only /basecamp/. The gazette link goes to governmentprintery.gov.bb/the-online-gazette/ (not probed yet). |
| governmentprintery.gov.bb | not probed | | | Official Gazette, so likely the source of the Acts as published |

## Cached (in `.cache/`, by sha256 of the URL; base https://www.barbadoslawcourts.gov.bb/assets/content/pdfs/statutes/)
- `ConstitutionofBarbados.pdf`: 121 pp, L.R.O. 2002, text layer present (233k chars, clean). Its producer is the "Acrobat 3.0 Scan Plug-in", so check the text quality before relying on it.
- `Constitution(Amendment)Act,1974.pdf`: 16 pp, L.R.O. 1978, text layer
- `BarbadosIndependenceAct&Order,1966.pdf`: 17 pp. The text layer has OCR errors ("Printed io Eoglaod"), so don't use it as legal text.
- `CompaniesCAP308.pdf`: Cap. 308, 297 pp, L.R.O. 2002, typeset with a clean text layer. This is the Phase 1 core act candidate.

## Exact next step
1. Run the Wayback CDX (`wayback.captures(..., match='prefix')`) for `barbadosparliament-laws.com/` and `d3rjznhzn844vx.cloudfront.net/`. If you find a Constitution PDF dated after 2021 (it would include the republic amendment), that is today's text. Do the same for Data Protection Act 2019-29.
2. Find each post-2002 Constitution amending act as gazetted, through governmentprintery.gov.bb or archive captures, including the Constitution (Amendment) (No. 2) Act 2021 (republic, in force 30 Nov 2021). Each needs a text layer; leave out scans and name them.
3. Build L.R.O. 2002 as the oldest available version (`first_law: null`), then replay the amendments, then check the result against the newest consolidated text.

## Open issues
- There is no official consolidated text after about 2002 that I could reach without the laws-portal API gate.
- There is no direct source for the Data Protection Act yet.
