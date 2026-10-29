CHECKPOINTED 2026-10-28T17:00Z; resumed ~17:20Z (after the restart: autopush.py owns wip and builds/pushes; see BRIEF "Changed after the restart")

# gitlaw-AR progress (Argentina)

Resume from here. Brief: `scripts/south-america-law/BRIEF.md` (read it, plus `memory/git_for_law.md` and `scripts/gitlaw_common/SCHEMA.md`). Repo: `lexifina/argentina-law` (PRIVATE, never change), law-build clone `C:/Users/alany/Documents/argentina-law` (still only the scaffold commit). Wip clone `C:/Users/alany/Documents/argentina-law-wip`, pushed by `sh wip_push.sh` to branch `wip` (folder snapshot under `wip/`, no .cache). Retrieval day / `--docs-date`: **2026-10-28**. tz America/Argentina/Buenos_Aires, lang es, future_branch `futuro`. Shared builder is READY (`scripts/gitlaw_common/build.py`, `check.py`).

## Checklist

- [x] Probe sources (table below)
- [x] Clone scaffold (README/SOURCES/jurisdiction.json there: fold into `repo/README.md`, keep `jurisdiction.json` in `repo/` with `build` set to real status)
- [x] fetch.py (curl, sha256(url) cache in `.cache/`, 1 req/s/host, `.cache/requests.jsonl`)
- [x] htmltext.py (InfoLEG HTML -> paragraph lines; links to norms kept as `⟦id⟧` markers)
- [x] acts.py (registry: Constitución 804, CCyC 235975, Ley 25.326 64790, with start/end line regexes)
- [x] parse.py part 1: `act_lines`, `split_units` (articles, preámbulo, disposiciones transitorias, notes split off incl. inline trailing notes), `parse_note`, `modifiers` (verVinculos), `bulk()` (CSV index), `norm_cmp`
- [x] All amending norms' norma.htm + ficha cached (30 ids, list below)
- [x] parse.py part 2 (replay engine + `main()` in parse.py; `python -X utf8 parse.py [act-slugs…] [report] [--dry]`). corpus.json written 17:23Z with Constitución (1 version) + Ley 25.326 (2 versions): test build in .tmp-build: 0 mismatches.
- [x] CCyC replay: 12 amenders, 51 ops, 12 versions (2015-08-01 … 2026-01-02); final text vs texact: **0 word mismatches** (16 typography-only -> texact wording from the unit's last change; arts 2277/2446 InfoLEG transcription errors -> texact wording). Ley 25.326: 2 versions, 0 mismatches. corpus.json (all 3 acts) written ~17:35Z, deterministic (same sha256 twice).
- [x] repo/README.md (standard shape + Spanish section), repo/LICENSE, repo/jurisdiction.json (build = real status), repo/tools/en_vigor_el.py (wrapper over on.py, copied from Chile's). wip_push.sh deleted (autopush owns wip).
- [x] Test build in .tmp-build: 16 commits, 31 tags, 13 laws, 0 unexplained; check.py 0 mismatches / 0 trailer errors; `--compare` history identical (tip 61d7b54; docs commit differed only because the coordinator changed build.py between the two runs).
- [x] BUILD_STATUS 17:33Z: preview 6d7051d, 3 acts / 15 versions, 0 mismatches. **PUBLISH created ~17:40Z** (autopush now pushes main + tags). Law labels for DNUs are now "DNU 70/2023" etc.
- [x] Phase 2 **Código Penal** (18:28Z): base = T.O. Decreto 3992/1984 (id 38033, B.O. 1985-01-16, publisher "oldest version available", earlier_laws ley-11179 + decreto-3992-1984); replay of all laws/decrees named in texact notes or verVinculos with B.O. > 1985-01-16 (`amenders_of`): 264 ops, **72 versions, 0 word mismatches vs texact**. Engine now handles: inciso/párrafo ops (`lines`), renumbering, multi-article inserts, composite "de la siguiente manera" and "siguientes modificaciones / ARTICULO N" formats, epigraph-first instructions, annex numbering (1000*k+n), implicit target (law titled CODIGO PENAL), fines laws (no-word credits + law note), note-derived ops for laws InfoLEG can't serve (24.453, 24.454), vetoes (`patches`: Decreto 14/2021 "integral" in art 86 inc 2, kept out even though texact keeps it), overrides (26.733/26.734 numbering per Decreto 169/2012; 25.602 art 4 vetoed by Decreto 1059/2002). Reconciliation rules: 39 unamended "transcription" articles take texact wording from v1; 32 partial-change articles take texact from the last norm its note names. All listed in decisions. Vigencia auto-detected per amender (`auto_rule`) + IN_FORCE overrides (25.188 pub+8, 26.394 2009-02-26).
- [x] corpus.json with 4 acts written ~18:27Z; PUBLISH updated to cover the CP. README/jurisdiction updated (CP row, checks, what it does not show).
- corpus.json now uses SCHEMA "Large acts" `changes` after the first version (coordinator, 18:30Z): 31.6 MB -> 2.06 MB, history identical (tip 5a420ad, 95 commits, 180 tags), deterministic (same sha256 twice). Test build: check.py 0 mismatches / 0 trailer errors, --compare identical.
- 4 Wayback availability checks for Leyes 24.453/24.454 made with plain curl (not in requests.jsonl): none archived.
- [x] Phase 2 **Ley de Contrato de Trabajo** (18:44Z): base T.O. Decreto 390/1976 (id 229909, B.O. 1976-05-21); 130 amender texts fetched; 164 ops, **39 versions, 0 mismatches** (52 transcription, 10 reconciled, Ley 24.522 changes from notes). Engine additions: infinitive verbs at line start ("Incorporar como artículo 255 bis"), "waiting" rule in amender_articles (an instruction ending ":" swallows the next "Artículo N:" heading even if N is the next expected number), Spanish reopened quotes per paragraph, "Salvo disposición en contrario … entrarán en vigencia" vigencia form, repealed-in-texact detection (heading + epigraph + "derogado" note) and note-derived repeals (incl. "Capítulo VIII derogado"), "(Inciso b) sustituido …)" inline notes, Antecedentes Normativos laws added to amenders_of.
- [x] corpus.json (5 acts, 2.4 MB, `changes` format) written 18:44Z, deterministic. Test build: 137 commits, 260 tags, 132 laws, check 0 mismatches, `--compare` identical (history tip 582c0d0). README/jurisdiction/PUBLISH updated for the LCT.
- [x] **Código Procesal Civil y Comercial: not possible.** InfoLEG answers "No se pudo acceder al archivo solicitado" for both Ley 17.454 norma.htm (id 16547) and the T.O. 1981 (Decreto 1042/1981, id 45332); Wayback has no copy (7 availability checks via fetch.py). Only texact exists, so no history. Recorded in decisions and README.
- [x] **Código Procesal Penal Federal** (19:02Z): base T.O. Decreto 118/2019 (id 319681), act slice from "ARTÍCULO 1°.- Juicio previo" to "ANEXO II" (texact 239340). Text replay: Leyes 27.785 (pub+1, 2025-03-08) and 27.784 (pub+10, 2025-03-17), 0 mismatches. Staged entry into force: `steps` in ACT_SETUP (op "step" = no-word credits) from InfoLEG's notes on art. 3 of Ley 27.063 + Comisión Bicameral Res. 2/2019, 1/2020, 1/2021 (3rd business day after B.O., holidays counted by hand) + MJ resolutions per district; deferrals credited to the deferring resolution. First version 2019-06-10 (Salta/Jujuy) from Resolución PGN 127/2019 (mpf.gob.ar PDF, text layer read with pdftotext, no OCR; 1 WebSearch used, 2 of 12 total). 18 versions, 3 future (futuro branch). Resolution law keys `resolucion-{mj|cb}-N-YYYY`. Also fixed: inline "… Nación. ARTÍCULO 387.- …" headings now split (act_lines).
- [x] corpus.json (6 acts, 3.06 MB, deltas) written 19:02Z, deterministic; test build 151+ commits, 294 tags, check 0 mismatches, `--compare` identical. PUBLISH/README/jurisdiction updated for the CPPF.
- [x] Coordinator follow-up (19:12Z): business-day holidays now sourced and cached: Ley 27.399 norma.htm (281835; fixed holidays, art. 6 moves Wed 20 Nov to Mon), Decreto 923/2017 (287145; 2019 tourist days), Decreto 717/2019 (330204; 2020: 23 Mar, 10 Jul, 7 Dec), Decreto 947/2020 (344620; 2021: 24 May, 8 Oct, 22 Nov), argentina.gob.ar feriados-nacionales-2021 via https://web.archive.org/web/2021id_/ ("15 y 16. Carnaval. Feriado inamovible"; live page 404; archive.org availability API answered 429 twice). Dates unchanged: 2019-11-22, 2020-12-10, 2021-02-17; cited in the step notes and decisions. News sites: none cited; the DNU 70/2023 decision now cites the Boletín Oficial edition stamp (e. 21/12/2023 N° 104706/23) instead of "Government and the press". No WebSearch used (2 of 12 total). corpus.json rewritten atomically 19:12Z (sha256 7a9178fb…), deterministic; test build check 0 mismatches. STOPPED here per coordinator.
- [x] **Third batch (19:56Z)**, all 0 word mismatches vs texact, corpus.json 9 acts (3.59 MB, deltas), deterministic; test build 178 commits, 347 tags, 169 laws, check 0, `--compare` identical (tip 02424db):
  - **Ley General de Sociedades** (ley-19550): base T.O. Decreto 841/1984 (78064; 1972 text not served). 14 versions. Needed: `epigraphs` (title line above heading moves into the next article), Ley 26.994 Anexo II points (`POINT_AMENDERS`, `anexo_points`, in force 2015-08-01 via IN_FORCE), range repeals from notes ("arts. 361 a 366 … derogada"), `amount_notes` (capital/fine amounts by Decretos 1937/1991, 1331/2012, 209/2024 and MJ Res. 623/1991, 166/2024 → no-word credit + reconcile), override for Ley 24.435 ("replace_section" under "Plazo de ejercicio"), "Incorpórase al artículo N … el siguiente inciso", touched-reconcile (same words re-given by Ley 27.444). 151 transcription articles (mostly epigraph layout; 8 below 0.90 listed in decisions).
  - **Ley 24.240 Defensa del Consumidor**: v1 = bill minus Decreto 2089/1993 vetoes (`vetoed` + `vetoed_words`; texact keeps the vetoed sentence of art 56 g with a note → removed in compare too). 12 versions. Ley 27.444 art 134 → `restore` op on art 4 (undoes DNU 27/2018). `implicit_title` for Ley 24.787. Reglamentación changes excluded.
  - **Ley 19.549 Procedimientos Administrativos**: v1 as enacted (1972-05-06). 5 versions. Art 34 (de forma) excluded; section-name line dropped (`drop_lines`). Multi-article "Sustitúyense los artículos …" replace.
  - **Código Aduanero: skipped** (norma.htm of 16536 is an error page; texact is only an index of sub-pages).
  - Side effect on the published Código Penal: Ley 24.441 (1995) "Incorpórase al artículo 173 … el siguiente inciso" was previously read as replacing the whole art 173 (1995–2004 versions showed only the new inciso); now inserted correctly. Only art 173 changed (checked by diff).
- [x] (CPPN and Ley 24.240 done in batches 3 and 6; Código Aduanero done in batch 7, see the end.) Next if resumed: the InfoLEG-replayable candidates listed under Batch 7.

## Sources (probed 2026-10-28 with curl)

| Source | Status | Format | Dated versions | Amendment notes | robots / licence |
|---|---|---|---|---|---|
| InfoLEG `https://servicios.infoleg.gob.ar/infolegInternet/anexos/<lo>-<lo+4999>/<id>/norma.htm` (lo = id//5000*5000) | 200 | HTML cp1252 | no: original text only | n/a | robots.txt 404 (none). Footer "Copyright 2005 Ministerio de Justicia, infoleg@jus.gob.ar" |
| InfoLEG `.../<id>/texact.htm` (texto actualizado) | 200 | HTML | no: today's text only (up to date: has 2026 Ley 27.799) | yes, per article: "(Artículo sustituido por art. N de la Ley N° X⟦id⟧ B.O. d/m/y. Vigencia: …)" | as above |
| InfoLEG `verVinculos.do?modo=2&id=N` (modified/complemented by), `modo=1` (modifies) | 200 | HTML table | n/a | lists amending AND merely complementing norms | as above |
| InfoLEG `verNorma.do?id=N` (ficha) | 200 | HTML | n/a | sanción date, B.O. date/number/page | as above |
| datos.jus.gob.ar `base-infoleg-normativa-nacional.zip` (URL in parse.py BULK_NORMAS) | 200, 49.7 MB zip, CSV 257 MB, **dated 2026-10-01** | CSV cols id_norma, tipo_norma, numero_norma, clase_norma (DNU shows here), organismo_origen, fecha_sancion, fecha_boletin, titulo_*, texto_original, texto_actualizado URLs, modificada_por, modifica_a | n/a | graph | licence not yet recorded (check dataset page "Licencia") |
| datos.jus.gob.ar `base-complementaria-infoleg-normas-modificatorias.zip` (BULK_MODIF) | 200, 9.5 MB zip, CSV 60 MB, 2026-10-01 | id_norma_modificatoria -> id_norma_modificada, fecha_boletin | | | |
| argentina.gob.ar/normativa | 200; robots `Crawl-delay: 10` | same text as InfoLEG | no | same notes | not used |
| boletinoficial.gob.ar | robots empty answer (curl 000) | | | | not needed: amenders' texts are on InfoLEG |

Cache: 62 MB, 98 requests (2026-10-28). Key finding: InfoLEG never keeps intermediate versions; history = **replay** of the amending norms' own texts on the original, checked against texact.

## Findings for the replay (CCyC, Ley 26.994)

- norma.htm: 2669 article units; texact: 2672 (adds 700 bis, 1204 bis, 1221 bis). Heading form "ARTICULO N.- Epígrafe. text"; two use "N,-" (762, 1536: regex already fixed). Act slice: from `TITULO PRELIMINAR` to `ANEXO II`. Unit keys `art-0001` (width 4) for the code, `art-001` (width 3) elsewhere.
- 38 texact-noted articles, 41 differ orig vs texact; 3 un-noted diffs: art-1219 (inline note for inciso d), parsed now), art-2277 ("testa-mento" hyphen), art-2446 ("Iegitimarios"): InfoLEG transcription errors in norma.htm. Plan: correct these two in the first version and list them in `decisions` (not law changes).
- Structural headings (LIBRO/TITULO/CAPITULO/SECCION/Parágrafo + their title line) are skipped, not units (decision to record).
- Amenders that change the CCyC text, with in-force date (from their own vigencia article; default pub+9):
  - Ley 27.271 (id 265453) B.O. 2016-09-15, art. 25 "desde su publicación" -> 2016-09-15; arts 23-24 replace 2189, 2210
  - Ley 27.363 (276135) B.O. 2017-06-26, no vigencia clause -> 2017-07-05 (art. 3 = applicability "situaciones jurídicas pendientes o en curso"); art 1 inserts 700 bis, art 2 replaces 702
  - Ley 27.440 (310084) B.O. 2018-05-11, none found -> 2018-05-20; arts 201-204 replace 1673, 1692, 1693, 1839 (numbers written "1.673")
  - DNU 62/2019 (319068, clase DNU) B.O. 2019-01-22, art 6 "a partir de la fecha de su publicación" -> 2019-01-22; art 2 replaces 1907 (target written in CAPITALS: make the target regex case-insensitive)
  - Ley 27.551 (339378) B.O. 2020-06-30, art 23 "el día siguiente" -> 2020-07-01 (applies to contracts concluded from then: an `applies` group); arts 1-12: replace 75, 1196, 1198, 1199, 1201, 1203, 1209, 1221, 1222, 1351; insert 1204 bis, 1221 bis ("Agréguese como artículo …")
  - Ley 27.586 (345233) B.O. 2020-12-16 -> 2020-12-25; replace 2537, 2560; "Derógase el último párrafo del artículo 2561" (partial)
  - Ley 27.587 (345235) B.O. 2020-12-16 -> 2020-12-25; replace 2386, 2457, 2458, 2459
  - Ley 27.737 (391456) B.O. 2023-10-17, art 12 "día siguiente" -> 2023-10-18; replace 1198, 1199, 1201, 1221
  - DNU 70/2023 (395521, clase DNU) B.O. 2023-12-21; arts 250-263: replace 765, 766, 958, 960, 989, 1196, 1198, 1199, 1220, 1221; repeal 1202, 1204, 1204 bis, 1221 bis; insert inciso d) in 1219 (partial). In-force date still TO VERIFY from its final articles (believed 2023-12-29 = pub+8 per its own clause; the vigencia grep was noisy because DNU quotes other laws' text; search its last ~10 articles). Its art 249 abrogates Ley 27.551 (does not revert code text).
  - DNU 1017/2024 (406267) B.O. 2024-11-13, art 22 "el día de su publicación" -> 2024-11-13; art 14 replaces 2071
  - DNU 338/2025 (412944) B.O. 2025-05-20, art 12 same day -> 2025-05-20; art 11 replaces 75
  - Ley 27.799 (422008) B.O. 2026-01-02, art 45 same day -> 2026-01-02; arts 33-34 replace 2532, 2560
  - Ley 27.077 (239773) B.O. 2014-12-19: replaced Ley 26.994 art 7 -> the Code is in force **2015-08-01** (first version date; first_law ley-26994, cite 27.077 in decisions). It does not change Code text.
  - Checked, no CCyC text change: Decreto 1795/2014, Ley 27.221, Decreto 323/2017, DNU 27/2018, Decreto 182/2018, Ley 27.449, DNU 319/2020, DNU 320/2020 (rent emergency: suspensions, not text — say so in README "what it does not show"), DNU 522/2020, Decretos 138/2025, 486/2025, 487/2025.
- Amender format: amender articles are sequential ("ARTÍCULO 250.-", "Art. 2°-", "Artículo 1º -"); the instruction line names the target article and the Code; the new text follows on the next lines starting "Artículo N[ bis]:"/"ARTÍCULO N.-" (beware: that line also matches ART_RE, so segment amender articles by **expected next sequential number**), until the next amender article. Plan: ops replace / insert / repeal (list "los artículos 1204 y 1204 bis") / partial (último párrafo derogado; incorpórase como inciso d)); unknown ops -> use texact text if it is that unit's last amendment, else record a mismatch.

## Ley 25.326

- Slice `^Capítulo I$` to `^(DADA EN LA SALA|- Artículo 47 vetado)`; 48 units both sides; 2 diffs, both noted.
- Promulgated with partial veto by Decreto 995/2000 (id 64791, B.O. 2000-11-02): art 47 and two points vetoed (texact shows "2. (Punto vetado …)"); vetoed text never in force -> first version should already exclude vetoed parts (check how norma.htm shows them).
- Ley 26.343 (136483) B.O. 2008-01-09, no vigencia -> 2008-01-18: "Incorpórese como artículo 47" (new art 47 text).
- In force: B.O. 2000-11-02, no vigencia clause -> 2000-11-11 (Código Civil, Ley 340, art. 2: 8 days; cite InfoLEG id 109481 — not yet fetched).
- Nota Infoleg on art 46 (Decreto 1558/2001 sets the 180-day term) is a note, not text.

## Constitución

- InfoLEG 804 = Ley 24.430 (B.O. 1995-01-10), official text "1853 with the reforms of 1860, 1866, 1898, 1957 and 1994". Slice `^PREÁMBULO$` to `^ARTICULO 2º` → 147 units (preambulo, art-001..129, disp-transitoria-01..17). No texact.
- One version from **1994-08-24** (Disposición transitoria decimosexta: "entra en vigencia al día siguiente de su publicación"; oath 24 Aug 1994), first_law = the 1994 reform (kind law, label "Reforma constitucional de 1994"), earlier_laws = 1853, 1860, 1866, 1898, 1957 for context. Ley 24.430 art 2 confirms art 77 2nd paragraph (omitted from the Aug 1994 publication) is part of the text; we cannot show that omission (no 1994 B.O. text cached). Leyes 27.044 (2014) and 27.700 (2022) gave treaties constitutional hierarchy (art 75 inc 22) without changing the words: README "what it does not show".

## Decisions so far

- In-force default: CCyC art. 5 ("Las leyes rigen después del octavo día de su publicación oficial, o desde el día que ellas determinen") with art. 6 counting (publication day excluded) = publication + 9 days; before 2015-08-01 Código Civil (Ley 340) art. 2, same rule. A vigencia clause in the norm overrides (texact note "Vigencia: …" or the norm's own article).
- DNU decrees: kind `decree`, no `temporary_until` (DNUs stay in force unless both chambers reject them, Ley 26.122).
- Phase 1 third act: Ley 25.326 (the user's candidate). Código Penal first in Phase 2.

## Next 3 steps

1. Write the replay + `main()` in parse.py (country block, sources with request count from requests.jsonl, laws from bulk CSV, acts, decisions, ai_use "none"); build Constitución + Ley 25.326 first and push main, then CCyC.
2. repo/README.md + LICENSE + jurisdiction.json + tools/en_vigor_el.py; build, check, `--compare`, push.
3. Phase 2: Código Penal (16546) by the same replay.

## Gotchas

- Use curl only (fetch.py); Python TLS fails on this machine.
- Background long fetches (>120 s tool timeout).
- htmltext.decode uses cp1252; amender texts quote other laws, so vigencia/notes regexes must ignore quoted text.
- Write Python with the Write tool, not heredocs (escape mangling). Keep LF line endings.

## Pushed

- autopush owns pushes since 17:10Z (see BUILD_STATUS.json). **main pushed 9852411 at 19:58Z with 9 acts (175 versions, check 0 mismatches / 0 trailer errors)**; before that 30b2b9e (6 acts); futuro pushed (3 future CPPF steps); earlier 2f19498 (5 acts). PUBLISH present, so main + futuro + tags.

- wip: see `git -C C:/Users/alany/Documents/argentina-law-wip log -1 wip-tmp`
- main: nothing yet (scaffold only)

## Resume log (after restart)

- Fetched 3 more: Ley 340 texact index + `texactley340_preliminar_tituloI.htm` (art. 2: "serán obligatorias después de los ocho días siguientes al de su publicación oficial" -> pub+9 confirmed), datos.jus.gob.ar dataset page (licence **CC BY 4.0**, "Fuente https://www.infoleg.gob.ar").
- DNU 70/2023: no vigencia clause in its text and no "Vigencia" in texact notes -> default rule gives 2023-12-30; Government/press (El Cronista) said 29 Dec 2023, Allende & Brea said 30 Dec. Keep 2023-12-30, record the disagreement in decisions. WebSearch used: 1 of 12.
- Constitution fixes needed: "Undécimo." (masc.) for disp. transitoria 11; "DADA EN LA SALA…" -> own unit `cierre`.
- Ley 25.326 v1 must drop vetoed art 29 points 2, 3 (lines "2. …", "3. …") and art 47 (Decreto 995/2000 arts 1-2).

- fetch.py: curl now runs with `--compressed` (coordinator, 2026-10-28): gzip/brotli transfer; cached bytes and sha256 unchanged, nothing refetched.

## Open issues

- none for the shared builder yet (no ISSUES.md)

## Batch 6 (gitlaw-AR-2, 2026-10-29): DONE, verified, 70-batch6.PUBLISH written (not pushed; the 4-hourly pass publishes)

- Part `corpus.d/70-batch6.json` (sha256 0bf943a1…, deterministic), tools `batch6/fetch_batch6.py` (`archive` = Wayback captures via gitlaw_common/wayback.py) and `batch6/parse_batch6.py` (`report`, `titles`, `--dry`). Acts: Código Procesal Civil y Comercial `codigo-procesal-civil-y-comercial` (11 versions), Código Procesal Penal de la Nación `codigo-procesal-penal` (9), Ley 24.522 Concursos y Quiebras `ley-24522` (3).
- Why archives: InfoLEG serves no pre-today text of these (norma.htm error pages; 24.522 is pre-1997). Base = InfoLEG's own texact.htm as captured by the Wayback Machine: CPCCN 20130404170145 (infoleg.mecon.gov.ar), CPPN 20130404141841 (infoleg.mecon.gov.ar), LCQ 20130820110229 (www.infoleg.gov.ar); first version dated by capture day, publisher "oldest version available". Then replay of amenders published after the capture (107 InfoLEG requests on 10-29, 28 archive requests).
- Results vs today's texact: 0 word mismatches, except CPCCN art. 698 4th paragraph kept (present 2013, gone from InfoLEG from Nov 2014 with no note/norm; decision). 16 later captures (2014-2025) checked against the replay on their day: only transcription slips, publication-before-force (CPCCN 242 Dec 2018, CPPN 33 Dec 2017), notes printed as text, and Ley 27.423 art. 63 (vetoed by Decreto 1077/2017, shown by InfoLEG in Jan 2018 only).
- Engine additions (batch6 only): title-line filter for the two procedure codes (caps lines, section headings, verb-less short lines above an article heading; every dropped line reviewed by hand), base articles printed only as heading + repeal note dropped, "derogado …, en cuanto dispone" not a repeal (CPPN 516/517), CPPN target excludes "Código Procesal Penal … ley 27.063" (CPPF), Ley 27.500 arts. 2-3 multi-article overrides, Ley 27.272 in force on publication (art. 17), Ley 27.423 art. 63 override (vetoed), art. 242 amounts from 7 CSJN Acordadas (steps + amount patches, kind court, applied on the day each says).
- Scratch verification (2026-10-29, docs-date 2026-10-28, GITLAW_VERIFIED_PARTS_ONLY=1): 19 acts, 230 versions, 224 commits, 445 tags; check.py 0 mismatches / 0 trailer errors; --compare identical (history tip f9305d6). Published 16 acts: files, dates, authors and diffs identical to a build without part 70; 13 acts' commits identical in content, and 4 shared-law commits (DNU 62/2019, Leyes 27.401, 27.784, 27.785) now also list the new acts' changes in their messages. Hashes after 2013 change (one linear history).
- README: table rows for batch 4/5/6 acts, archive method, checks, Sources row (Wayback), licence/attribution, "does not show", Spanish section; jurisdiction.json build string.
- Not done: Código Aduanero (texact split over sub-pages, no full older text; archive route not tried). SAIJ not needed (only its robots.txt probed: allows document pages).

## Batch 7 (gitlaw-AR-3, 2026-10-29): Código Aduanero DONE, verified, 80-batch7.PUBLISH written (not pushed; the push loop publishes)

- Part `corpus.d/80-batch7.json` (sha256 f509e8cc…, deterministic), tools `batch7/fetch_batch7.py` (`pin` = CDX listing -> `batch7/snapshots.json`; `archive` = pinned Wayback captures; `infoleg` = today's 29 sub-pages + 105 post-2013 norms via `wayback.host_get`, 8 threads) and `batch7/parse_batch7.py` (`report`, `titles`, `--dry`). Act `codigo-aduanero` (short CA, width 4, 1130 article files today), 9 versions: 2013-04-24 (base), 2016-11-17 Ley 27.302, 2017-12-30 Ley 27.430, 2018-01-12 DNU 27/2018, 2018-06-27 Ley 27.445, 2018-12-13 Ley 27.467, 2023-12-30 DNU 70/2023, 2025-08-22 DNU 575/2025, 2026-01-23 DNU 41/2026 (its art. 3: "el día de su dictado", signed 01-23, B.O. 01-26).
- **legalize-ar finding** (blob-less clone in scratchpad/ar3/legalize-ar, HEAD 3d2450b5c09a…, 38,153 commits): its source is InfoLEG (not SAIJ's own base), same method as ours (norma.htm + amenders, checked vs texact), commits dated by B.O. publication; first commits are dated 1970-01-02. `ar/LEY-22415.md` is only InfoLEG's index page (`reform_quality: bootstrap-only`, 805 skipped). For pre-1997 acts whose original InfoLEG lacks (e.g. LEY-17454 CPCCN, "clean"), its "original version 1967" commit is today's texact (contains Ley 27.500 of 2019): no real history. So legalize-ar adds no text InfoLEG cannot give; recorded as a checked source (repo, commit, CC BY 4.0 / SAIJ attribution, MIT pipeline) in the part and README.
- Base: Wayback captures of the 29 sub-pages on www.infoleg.gov.ar, 2013-04-20..24 (InfoLEG norma.htm of 16536 is an error page; texact.htm is an index). Engine additions (batch7 only): sub-pages concatenated in index order; sha256 = all pages' bytes concatenated; page footer and "DISPOSICIONES TRANSITORIAS" line dropped; trailing notes with unbalanced ")" split off as notes (links kept); sub-chapter title lines above an article/chapter heading dropped (`titles` lists all ~140, read by hand); apartado overrides (Ley 27.430 arts. 259/261/272/277, DNU 70/2023 arts. 103/110, Ley 27.467 art. 79); IN_FORCE for dated vigencia clauses; art. 959 inc. b) amount (Res. ANA 2344/1991) as transcription; texact fixes for the amount notes (arts. 959, 1028) and the Nota on art. 791.
- Result vs today's sub-pages: 0 word mismatches; typography 320, 1058, 1094; transcription 260, 401, 959, 973, 987, 1028; reconciled 10, 453, 576, 1037, 1151. Checks vs later capture sets (2014-12 mecon, 2016-06, 2023-12 27 pages, 2024-09 19 pages): only those transcription slips, notes (791, 1028) and DNU 70/2023 on its B.O. day (1037).
- Scratch verification (copy of the folder, GITLAW_VERIFIED_PARTS_ONLY=1, docs-date 2026-10-28): 20 acts, 239 versions, 227 commits on main, 459 tags; check.py 0 mismatches / 0 trailer errors; --compare identical (history tip fc7d885). The 19 published acts: act-changing commits (dates, authors, file changes) and final trees identical to a build without part 80. **Shared law-days whose commit messages now also list CA:** DNU 27/2018 (2018-01-12), Ley 27.445 (2018-06-27), DNU 70/2023 (2023-12-30); plus the docs commit. Hashes after 2013-04-24 change (one linear history).
- README: CA table row, history paragraph (four archive acts + legalize-ar), checks bullet, "does not show", Sources rows (Wayback, legalize-ar), licence/attribution (SAIJ line), Spanish section; jurisdiction.json build string. corpus.json still carries the old decision "Código Aduanero: not built" (from parse.py; left untouched so corpus.json stays byte-identical); part 80's decisions say batch 7 supersedes it.
- **No further acts added, and why:** the task was acts InfoLEG cannot give history for, sourced from legalize-ar. legalize-ar has no real history for any such act (see above). Probed 23 candidates on InfoLEG (2026-10-29): Leyes 11.683 (T.O. 1998), 20.628/Decretos 649/1997, 824/2019 (Ganancias T.O.), Decreto 280/1997 (IVA T.O.), 24.241, 24.557, 23.737, 19.945 (Código Electoral), 24.660, 11.723, 21.526, 17.418, 24.481 (Decreto 260/1996 T.O.), 22.362, 24.013, 24.065, 24.076, 23.660, 23.661 all have a real norma.htm (texto original or texto ordenado), so InfoLEG itself gives their history by the ordinary replay (some texact pages are split into sub-pages like the CA: 24.241, 19.945, 24.065, 24.076). They are the next candidates for the normal InfoLEG route (most useful first: 11.683, IVA T.O. 1997, Ganancias T.O. 2019, 24.241, 24.557, 19.945, 23.737, 24.660), not for this archive/legalize route.
