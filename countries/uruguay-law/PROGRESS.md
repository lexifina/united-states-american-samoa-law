CHECKPOINTED 2026-10-28T20:05Z

# Uruguay law history: progress (gitlaw-UY)

Slug `uruguay`, repo `lexifina/uruguay-law` (exists), clone `C:/Users/alany/Documents/uruguay-law` (OWNED BY autopush.py: never build or push into it). tz America/Montevideo, lang es, future branch `futuro`. Test builds go to `scripts/uruguay-law/.tmp-build` (gitignored). Results of autopush: `BUILD_STATUS.json`.

## Checklist
- [x] Read BRIEF (incl. "Changed after the restart"), memory/git_for_law.md, SCHEMA.md, PLAN.md
- [x] Probe IMPO and Parlamento
- [x] fetch.py (curl, cache `.cache/<sha256(url)>`, requests.jsonl, IMPO 10.5 s/request, others 1 s)
- [x] parse.py -> corpus.json (atomic write via corpus.json.tmp); also writes `repo/data/verification.json`
- [x] Constitution: 5 versions, 40 credited unit changes, 0 unexplained; test build + check.py 0 mismatches; `--compare` main_identical true
- [x] repo/README.md (English + español), repo/LICENSE, repo/jurisdiction.json
- [x] PUBLISH created 2026-10-28 ~18:00Z (see file)
- [x] Ley 18.331 (data protection): 7 versions 2008-08-28..2023-01-01, 18 credited unit changes, 0 unexplained; pushed main bff7d65 (autopush). Rebuilt by impo_history.py from IMPO notes + leyes-originales; in-force days from each amending law's own vigencia article (regex over cached text) or publication+10.
- [x] Código Civil: 18 versions 1994-12-01..2026-01-01, 135 credited unit changes, 0 unexplained, base_is_enactment=False (first commit "oldest version available", naming Ley 16.603). 2 unresolved intermediate texts (arts. 98, 1782) listed in verification.json. Vigencia articles read by hand: fetch.IMPO_ACTS['codigo-civil'][2]. Arts. 2393-2405 removed on Ley 19.920's day (IMPO "Ver vigencia ... derogó").
- [x] Size fix (coordinator 18:40Z): versions after the first are written as `changes` (parse.as_changes); corpus.json 1.46 MB with CC.
- [x] Phase 2: Código Penal: 36 versions 1934-08-01..2024-10-07, 196 credited unit changes, 0 unexplained, first_law ley-9155 (in force 1934-08-01 by Ley 9.414 art. 2; parse.BASE_IN_FORCE). IMPO records no amendment 1934-1969 (text = update of the Versión Oficial 1967); sample of 11 unamended articles equals IMPO's 1933 originals word for word. 25 articles with an unresolved intermediate text (verification.json). Vigencia by hand: Ley 15.903 art. 2, Ley 17.897 art. 23; Ley 19.138 (in force 10 days after its regulation) dated by default rule.
- [x] Final local check (20:01Z): 4 acts, 66 versions, 64 commits, 129 tags; check.py 0 mismatches, 0 trailer errors, 0 backwards, 0 future-dated; --compare main_identical true. today's text == IMPO for every act.
- [ ] Not done: Código de Comercio, Código del Trabajo (Uruguay has none: labour law is dispersed), Código General del Proceso (Ley 15.982), Código del Proceso Penal (Ley 19.293). Each is one `IMPO_ACTS` + `IMPO_TITLES` entry plus a fetch (~10.5 s per IMPO request; CP took ~300 requests / 52 min) and a vigencia_candidates pass by hand.

- [x] Batch 2 (gitlaw-UY-batch2, 2026-10-29): CGP, Código de Comercio and CPP in corpus.d/50-batch2.json, verified locally (check 0 mismatches, --compare identical, published acts unchanged) and 50-batch2.PUBLISH written; see batch2/PROGRESS.md.

- [x] Batch 3 (gitlaw-UY-3, 2026-10-29): Código Tributario, Ley 16.060, Ley 17.250, CNA and CAROU in corpus.d/60-batch3.json, verified locally (check 0 mismatches, --compare identical, published acts' trees unchanged) and 60-batch3.PUBLISH written; LUC skipped (IMPO gives it as pointers). See batch3/PROGRESS.md.

- [ ] Batch 4 (gitlaw-UY-4, 2026-10-29, in progress): Leyes 18.381, 17.514, 19.580, 19.574, Código de Minería and Código Rural in corpus.d/70-batch4.json; see batch4/PROGRESS.md.

## Next steps
1. Next agent: add the remaining codes as above (paths to probe: codigo-comercio/817-1865, codigo-general-proceso/15982-1988, codigo-proceso-penal-2017/19293-2014 - unverified guesses, probe with one request each).
2. Improve impo_history for the unresolved intermediate texts (quotes that give several items at once, "Numerales 1º), 2º) y 7º)").

## Constitution: how it is built (details in corpus decisions)
- Versions (from): 1967-02-15 (Parlamento 1967 edition, transitional A "a partir del 15 de febrero de 1967"), 1990-05-01 (1989 reform; V) puts art. 67 reform in force 1 May 1990), 1994-11-27, 1996-12-08, 2004-10-31 (plebiscite days: proclamation dates NOT found in any official source; law notes say so; Parlamento labels "vigencia 1995/1997"; Decreto 435/004 of 13/12/2004 says 2004 reform then in force).
- Units changed per reform = word diff of consecutive Parlamento editions; parse.py asserts equality with IMPO notes per plebiscite: 1989 {art-067, V}, 1994 {V'}, 1996 {27 arts + A, L, W, X, Y, Z, Z'}, 2004 {art-047, art-188, Z''}. All match.
- Rendering: IMPO text from a unit's last reform on; Parlamento text before (or IMPO minus later incisos when words match: arts. 46, 47, 50, 67, 88, 179, 188).
- Verification (repo/data/verification.json): every version's units have the Parlamento edition's words except the ~40 IMPO/Parlamento transcription-difference units; last version == IMPO exactly.
- Parlamento 2004 edition changes arts. 7, 135, 197, 275, 313 with no reform/IMPO note: not committed.

## Sources (pinned)
- IMPO JSON: `https://www.impo.com.uy/bases/constitucion/1967-1967?json=true`, `.../disposiciones-transitorias-especiales-constitucion/1967-1967?json=true`, `.../decretos-originales/435-2004?json=true`, `.../codigo-civil/16603-1994?json=true`. Latin-1. robots Crawl-Delay 10.
- Parlamento via Wayback id_ (fetch.py CONST_PARLAMENTO, CONST_PARLAMENTO_OLD): new site 1967 (20250820033544) + 1997 (20240528053904) temp files; old site Const989 (20141126013720), Const994 (20141126035426), const997 (20160402141915), const004 (20160402133447). Old-site const967 capture is empty (0 bytes) -> not used.
- parlamento.gub.uy itself: 403. Wayback CDX was "temporarily offline" once; the availability API works.
- Cache: 19 MB, 550 logged requests.

## Commits / pushes
- autopush builds `preview` from corpus.json; with PUBLISH it pushes main + tags. Local test build: 5 law commits + docs commit (029a899); tags constitucion/<day> x5, law/<key> x5.
- Pushed head (autopush, 20:07Z): main 1316aa7 (4 acts, 66 versions, check 0 mismatches). No futuro branch (nothing in force after the docs date).

## Probe notes (IMPO, for the next acts)
- `https://www.impo.com.uy/robots.txt`: `Crawl-Delay: 10` for `*`. **Keep 10 s between IMPO requests** (stricter than the brief's 1/s). This caps Phase 2 at ~360 req/hour.
- Responses are **ISO-8859-1**; decode latin-1. `?json=true` on a whole norm works:
  - `https://www.impo.com.uy/bases/leyes/18331-2008?json=true` → `{tipoNorma, nroNorma, anioNorma, nombreNorma, leyenda, urlVerImagen, fechaPromulgacion "11/08/2008", fechaPublicacion "18/08/2008", RNLD, referenciasNorma, firmantes, articulos:[...]}` (51 articles).
  - each article: `nroArticulo, secArticulo (e.g. BIS), titulosArticulo (section headings, <br>-separated), tituloArticulo, urlArticulo, textoArticulo (CRLF, hard-wrapped at ~72 cols; new paragraph = line starting with spaces; trailing " (*)" marks amended text), notasArticulo (HTML)`.
  - notes format: `Inciso 2º) <b><font color="#0000FF">redacción dada por:</font></b> Ley Nº 18.719 de 27/12/2010 artículo <a href="/bases/leyes/18719-2010/152">152</a>.` and `<b><font color="#008200">TEXTO ORIGINAL:</font></b> Ley Nº 18.331 de 11/08/2008 artículo <a href="/bases/leyes-originales/18331-2008/9">9</a>.` Also expect "agregado por", "derogado por", "Ver vigencia".
  - **Original text of the base law**: `/bases/leyes-originales/<n>-<yyyy>/<art>` (try `?json=true`). Intermediate versions (article amended by 2+ laws on different dates) need inciso-level replay, or the amending law's own original article (`/bases/leyes-originales/18719-2010/152`), which quotes the substituted text ("Sustitúyese ... por el siguiente: ...").
  - Ley 18.331 amended by Ley 18.719 (27/12/2010), 19.670 (15/10/2018), 20.075 (20/10/2022), others; 13 articles have TEXTO ORIGINAL links.
- Constitution `https://www.impo.com.uy/bases/constitucion/1967-1967?json=true`: current text, 332 articles. Notes name plebiscites of 26/11/1989 (art. 67 incisos 2-3 added), 8/12/1996 (27 articles "redacción dada por"), 31/10/2004 (art. 47 inciso 2 added; art. 188 inciso final added). **No original text, and the 1994 reform (art. 216) is not annotated.** Transitional provisions are a separate norm: `/bases/disposiciones-transitorias-especiales-constitucion/1967-1967`.
- Código Civil: likely `/bases/codigo-civil/16603-1994` (re-edition approved by Ley 16.603) — not probed yet.

## Code layout
- fetch.py (ACTS static URL lists; IMPO_ACTS: slug -> (IMPO path, base law, manual vigencia articles) fetched via impo_history.needed_paths)
- parse_text.py (norm, key_of, MARK, impo_paragraphs, wrap_width), impo_history.py (notes parser, chains, build_act), parse.py (Constitution + main)
- IMPORTANT: Git Bash heredocs mangle backslashes (\1, \b): edit regex code with the Edit/Write tools only.

## Gotchas
- Use curl, never urllib. Wayback `id_` needs -L.
- IMPO hard-wraps lines; impo_paragraphs() rebuilds paragraphs from layout (item markers incl. 1°)/A)/V´)/Z"), continuation columns). Checked against Parlamento paragraphing of the Constitution: only 9 units differ, all genuine layout differences.
- Parlamento letters V')/Z'') as a repeated "V) **" / "Z) ***"; the parser dedupes into primes. The footnote table at the page end stops the parse.
- WebSearch: 7 of 12 used (1 before restart + 6 after). Proclamation dates not found.

## Open issues
- None for the coordinator (ISSUES.md empty).
