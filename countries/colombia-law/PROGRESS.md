CHECKPOINTED 2026-10-28T17:55Z (resumed run)

# gitlaw-CO progress (Colombia)

Resume from here. Brief: `scripts/south-america-law/BRIEF.md` (follow it). Slug `colombia`, repo `lexifina/colombia-law` (PRIVATE, never change), clone `C:/Users/alany/Documents/colombia-law` (only the scaffold commit c94ec90 "Colombia: sources, before any law"; scaffold README.md/SOURCES.md/jurisdiction.json/REPRODUCE.md are there to fold into `repo/`). tz America/Bogota, lang es, future branch `futuro`. Shared builder is READY (`scripts/gitlaw_common/build.py`, `check.py`, `on.py`). AFTER RESTART: autopush.py (scripts/south-america-law/) owns the clone and all pushing (wip + builds -> `preview` until `PUBLISH` exists, then main/futuro/tags). Do NOT build into the clone or push. Test builds: `sh .tmp-build/test.sh` (copies corpus from .tmp-build/corpus.json, builds .tmp-build/repo, runs check). Read BUILD_STATUS.json after each corpus change.

## Checklist
- [x] Read brief, memory/git_for_law.md, gitlaw_common/SCHEMA.md, PLAN.md
- [x] Clone scaffold
- [x] Probe sources (table below)
- [x] fetch.py written (`python -X utf8 fetch.py doc <basedoc name>`; resumable, cached)
- [x] Fetching: Constitución, codigo_civil (base + pr pages + JS, 168 urls), ley_1581_2012 (1 page + JS) all cached (fetch.py all finished 17:13Z)
- [x] parse.py: Constitución (+ court layer). corpus.json: 81 versions, 82 laws (63 AL, 18 court, 1 Aclaración Gaceta 125). Deterministic (two runs byte-identical).
- [x] verify.py: today's text == basedoc current text, 496/496 units. check.py 0 mismatches; --compare rebuild main_identical (82 commits, 163 tags).
- [x] repo/README.md (EN + ES), LICENSE, jurisdiction.json, tools/en_vigor_el.py
- [x] PUBLISH created; autopush pushed main bf29ba5 at 17:54:10Z (83 commits, 163 tags, check 0 mismatches).
- [-] Código Civil, Ley 1581 de 2012: owned by helper gitlaw-CO-codes (corpus.d/50-codes.json, codes/)
- [x] (see line above) repo docs done
- [-] (not mine after the split: coordinator assigns) Phase 2 codes from basedoc: codigo_penal (ley_0599_2000), codigo_comercio, codigo_sustantivo_trabajo, codigo_general_proceso (ley_1564_2012), ley_0906_2004 (procedimiento penal) — confirm basedoc names from the index pages

## Split (coordinator, 18:10Z)
- gitlaw-CO-codes (helper) owns Código Civil + Ley 1581 de 2012 in `corpus.d/50-codes.json`. I (gitlaw-CO) own ONLY the Constitution in `corpus.json`. Don't edit corpus.d/.
- Shared law keys/labels (same key must have same label across parts): `al-<n>-<yyyy>` label "Acto Legislativo <n> de <yyyy>"; `c-<nnn>-<yy>` label "Sentencia C-<nnn> de <yyyy>" (kind court); `ley-<n>-<yyyy>`.

## Next steps
1. DONE: main pushed bf29ba5.
2. Optional: reduce remaining gaps (placeholders: arts 122, 256, 263, 322, 328, 361; approximations: 241, 250, 328, TRANSITORIO ACL02021-5) - all listed in corpus decisions.
3. README "What is in it now" should gain the helper's acts when corpus.d/50-codes.json lands (helper or coordinator).

## parse.py design (Constitution)
- doc_units(): splits pages into anchored units (anchors `<a name=..>`; unanchored "ARTICULO 247." too); boxes from js.
- article_history(): article-level chain (full "Legislación Anterior" texts, ART markers, NV notes; whole-AL INEXEQUIBLE -> court restores pre-AL text) until the last article-level event; after it, slots (paragraph groups by partial markers / fragment labels) each with own chain. chain() resolves states with equalities (struck AL, 'adicionado' = absent before).
- assemble(): per-day versions; titulos.md shows a heading while an article under it exists; unknown states -> placeholder line credited to the act named.

## Sources probed (2026-10-28)
| Source | URL | Status | Format | Dated versions | Per-provision notes | robots / licence |
|---|---|---|---|---|---|---|
| Secretaría del Senado basedoc | http://www.secretariasenado.gov.co/senado/basedoc/constitucion_politica_1991.html | 200 (http, not https), base 83 KB + `constitucion_politica_1991_pr001.html`..`_pr015.html` | HTML in ISO-8859-1 (decode latin-1, then html.unescape), plus one JS per page `js/<page>.js` holding the note boxes | No dated snapshots, but each article's "Legislación Anterior" box holds earlier texts ("Texto original de la Constitución Política:", "Texto modificado por el Acto Legislativo N de YYYY:") | Inline `&lt;Artículo modificado por el artículo N del Acto Legislativo N de YYYY. El nuevo texto es el siguiente:&gt;`; "Notas de Vigencia" with Diario Oficial no. + date + "Rige a partir de su publicación"; "Jurisprudencia Vigencia" with Corte Constitucional rulings | robots.txt only disallows Joomla system dirs. Footer "Derechos de autor reservados - Prohibida su reproducción" (Avance Jurídico compilation, "Última actualización: 15 de octubre de 2026 - Diario Oficial No. 53.651"). Official legal text is free to reproduce (Ley 23 de 1982 art. 41); take only official text and facts, never Avance's editorial notes. |
| SUIN-Juriscol | https://www.suin-juriscol.gov.co/viewDocument.asp?ruta=Constitucion/1687988 | 200 but Angular SPA shell (4.7 KB "GovcoFrontendBase"); robots.txt also returns the shell | SPA | none seen | per-article "Modificado por" (per register) | Wayback copy exists (20260922080758). Not used for text: basedoc has earlier texts, SUIN does not. Possible cross-check later. |

## Basedoc page structure (gotchas)
- Article heading: `<a class="bookmarkaj" name="138">ARTICULO 138. </A>` or `<span class="b_aj"><A name="22A">ARTÍCULO 22A.</A></span>`; body is following `<p>` until next anchor/`caja_vja_encabezado` div.
- Note boxes: `<div><a class="caja_vja_encabezado" href="javascript:insRowN()">Notas de Vigencia|Jurisprudencia Vigencia|Concordancias|Jurisprudencia Concordante|Antecedentes|Legislación Anterior</a></div>`; content is in `js/<page>.js` as `function insRowN() { ... description[0] = "<tbody>...";` (regex `function insRow%s\(\)\s*\{(.*?)\n\}`). insRow numbering is per page/JS file.
- Base page's JS `js/constitucion_politica_1991.js` insRow1 = "Resumen de Notas de Vigencia": numbered list of all 65 Actos Legislativos with title, Diario Oficial no. and date, and "Rige a partir de ..." — use as the law table.
- Struck text (INEXEQUIBLE) is in `<s>` tags (red) with a marker like "&lt;Aparte tachado INEXEQUIBLE&gt;" — expected, verify.
- Page list: `<option value="_pr001ç#33">` in the base page.
- Scratch probe copies in scratchpad `co/` (not needed).

## Decisions so far
- Basedoc is the primary source: the only one with earlier texts per article.
- Versions rebuilt per article from "Legislación Anterior" texts, inline amendment notes and Notas de Vigencia dates; court strikes (INEXEQUIBLE / conditional EXEQUIBLE) are `court` laws dated by the ruling's effect.
- Default in-force rule to cite: Ley 4 de 1913 (Código de Régimen Político y Municipal) arts. 52–53 (law binding two months after promulgation unless it fixes its own date); ALs mostly say "Rige a partir de su publicación".

## Cache
`scripts/colombia-law/.cache/` (`.gitignore` = `*`), sha256(url) filenames, log `.cache/requests.jsonl` (48 requests at checkpoint).

## Open issues
- No ISSUES.md (no builder problems).
- parse.py --report: 14 lines (gaps/approximations above; "unparsed heading: Texto modificado por el Acto Legislativo:" (no number, ignored); al-5-2011 taken from an article note).

## Election-day sourcing (coordinator rule fix, 18:10Z) - DONE
- The 3 election days (AL 2/2005 -> 2006-03-12, AL 3/2005 -> 2010-03-14, AL 3/2007 -> 2007-10-28) are now READ by parse.py (`election_day()`) from cached Registraduría pages listed in fetch.py `ELECTION_SOURCES`; parse stops if a page lacks the day:
  - https://www.registraduria.gov.co/Calendario-Electoral-2006-2010.html (Resolución 0497 de 2005: "elección de congresistas ... el día 12 de marzo de 2006")
  - https://web.archive.org/web/20110726040247id_/http://www.registraduria.gov.co/ESTA-LISTO-EL-PRE-CALENDARIO.html (Comunicado 050 de 2009: "el 14 de marzo de 2010 se realizarán las elecciones legislativas")
  - https://web.archive.org/web/20070930160642id_/http://www.registraduria.gov.co/ (home page 2007-09-30: "proceso electoral del 28 de octubre"; year = capture's)
- All three dates were unchanged. Each election-day version carries a note with the URL; decisions + README + sources[] name them. WebSearch used: 3 (total this agent: 3).
- Found and fixed while doing this: vigencia clauses "a partir del 1o. de enero de 2002/2008" were not parsed (regex stopped at "1o."), so AL 1/2001 is now 2002-01-01 and AL 1 and 4/2007 are 2008-01-01 (were publication days); header typo "Acto Legislativi" hid AL 3/2007 on art. 323 (now its own version, 2007-10-28).
- corpus.json rewritten: 81 versions, 83 laws; verify 496/496; check 0 mismatches; --compare identical; deterministic. Autopush rebuilds main from it.
- BLOCKED push (18:10:40Z): autopush errors on the helper's `.tmp-build-codes/` (nested .git not in autopush SKIP_DIRS). Written to ISSUES.md for the coordinator. main still bf29ba5 (pre-fix). When autopush is fixed it will build the current corpus.json + corpus.d/50-codes.json; check BUILD_STATUS.json.

## Phase 2 (coordinator, 18:20Z): Código Penal, CGP, CST
- Owner: me (gitlaw-CO). Don't touch corpus.json (Constitution, published) or the helper's 50-codes part.
- Code in `phase2/`: `fetch_phase2.py` (docs + amending acts' base/last pages, 2.1 s/host), `engine.py` (frozen copy of
  codes/parse_codes.py at 18:20Z; never run directly; patched: art labels "38-H"/"38Ñ" -> art-0038h / art-0038nn),
  `parse_phase2.py` (driver: build_penal, build_cgp, build_cst; writes deltas `changes` after the first version per
  SCHEMA "Large acts"), `verify_phase2.py` (last version vs today's page text, line for line).
- Fetch: docs done (penal 40 urls, CGP 44, CST 34); `fetch_phase2.py laws` running (230 act pages; log phase2/fetch_laws.log).
- Dates sourced from pages: CP from art. 476 (1 year after DO 44.097 of 24 Jul 2000 -> 2001-07-24); CGP first version at
  promulgation 2012-07-12 with art. 627 quoted in a note; CST first version = official edition DO 27.622 of 7 Jun 1951
  (first_law null, earlier_laws Decretos 2663/3743 de 1950, 905 de 1951); '{empleador}' braces = Ley 50 de 1990 art. 107
  (patrono -> empleador), reverted before its in-force day.
- Ley 890 de 2004 art. 14 penalty increases: the source prints computed penalties; credited to Ley 890 (1 Jan 2005), disclosed in decisions.
- Next: when laws fetch ends, run `python -X utf8 phase2/parse_phase2.py --report --out .tmp-build/p2.json`, then
  `python -X utf8 phase2/verify_phase2.py .tmp-build/p2.json -v`; fix differences; write corpus.d/60-phase2.json; test build;
  then corpus.d/60-phase2.PUBLISH when verify shows 0 differences.

### Phase 2 status (19:20Z)
- Parts (deltas: `changes` after the first version, SCHEMA "Large acts"):
  - `corpus.d/60-phase2.json` = Código Penal (139 versions) + CGP (26 versions), 176 laws, 2.1 MB. verify_phase2: 0 differences
    (600 + 634 articles). Full-corpus test build (corpus.json + 50 + 60 + 61): check 0 mismatches, 1 unexplained (CPen
    titulos 2022-11-23). `corpus.d/60-phase2.PUBLISH` written -> main.
  - `corpus.d/61-cst.json` = Código Sustantivo del Trabajo (90 versions), NOT published (preview only): 16 articles differ
    from today's text + 6 extra units (art-0040 from a broken anchor "A"/"RTÍCULO 40", art-0266, 163a, 167a, 391-01,
    481-01), and 8 old acts with no day (Decreto 13 de 1967 "DO No 32.131 de 1967" has no day; Ley 39 de 1985, Decreto
    204 de 1957, Ley 3 de 1969, Decretos 753 de 1956/2351 de 1995, Leyes 48 de 1968/27 de 1974: no basedoc page).
    Fix: fetch Colpensiones copies (normativa.colpensiones.gov.co/colpens/docs/<page>.htm) for headings; handle
    "Artículo derogado a partir de la vigencia de ... según la Sentencia C-170-04"-style notes; anchors named "A".
- Engine fixes made in phase2/engine.py (copy only): labels 38-H/38Ñ; notes without leading "-"; VERB 'eliminad';
  one marker naming several acts; DO dates "1o. de"; DO after a quoted title; vigencia clauses up to 4000 chars,
  "los demás ... rigen ... promulgación" = pub, "día siguiente de su promulgación" = pub+1d, "entra a regir"/"rigen";
  note-level "Rige a partir de su publicación"; chain uses today's text for the latest state (listed in decisions).
- Driver rewrites "<Penas aumentadas por ...>" and "<Pena aumentada por ...>" markers to article-level changes, and
  "<Ley N de AAAA declarada INEXEQUIBLE>" to "<Artículo INEXEQUIBLE>"; typo keys ley-599-0000, ley-1565-2012 fixed.
- Next: watch BUILD_STATUS.json for main with 60-phase2; then CST fixes (above) and 61-cst.PUBLISH when verify shows 0.

### Split again (coordinator, 19:25Z)
- CST now belongs to helper gitlaw-CO-cst (corpus.d/70-cst.json). I deleted my unpublished 61-cst.json and stopped building
  the CST (build_cst kept in parse_phase2.py, not run). I own only corpus.d/60-phase2.json (Código Penal + CGP), published.
- Rule: at most 1 request/s to secretariasenado.gov.co across all agents; no OCR. My fetches are finished (no running tasks).
- DONE: main pushed 1445054 (18:48:30Z) with codigo-penal (127 commits) and codigo-general-del-proceso; check 0 mismatches. Stopped.

### Date fixes (coordinator, ~20:05Z) - DONE
- Ported cst/engine.py (CST helper's fixes) into phase2/engine.py (header/main adjusted). Plus: the act's own page
  Diario Oficial day now wins over a day from the code's notes (no conflicts found in CP/CGP after the port).
- Ley 2452 de 2025: 2026-04-02 (art. 330, one year after publication; before the retrieval day, so on main).
- Audited every act whose vigencia clause has exceptions or differs from publication (list in decisions):
  - Ley 890 de 2004 art. 15: arts. 7-13 immediately (2004-07-07): CP arts 230A, 442, 444, 444A, 453, 454, 454A-C now
    dated 2004-07-07; the rest (incl. art. 14 penalty increases) 2005-01-01. Driver wraps engine.unit_day.
  - Ley 2080 de 2021: the cst "un año después" rule wrongly gave 2022-01-25; HAND_RULE "pub" (2021-01-25) with art. 86.
  - Ley 2502 de 2025: only change is CP art. 296, which its art. 6 starts one year after promulgation -> 2026-07-31 (HAND_RULE).
  - Checked and kept: Ley 599/2000, 1098/2006 (note says 8 May 2007), 1142/2007, 1676/2013, 1943/2018 (art. 70 only
    later; CP changes 434A/434B are not art. 70), 2220/2022, 2272/2022 (CP art. 32 by art. 13: general rule), 2292/2023
    (pub+1d), Decreto 1136/2025 (note: from publication). Decretos 4449/2008 and 1736/2012: no vigencia in any cached
    source, default rule (stated in decisions).
- New units found by the port's label_num: CP arts 269-1, 319-1, 320-1, 322-1 (were dropped as duplicates before).
- Result: 60-phase2.json 167 versions (CP 141, CGP 26), 177 laws; verify 0 differences (605 + 634 articles);
  deterministic; full-country test build (corpus.json + 50 + 60 + 70) check 0 mismatches, --compare identical.
  Written atomically 19:22:32Z; autopush pushed main ec046cb at 19:25:01Z (6 acts, 466 versions, check 0 mismatches). Stopped.

## Batch 3 (coordinator, ~19:40Z): corpus.d/80-batch3.json
- Acts: Código de Comercio (basedoc codigo_comercio, Decreto 410 de 1971), CPACA (ley_1437_2011), Código de
  Procedimiento Penal (ley_0906_2004), Código de la Infancia y la Adolescencia (ley_1098_2006).
- Code: `batch3/fetch_batch3.py` (reuses phase2/fetch_phase2.py, 2.1 s/host), `batch3/parse_batch3.py` (reuses
  phase2/parse_phase2.py + phase2/engine.py; builders read each code's own vigencia article: CCo art. 2038 -> 1972-01-01,
  CPACA art. 308 -> 2012-07-02, CPP art. 530 -> 2005-01-01 (gradual), CIA art. 216 -> promulgation + 6 months).
- Anachronism rule (my reading; not written down anywhere I could find): no change is credited to an act before that
  act's own sanction/publication day, and no ruling before the text it rules on. `anachronisms()` in parse_batch3.py
  checks it (also run on 60-phase2: 0). PUBLISH only with 0 anachronisms and verify 0 differences.
- Fetch running (started 19:42Z): `batch3/fetch_batch3.py docs` then `laws` (logs batch3/fetch_*.log).
- Next: when fetch ends, `python -X utf8 batch3/parse_batch3.py --out-dir .tmp-build/b3 --report`; verify (adapt
  phase2/verify_phase2.py ACTS); fix; test build; write corpus.d/80-batch3.json + 80-batch3.PUBLISH.

### Batch 3 status (~21:00Z) - DONE, published
- corpus.d/80-batch3.json: CCo 29 versions, CPACA 16, CPP 90 (1 on futuro: Ley 2592 de 2026 -> 2027-01-09), CIA 28; 166 laws,
  2.7 MB deltas. verify_batch3: 0 differences (2037 + 321 + 590 + 218 articles). 0 anachronisms. Deterministic.
  Full-country test build (corpus.json + 50 + 60 + 70 + 80): 10 acts, check 0 mismatches, 2 unexplained (titulos
  of CPen 2022-11-23, CPP 2022-05-05), --compare identical. corpus.d/80-batch3.PUBLISH written. README rows added.
- First versions (earliest day any part took effect, the code's own article quoted in the note): CCo 1971-03-27
  (art. 2038 exceptions), CPACA 2012-07-02 (art. 308), CPP 2004-09-01 (arts. 531-532 on publication, art. 530 districts
  from 2005), CIA 2006-11-08 (art. 199 on promulgation, rest +6 months).
- Page repairs (batch3 doc_units): CCo braces = errata of the official edition (braces dropped); anchors named
  "Nivel001" for art. 508; anchors "A"/"" holding "ARTÍCULO 1913."/"ARTÍCULO 1129." rebuilt; trailing unanchored
  headings ("SECCIÓN III.", "DISPOSICIONES FINALES.") made headings; sign-off "Comuníquese y publíquese" cut.
- Key fixes: ley-1437-2001 -> 2011, ley-1908-2019 -> 2018, dec-1959-2019 -> ley-1959-2019. Colpensiones copies fetched:
  Ley 45 de 1990, Decreto 2279 de 1989 (Ley 44 de 1981 nowhere: HAND 1981-12-31, disclosed).
- HAND_RULES (clause read from the act's page): Ley 1328/2009 pub (art. 101 itself), 2475/2025 pub+12m, 2592/2026
  pub+6m, 1760/2015 pub (numeral 6 of CPP art. 317 a year later: not split, disclosed).
- Engine change (phase2/engine.py): note-only rulings dated before an act's first day are moved to that day (60-phase2
  output unchanged by it).
- Anachronism rule as implemented: no credit before the act's own sanction/publication day; no ruling older than the code.
- Published: autopush pushed main 375488e at 20:32:44Z (10 acts, 629 versions, check 0 mismatches). Stopped here.

## Batch 4 (coordinator, ~20:50Z): corpus.d/90-batch4.json (agent gitlaw-CO-batch4)
- Acts: Código Nacional de Seguridad y Convivencia Ciudadana (ley_1801_2016), Ley 100 de 1993 (ley_0100_1993), Código
  General Disciplinario (ley_1952_2019), Código Electoral (decreto_2241_1986, if time allows).
- Code: `batch4/fetch_batch4.py` (imports batch3/fetch_batch3.py + phase2/fetch_phase2.py; 2.1 s/host, curl --compressed),
  `batch4/parse_batch4.py` (imports batch3/parse_batch3.py -> phase2 driver + engine), `batch4/verify_batch4.py`.
  Test output only in `batch4/.tmp/`.
- Senado terms (re-checked 20:55Z): robots.txt (http://www.secretariasenado.gov.co/robots.txt) disallows only Joomla
  system dirs (/administrator/, /cache/, /cli/, /components/, /images/, /includes/, /installation/, /language/,
  /libraries/, /logs/, /media/, /modules/, /plugins/, /templates/, /tmp/); /senado/basedoc/ is allowed. No terms page is
  linked from the home page. Each basedoc page's footer: Avance Jurídico's notes of vigencia, concordances, editor's notes,
  presentation and arrangement are protected by copyright, and their use in similar publications for commercial ends
  (copying, mass reproduction ...) is forbidden. We take only the official text and the facts (dates, acts, rulings);
  official legal text is free to reproduce (Ley 23 de 1982, art. 41). No ai-input signal, no bot challenge.
- Fetch started 20:56Z (logs batch4/fetch_docs.log, fetch_laws.log).

### Batch 4 status (~21:55Z) - DONE, published (90-batch4.PUBLISH)
- corpus.d/90-batch4.json: CNSCC (Ley 1801/2016) 36 versions, Ley 100/1993 80, CGD (Ley 1952/2019) 13, Código Electoral
  (Decreto 2241/1986) 10; 139 laws, 1.6 MB deltas. verify_batch4: 0 differences (248 + 296 + 281 + 218 articles).
  0 anachronisms, 0 pre-start events, deterministic. Full-country test build (batch4/.tmp/b): check 0 mismatches,
  2 unexplained (the old CPen/CPP titulos), --compare main_identical.
- First days: CNSCC 2017-01-29 (art. 243, pub+6m); L100 1993-12-23 (art. 289, pensions from 1994-04-01 per art. 151,
  in the note); CGD 2019-01-28 promulgation (never in force until 2022-03-29: art. 265 / Ley 1955 art. 140 /
  Ley 2094 art. 73, all in the note); CE 1986-08-01 (art. 218, publication).
- Fixes in parse_batch4.py (all listed in decisions): HEADING_FIXES (typo'd 'Texto original' headings: Leyes 1810/1805/906
  for 1801; Ley 100 de 2007, Decreto 2277/1979 for Ley 100); DEFERRED (C-223/17 struck Ley 1801 Título VI arts 47-75 with
  effect deferred to 2019-06-20: synthetic 'Texto vigente hasta su declaratoria' block from the printed text, ruling day
  read as 2019-06-20, law enacted kept 2017-04-20, titulos credited to it); NOTE_FIXES (Decreto 132/2010 and 1280/2002
  notes that changed no words of L100 arts 215, 216, 271); JV_FIXES (CGD art. 52 'grave' struck by C-560/19, not C-181/02);
  replaced_words() (CGD '<Aparte tachado reemplazado/eliminado por ... Ley 2094>' with new words in <...> after </S>);
  HAND_RULES ley-2094-2021 pub+9m (+ art 1 pub, art 7 pub+30m via unit_day), dec-207-2022 pub (art. 29, read from Bogotá
  Sisjur; 404 on basedoc), dec-1656-2021 = 2022-03-29 (404 on basedoc; corrects Ley 2094 additions); CGD art. 225D absent
  before 2022-03-29; Ley 1955/2019 note-only version on CGD art. 265 (2019-05-25).
- Remaining placeholders: CNSCC arts 155/180/185A/223A 2022-01-25..02-08 (Ley 2197 text before Decreto 207's correction);
  L100 art 221 (1993..1996), 214 (2007-01-09..07-25), 188 (2010-04-16..07-21). Ley 6 de 1990 (Código Electoral) on the
  default rule (not on basedoc or Colpensiones). Ley 1801 art. 162 (struck whole by C-223/17 at once, no text printed) absent.
- Requests: ~190 to the Senado (2.1 s pacing), 1 Colpensiones x2, 1 Sisjur. WebSearch used: 1.
- README rows for the four acts not added (task said don't touch other files): coordinator/owner of repo/README.md to add.

## Batch 5 (gitlaw-CO-2, 2026-10-29): corpus.d/95-batch5.json - DONE, 95-batch5.PUBLISH written
- Asked for: CGP, CPACA, Código Nacional de Policía, Ley 1581 (all already published in 60/80/90/50 parts) or the
  Estatuto Tributario. Took the Estatuto Tributario plus three more acts the basedoc carries with full history:
  Estatuto Tributario (estatuto_tributario, Decreto 624 de 1989) 134 versions; Ley 80 de 1993 (Estatuto General de
  Contratación) 41; Ley 1480 de 2011 (Estatuto del Consumidor) 11; Ley 769 de 2002 (Código Nacional de Tránsito) 48.
  236 laws (100 law, 38 decree, 98 court), 5.7 MB deltas. Nothing skipped: sourcing took ~10 minutes.
- Code: `batch5/fetch_batch5.py` (batch3/phase2 fetchers at ../fetch.py's 1.05 s/host pacing), `batch5/parse_batch5.py`
  (imports batch4 -> batch3 -> phase2 driver + engine; page repairs listed in decisions), `batch5/verify_batch5.py`.
  Fetch: 321 requests on 2026-10-29 (ET 36 pages + JS, the other three acts' continuation pages, 311 amending acts'
  base + last pages), all 200. Logs batch5/fetch_*.log.
- Repairs (all in decisions): ET decree arts. 2-4 cut from art. 933 (art. 3 dates the start, 1989-05-30); heading at
  the end of 'DECRETO 624 DE 1989' read by hand; duplicate numbers 485-1/512-22/623-2 -> `-bis`; 'ARTICULO ADICIONAL'
  -> art-adicional; 'ARTÍCULO 296-3 TARIFA.' (no dot); 'TITULO PRE' anchors of arts. 19-5 and 580-1; art. 424-7 split
  out of 424-6; unnumbered art. after 260-2 -> art-0260-02a; art. 368 braces (Ley 488/1998 words); 36 trailing
  capital-only section headings -> headings; 88 anchored section headings kept in titulos; 23 typo'd law keys
  (KEY_FIXES) and 5 typo'd earlier-text headings (batch4 HEADING_FIXES); yearly value decrees (Decretos 2587/1999 ..
  4715/2005) dated 1 January of the year the ET's notes give; Decreto 62/1996 day by hand (month-first DO date);
  Ley 769 '(6 de julio)' heading, two 'ARTÍCULO TRANSITORIO.' -> art-transitorio-1/2, bill texts ('Proyecto de Ley
  12 de 2006') dropped; struck words inside heading anchors (Ley 80 art. 11, Ley 769 art. 98) moved into the text.
- Placeholders ('[La fuente no da el texto vigente en esta fecha.]'): ET 53 units in the first version (95 ever; the
  source gives no 1989 wording for many rewritten articles), Ley 80 9 (12 ever), Ley 769 1 (3), Ley 1480 0 (1); none
  in today's text.
- Checks: verify_batch5 0 differences (1304 + 84 + 84 + 181 articles); 0 anachronisms, 0 pre-start events; parse
  deterministic (two runs byte-identical). Scratch build of the whole country (scratchpad co2/, copy of this folder):
  18 acts, 1002 versions, 941 commits, check.py 0 mismatches / 0 trailer errors, --compare identical. Baseline build
  with GITLAW_VERIFIED_PARTS_ONLY=1 before the PUBLISH equals the pushed clone (main~1 77b82d7) apart from the docs
  commit; with batch 5 the 14 published acts keep the same commits by day, author and tree; 47 of their commit
  messages now also name ET/EGC/EC/CNT provisions changed by the same law on the same day (the builder's one commit per
  law per day).
- repo/README.md: "What is in it now" table made one table with all 18 acts (it had blank lines splitting it and lacked
  the CC, Ley 1581, CST and batch 4 rows); stale "CST not on main yet" sentence replaced; Spanish section names the acts.
- Not pushed or committed (cadence rule); the next 4-hourly autopush pass publishes 95-batch5 to main (docs date becomes
  2026-10-29, the part's `retrieved`).

## Batch 6 (gitlaw-CO-3, 2026-10-29): corpus.d/97-batch6.json - DONE, 97-batch6.PUBLISH written
- Candidates in the task already built: CCo, CPP, CIA, CPACA (80-batch3); CGD, Ley 100, Código Electoral (90-batch4).
- Built (6 acts, 164 versions, 156 laws, 3.7 MB deltas):
  - Estatuto Orgánico del Sistema Financiero (estatuto_organico_sistema_financiero, Decreto 663 de 1993): 63 versions,
    from 1993-05-02 (art. 339).
  - Código de Minas (ley_0685_2001): 18 versions, from 2001-09-08 (art. 362); Ley 1382 de 2010 reform until Sentencia
    C-366 de 2011's deferred effect ends (2013-05-13).
  - Código Procesal del Trabajo y de la Seguridad Social, Decreto-Ley 2158 de 1948 (codigo_procedimental_laboral, slug
    codigo-procesal-del-trabajo-1948, CPTSS48): 34 versions, 1948-06-29 (art. 156) to its repeal as a whole by Ley 2452
    de 2025 art. 331 on 2026-04-02 (last version empty). '{empleador}' braces = Ley 50 de 1990 art. 107 (CST approach).
  - Código Procesal del Trabajo y de la Seguridad Social, Ley 2452 de 2025 (ley_2452_2025, slug
    codigo-procesal-del-trabajo, CPTSS): 1 version, from 2026-04-02 (art. 330).
  - Régimen de Insolvencia Empresarial (ley_1116_2006): 9 versions, from promulgation 2006-12-27 (art. 126).
  - Régimen de los Servicios Públicos Domiciliarios (ley_0142_1994): 39 versions, from 1994-07-11 (art. 189).
- Not built: Ley 222 de 1995 (mostly rewrites of Código de Comercio articles, already in CCo's history; no vigencia
  article); Decreto 2811 de 1974 (no 'Legislación Anterior' boxes). Nothing skipped for time (sourcing ~12 minutes).
- Code: batch6/fetch_batch6.py, batch6/parse_batch6.py (imports batch5 -> batch4 -> batch3 -> phase2), batch6/verify_batch6.py.
  Requests: ~325 (Senado 308 at 1.05 s/host, Colpensiones 15 for pre-1992 acts, Sisjur 2 for Decreto 673 de 1994).
  WebSearch used: 1 (identify Decreto 673 de 1994).
- Repairs (all in decisions): key slips (Decreto 673/674 de 1999 -> 673 de 1994; Decreto 2489 de 1989 -> 1999; Ley 685
  de 2021 -> 2001); Decreto 673 de 1994 = 1994-05-01 (its art. 17, Sisjur); Decreto 2423 de 1993 = 1994-01-01 (EOSF
  note); Decreto 1154 de 1999 DO from EOSF notes + default rule; month-first DO lines (Leyes 689 de 2001, 926 de 2004);
  EOSF '(Abril 2 de 1993)' heading; EOSF arts. 168-175 removed 2021-05-25 by Ley 1955 art. 336 par. 3 (marker 'derogado
  el a partir del' taken out, text kept until then); EOSF arts. 143-145 'Suprimido' = repealed by Ley 454 de 1998;
  EOSF art. 306 history set from its own boxes (C-037-94 inciso 3, C-452-95 rest); EOSF art. 12 braces dropped;
  Minas arts. 75/76/90 heading split; unnumbered 'ARTÍCULO NUEVO' -> art-0053-nuevo-1/2 (Ley 142), art-0342-nuevo
  (Minas, Ley 1382); '<Artículo ...>.' trailing dot; epigraph-only articles absent; LSPD titulos 1999-12-01 credited to
  C-969-99.
- Placeholders: EOSF 31 in the first version (44 ever), LSPD 3, CPTSS48 3 ever, Minas 1 ever; none in today's text.
- Checks: verify_batch6 0 differences; 0 anachronisms, 0 pre-start; parse deterministic. Scratch builds (session
  scratchpad co3/, copies of this folder): baseline = published parts only; with batch 6: 1063 commits, 24 acts,
  check.py 0 mismatches / 0 trailer errors, 2 unexplained (old CPen/CPP titulos), --compare identical. The 18 published
  acts keep the same trees, authors and In-force trailers; their pre-1970 commits' encoded 1970-01-01T00:00:NN author
  times shift by 1-5 s (the builder numbers pre-1970 commits in sequence; CPTSS48 adds 6). 35 commit messages of
  published acts change because the same law-day now also covers batch 6 provisions (full list: session scratchpad co3/changed_messages.txt;
  e.g. Ley 50 de 1990 'CST: 210 provisions' -> 'CPTSS48 + CST: 215 provisions'; Ley 2452 de 2025 'CGP Art. 622; CST
  Art. 380' -> 'CGP + CPTSS48 + CST: 129 provisions').
- repo/README.md: six rows added to "What is in it now"; Spanish section names the acts.
- Not pushed or committed (push loop publishes 97-batch6 to main).
