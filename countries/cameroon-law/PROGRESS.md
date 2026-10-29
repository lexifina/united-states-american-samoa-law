# gitlaw-CM: Cameroon law history (progress, handoff 2026-10-29 00:45 UTC)

Slug `cameroon`, repo `lexifina/cameroon-law` (PRIVATE), clone `C:/Users/alany/Documents/cameroon-law` (autopush owns it).
tz Africa/Douala, lang fr (+ en where an official text-layer exists), future branch `future`. Rules: `scripts/africa-law/FANOUT.md`.
Not a Peachjam country (no Cameroon LII). **No PUBLISH: preview only.**

## Status
- [x] fetch.py (curl, sha256 cache, 1 req/s gov hosts; archive.org via gitlaw_common/wayback.py)
- [x] Probe done (below). 4/4 WebSearch used.
- [~] parse.py -> corpus.json: Constitution (fr), 1 version dated 2008-04-14, 68 units. UNVERIFIED preview.
- [ ] Penal Code 2016, Loi 2024/017 personal data: NOT POSSIBLE under no-OCR (scans only).

## Open bugs / exact next steps
1. parse.py misses Article 1 (heading is probably "ARTICLE PREMIER"; extend the regex) and the TITRE headings go nowhere.
   Paragraph joining is heuristic; check every article against the PDF by word count before any PUBLISH.
2. Loi 2026/002 of 14 April 2026 amends the Constitution; only a scan exists (prc.cm `/files/b4/44/82/682c...pdf`,
   HP Scan, no text). Today's text therefore != latest expression -> never PUBLISH until a text-layer copy is found.
3. English Constitution: the only text-layer English copy found is an Africa Agenda booklet (`Const.ofCameroon2008.pdf`,
   Wayback 20240612092258 on chambredescomptes.cm) — NGO-printed, not official; not used. Its first capture
   (20240520212452) is truncated (1 MiB).
4. In-force rule not sourced (versions dated by promulgation). Find the Cameroon publication/urgency-procedure rule.

## Sources probed (2026-10-28/29)
| Source | Result |
|---|---|
| prc.cm (robots allows /files/, /en/; disallows /media/) | Law pages + `/en|fr/multimedia/documents/<id>` -> `/files/..pdf`. ALL scans: 96/06 (34 pp, no text), 2008/001 (Paper Capture OCR), 2016/007 Penal Code EN (139 pp, OCR layer with errors: "ta refrain", "persan"), 2019/020 (OCR), 2024/017 data law FR (scan), 2026/002 (scan). Index of EN law pages: .cache/prc_laws_en.json |
| assnat.cm | `images/constitution.pdf` image-only scan (download truncated). Adopted-laws list covers 2017–2019 only |
| spm.gov.cm | decrees/appointments only |
| WIPO Lex (wipolex-res.wipo.int/.../cm/cm014en.pdf -> HTML) | Penal Code 2016 HTML is OCR-derived ("the Jaw set out below"); not used. Signed PDF links expire |
| chambredescomptes.cm (Wayback; live site rebuilt, old blobs 404) | **La_Constitution.pdf**, born-digital Word PDF 2015-05-26, 30 pp, French consolidated 1996+2008 with "(nouveau)" marks. Capture 20240422094215, pinned in parse.py. Other files: audit reports, not law |
| conseilconstitutionnel.cm, minjustice.gov.cm | connection failed (000) |
| senat.cm, antic.cm, minpostel.gov.cm | homepages cached, not explored |

Cache: `.cache/` (~85 MB, mostly prc.cm scans). Requests in `.cache/requests.jsonl`.
