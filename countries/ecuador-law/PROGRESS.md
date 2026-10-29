UPDATED 2026-10-29T(gitlaw-EC-3, after 06:10Z)

# Ecuador (gitlaw-EC): progress

## 2026-10-29: Código del Trabajo brought to 20-VI-2025 (gitlaw-EC-3; corpus.d/90-trabajo.json; still NO .PUBLISH)

- **State:** 37 versions (was 15), 35 laws, 267 unit changes; other parts and corpus.json untouched (byte-identical, mtimes unchanged).
- **Applied from text layers (codes/trabajo.py):** Ley Justicia Laboral (3S 483, 20-IV-2015, plain rotext; art. 15/art. 97.1 on 1-I-2016 per DT tercera); COGEP DR sexta num. 9 (art. 634) on 22-V-2015 (DF segunda: abandono rules at once), rest + DD octava (40 arts) on 22-V-2016; S720/2016 trabajo juvenil (34.1-34.4, 47.1-47.2, art-0152-3); S906/2016 feriados (art. 65); S1008/2017 (art-0247-1); S116/2017 acoso laboral (strict.py; 42 n.36, 44 m), 46 j), art-0046-1, 172, 173, 545); S175/2018 (42 second num. 10); S309/2018 Fomento Productivo (112); S517/2019 (195.2); S229/2020 Apoyo Humanitario (art-0016-2 teletrabajo, 363 n.4); sentencia 36-19-IN/21 (EC 231; art. 155); S222/2023 Juventudes (34.1, 42 n.27); S234/2023 Economía Violeta (42.1, 79, 152, art-0154-1); S242/2023 derechos trabajadores (42 n.25, 57, 58); S309/2023 Cuidado Humano (152.1/155.2 innumerados, 155, repeal of Economía Violeta arts. 24-25); 5S 64/2025 discapacidad (art-0152-4; its art. 10 on art. 42 STALE).
- **Missing pre-2014 act found and added:** Ley para el Pago Mensual del Fondo de Reserva (S644, 29-VII-2009) art. 4 (arts. 95, 201). index_docx.py truncates notes at "Art. 4 de Ley" so the Lexis index missed it; with it, COPCI 2010 num. 5 (art. 95) now applies (decision rewritten).
- **NOT APPLIED (image-only), note-only versions:** EC 40 (6-IV-2018, arts. 97.1, 459; key cc-ec40-2018); S559/2024 violencia y acoso (42, 44, 46.1, 172, 173, 545 -> STALE); 3S 588/2024 femicidio (adds 152.3; credited art-0152). No version: 2S 94/2025 trabajo del hogar (articles are images; provisions unknown). ~40 image-only laws after 27-VI-2024 unchecked.
- **Consolidations found (codes/find_consol.py, archive CDX):** SRI 27-VI-2024 (cache 9cc069f6..., capture 20250422103829) = newest from a public body; MDT 2024/01 (Ediciones Legales to 12-V-2023); defensa.gob.ec to feb-2023; LegalCloud Lexis 1-II-2023. None reaches today -> no .PUBLISH.
- **Reconcile (codes/reconcile_trabajo.py, new; `--sri` for the SRI copy):** Lexis 1-II-2023: 540 agree; SRI 27-VI-2024: 576 agree; every remaining class explained in decisions (repealed headings, innumerados, tables, literal choices, STALE 2024, SRI renumbering after art. 152, SRI transcription slips in 228/262/280/435/442/447/628).
- **README:** table row (37 versions) and the bold warning now say "text-layer reforms to 20 June 2025; not the law in force" (+ Spanish).
- **Verified:** part deterministic (two runs byte-identical); build from the folder into empty scratchpad/ec3/repo: 124 commits, 254 tags, check.py 6 acts / 139 versions / 0 mismatches / 0 trailer errors; `--compare` identical, main_identical true.
- New editions in codes/editions_trabajo.py: s644-2009, s309-2023, s559-2024, s588-2024, s64-2025, s94-2025.
- Rule slips: reconcile_trabajo.py was edited twice with a Python one-off instead of the Edit tool (content checked, LF kept). WebSearch used: 0.
- **Next (if anyone resumes):** a text-layer copy of S559/2024, 3S 588/2024, 2S 94/2025 or EC 40/2018 would let them be applied; a consolidation newer than 27-VI-2024 (SRI, MDT, gob.ec) would allow checking 2024-2026 and maybe .PUBLISH.

## 2026-10-29 06:10Z: COGEP and Código del Trabajo parts (gitlaw-EC-2; corpus.d/80-cogep.json, 90-trabajo.json; NO .PUBLISH for either)

- **State at a glance:** 6 acts. Published (PUBLISH): corpus.json (Constitution), 50-civil, 60-coip, all untouched (mtimes 10-28). Preview only: 70-comercio (held by coordinator), 80-cogep, 90-trabajo.
- **COGEP (slug `cogep`), 17 versions, 17 laws, 104 unit changes**: base Supl. 506 (22-V-2015) dated 22-V-2016 (DF segunda, 12 months); applied from text layers: Ley APP 2015 (art. 329, same_day), COESCCI 2016 (art. 133 innumerado), COA 2017 (in force 7-VII-2018), Fomento Productivo 2018, Ley Reformatoria COGEP 2019 (Supl. 517, 70 provisions; read with codes/strict.py), sentencia 92-15-IN/21, Transformación Digital 2023 (arts. 70-82), Integridad Pública 2025 (DR sexta) then restored by 52-25-IN/25 (3-X-2025). NOT APPLIED (image-only): EC 1/2017 (art. 137), EC 19/2017 006-17-SCN-CC (adds words to arts. 23, 25), Supl. 345/2020 COFJ reform (53, 55, new 53.1), 5S 452/2021 Extinción de Dominio (1, 36), 3S 587/2021 Desarrollo Económico (10, 76, 317, 324). STALE rule as in COIP: 2023 partial amendment of art. 25 not applied (version note). Note-only rulings: 19-20-CN/21 (art. 22), 36-16-IN/22 (art. 27).
- **Why COGEP stays on preview:** image-only amendments above; newest consolidation found ends 7-II-2023 (LegalCloud Lexis DOCX) / 29-XI-2021 (Función Judicial, archive 2026); 50 of 97 laws 2023-2026 are image-only (codes/screen_cogep.json). README says so.
- **Reconcile** (codes/reconcile_cogep.py -> reconcile_cogep.json): 358 articles agree with Lexis on 7-II-2023; the rest classified in decisions.
- **Código del Trabajo (slug `codigo-trabajo`), 15 versions, 15 laws, 102 unit changes, history STOPS at 12-IX-2014.** Base Codificación 2005-017 (Supl. 167), first_law null. Applied: Leyes 2006-28 (+ fe de erratas RO 223), 2006-39, 2006-40, 2006-48, fe de erratas RO 340, 2006-60, 2007-77, Mandato 8 (2008), Supl. 528/2009, COPCI 2010 (num. 5 not applied), 031-10-SCN-CC, Ley Derechos Laborales 2012, COMF 2014. Started by a helper agent (stopped at the usage limit), finished by me. **Next:** Ley Orgánica para la Justicia Laboral, Tercer Supl. 483, 20-IV-2015 (read with plain rotext.paragraphs: codes/strict.py drops half of it!), then S494/2015, COGEP DR sexta (2016-05-22), S622/2015, RO651/2015, S720/2016, S732/2016, S906/2016, RO942/2017, S1008/2017, S116/2017, S175/2018, EC40/2018 (image-only), S309/2018, S517/2019, S229/2020, EC231/2021, EC259/2022, S44/2022, S222, S234, S242/2023 (editions in codes/editions_trabajo.json; 4S/3S 242 image-only). Index: `python -X utf8 codes/index_docx.py trabajo`; newer index copies (not fetched): SRI Codigo_Trabajo_act_27062024.pdf (archive 20250422103829), trabajo.gob.ec 2024/01 CODIGO_DEL_TRABAJO-CT.pdf.
- **Verified (06:05Z):** stage = corpus.json + all 5 parts + repo/ in codes/.tmp-cogep/stage, empty repo codes/.tmp-cogep/repo: 107 commits, 217 tags, check.py 6 acts / 117 versions / 0 mismatches / 0 trailer errors; `--compare` identical, main_identical true. Verified-only build (GITLAW_VERIFIED_PARTS_ONLY=1): 77 commits, as before. Parts deterministic (two runs byte-identical).
- New tools: codes/editions.py (+ editions.json), codes/editions_trabajo.py, codes/find_consol.py (archive CDX search of gob.ec hosts for consolidations), codes/index_docx.py (Nota index from LegalCloud DOCX), codes/show.py, codes/review.py (per-version diff of a part), codes/cogep.py, codes/trabajo.py, codes/reconcile_cogep.py. `.gitignore` now ignores `.tmp-*/`.
- Commands: `python -X utf8 codes/editions.py` / `codes/editions_trabajo.py` (all cached) · `python -X utf8 codes/cogep.py` (COGEP_OUT=...) · `python -X utf8 codes/trabajo.py` (TRABAJO_OUT=...) · `python -X utf8 codes/review.py corpus.d/80-cogep.json <law-regex>`.
- Requests: 1324 in .cache/requests.jsonl; cache 3.7 GB. WebSearch used: 0. One edit to codes/cogep.py was made with a Python one-off instead of the Edit tool (content checked; LF kept).

## 2026-10-29 01:40Z: Código de Comercio part (gitlaw-EC-GY; corpus.d/70-comercio.json + 70-comercio.PUBLISH)

- **State at a glance:** 4 acts (Constitution in corpus.json; 50-civil, 60-coip, 70-comercio parts), all with PUBLISH. The old "Next steps" below (Civil index, COIP) are DONE; read sections top-down.
- **Código de Comercio (slug `codigo-comercio`, short CCom), 3 versions:** 2019-05-29 as enacted (Supl. 497, text layer; 1,348 arts + DG 1-3, DT 1, DD 1-5, DF, `titulos`) · 2020-12-10 Ley de Modernización a la Ley de Compañías (3S 347, 80/83 pages images) NOT APPLIED, no-words commit credited to art-0607 + titulos (it adds Cap. Tercero arts. 607.1-607.6) · 2023-02-07 Ley Orgánica para la Transformación Digital y Audiovisual (3S 245, arts. 45-61, text layer): 17 unit changes incl. new art-0112-1, art-0113-1, art-0189-1.
- **How amendments were found:** `codes/screen.py` (Asamblea 'leyes aprobadas' 2019-2026, 35 laws matching commerce titles, text layer grepped for "Código de Comercio" -> `codes/screen_comercio.json`); Lexis consolidation 10-XII-2020 from derechoecuador.com via Internet Archive 20240527012147 (index + reconciliation only). Bomberos Quito Lexis copies cdc25/cdc26.pdf (last reform 2023-02-07 / 2025-10-13 per a search snippet) unreachable (ECONNREFUSED, also from WebFetch) and not archived; Common Crawl index query returned nothing (tried once). The 13-X-2025 reform is presumably 6S 142 (COMF reform, image-only): recorded as a gap only, no version.
- **Text-layer cleanup:** Supl. 497 has many stray overlay fragments and headings printed twice; `codes/strict.py` drops blocks overlapping a fuller block by >=15% and identical duplicate blocks (no block >25 chars dropped; review with `python -X utf8 codes/strict.py <url>`). `fix_layer`: combining accent after accented vowel, "té rminos". Literals "a) ...; b) ..." split one per line (same split on quoted reform text).
- **Reconcile:** `codes/reconcile_comercio.py` -> `codes/reconcile_comercio.json`: 1,321/1,348 agree with Lexis 2020; 27 classified in decisions.
- **Verified:** part deterministic (two runs byte-identical); stage = corpus.json + all 3 parts + repo/ in `codes/.tmp/stage`, repo `codes/.tmp/repo`: 80 commits, 161 tags, check.py 4 acts / 85 versions / 0 mismatches / 0 trailer errors; `--compare` identical, main_identical true. Published acts unchanged (parts 50/60 and corpus.json untouched).
- README: "What is in it now" table now lists all 4 acts; new "Código de Comercio (2019)" section (+ Spanish).
- Commands: `python -X utf8 codes/fetch_codes.py` (all cached) · `python -X utf8 codes/comercio.py` (COMERCIO_OUT=... to test) · `python -X utf8 codes/reconcile_comercio.py` · `python -X utf8 codes/probe.py <product> <date> <num> [title]` finds+tests an RO edition · `python -X utf8 codes/arch.py cc|cdx|get <url>`.
- WebSearch used by this agent: 1.
- **Next acts (not started):** COGEP (Supl. 506, 22-V-2015, cached, text layer; reforms 2016-2019 likely text, incl. Ley Reformatoria COGEP Supl. 517 26-VI-2019; 3S 245 2023 arts. 70-82 reform COGEP with text; need an index: try a derechoecuador.com Lexis COGEP PDF via Internet Archive, as for Comercio). Código del Trabajo (codificación 2005, Supl. 167 16-XII-2005, text layer OK, 80 pp; dozens of reforms, larger). LOPDP: image-only.

## 21:15Z: COIP brought to 2026 (gitlaw-EC-coip2; corpus.d/60-coip.json rewritten, 60-coip.PUBLISH line updated)

- **50 versions (was 30), 49 laws, 338 unit changes.** Versions to 2023-01-04 and their laws are byte-identical to the previous part (checked); parse is deterministic (two runs identical).
- **Index of 2023-2026 reforms:** `coip/index_el2026.py` (Ediciones Legales 2026 consolidation on aduana.gob.ec, last reform 29-IV-2026; `--andina` for the Andina Ediciones compilation to 24-VIII-2026 on legalcloud.ec; both reading only), `coip/index_asamblea.py` (Asamblea "leyes aprobadas", 97 laws 2023-2026 with RO refs and PDF copies, byte-identical to the RO's), `coip/screen_laws.py` → `coip/screen.json` (every one of the 97 laws downloaded; text layer searched for the Code). Editions located with `coip/find_editions.py` (new 4th tuple item = edition title, so only that supplement is downloaded).
- **Applied from text layers** (`coip/reforms_2023_2026.py`, steps in `coip_replay.py`): Ley de Seguridad Integral (Supl. 279, 29-III-2023, arts. 38-126, in force 13-V-2023 = 30 días hábiles + 1 via `termino_days`); sentencia 61-18-IN/23 (EC 319, art. 383 phrase); sentencia 49-21-CN/25 (EC 15, art. 536 last inciso); Ley de Solidaridad Nacional (6S 56, 10-VI-2025); Ley de Integridad Pública (3S 68, 26-VI-2025); Ley de Lavado 2024 (4S 610, in force 30-VII-2025, a year + 1 day); sentencias 52-25-IN/25 then 51-25-IN/25 (EC 96, 3-X-2025) restore the exact pre-law wording (`restore_law`, snapshots in `BEFORE`/`CHANGED`); Ley Penitenciaria (4S 275, 29-IV-2026, arts. 7-24 incl. Título VI arts. 731-734); Ley de Ciberseguridad (5S 290, 22-V-2026, art. 232: not applied, see below).
- **NOT APPLIED, image-only** (no-words commits credited to existing articles): 471-S 2024 (76), 2S 496 2024 (69, 443), 3S 588 2024 (key `ley-victimas-femicidio-2024`, shared with 50-civil), S 599 2024 (12 arts), DL 477 5S 700 2024 (69, 552) + its annulment 94-24-IN/25 (EC 8), 5S 38 2025 (388), 7S 151 2025 (12, 61, 667.1, 729, 730), 5S 316 2026 (47, 69), 5S 343 2026 (541).
- **New rule (STALE):** `coip_replay.STALE` = provisions an image-only reform amended and no applied act has replaced whole since. Partial amendments of them after 2023 are not applied (`editable()`), credited with a "Partly NOT APPLIED" version note: 47, 430.1 (2023); 47, 77, 536 (S56); 45, 698, 699 (S68); 698, 699 (S275); 232 (S290). Pre-2023 steps don't consult it (unchanged output).
- `coip_replay.order()` now sorts numeric suffixes as numbers (art-477-10 after art-477-9); single-digit order unchanged. `Heads.remove()` added. `reforms_2023_2026.src()` reads U+F020 (symbol-font space, 4S 275) as a space.
- Shared law keys with 50-civil must carry the same label (builder merges by key, first file wins): ley-salud-mental-2024, ley-ahorro-monetizacion-2024, ley-victimas-femicidio-2024 use civil's labels.
- **autopush** 21:13Z: main bcd7fa6 pushed, 78 commits, check 0 mismatches (BUILD_STATUS.json).
- **Test build** (stage = corpus.json + 50-civil + new 60-coip in `coip/.tmp2/stage`, repo `coip/.tmp2/repo`): 77 commits, 155 tags, 82 versions, check.py 0 mismatches / 0 trailer errors; `--compare` identical, main_identical true.
- **Gaps (in README and decisions):** image-only laws published after 24-VIII-2026 (Sept-Oct 2026: tránsito 7S 380, reclutamiento 7S 382, aviación 6S 382, tributario 9S 392, etc.) could not be checked; sentencia 129-21-IN/25 (EC 78, art. 294.1) has no unit; decree-laws are not on the Asamblea list (DL 477 came from the index).
- **Settled (coordinator item 7):** the 2021 anticorruption reform (2S 392) is image-only from page 4 to 26; its text layer (cover, oficio, certification, signatures) has no vigencia clause, so its date stays on publication (17-II-2021); recorded in decisions. Re-parse: only `decisions` changed; test build 0 mismatches; part rewritten atomically.
- Requests: 1115 logged in .cache/requests.jsonl; cache 3.1 GB (the 97 screened law PDFs; prunable, refetchable). WebSearch used by this agent: 2 of 4.
- Commands: `python -X utf8 coip/fetch_coip.py` (53 URLs, all cached) · `python -X utf8 coip/parse_coip.py` (COIP_OUT=... to test) · `python -X utf8 coip/index_el2026.py --since 2023 --full` · `python -X utf8 coip/screen_laws.py`.

## 20:40Z: COIP part done (corpus.d/60-coip.json + 60-coip.PUBLISH)

- Base: RO Supl. 180, 10-II-2014 (text layer OK; 730 arts + 4 DG, 23 DT, 14 DR, 26 DD, DF, titulos). In force 2014-08-10 (180 days, CC art. 33 counting: `coip_replay.plazo_days`).
- 30 versions, 29 laws (12 NOT APPLIED: image-only editions, or EC222 which strikes words from an image-only reform), 161 unit changes, coverage to 2023-01-04. Applied acts: COMF 2014, Ley Reformatoria COIP 2015 (3S 598), Ley de Drogas 2015 (two steps), Ley de Tierras 2016, Ley de Lavado 2016 (2S 802), Ley violencia mujeres 2018 (S 175), referéndum 2018 (Decreto 229 annexes), Ley deporte 2019, Ley Defensoría 2019, Ley Reformatoria COIP 2019 (S 107, 118 provisions, in force 2020-06-22; `coip/s107_2019.py`), CC 34-19-IN/21, EC261 (art 75), 53-20-IN/21 (art 47), EC268 (art 175), EC20 (art 476), Ley economía campesina 2023 (art 308).
- Files: `coip/coip_base.py` (base + HEAD_NEXT heading map + hyphen rule), `coip/coip_replay.py` (acts, LAWS, STEPS, DECISIONS, csrc/clean_src, Heads), `coip/s107_2019.py`, `coip/parse_coip.py` (writes the part atomically; COIP_OUT=... to test elsewhere), `coip/find_editions.py` → `coip/editions.json`, `coip/fetch_coip.py` (32 URLs, all cached), `coip/index_notes.py` (Ediciones Legales 2021 index), `coip/index_lexis.py` (Lexis/FAOLEX 2023 index), `coip/reconcile_coip.py` (663/754 agree on 2021-10-13; rest classified), `coip/show.py`. Reuses civil/replay.py (Src, Units, unquote).
- rotext.py: new opt-in `drop_overlaps` (default off; Constitution and civil outputs unchanged) to skip stray text fragments over real text blocks (Supl. 175/2018, Supl. 133/2017, Supl. 107/2019).
- Test build (corpus.json + 50-civil + 60-coip) in .tmp-build3: check.py 0 mismatches / 0 trailer errors / 62 versions; `--compare` identical (main_identical true).
- Label clash comf-2014 / ley-extincion-dominio-2021 with 50-civil fixed (labels now identical; referendo-2018 shared with corpus.json, same label).
- (Superseded 21:15Z: COIP reforms 2023-2026 now indexed and replayed, see above.)
- WebSearch used: 10 of 12.

## 18:56Z: OCR removed (user decision, via coordinator)

- The enmiendas of **2021 (art. 272 num. 4, Tercer Supl. 377)** and **2024 (art. 138, Tercer Supl. 568)** were OCR-transcribed. The search for a machine-readable official copy found none:
  - RO site search indexes only sumarios
  - Asamblea search: news pages only
  - CC esacc: only the 2020 proposal request
  - a gob.ec consolidation (lotaip.bomberosquito.gob.ec constitucion26.pdf, "última reforma 2024-05-30") is unreachable from here and not in Wayback
  - 3 WebSearch calls used (8 of 12 total)
- So both were **taken out**: their laws, steps and notes are gone from amendments.py, and the OCR machinery is deleted (ocr_pages.py, ocr_data.py). They are listed as "Not possible" in decisions, in the README ("What it does not show", plus the Spanish section) and in PUBLISH; LICENSE is updated; ai_use now says no OCR output is legal text.
- Art. 272 and art. 138 keep their earlier wording from 2021 and 2024, which is NOT the law in force. This is stated in the README.
- OCR is still disclosed in ai_use, as reading only, for the CC 018-18-SIN-CC pages (date and scope) and Decreto 147/2025 (which article). If the user wants no OCR even for reading, those two facts need another source.
- corpus.json was regenerated atomically: 10 versions, 11 commits, 10 laws, 20 tags. check.py: 0 mismatches. `--compare`: identical (main_identical true once files stopped changing).
- NOTE: another agent is writing `civil/` in this folder (18:53Z). The builder ships it in tools/, so the docs commit changes whenever it changes.
- If a text-layer copy of either enmienda turns up (for example the Bomberos Quito PDF from a reachable network), re-add it as a normal `Src` step in amendments.py.

Slug `ecuador`, repo `lexifina/ecuador-law` (private, never change visibility), clone `C:/Users/alany/Documents/ecuador-law` (main = scaffold 549667a "Ecuador: sources, before any law"; `wip` branch pushed). tz America/Guayaquil, lang es, future branch `futuro`. Brief: `scripts/south-america-law/BRIEF.md`. Shared builder is READY (`scripts/gitlaw_common/build.py`, `check.py`).

## Status (2026-10-28 ~18:30Z) — Constitution DONE and PUBLISHED

- **corpus.json: Constitution, 12 versions, 13 commits, 12 laws, 24 tags, 0 unexplained.** Local test build (.tmp-build): check.py 0 mismatches / 0 trailer errors; `--compare` main_identical true. PUBLISH created 18:30Z → autopush now pushes main + tags. Pushed head (autopush, verified with git ls-remote 18:50Z): main fa29703, 24 tags; preview becd679.
- Versions (in force → law): 2008-10-20 constitucion-2008 (RO 449) · 2011-07-13 referendo-2011 (Supl 490) · 2015-12-21 enmiendas-2015 (Supl 653) · 2017-05-24 enmiendas-2015 (114/144, deferred by its DT 2ª) · 2018-02-14 referendo-2018 (results Supl 180; wording = annexes of Decreto 229, Supl 133 4-XII-2017) · 2018-08-02 cc-018-18-sin-cc (court, restores enmiendas-2015 except 114/144; Ed. Const. 79, image-only, read by OCR for date/scope only) · 2021-01-25 enmienda-2021 (art 272 num 4; Tercer Supl 377, image-only → OCR) · 2023-02-05 referendo-2023 (note, rejected; annexes Tercer Supl 204 7-XII-2022, results Supl 264 8-III-2023) · 2024-04-21 referendo-2024-rechazos (note, D/E: arts 422, 327) · 2024-05-09 reforma-parcial-2024 (art 158 + disp-general-03 + reforma-2024-* units; text from CNE convocation Supl 508) + referendo-2024 (arts 79, 86; Decreto 163, Segundo Supl 498; results Supl 554) · 2024-05-30 enmienda-2024 (art 138; Tercer Supl 568, image-only → OCR) · 2025-11-16 referendo-2025 (note, rejected; arts 5 (Decreto 147, image → OCR to identify article), 110 (Decreto 149), 118 (Decreto 173, Quinto Supl 139), 444 (Decreto 148); results Cuarto Supl 177).
- Searched RO for later enmiendas (site search "Enmienda a la Constitución"): only CC procedure (dictámenes/autos de vía, 2025–2026); none in force.
- Files: rotext.py (RO PDF → paragraphs; running heads/page-number blocks dropped; ligature "ﬁ " fix), parse.py (base), amendments.py (replay: Src.grab anchors, Src.check phrases, Units edits, note-only laws as lists, same-day merge, restore_from for the court), ocr_pages.py (`--make` renders + Windows OCR → ocr_data.py, which ships), reconcile.py (Lexis reading-only comparison → reconcile.json: 430/444 arts identical on 2021-01-25; 14 = gazette spellings ei/étnia/periodo/unicamente/unica/valida + Lexis note artifacts 146/148/208/313/379), sources.json (17 URLs; `fetch.py --plan` all 200), repo/ (README, LICENSE, jurisdiction.json, tools/vigente_el.py).
- fetch.py passes `--compressed` (coordinator request). Never kill processes you didn't start (coordinator rule).
- Cache: 556 MB after pruning 303 big PDFs (>2 MB) fetched only while searching for editions (findsum scans; refetchable; requests.jsonl keeps them); 609 requests. WebSearch used: 5 of 12.

## Next steps (Phase 1 acts 2 and 3: NOT done; findings)

- **LOPDP 2021: not possible from the gazette text layer.** Quinto Supl. 459, 26-V-2021 (PDF 915e2204..., 72 MB) is page images only (70 pages, no text). Building it would mean OCR-ing ~70 pages of legal text with an en-US engine and correcting every accent by hand; not done. Look for a text-layer reprint first.
- **Código Civil: feasible but large; research only so far.** Base: Codificación 2005-010, RO Primer Supl. 46, 24-VI-2005 (PDF c3070818..., cached, text layer OK, 177 pages; art. 6 now quoted as default_in_force_rule). Amendment index from the Lexis consolidation of 12-IV-2017 at WIPO Lex (https://wipolex-res.wipo.int/edocs/lexdocs/laws/es/ec/ec118es.pdf, an HTML page, cached; reading only). "Nota:" counts per amending RO: RO 169 20-XII-2005 (1), Supl. 274 19-V-2006 (1), Supl. 452 19-V-2011 (1), Supl. 732 26-VI-2012 (2), Supl. 796 25-IX-2012 (9), Supl. 797 26-IX-2012 (1), Supl. 843 3-XII-2012 (1), Supl. 506 22-V-2015 COGEP (23), Supl. 526 19-VI-2015 Ley Orgánica Reformatoria del Código Civil (76), Supl. 983 12-IV-2017 (3). After 2017 unknown (other consolidations claim 2019, 2022, 2024 changes): needs RO search per year. Plan: same replay machinery (amendments.py Units/Src), one function per amending act, act slug `codigo-civil`, first_law null (codificación = oldest version available).
- **COIP 2014** (Supl. 180, 10-II-2014, text layer OK) has dozens of reform laws; much larger than the Civil Code.

## Checklist

- [x] Read BRIEF, git_for_law memory, SCHEMA, PLAN; cloned scaffold
- [x] fetch.py (curl --compressed, sha256 cache, 1 req/s/host, requests.jsonl; POST body in cache key), ro_index.py, ro_search.py, push_wip.sh (obsolete since autopush)
- [x] Base Constitution (RO 449) parsed: 444 arts + preamble + 30 DT + derogatoria + 30 RT arts + final + titulos
- [x] Every amending act, ruling and referendum found in the RO and replayed (see Status)
- [x] Build/check/compare in .tmp-build: 0 mismatches, identical; README/LICENSE/jurisdiction.json in repo/; PUBLISH
- [ ] Código Civil (index ready, see Next steps)
- [ ] LOPDP 2021 (image-only gazette; not possible from text layer)

## Sources (probe 2026-10-28)

| Source | Status | Format | Dated versions | Amendment notes | robots / licence |
|---|---|---|---|---|---|
| registroficial.gob.ec (WordPress/Divi, run by the Corte Constitucional) | 200 | HTML index + one PDF per edition | gazette editions, dated | no | robots: Disallow /wp-admin/ only (admin-ajax.php allowed). No licence stated. |
| esacc.corteconstitucional.gob.ec/storage/api/v1/10_DWL_FL/<base64 JSON {"carpeta":"ro","uuid":"<uuid>.pdf"}> | 200 | PDF | — | — | PDF host for every RO edition |
| asambleanacional.gob.ec (Drupal) | 200 | HTML/PDF | — | — | robots Crawl-delay 1 |
| corteconstitucional.gob.ec | 200 | WordPress | — | — | robots allows all |
| defensa.gob.ec Lexis consolidation `https://www.defensa.gob.ec/wp-content/uploads/downloads/2021/02/Constitucion-de-la-Republica-del-Ecuador_act_ene-2021.pdf` | 200 | PDF (Lexis Finder, "Ultima modificación 25-ene.-2021") | no | YES per provision ("Nota: … reformado por … RO Suplemento N de …") | Lexis copyright: use ONLY as index of amendments / reconciliation, never copy text |
| portal.compraspublicas.gob.ec (SERCOP 2025-11 copy) | connect timeout; no Wayback copy | | | | |

### Registro Oficial endpoints

- `wp-json` returns 403. Post sitemaps `wp-sitemap-posts-post-{1..13}.xml` (25,901 posts) have no PDF links and edition numbers restart each presidential period, so don't index by slug.
- Product pages hold a year/month tree (2001–2026): RO `/245427-2/`, Suplemento `/255776-2/`, Edición Especial `/261974-2/`, Edición Constitucional `/267099-2/`, Edición Jurídica `/266381-2/`.
- Month listing: POST `https://www.registroficial.gob.ec/wp-admin/admin-ajax.php` body `action=get_term_post_kilur_con_imagen&year_id&mes_id&name_folder&page&id_carpeta` (values from the tree's `data-*`). JSON `{data: html}` with cards (`card__title_post_imagen`, `card__title_numero_imagen` "Año I - Nº 449", `txt_fecha_post_imagen` "lunes, 20 octubre 2008", `cta_post_imagen` PDF href). `python -X utf8 ro_index.py <ro|suplemento|especial|constitucional|juridica> <year> <month>`. Pagination via `button-post-imagen-link data-page` (untested).
- Site search: `https://www.registroficial.gob.ec/?s=<q>` and `/page/N/?s=<q>` — cards include the sumario text + PDF link. `python -X utf8 ro_search.py "enmienda+constitucional" <pages> <regex>`. Page may be cp1252, not UTF-8.

### Base text (done)

- Constitución 2008 = Registro Oficial Nº 449, lunes 20 octubre 2008, PDF `http://esacc.corteconstitucional.gob.ec/storage/api/v1/10_DWL_FL/eyJjYXJwZXRhIjoicm8iLCJ1dWlkIjoiMDZmMTE3NmQtMGMxNC00OTNmLWFhZGYtMjQ0ZmQ0OWQ1OTVmLnBkZiJ9` (82 pages, sha256 of URL 19999c92…). pymupdf `page.get_text()` reads columns in order. Text: Preámbulo, Art. 1–444, Disposiciones transitorias (1ª–30ª), Disposición derogatoria, Régimen de transición (Art. 1–30), Disposición final ("entrará en vigencia el día de su publicación" → in force 2008-10-20).
- Parsing notes: paragraphs separated by whitespace-only lines; justified lines sometimes split one word per line (join with spaces); page header "Registro Oficial Nº 449 -- Lunes 20 de Octubre del 2008 -- N" (and "N -- Registro Oficial …") must be dropped; join a paragraph across a page break when the previous chunk lacks final punctuation or the next starts lowercase. Pages 3–7 are the index (skip until the second "PREÁMBULO", line ~1549).

## Constitution amendment index (initial, from Lexis notes; all rows since verified and built, see Status)

| Date (publication = in force unless stated) | Act | RO | Kind | Provisions |
|---|---|---|---|---|
| 2011-07-13 | Referéndum y consulta popular 7-V-2011, Resolución CNE | Suplemento 490, 13-VII-2011 | referendum | art 77 nums 1, 9, 11; art 179, 181(?); art 312 + transitoria 29ª; Régimen de transición art 20 (verify) |
| 2015-12-21 | Enmiendas, Resolución Legislativa (Asamblea, 3-XII-2015), arts 1–16 + disposiciones | Suplemento 653, 21-XII-2015 | law | arts 104, 114, 142, 144, 158, 211, 212, 229, 261, 264, 326, 370, 372 … + transitorias (reelection part effective 24-V-2017? verify) |
| 2018-02-14 | Referéndum y consulta popular 4-II-2018, Resolución CNE No. 1 | Suplemento 180, 14-II-2018 | referendum | arts 46 (num 4, 2º inciso), 114, 144, 233, 407, CPCCS arts (207…), transitorias; derogated 2015 transitoria |
| 2019-04-30 (decision 2018-08-01) | Corte Constitucional sentencia 018-18-SIN-CC: 2015 enmiendas unconstitutional por la forma | Suplemento 79, 30-IV-2019 | court, `restores` | every 2015 enmienda still in text; check the sentence for the effective date and any deferred effects |
| 2021-01-25 | Resolución Legislativa, artículo único (enmienda) — adds a numeral 4 to an article near art 272 | Suplemento 377 (tercer?), 25-I-2021 | law | verify |
| 2024-05-30 | Enmienda art 138 (veto parcial), Asamblea, after CC 4-20-RC/20 | Tercer Suplemento 568, 30-V-2024 | law | art 138 |
| 2024 (~May) | Consulta popular 21-IV-2024, questions A (art 158) and E (art 79) approved | find RO (CNE results) | referendum | arts 158, 79 |
| 2023-02-05 consulta | all rejected | — | — | none (verify) |
| 2025-11-16 consulta | rejected (verify) | — | — | none |
| 2025–2026 | CC dictámenes de vía only so far found: 5-25-RC/25, 7-24-RC/26 (enmienda apt for arts 108, 109 → pending in Asamblea), 8-25-RC/26, 9-25-RC/26, 2-26-RC/26 | Ed. Constitucional | — | none in force unless an Asamblea enmienda/consulta is found; search RO 2025–2026 |

Not amendments (do not commit as text changes): CC interpretative rulings (RO 549-S 2009, 50 2009, 25-S 2009, 159-S 2010, 294-S 2010, 629-S 2012, 40-S 2020); Lexis's editorial "Imputado"→"Procesado" from COIP Disp. Reformatoria Primera (RO 180-S 10-II-2014) — a law cannot amend the Constitution; record as decision.

## Default in-force rule

Código Civil (codificación 2005, RO Supl. 46) art. 6, verified in the cached PDF: "La ley entrará en vigencia a partir de su promulgación en el Registro Oficial ... Podrá sin embargo, en la misma ley, designarse un plazo especial para su vigencia". Constitution Disposición final: in force on publication. Referendums: in force on publication of the CNE results.

## Gotchas

- Never pass Python through bash heredocs (`"\n"` became a real newline once). Use the Write tool.
- pymupdf (`fitz`) is in the user site; `python -I` can't import it. Run parse scripts from this folder, never from .cache.
- RO HTTP links are `http://esacc…`; curl follows. Listing pages claim "40 PÁGINAS" for every old edition (placeholder).
- Edition numbers restart per presidential period: always pair number with date.
- Heredocs also mangle backslashes in Python (`\\s` arrives as `\s`): write helper scripts with the Write tool.
- Windows OCR: `ocr_pages.py --make` (only en-US engine installed); `.tmp/ocr.ps1` for ad-hoc reading.
- `.tmp/findsum.py <product> <y> <m> <from> <to> <regex>` greps the first 3 pages of each edition in a date window; it downloads every edition (prune big PDFs afterwards).

## Coordinator (2026-10-29): Código de Comercio held on preview
`corpus.d/70-comercio.PUBLISH` was renamed to `.70-comercio.PUBLISH.held`. Today's text is missing arts. 607.1–607.6 (the 2020 Ley de Modernización exists only as images), and a 13 Oct 2025 reform is probably not applied, so it does not yet equal the official current text. Restore the file once those are sourced, or if the user decides otherwise.
