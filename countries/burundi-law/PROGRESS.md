# Burundi (BI): progress of gitlaw-BI

Repo lexifina/burundi-law (PRIVATE). tz Africa/Bujumbura, lang fr, future branch `futur`, on-date tool
`en_vigueur_au`. Rules: scripts/africa-law/FANOUT.md. Not a Peachjam LII country.
Checked 2026-10-28 23:07 UTC: remote main = scaffold only (0c1a293 "Burundi: sources, before any law", 1 commit, no
other branches). Clone at C:/Users/alany/Documents/burundi-law (autopush owns it; nothing built into it).

Status at wind-down (2026-10-29 ~00:40 UTC): **no corpus.json, no PUBLISH.** Nothing is built yet: no text-layer
official source has been found for the Phase 1 acts.

## Checklist
- [x] Read FANOUT, both BRIEFs, SCHEMA, PEACHJAM, memory/git_for_law.md
- [x] fetch.py (curl --compressed, sha256 cache, <=3 req/s per host, 429/503 back-off, requests.jsonl; wayback.py import)
- [x] Probe presidence.gov.bi and assemblee.bi (below)
- [ ] Find a text-layer official text of the 2018 Constitution (presidence copy is a scan)
- [ ] Code pénal 2017 (Loi n° 1/27 du 29 décembre 2017): official text-layer source not yet found
- [ ] Third act
- [ ] parse.py, corpus.json, .tmp-build + check.py, README (EN then FR), LICENSE, PUBLISH

## Sources probed
| Source | Result |
|---|---|
| presidence.gov.bi | 200. robots.txt: `User-agent: * / Disallow:` (Yoast). WordPress REST media API open: `/wp-json/wp/v2/media?mime_type=application/pdf&per_page=100&page=N` lists 2,898 PDFs (cached). `/bulletin-officiel/` 404. Constitution: `wp-content/uploads/2018/07/constitution-promulguee-le-7-juin-2018-1.pdf` (4.7 MB, PDF-1.3) is an **image scan, no text layer** (pdftotext gives 59 bytes) -> not usable (no OCR). Laws posted 2014-2019 as `loi-NN-YYYY-1.pdf` (text layer not yet checked); no Code pénal found. Most 2020+ uploads are decrees/communiqués, many named scan*/numerisation*. |
| assemblee.bi | 200 (www. 301s to bare host). robots.txt 404. REST media `index.php?rest_route=/wp/v2/media&mime_type=application/pdf` lists 589 PDFs (cached): laws 2003-2012 (`loi_n1-NN_du_...pdf`), `2023/11/exp_Code_proc_pénale.pdf` (exposé des motifs), `2024/01/code-electoral2019.pdf`, recent `n°NN-du-...-2026.pdf`. `/2024/03/06/textes-de-reference/` 404. No Constitution or Code pénal PDF. |
| Common Crawl | `wayback.cc_crawls()` returned no crawls (index.commoncrawl.org collinfo fetch failed from this machine, as Senegal also saw), so the domain survey of gov.bi/assemblee.bi PDFs returned 0. Retry first. |
| WebSearch (1 of 3 used) | Code pénal 2017 copies: FAOLEX `faolex.fao.org/docs/pdf/Bur185179.pdf` (scan with rough OCR layer: not usable), lemandat.org copy of droit-afrique.com (private compiler: not official). refworld.org holds `sites/default/files/2025-01/constitution-promulguee-le-7-juin-2018.pdf` (same file name as the Présidence scan; text layer not checked). |

Cache: .cache/ (requests.jsonl): presidence + assemblee media listings, the Constitution scan, ecoi listing in .tmp/.
Media index extracted to .tmp/media.json (3,487 PDFs: date, URL, title).

## Exact next step
1. Retry Common Crawl (`wayback.cc_crawls(CACHE)`; if empty, check `curl https://index.commoncrawl.org/collinfo.json`),
   then run .tmp/ccsurvey.py for PDFs under gov.bi / assemblee.bi; look for a text-layer Constitution 2018 and Code
   pénal 2017.
2. Check refworld's constitution PDF for a text layer (if it is the same scan, it is out).
3. If no text-layer Code pénal exists from an official source, skip it (note in decisions) and take a third act from
   the presidence 2017-2019 `loi-NN-YYYY-1.pdf` set that has a text layer (check with pdftotext first).
4. Archive.org CDX (`wayback.captures('presidence.gov.bi/wp-content/uploads/', match='prefix')`) only for what CC lacks.

## Open issues
- No official text-layer source yet for either Phase 1 act; the Présidence Constitution is a scan.
- No background processes left running.
