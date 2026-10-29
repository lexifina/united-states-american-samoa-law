CHECKPOINTED 2026-10-29T02:40:00Z

# Bolivia (gitlaw-BO) progress

Slug `bolivia`, repo lexifina/bolivia-law (PRIVATE, never change), clone `C:/Users/alany/Documents/bolivia-law` (owned by autopush; do NOT build into it or push). tz America/La_Paz, lang es, future branch `futuro`. Brief: `scripts/south-america-law/BRIEF.md` (its "Changed after the restart" section overrides steps 5 and 6: autopush.py builds and pushes every corpus.json change; result in BUILD_STATUS.json; test builds go in `.tmp-build/`).

## Checklist
- [x] Probe sources (2026-10-28)
- [x] fetch.py (curl `--compressed` since 17:30 per coordinator; sha256(url) cache in .cache/, 1 req/s/host, .cache/requests.jsonl; 38 requests, ~19 MB)
- [x] acts_meta.py (country, laws, sources(), DECISIONS, AI_USE, CPE_EVENTS)
- [x] parse.py runs: `python -X utf8 parse.py` (or `--dry` to write only crosscheck.json). Writes corpus.json atomically (tmp + rename).
- [x] crosscheck: 412 units (411 arts + closing block) vs TCP and Diputados: 0 Gaceta-only wording diffs; 47 Gaceta-only punctuation diffs (kept as printed); 14 single-edition wording diffs (listed in decisions -> REPRODUCE.md). Preamble TCP == Diputados (7 paras).
- [x] repo/README.md (+ Spanish), repo/LICENSE, repo/jurisdiction.json (build set), repo/tools/en_vigor_el.py
- [x] test build in .tmp-build/repo: 4 commits + docs, 8 tags, check 0 mismatches, `--compare` history identical (history tip 1024416)
- [x] autopush preview build 96649b9 pushed, check 0 mismatches (17:25Z)
- [x] PUBLISH created ~17:29Z. autopush did not react to PUBLISH alone (ISSUES.md #4); re-running parse.py (new request counts) triggered it: **main pushed 6baf972 at 17:33:33Z** (history tip 1024416, 8 tags; preview 96649b9, wip 896fbc9). Remote README has the final text.
- [x] ISSUES.md: 3 minor builder items (no-words line with note; no Affecting for no-words credits; event needs a full units copy)
- [x] Phase 2 probe (17:30Z), result: NOT POSSIBLE to the standard. Wayback has no capture of Gaceta `buscar_comp/12760`, `/10426`, `/1768`. `listadonor/11` = 28,185 decretos (newest first), `listadonor/16` = 41 sentencias constitucionales (none on the CPE). WebSearch (2nd BO call, 2 of 12 used) found no official consolidated Código Civil or Código Penal on any gob.bo site; only commercial/volunteer copies (vlex, infoleyes "texto original", lexivox), which we may not use. Without an official current text there is nothing to check a replay against, so no Civil or Penal Code is added. README "What it does not show" already says so.

## Session 2026-10-29 (gitlaw-BO, deepening): Código Civil added as corpus.d/50-codes.json
- [x] **New source: SILEP** (Sistema de Información Legal del Estado Plurinacional, Vicepresidencia). silep.gob.bo does not resolve here, but the Internet Archive has ~650 SILEP URLs (`wayback.captures('www.silep.gob.bo/', match='prefix', collapse='urlkey')`). Views: `/norma/<id>/ley_actualizada` (current consolidated text; per article only the LAST affecting law: "Modificado por Ley Nº N de ...", "Derogado por ley Nro. N de dd/mm/yyyy", "Insertado por ley Nro. N - TITLE", "Declarado Inconstitucional por SCP N de ..."), `/texto_ordenado`, `/leyes` (historial: plain text, NO markers), `/api/v1/documento_actualizado/<id>/pdf`. Footer: not a legal reference, the Gaceta is. Some captures are truncated at exactly 1 MiB (silep.py refuses them: no "Fuente" line).
- SILEP ids: 4451 Código Civil (1 capture 20240224013706); 4368 Código Penal (complete captures 2020-09-07..2024-01-24, text identical); 4311 CPP (captures 2022-2025); 4465 Código de Comercio (2020 captures, also /leyes and /texto_ordenado); 15931 Ley 1390 (2021); 16260 Ley 1639 (2025, modifies Ley 603). Others captured: 895, 1182, ... 4660, 12733..16260 (not identified).
- [x] Common Crawl tried once: `cc_crawls` returned [] (index unreachable). archive.org only.
- [x] `silep.py` (page -> headings + blocks + notes), `fetch_codes.py` (pinned captures via wayback.get), `parse_codes.py` (writes corpus.d/50-codes.json atomically + codes_report.json; `--dry`).
- [x] **Código Civil** (`codigo-civil`, short CC): 1 version, first_law null ("oldest version available"), from 2024-02-24 (capture day; Ley 060's Gaceta publication day not sourced), 1570 articles + estructura (812 heading lines), earlier_laws = DL 12760 + Leyes 1367/1992, 1654/1995, 1777/1997, 2089/2000, 004/2010, 018/2010, 060/2010; version note lists the 18 articles SILEP marks. Art. 1537 is an unnumbered SILEP "Artículo DEROGADO..." block (assigned by sequence).
- [x] Scratch build `.tmp-build/codes` (empty dir): 5 commits, 9 tags; check.py 0 mismatches / 0 trailer errors; `--compare` identical (history tip 9255270). `tools/en_vigor_el.py 2025-01-01 codigo-civil 1570` works.
- [x] `corpus.d/50-codes.PUBLISH` written; repo/README.md (table, dates, checks, gaps, sources, licence, Spanish) and repo/jurisdiction.json updated. ISSUES.md #5 (per-act publisher).
- [x] **Código Penal NOT built:** SILEP's page lacks Ley 1390 of 27/08/2021 (SILEP's own page for Ley 1390 shows arts. 2-3 modifying/inserting ~35 Código Penal articles); latest note on it is Ley 1173 (2019-05-03). No current official consolidated text => a replay can't be checked. Ministerio de Justicia *texto ordenado* 2010 (TSJ-hosted PDF `tsj.bo/wp-content/uploads/2019/11/codigo-penal-y-procedimento-penal.pdf`, text layer, DS + RM 404/10) is older still.
- Data protection law: Bolivia has none (only bills), so Phase 1's third act is the Penal Code, which is blocked as above.
- Probed and rejected: diputados.gob.bo WP media API (7,133 PDFs; `Leyes/Ley_N_0001..1257.pdf` + `2022/12/LEY_N_14xx.pdf`) = scans with poor publisher OCR (439, 348) or no text layer (1173, 603); tsj.bo WP media (365 PDFs: Ley 439, 603, 025, 1173 ... as enacted; 2015 Ministerio de Justicia penal compilation); Gaceta `app/webroot/archivos/` has only the CPE and a few decrees.
- Not attempted (45-min rule): Código de Comercio (SILEP 4465: /leyes has no markers, so only a 2020 snapshot; amendments after 2019 unknown), CPP (SILEP 4311 lacks Ley 1390's CPP changes, so stale).
- WebSearch: 3 of 12 used by BO (3rd: found Ley 1071/2018 raised the Código Civil to law rank; no later text amendment found).
- Cache: 108 MB, 99 lines in requests.jsonl (wayback.py logs there too).

## Session 2026-10-29 (gitlaw-publisher-fix): Código Civil publisher = SILEP
- [x] `parse_codes.py`: `SILEP_PUBLISHER = {'name': 'SILEP (Vicepresidencia del Estado)', 'email': 'silep@silep.invalid'}` on the Código Civil act (SCHEMA.md "Per-act publisher"); the publisher decision rewritten. `corpus.d/50-codes.json` regenerated (deterministic; only `publisher` and that decision changed; codes_report.json identical). repo/README.md "What author means" updated.
- [x] Scratch build (empty dir, docs-date 2026-10-29): 5 commits, 9 tags; CC commit a8acb72 authored by SILEP (was 9255270, Gaceta); CPE commits unchanged (97f3e54, ea30fb8, 348f22c, 91812d8); check.py 0 mismatches / 0 trailer errors; `--compare` identical. ISSUES.md #5 closed. No new PUBLISH needed (50-codes.PUBLISH exists); the next 4-hourly pass publishes.

## Constitution: what is built
- Act `constitucion` (short CPE), 426 units: promulgacion, preambulo, estructura, art-001..art-411, disp-transitoria-01..10, disp-abrogatoria, disp-final.
- Versions (all the same text, Gaceta PDF): 2009-02-07 as enacted (first_law cpe-2009, kind referendum); 2016-02-21 referendo-2016 (art-168); 2017-11-28 scp-0084-2017 (arts 156,168,285,288, kind court); 2023-12-28 scp-1010-2023-s4 (arts 156,168). The last three are no-words-changed commits with a law `note`.
- Facts for the events come only from SCP 1010/2023-S4 (cache 0a5df836…, PGE-hosted, 82 pp) and CIDH Informe 121/24 (cache 0968e0db…). Vote counts are only quoted in the README as the CIDH's petitioner account. The number and date of the convocation law (Ley 757?) are NOT verified and not stated.

## Sources (probe, 2026-10-28) — exact URLs
| Source | Status | Use |
|---|---|---|
| Gaceta Oficial gacetaoficialdebolivia.gob.bo | live site: connect timeout. Wayback has Oct 2026 copies. | **CPE primary text:** `https://web.archive.org/web/20261006172245id_/http://www.gacetaoficialdebolivia.gob.bo/app/webroot/archivos/CONSTITUCION.pdf` (cache af43978f…; 111 pp, "TEXTO DE CONSULTA"). No preamble. Site paths: `/normas/verGratis_gob/<id>`, `/normas/descargarPdf/<id>`, `/normas/buscar_comp/<lawno>` (norms citing a law; cards with edition, publication date, title, links), `/normas/listadonor/10` (5,617 leyes, 50/page), `/listadonor/11`, `/16`, `/normas/listadofec`, `/edicions/view/<n>NEC`. CDX: `https://web.archive.org/cdx/search/cdx?url=<url>&output=json` (prefix * queries 504). |
| TCP tcpbolivia.bo (bare host) | 200 | `https://tcpbolivia.bo/wp-content/uploads/2025/04/CPE_2009.pdf` (2023 edition; ligature glyphs fixed in norm). `/normas-inconstitucionales/` PDFs cached. buscador.tcpbolivia.bo = Angular app over `/api/buscador-tcp/*` (not explored). |
| Cámara de Diputados | 200 | `https://diputados.gob.bo/wp-content/uploads/2025/11/constitucion_politica.pdf` (has preamble; kerning artefacts). |
| Procuraduría General del Estado | 200 | iad_121_24.pdf (CIDH report) and `_Opinion/ant/SENTENCIA10102023S4.pdf` (SCP 1010/2023-S4, fetched). |
| presidencia, organojudicial, sepdep | 200 | no usable CPE PDF |
| silep.gob.bo, web.senado.gob.bo | DNS fail | |
| oep.org.bo | TLS reset | |

## Gotchas
- WebSearch cap: 12 total shared; 1 used by BO.
- Python urllib fails TLS; always curl. PyMuPDF (fitz) installed; `python -I` hides it, so run parse from this folder without -I (only cached PDFs are read, as data).
- Gaceta prints "CAPITULO"/"TITULO" unaccented sometimes, lone "I"/"II" numerals without period (arts 144, 182); TCP splits "Artículo"/"353." over two lines and puts the PREÁMBULO heading after the first page. All handled in parse.py.
- Heredoc python with regex escapes is fragile; use the Edit tool.
- Never commit in the main lexifina repo.

## Next steps
1. Nothing pushed by hand (cadence change): the next 4-hourly autopush pass publishes corpus.json + corpus.d/50-codes.json (PUBLISH files exist). Read BUILD_STATUS.json after it.
2. To rebuild: `python -X utf8 fetch_codes.py` (cache hits) then `python -X utf8 parse_codes.py`; test in an EMPTY dir under .tmp-build, check.py with `--corpus corpus.json` (it merges corpus.d), then `--compare`.
3. Possible depth, each needs a current official text first: Código Penal (replay Ley 1390 from SILEP 15931 onto SILEP 4368, but later laws, e.g. 2022, are unknown and nothing checks the result), Código de Comercio (SILEP 4465, 2020 snapshot only). Look for newer SILEP captures if silep.gob.bo comes back or Common Crawl's index becomes reachable.
