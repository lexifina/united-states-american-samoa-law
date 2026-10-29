CHECKPOINTED 2026-10-29T00:40Z (wind-down; run stopped by coordinator)

# Dominican Republic (gitlaw-DO) progress

Slug `dominican-republic`, code DO, tz America/Santo_Domingo, lang es, future branch `futuro`, on-date tool `en_vigor_el`.
Repo lexifina/dominican-republic-law (private scaffold, root "sources, before any law"). Scaffold read in `.tmp-build/scaffold`
(README, SOURCES.md, jurisdiction.json with build "gazette": fold into `repo/`). No corpus.json yet, so nothing builds; no PUBLISH.

## Checklist

- [x] Read WAVE.md, FANOUT.md, BRIEF.md, git_for_law.md, SCHEMA.md
- [x] fetch.py (copy of the Venezuela fetcher: curl --compressed, sha256 cache, requests.jsonl, 3 req/s per host)
- [x] Probe sources (below); all Phase 1 texts are CACHED, with text layers. See `sources.json` (URL -> cache path).
- [ ] parse.py -> corpus.json (NEXT STEP)
- [ ] repo/: README (EN + ES), LICENSE, jurisdiction.json (build: real status), tools/en_vigor_el.py
- [ ] test build in .tmp-build, check.py 0 mismatches, --compare; then PUBLISH

## Probe results (2026-10-28/29)

| Source | Result |
|---|---|
| consultoria.gov.do (CJPE, new Next.js site) | Home/JS fine; robots allows all but /api/auth, /api/admin. `/uploads/constitucion_YYYY.pdf` (listed in the JS) all 404. `POST /api/consultas/search` hits a Cloudflare challenge: NOT used (never touch bot challenges). `GET /api/consultas/catalog`, `/document-types` work; `GET /api/document/{DocId}` needs DocIds from search, so unusable. |
| consultoria.gov.do OLD site via Wayback | CDX (domain, PDFs only): 1,110 PDFs, list saved `.tmp-build/consultoria_pdfs.json`. Includes CJPE's constitution archive `constituciones%201844-2008/Constitucion%20YYYY.pdf` for 1844...2015 (Phase 2: all historical constitutions as one act). |
| tc.gob.do | TLS cert expired (curl SEC_E_CERT_EXPIRED); not used directly. Its blob storage (tribunalsitestorage.blob.core.windows.net) works. |
| camaradediputados.gob.do | robots allows all. wpfd file sitemaps list 6,230 files (`.tmp-build/wpfd_urls.txt`); only 58 are laws. Has Constitución 2024 + Ley 172-13; no Código Penal, no Ley 44-26. |
| dgii.gov.do | Hosts CJPE's official consolidated Código Penal special edition (see below). |

WebSearch used: 4 of 4.

## Phase 1 sources (all cached, all text layer, `pdftotext -enc UTF-8 -layout` works)

1. **Constitución** (act `constitucion`), 3 full texts (each reform republishes the whole text; diff them, credit the diff to the reform):
   - 2010: CJPE G.O. 10561, 26 Jan 2010, Wayback id_ 20100524181408. cache `.cache/wb/61ba4cf0...`.
   - 2015: CJPE copy, Wayback id_ 20151117220141, cache `.cache/wb/2838f1c1...`; cross-checks: DGCP-hosted CJPE G.O. 10805 copy (`.cache/52ae2e96...`, "certifica que la presente publicación es oficial") and TC 2022 edition (`.cache/a6756515...`). The 2015 reform is said to touch art. 124 + a new transitional disposition: confirm by diff.
   - 2024: Cámara de Diputados first edition (`.cache/dc3d2d59...`, 83 MB, front matter + presentación to strip). Proclaimed 27 Oct 2024. Gazette number not yet confirmed.
   - In-force date: check the text's own final disposition (proclamation vs G.O. publication; WIPO lists 2015 in force 10 Jul 2015 = publication). Decide and record in `decisions`.
2. **Ley 172-13** datos personales (act `ley-172-13`), 1 version: promulgated 13 Dec 2013, G.O. 10737 of 15 Dec 2013. cache `.cache/` URL in sources.json. Text starts at page -44- with the tail of the previous law in the compilation: start at "Ley No. 172-13 que tiene por objeto", strip "-NN-" page markers and rule lines.
3. **Código Penal, Ley 74-25** (act `codigo-penal`): CJPE G.O. 11257 edición especial (14 Aug 2026), text at `.tmp-build/cp_dgii.txt` (regenerate from cache). Ley 74-25 of 3 Aug 2025, G.O. 11208 of 5 Aug 2025; art. 393: in force 12 months after promulgation and publication (CJPE note implies 5 Aug 2026). Amended by Ley 44-26 (27 Jul 2026, G.O. 11254 of 5 Aug 2026). 29 footnotes: "Texto original del artículo N: ..." (original 74-25 wording, flattened into one paragraph: split at "Párrafo" / "N)" markers) and art. 31 of Ley 44-26 deferring arts 8, 9, 10, 11 to "tres meses a partir del 5 de agosto de 2026" (= 2026-11-05, after docs date -> `futuro`). Parsing gotchas: footnote numbers glue onto article numbers ("Artículo 1045.-" = art. 104 + fn 5; use the expected sequence), "(Modificado por ...)" / "(Agregado por ...)" annotations must be removed from text and used as credits (also on items, e.g. art. 238 items 7 and 8), footnote blocks at page bottoms must be removed from body.
   Proposed versions: v1 2026-08-05 original 74-25 (first_law ley-74-25; originals from footnotes); v2 same_day 2026-08-05 Ley 44-26 changes, arts 8-11 removed (not yet in force, note it); v3 2026-11-05 arts 8-11 commence (futuro). OPEN: Ley 44-26's own entry-into-force clause is not in the special edition; no official copy of Ley 44-26 found yet (phlaw.com has an unofficial PDF; do not use its text). Default in-force rule (Código Civil art. 1) also still needs an official source.

## Phase 2 ideas

- All historical constitutions 1844-2010 from the CJPE Wayback archive (check text layers; older ones may be scans = no OCR).
- Código Civil: not yet probed (no official consolidated source found; the register says CJPE is "not consolidated").

## Open issues

- None for the shared builder yet (nothing built).

## STOPPED 2026-10-29 (gitlaw-DO-2): remote main is not the bare scaffold

Read-only check (`git ls-remote` + bare clone to scratch) of lexifina/dominican-republic-law:
- `main` == `wip` == e3bf2d7 "Documentation, tools and REPRODUCE.md" (2026-10-28), 4 commits, NO "sources, before any law" root.
- History: b874233 Constitución de 2010 (2010-01-26) -> 11b765d Reforma 2015 (2015-06-13) -> fdc9406 Reforma 2024 (2024-10-27); tags constitucion/2010, reforma/2015, reforma/2024.
- It is another session's Constitution build with its own tooling (tools/build.py, parse.py, reproduce.py, in_force_on.py; corpus.json is a different format, "do/national/acts"), sourced from new consultoria.gov.do `/uploads/<id>.pdf` URLs, dates = proclamation days.
- Per instructions: no parse.py, no build, no PUBLISH. The user must decide which build wins before this folder's work continues.
