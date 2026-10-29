# The Gambia (gitlaw-GM): progress

Slug `gambia`, repo `lexifina/gambia-law` (private scaffold, untouched), tz Africa/Banjul, language en, future branch `future`.
Rules: `scripts/africa-law/FANOUT.md`, `BRIEF.md`, `scripts/south-america-law/BRIEF.md`, `scripts/gitlaw_common/SCHEMA.md`.

## Status (2026-10-28, 22:20 UTC): probed; no corpus.json, and nothing built

None of the Phase 1 targets can be built to the standard from the allowed sources: government sites plus any LII through archives only. There are two reasons, and both are blockers:

1. **Every Constitution amendment after 2001 survives only as a scan.** Under the no-OCR rule none can be applied.
2. **No allowed source gives an in-force date for any version.** Constitution s.100(7) brings an Act into operation on its publication in the Gazette. No Gazette for these Acts is online, and the Acts' date brackets are blank.

So no `corpus.json` was written, and autopush only snapshots this folder to `wip`. No PUBLISH.

## Checklist
- [x] Probe the National Assembly (assembly.gm) and the Ministry of Justice (moj.gm); record robots, formats and dates
- [x] Look for a Gambian LII: none exists. gambialii.org, gambialii.gm and www.gambialii.gm do not resolve in DNS. An archive.org CDX query for them timed out. Laws.Africa has no Gambia LII, so there is no Akoma Ntoso source.
- [x] fetch.py (shared Peachjam `Cache`, imported read-only), with a cache in .cache/
- [x] sources.json lists every probed document with its sha256, page count, text-layer size and status
- [ ] Constitution: blocked (see below)
- [ ] 2 core acts: blocked (see below)

## Sources
| Source | robots / terms | What it has |
|---|---|---|
| assembly.gm (National Assembly) | robots.txt `User-agent: * / Disallow:` (all allowed) | `/documents/type/acts?page=1..9` lists 537 entries, mostly 1998–2024. Each entry has a page `/documents/<id>` and a PDF `/documents/<id>/download`. The "Published" dates are 2026 upload dates, not law dates. `/constitution` links the 2002 reprint PDF (DigitalOcean Spaces). `/bills` is a bill tracker. |
| moj.gm (Ministry of Justice; moj.gov.gm does not resolve) | no robots.txt (404) | `/downloads` has the Constitution "1997 (2002 revision)", the NHRC Act 2017, the TRRC Act 2017, the CRC Act 2017 and the Victims Reparations Act 2023. `/legislative-year-2017` and `-2018` list Acts with passed and **assent** dates and Act numbers. They do not give Gazette dates. |

Cache: 21 MB, 50 requests (.cache/requests.jsonl), all at 1 request per second. archive.org: one CDX attempt, which timed out with no result; Common Crawl: none.

## Findings
- **Constitution text.** The only text-layer copy is the 1997 Constitution "REPRINED [sic] 2002", 142 pages. The NA and MoJ PDFs give identical extracted text.
  - It includes Act No. 6 of 2001. Margin notes read "6 of 2001", and some sections read "Deleted by No. 6 of 2001", but the deleted text is not given.
  - So the 1997 text as enacted can't be produced. Reconstructing it would mean placeholders for every section the 2001 Act touched.
  - The reprint has no date to the day, and no allowed source gives the 2001 Act's Gazette or in-force date. A non-government law report (lawhubgambia.com, Jammeh v AG) gives assent on 25 May 2001.
- **The reprint is not accurate law even for 2002.** Its s.1 reads "The Gambia is a Sovereign Secular Republic".
  - The CRC Explanatory Memorandum (MoJ, 30 March 2020, footnote 1) says the Supreme Court declared the 2001 "secular" amendment unconstitutional, because the entrenched s.1 was never put to a referendum.
  - It says that s.1 "remains as it was originally approved". It also says the 2009 Revised Edition still prints "secular" with an asterisk.
  - A court law would need the ruling's date, which none of our sources gives.
- **Later amendments are scans only.** The amending Acts of 2004, 2006, 2006 (No. 2), 2007, 2015, 2017 and 2017 (No. 2) are 2–3 page phone or mlkit scans with no text layer, so they are excluded under the no-OCR rule. The 2009 Act's download answered HTTP 500 twice.
  - The MoJ table says "Constitution (Amendment) Act, 2017" (No. 2 of 2017, passed 28 February 2017) "Was not assented to due to procedural defect". "Constitution (Amendment No. 1) Act, 2017" is Act 5 of 2017, assented 27 July 2017.
  - The Constitution (Amendment) Bill 2023 has a text layer (it amends s.152), but the NA bill tracker marks it "Rejected".
- **Acts with a text layer.** These are the Labour Act 2023 (NA 16), The Gambia Anti-Corruption Act 2023 (NA 24), the Children's Act 2005 (NA 285), the Victims Reparations Act 2023 (MoJ) and the NHRC Act 2017 (MoJ).
  - All are as-passed texts, and their date brackets are blank (`[ ]`).
  - The Children's Act and the NHRC Act commence by ministerial Order. The others commence on Gazette publication. None of the Orders or Gazettes is online.
  - The NHRC PDF still carries Word tracked-change markup ("Deleted:", "Formatted:").
  - The Children's Act 2005 and Women's Act 2010 were amended in 2015, and those amending Acts are scans. The Women's Act PDF is itself a scan with a third-party text layer.
- **Further scans.** The MoJ copies of the TRRC Act and the CRC Act are scans (42 characters of text), stamped "Document Sourced from www.lawhubgambia.com".

## What would unblock it
- The Gambia Gazette issues (with dates) for the chosen Acts, from an official text-layer source or a dated official commencement list. The MoJ assent tables cover 2017–2018 only, and assent is not commencement.
- An OCR exception for the amending-Act scans. They are short (2–3 pages each), about 10 Acts in all.
- The 2009 Revised Edition of the Laws of The Gambia, if it is ever published with a text layer.

## Files
- `fetch.py`: with no arguments, it fetches the listing pages and every document in sources.json. With URLs, it fetches those. Rate: assembly.gm 1/s, moj.gm 5 s (the adapter default).
- `sources.json`: the probe record, pinned by sha256.
- Nothing for the shared Peachjam adapter to adopt: The Gambia has no Peachjam LII.
