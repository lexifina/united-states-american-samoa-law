# Equatorial Guinea (gitlaw-GQ) progress

Last update: 2026-10-29 ~07:30 UTC, session gitlaw-BF-GQ. corpus.json written (preview only). **No PUBLISH.**

## Checklist
- [x] Remote check (ls-remote, read-only, 2026-10-29): `main` = cd2b3de "Paused, not yet law: gazette only, one unversioned constitution PDF" on 6f4f740 "sources, before any law"; `wip` = e1f0cae. No law commits.
- [x] Why it was paused (cd2b3de README): BOE has no consolidation/past versions/amendment notes, and its Ley Fundamental PDF (FPDF, 2020-11-27) had lost its accents. A **source-availability** pause, not a rights problem, so building was allowed. The accent problem is gone: the same URL now serves the accented file.
- [x] BOE search listed (POST /resultados + GET /masresultados?offset=N with a cookie jar, ~1 req/s): CONSTITUCIÓN category = 0 documents; LEYES = 110 documents; title "Ley Fundamental" = 2 (Ley 1/2012 and **Ley 1/2025**); title "Penal" = 0 (no Código Penal on the BOE).
- [x] Older texts (1991, 1995): Internet Archive CDX of boe.gob.gq (via wayback.py) has only the same 2012 file (captures 20220525, 20261007). Common Crawl index timed out from this machine (index.commoncrawl.org, 20 s, 2026-10-29 ~07:00 UTC). Not found.
- [x] Later reform: **Ley Nº 1/2025, de fecha 16 de julio, reforms arts. 56.1, 80 and 84.1 y 2.** BOE file `/files/MODIFICACIÓN DE LA LEY FUNDAMENTAL.pdf` (FPDF 2026-09-09, 5 pages): scan, only the e-signature line is text. Not applied (no OCR); in-force date unknown. So the 2012 text is NOT today's text.
- [x] fetch.py (curl, sha256(url) cache in .cache/, requests.jsonl, 1 req/s), parse.py (PyMuPDF) → corpus.json
- [x] repo/README.md (EN + ES), LICENSE, jurisdiction.json, tools/en_vigor_el.py
- [x] Scratch build (scratchpad/gq-build, --docs-date 2026-10-29): check.py 0 mismatches / 0 trailer errors; `--compare` identical (history tip 8d36af0)
- [ ] PUBLISH: not possible — today's text needs Ley 1/2025 (scan only).

## Corpus
- Act `ley-fundamental`, 1 version from 2012-02-16 (promulgation, Bata; Disposición final: in force on promulgation + BOE publication; BOE gives no separate publication date). `first_law` = `ley-1-2012` (as enacted).
- 142 units: introduccion, preambulo, art-001..art-134 (none missing), disposicion-transitoria-1/2, disposicion-derogatoria, disposicion-final, formula-final, estructura.
- Source: `https://boe.gob.gq/sites/default/files/2026-10/LEY%20FUNDAMENTAL_0.pdf`, sha256 16d61b73…a89a25 (identical to `/files/LEY%20FUNDAMENTAL.pdf`; parse.py checks this). The old manual copy `.cache/raw/LEY_FUNDAMENTAL_0_2026-10.pdf` is the same bytes.
- Check: every word of the corpus compared with pdftotext's extraction; differences only in headings/title page (excluded) and pdftotext word-merging artefacts. parse.py deterministic (same md5 twice).

## Open
- To publish: a text-layer copy of Ley 1/2025 (and its in-force clause). Retry Common Crawl for boe.gob.gq / guineaecuatorialpress.com when the index answers.
- Phase 2 candidates in BOE LEYES (as enacted, one version each): Ley Orgánica del Poder Judicial 5/2009 (+ Ley 2/2026 amending it), Ley Orgánica del Tribunal Constitucional 4/2011. Not started.
- No ISSUES filed. No background processes running. WebSearch used: 0.
