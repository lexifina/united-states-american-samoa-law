# gitlaw-CL: Chile progress

Repo: lexifina/chile-law (PRIVATE, never change), clone `C:/Users/alany/Documents/chile-law` (owned by autopush: never build into it or push). tz America/Santiago, lang es, future branch `futuro`. Brief: `scripts/south-america-law/BRIEF.md` ("Changed after the restart" applies: autopush.py builds + pushes on every corpus.json change; PUBLISH exists, so builds go to main). Test builds: `.tmp-build/` only.

## State (2026-10-28 ~17:25Z)

- corpus.json (52.8 MB) = constitucion + codigo-civil + ley-19628, written 17:24Z; autopush builds it within 3 min → read BUILD_STATUS.json.
- Test build of the same corpus in `.tmp-build/repo`: 117 commits, 225 tags, futuro 1 commit (Ley 21.719 on Ley 19.628, 2026-12-01); check.py 0 mismatches / 0 trailer errors; `--compare` main_identical true.
- verify.py: all 3 acts in force on 2026-10-28 equal LeyChile's current text, 0 differences; all versions sourced (sha256 of cached response). PUBLISH rewritten with that line.
- repo/ docs written: README.md (standard shape + Spanish), LICENSE (BCN attribution, status unconfirmed; CC0 for Lexifina parts), jurisdiction.json, tools/en_vigor_el.py (wrapper around on.py; maps bare numbers to `art-NNN`, see ISSUES.md).
- push_wip.sh deleted (autopush does wip).

## Handoff (2026-10-28 ~17:40Z, coordinator message)

- **main pushed by autopush: `59e6a94`** (118 commits, 3 acts, check 0 mismatches), `futuro` `34a73a2` (Ley 21.719), 228 tags. README, LICENSE, jurisdiction.json, tools/en_vigor_el.py and tools/verify.py are in the repo.
- A helper agent (gitlaw-CL-codes) owns Phase 2: Código Penal, Código del Trabajo, Código de Comercio, written to `corpus.d/50-codes.json`. This agent keeps only constitucion, codigo-civil and ley-19628 in corpus.json. Don't edit corpus.d/.
- LeyChile rate is shared: fetch.py PAUSE is now 2.0 s.
- The Phase 2 fetch I started was stopped (exit 143): the cache holds the versions lists of all five codes and 92 of 165 Código Penal versions. CPC (22740) and CPP (176595) ids are verified (45 and 56 versions) but not fetched or assigned; ask the coordinator before adding them.
- parse.py changes made for the codes, which the helper can reuse: `COD` → type `codigo` (law key `codigo-penal-1874`), a code's first law gets the act title as its label ("Código Penal de 1874"), CP `first_law: True` (LeyChile "Texto Original" 1875-03-01 = its in-force day), versions identical to the one before with no credits are skipped (logged), and "Con Vigencia Diferida por Evento" versions (dated 2222-02-02, CT) are left out (logged). Open points for the codes: CCom in force 1867-01-01 and CPC 1903-03-01 per their final articles (check the cached text, then set ACT_META `first`); CT could chain [30011, 3471, 207436]; CT's `AVI S/N` modificatoria needs a TYPE_KEY/kind.
- When the helper's acts land, add them to the repo/README.md "What is in it now" table and jurisdiction.json `build`.
- corpus.json differs from a fresh parse only in `sources[0].requests` (155 vs 257); not rewritten, to avoid an empty rebuild.

## Checklist

- [x] Probe LeyChile; fetch.py; parse.py
- [x] Constitution built + pushed (earlier: c63964c)
- [x] Código Civil (DFL 1 2000, art. 2 subtree only) + Ley 19.628 parsed, test-built, checked, compare identical, verified → corpus.json written
- [x] BUILD_STATUS.json: main pushed 59e6a94 with 3 acts, 0 mismatches
- [ ] (helper owns CP/CT/CCom; CPC/CPP unassigned) Phase 2: verify ids in fetch.ACTS (codigo-penal 1984, codigo-comercio 1974, codigo-trabajo 207436, codigo-procedimiento-civil 22740, codigo-procesal-penal 176595: all five ids verified by get_versiones and get_cadena_refundidos on 2026-10-28), fetch, parse, test build, verify, then add to default `--acts` and README table; one act per corpus write
- [ ] Optional cheap extras (no new fetch): DFL 1 2000 arts 3,4,6,7,8 = Ley 4.808 Registro Civil, Ley 17.344 nombres, Ley 16.618 Menores, Ley 14.908 alimentos, Ley 16.271 herencias (set `part`)

## Workflow per act

1. `python -X utf8 scripts/chile-law/fetch.py <slug>` (resumable, cached)
2. `python -X utf8 scripts/chile-law/parse.py --acts constitucion,codigo-civil,ley-19628,<slug> --out .tmp-build/src/corpus.json`; then `cp -r repo fetch.py parse.py verify.py .tmp-build/src/`, build into empty `.tmp-build/repo`, check.py, verify.py `--corpus .tmp-build/src/corpus.json`
3. Add slug to parse.py default `--acts`, update repo/README.md table + jurisdiction.json `build`, then `parse.py` (writes corpus.json atomically) → autopush.

## Endpoints (all 200 on 2026-10-28, no token needed)

- versions: `https://nuevo.leychile.cl/servicios/Consulta/get_versiones?idNorma=N&formato=json&idParte=&idsParte=` → `Versiones.Version[]` with `@vigenteDesde`, `@vigenteHasta`, `@tipoVersion`, `Modificatorias.Modificatoria` (dict or list). **The Modificatorias on a version entry are the norms that END it.** Some entries list none at all (deferred entry into force; see below).
- one version: `https://nuevo.leychile.cl/servicios/Navegar/get_norma_json?idNorma=N&idVersion=YYYY-MM-DD&idLey=&tipoVersion=&cve=&agrupa_partes=1&r=` → `html` tree (`t` html, `i` id, `h` children), `estructura` (names `n`), `metadatos`. With `idVersion=` empty: the current text (used by verify.py).
- chain of refundidos: `Navegar/get_cadena_refundidos?idNorma=N`.
- robots: no crawl rules found.

## Ids

- Constitution: 7129 → 242302 (DS 100, 2005-09-22). First version moved to 1981-03-11 (Artículo final).
- Código Civil: 172986 (DFL 1, 2000-05-30) **part 2** ("ARTÍCULO 2 (CÓDIGO CIVIL)"); names inside carry "(DEL ART. 2)", stripped. Versions in which only other parts changed are skipped (50 → 29). Older chain 1973 (1855 code, 3 versions, no modificatorias) and 3551 (DFL 2 1996) not used; first_law null, earlier_laws [dfl-1-2000].
- Ley 19.628: 141599 (8 versions; 2026-12-01 Ley 21.719 → futuro).

## Credit rules (parse.py; printed as `decisions`)

- Changed unit credited to a norm in force that day (previous entry's Modificatorias) whose note names it (link idNorma, type+number, Rectificación by D.O. date). One norm that day → also removals/new units without notes.
- New note naming a norm (or a numberless "RECTIFICACION D.O. dd.mm.yyyy") with D.O. date = the day → credited.
- NEW (restart): deferred entry into force — if the versions list names no norm for the day, a new note naming exactly one norm published earlier, not credited before in this act, and not dated elsewhere by the versions list → credited; version note says so (CC: Ley 21.120, 21.334, 21.484).
- Laws first known from a note are merged when the versions list later gives the same type+number (`Laws.add`).
- Law keys now carry the publication year from metadatos (dfl-1-2000, dl-3464-1980, dto-100-2005-242302).
- Remaining unexplained: CPR 22 (BCN typo fixes 2003-01-06); CC 4 (art 1993 2000-09-14, art 141 2004-08-30, art 188 2005-07-05, art 144 2005-08-30).

## Open issues

- ISSUES.md: on.py bare-number ambiguity (art-019 vs disp-transitoria-019); worked around in en_vigor_el.py.
- Licence: Ley 17.336 has no explicit exclusion for legal texts; README attributes BCN and says status unconfirmed.
- corpus.json > 50 MB → autopush's wip snapshot skips it (fine; parse.py regenerates it).
- Cache: `.cache/` ~133 MB, ~155 requests. WebSearch used this session: 0.

## gitlaw-CL-2 (2026-10-29): parts 97-batch7, 98-batch8, 99-batch9 DONE, all three .PUBLISH written

- Owner: gitlaw-CL-2. Adds acts as new corpus.d parts through codes/parse_codes.py (`--part batch7|batch8`); parse
  logs kept as codes/parse-batch7.log / parse-batch8.log. Published parts 50-95 regenerate byte-identical with every
  change below (check: regenerate each published part into the scratchpad and cmp against corpus.d).
- fetch_codes.py: `--fast slug...` (3 parallel, up to 3 req/s, shared limiter; 429/503 halves the rate + waits 60 s;
  same cache/UA/request log as fetch.py), `--ley N...` (idLey -> id_norma), `--probe id...`. 508 requests on 10-29.
- parse_codes.py additions (none touches the published parts): VIGENCIA for dl-824 (1975-01-01, art. 2), ley-19886
  (2003-08-30), ley-18840 (1989-12-10), ley-18918 (1990-03-11), ley-21521 (2023-02-04, CC art. 48 count; LeyChile
  2023-02-03); OWN_ARTICLES {6368}: DL 824's own arts. 2-18 (beside the LIR text it enacts in art. 1) are keyed
  decreto-ley-art-NNN, "Art. N del decreto ley"; STRIP_WORD {30216}: "(DEL ART. PRIMERO)" dropped for Ley 18.840 only
  (doing it globally re-keyed Ley 20.285 in published 95-batch6, so it is per norm). Ley 20.066's art. 25 day
  (2005-10-01) precedes its publication (2005-10-07): kept LeyChile's day, decision line.
- Batch 7 (97-batch7.json 6.6 MB): DL 824 118 versions/45 unexplained, DL 825 76/76, Ley 21.325 7/0, Ley 19.886 16/0,
  Ley 18.840 19/0, Ley 20.066 10/0, Ley 18.314 14/1, Ley 17.798 (29291 -> Decreto 400 13031) 24/29, Ley 20.609 5/0,
  Ley 19.799 4/0.
- Batch 8 (98-batch8.json 2.8 MB): Ley 20.370 (1006043 -> DFL 2 2009 1014974; LOCE 30330/247551 not used) 22/0,
  Ley 20.730 7/1, Ley 21.430 1/0 (Única), Ley 19.253 10/1, Ley 20.422 22/1, Ley 10.336 (26356 -> Decreto 2.421 18995)
  19/7, Ley 17.997 (29427 -> DFL 5 2010 1016103) 13/2, Ley 19.640 25/0, Ley 18.918 13/0, Ley 21.442 8/0, Ley 19.418
  (30785 -> Decreto 58 70040) 13/25, Ley 3.918 4/0, Ley 19.857 2/0, Ley 21.521 1/0, Ley 20.500 1/0.
- Verified: verify_codes.py 0 differences for all 25 (text in force 2026-10-28 vs LeyChile dated version and current
  page read 10-29), all versions sourced. Scratch build (scratchpad src copy, empty repo, docs-date 2026-10-28):
  1801 commits, 72 acts, 2121 versions, check.py 0 mismatches / 0 trailer errors, --compare identical (history tip
  a36e06b). Published acts vs the clone's main 1651d5cf: per act, every commit touching its folder has the same tree,
  author and date; only pre-1970 placeholder seconds shift (new pre-1970 commits of Leyes 3.918 and 10.336) in CJM,
  COT, CP, CSan, Ley 14.908, Ley 16.744; 230 law commits now also hold new acts' files (shared law, same day).
- README table now lists all 72 acts (it listed 3); jurisdiction.json `build` updated. Docs date stays 2026-10-28
  (parts carry no `sources`).
- Batch 9 (99-batch9.json, .PUBLISH written): Ley 4.808 (24928 -> DFL 1 2000 art. 3) 23 versions/26 unexplained,
  Ley 17.344 (28940 -> art. 4) 4/0, Ley 16.618 (28581 -> art. 6) 27/66, Ley 16.271 (28367 -> art. 8) 13/70.
  parse_codes: ACT_NORM_PART {(act, 172986): article} beside NORM_PART {172986: 7}; CURRENT['act'] is set in setup()
  and main() per act; verify_codes wraps parse.ACT_META (ActMeta) so verify.py's per-act lookup sets it.
  verify 0 differences; every part (50-99) regenerates byte-identical (scratchpad/cl2/regen.sh).
- Final scratch build (scratchpad/cl2, empty repo, docs-date 2026-10-28): 1836 commits, 76 acts, 2188 versions,
  check.py 0 mismatches / 0 trailer errors, --compare identical (history tip 30c0998). Baseline build of the 47 earlier
  acts only (same scratch, parts 97-99 removed) vs the full build: 0 folders differ in per-commit tree/author/date;
  6 differ only in pre-1970 placeholder seconds (new pre-1970 commits of Leyes 3.918, 4.808, 10.336, 16.271, 16.618).
- autopush 12:30:41Z pushed main aa44fd65 without 97/98 (PUBLISH came after); the next pass should take 97, 98, 99.
  Read BUILD_STATUS.json to confirm (expect 76 acts, 2188 versions).
- README table: all 76 acts; jurisdiction.json `build` = 76 acts / 2188 versions.
- Next ideas: Ley 21.719 is already in ley-19628's futuro; candidates not built: Ley 18.892 pesca, Ley 20.370's
  predecessor LOCE (30330, 247551) as its own act, Ley 21.180 transformación digital, Ley 19.983 factura, Ley 18.287
  policía local, Ley 20.659, Ley 21.400 (amends CC only). Name new parts so they
  sort after 99-batch9 (e.g. 99a-batch10), and regenerate every part to confirm byte-identity.
- Note: the session scratchpad is shared with other agents (a guyana agent overwrote scratchpad/regen.sh); keep
  Chile scratch work under scratchpad/cl2/.

## gitlaw-CL-3 (2026-10-29): part 99a-batch10 DONE, .PUBLISH written

- Owner: gitlaw-CL-3. Scratch: session scratchpad `cl3/`. Part name 99a-batch10 (sorts after 99-batch9, so the
  published acts keep their order in the merged corpus and in shared-day commit messages).
- Already built (skipped from the brief's list): Código de Aguas, Minería, Sanitario, Aeronáutico, Leyes 19.300,
  18.046, 18.045, 20.720, 19.968, 18.695; Ley 21.719 is on ley-19628's futuro (it amends Ley 19.628).
- Chosen (20): DFL 458 LGUC [13560]; Ley General de Bancos [5205 DFL 252, 83135 DFL 3 1997]; DL 211 [5872, 74808,
  236106]; Ley 18.892 [30265, 13315]; Ley 18.168 [29591]; Ley 19.175 [30542, 243771]; Ley 19.070 [30437, 60439];
  Ley 20.600 [1041361]; Ley 18.287 [29705]; Ley 15.231 [28104, 12193]; Ley 19.728 [184979]; Ley 20.880 [1086062];
  Ley 19.983 [233421]; Ley 18.603 [29994, 1107684]; Ley 17.322 [28919]; Ley 18.097 [29522]; Ley 19.378 [30745];
  Ley 21.040 [1111237]; Ley 20.712 [1057895]; Ley 20.659 [1048718]. Chains in fetch_codes.CHAINS, META + PARTS
  'batch10' in parse_codes.py.
- parse_codes FROM_1970 {ley-general-bancos, ley-15231}: start at the first LeyChile version from 1970 on (oldest
  version available) so no new pre-1970 commit shifts the placeholder seconds of published pre-1970 commits.
- Fetch: `fetch_codes.py --fast <20 slugs>` (491 urls, log codes/fetch-batch10.log).
- anachronism.EXCLUDE: parse_codes sets it to the batch-10 slugs for every other part, so ley_dates reads only the
  versions lists known when those parts were published (without it, 80-batch4's ley-18838 gained a published date,
  which would reorder law commits). VIGENCIA added: Ley 19.983 2005-04-16 ("cuatro meses", pub 2004-12-15), Ley
  18.603 1987-04-03 ("diez días", pub 1987-03-23). Partial deferrals kept (Leyes 17.322 arts. 1-29, 19.728, 19.378);
  LeyChile already dates 18.892, 18.287, 20.880, 20.712, 20.659 by their clauses.
- Versions / unexplained: DFL 458 61/32, LGB 33/123, DL 211 18/93, Ley 18.892 66/66, 18.168 45/12, 19.175 24/61,
  19.070 35/63, 20.600 6/0, 18.287 27/43, 15.231 25/49, 19.728 22/8, 20.880 13/1, 19.983 8/7, 18.603 13/13,
  17.322 19/25, 18.097 4/15, 19.378 10/2, 21.040 11/0, 20.712 9/0, 20.659 2/0. 99a-batch10.json 9.4 MB.
- verify_codes 0 differences for all 20 (dated version + current page). Scratch build (cl3/src, empty repo, docs-date
  2026-10-28): 2152 commits, 96 acts, 2639 versions, check.py 0 mismatches / 0 trailer errors, --compare identical
  (history tip 77e4f17). Published acts: vs the clone main bc8776fe and vs a 76-act baseline build (1836 commits),
  0 of 76 folders differ in per-commit tree/author/date; 133 law commits on shared days (plus the docs commit) change
  message only, listed in codes/batch10-shared-commits.tsv. All parts 50-99a regenerate byte-identical
  (cl3/regen.sh).
- README table (96 rows) and jurisdiction.json build (96 acts / 2639 versions) updated.
- Not done / ideas: LGB 1960 versions and Ley 15.231's 1963 version held back (pre-1970 placeholder seconds); Ley
  21.719 stays on ley-19628's futuro; next candidates: DFL 4 2006 servicios eléctricos, DFL 251 seguros, Ley 21.000,
  Ley 20.551, Ley 20.255.
