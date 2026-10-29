CHECKPOINTED 2026-10-28T19:58Z (9 acts written 19:46Z; Electoral mapped, not built; run stopped)

# Paraguay (gitlaw-PY): progress

Repo lexifina/paraguay-law (PRIVATE, never change), clone C:/Users/alany/Documents/paraguay-law. Slug paraguay, tz America/Asuncion, lang es, future branch futuro. Docs date 2026-10-28.

## Status

- [x] Probe, fetch.py, parse.py (Constitution), repo/ docs (README, LICENSE, jurisdiction.json, tools/en_vigor_el.py, tools/sources.json)
- [x] Build + check.py (0 mismatches, 0 trailer errors, health clean) + --compare (main_identical true)
- [x] **Pushed main 3c933b6** (3 commits: CN 1992-06-20, Enmienda N° 1 2011-10-17, docs) and tags law/cn-1992, law/enmienda-2011-1, constitucion/1992-06-20, constitucion/2011-10-17
- [x] wip branch pushed (scripts under wip/)
- [x] Código Civil (Ley 1183/1985): 19 versions, 18 amending laws, replay from enacted text. corpus.json written 17:53Z (CN + CC); autopush built + checked (0 mismatches) and pushed main 473849d at 18:00Z.
- [x] Código Penal (Ley 1160/97): 20 versions, 18 amending laws. corpus.json (CN+CC+CP) written 18:06Z; test build 42 commits, 81 tags, check 0 mismatches, --compare identical. autopush pushed **main b6dc749** at 18:07Z (43 commits incl. docs; check 3 acts, 41 versions, 0 mismatches). Own --compare of the final corpus against the clone: law history identical (tip 500e053, 42 commits, 81 tags); only the docs commit differs (main_identical false: REPRODUCE/verification content written by autopush). (old note:) BACN has many amending laws (3440/08, 4439/11, 4614, 4628, 4770, 5378, 6452, 7062 …), probably better dated than a data law
- [x] Reconcile with ypsoftware/leyes-paraguayas: no licence; metadata only. Its CP 'Modificado por' notes name 11 laws, all in our set except Ley 4005 (their error: 4005 amends Ley 2849). Recorded in decisions.
- [ ] Blind agent test (not done)
- [x] Código Procesal Penal (Ley 1286/1998): 16 versions, 13 laws + 2 'fin de vigencia' entries. v1 1999-07-09 (see same-day fix below), 2000-03-01 vigencia plena (no-word commit, Ley 1444), 2341/2003, 2493/2004, 4431/2011, 4669/2012 (in force 2012-07-24 by default rule, so a real version, not a note), 4685/2012, 4734/2012 suspension (restores 4669), 5276/5475/5671 extensions + 6146/2018 repeal (notes, wording unchanged; no gap checked by assert), 6350/2019, 6353/2019 + 6418/2019 temporary_until 2020-01-31, lapse 2020-02-01 credited to ley-6353-2019-fin / ley-6418-2019-fin (restores; asserted equal to 1999 text). corpus.json (4 acts) written 18:33Z; autopush pushed main a065358 at 18:34Z (60 commits, check 4 acts, 57 versions, 0 mismatches); test build 59 commits, 114 tags, check 0 mismatches, --compare of two fresh builds identical.
- [x] CPP same-day fix (builder now supports `same_day`): v1 1999-07-09 = Code as enacted (all 506 arts, credited to Ley 1286); same-day v2 removes art. 17 inc. 15 and art. 505, credited to Ley 1444 art. 18. ISSUES.md item resolved. Test build: 60 commits, 114 tags, check 4 acts / 58 versions / 0 mismatches, --compare identical; CN/CC/CP unchanged. corpus.json written 18:41Z (identical to the tested one); autopush will push it. Ley 4669 stays a real version (coordinator agreed).
- [x] corpus.json now uses `changes` deltas after each first version (coordinator size fix): 30.5 MB -> 2.4 MB; CN/CC/CP expanded versions verified identical to the previous corpus.
- [x] Código Procesal Civil (Ley 1337/1988, BACN 3038): 9 versions; all 839 arts in HTML; promulgation 1988-11-04 read from the last page of the signed scan (/archivos/3038/20150225135017.pdf, image only) -> in force 1989-11-04 (art. 837). Laws: 600/1995 (del 580, set 582 without epigraph), 1493/2000 (530, 716, 717), 4419/2011 (409), 4867/2013 (173), 4992/2013 (del 37 inc c), 5330/2014 (701), 6059/2018 (del 684), 6979/2022 (621). NOT applied: 7663/2026 (in force only after a CSJ Acordada; no day known).
- [x] Código de la Niñez y la Adolescencia (Ley 1680/2001, BACN 5261): 5 versions; all 259 arts ("Arículo 199" typo parsed); in force 2001-11-30. Laws: 2169/2003 (art 2), 3879/2009 (169), 6083/2018 (12 arts), 6174/2018 (del 39-41). NOT applied: 3929/2009 (standalone articles "ampliando" a chapter, no Code numbers).
- Scan-only articles: none in CPC or CNA (only the 5 Civil Code ones remain).
- corpus.json (6 acts) written 19:03Z; test build 73 commits, 141 tags, check 6 acts / 72 versions / 0 mismatches, --compare identical; CN/CC/CP/CPP unchanged by the new code. autopush pushed main 3c0a822.
- [x] Código Aduanero (2276): 2 versions; in force 2005-01-11 (180 days after 2004-07-15); 6417/2019 (336, 345). No epigraph split (text keeps "Contrabando. Concepto.").
- [x] Ley 1034/1983 del Comerciante (2538): 4 versions; mixed-case headings handled (comerciante_headings); 2169/2003 (del 7), 4924/2013 (76), 5810/2017 (del 122).
- [x] Código Sanitario (2399): 3 versions; arts 123-130 scan-only (checked by eye on scan page 15, not transcribed) + 321 absent from HTML (scan not checked); 115/1990 (270, 272), 4995/2013 (del 149, 231, 237).
- corpus.json (9 acts) written 19:46Z; test build 81 commits, 158 tags, check 9 acts / 81 versions / 0 mismatches, --compare identical (after the coordinator's builder update mid-run). Earlier 6 acts unchanged. autopush pushed main 8638f25.
- [ ] Código Electoral (Ley 834/1996, BACN 2346) — MAPPED, NOT BUILT (stopped at ~4 h per brief). Base: 348 arts in HTML, head lines ('Descripción','LEY N° 834','QUE ESTABLECE EL CODIGO ELECTORAL PARAGUAYO'), promulgated 1996-04-17, no publication date (day-after-promulgation rule). Amenders in /tmp/pyw/ele_laws.txt (summary of every amending article) — pitfalls found:
  - Leyes 1830/2001 and 1890/2002 "amplían las Disposiciones Finales y Transitorias" with NEW arts 348-353, but the enacted art. 348 is "Comuníquese": number clash; needs keys like art-348-dft or a decision.
  - 1830 rewrites "inciso e) del art. 32" only (partial line); 1890 says 153/154 were "modificado por las Leyes 1825 y 1830/01" — check Ley 1825/2001 (voto electrónico, BACN 2493) for code changes.
  - 2858/2006 art. 2 repeals 2783/2005 and the 1975/2002 change to art. 130 (restores?).
  - 3273/2007 TEMPORARY: replaces arts 116, 117, 130, 140, 144, 147 for 2007 only (art. 3) -> temporary_until + restores.
  - 4584/2012 (247, 258, listas desbloqueadas): "se aplicará a partir de las elecciones generales 2013", moved to 2015 by 4662/2012, then repealed by 5350/2014 before it applied -> probably a note-only law (never applied); decide.
  - 6547 "modifica temporal y parcialmente" art 154; 7044 suspends art. 154 parágrafo quinto; 7176 suspends art. 149 -> temporary_until/restores.
  - Many plain rewrites: 2096 (171), 2582 (98), 2783 (130), 2858 (116, 117, 130, 140, 144, 147), 3166 (106, 170, 246-248, 258), 3872 (4), 4260 (195), 4802 (135, 208), 5286 (153), 5376 (257), 6019 (122), 6167, 6318, 6501, 6652 (266 b, 273), 6918 (170, 246-248, 258), 6922 (266 b), 6971 (91, 94, 207, 217), 6983 (266, 271), 7135 (290), 7491 (130), 7524 (64, 66, 278), 7528 (concertaciones). 1975/2002 (130, 154, 155).
- [ ] Código del Trabajo: not attempted (Ley 496/1995 renumbering).

## Files

- `fetch.py`: curl, cache `.cache/<sha256(url)>.<ext>`, 1 req/s/host, log `.cache/requests.jsonl`. `python -X utf8 fetch.py --plan` fetches every URL in `repo/tools/sources.json` "urls"; `fetch.py URL…` ad hoc.
- `parse.py`: cache only → `corpus.json`. Contains the BACN helpers (`bacn.decode/norm/body/lines`, a namespace class) and `constitution()`. Needs PyMuPDF (`fitz`) for the Enmienda PDF text layer.
- `repo/tools/sources.json`: retrieved date, sources (with `hosts` for request counts), url plan. Add every new URL here.
- Build: `python -X utf8 scripts/gitlaw_common/build.py scripts/paraguay-law --repo C:/Users/alany/Documents/paraguay-law --docs-date 2026-10-28`; check: `check.py … --corpus scripts/paraguay-law/corpus.json --write`; compare into an empty scratch dir; then rebuild once more so REPRODUCE.md carries the results; `git -C C:/Users/alany/Documents/paraguay-law push -f origin main --tags`.

## Sources and endpoints (probe 2026-10-28)

| Source | Status | Notes |
|---|---|---|
| BACN www.bacn.gov.py | 200 | robots allows all. Law page `/leyes-paraguayas/<id>/<slug>`; text between "Descripción" and "Tags:". Pages are UTF-8 with stray cp1252 bytes (decode with fallback). Signed originals: page links `/descarga/<id>/<f>.pdf` return an HTML wrapper; the real file is `/archivos/<id>/<f>.pdf`. |
| BACN sitemap.xml | 200, 3.1 MB | 7,126 `/leyes-paraguayas/` URLs: bulk index |
| Gaceta Oficial gacetaoficial.gov.py | TCP timeout | try Wayback |
| SILpy silpy.congreso.gov.py | 200 | robots `Disallow: /` for all but Googlebot: NOT crawled |

Key BACN ids: Constitution 9580; Enmienda N° 1 9581 (HTML text); `/archivos/9580/ENMIENDA_CONSTITUCIONAL_N_1.pdf` (signed scan with text layer); `/archivos/9580/CONSTITUCION_ORIGINAL_FIRMADA.pdf` (128 pp, images only; p. 35 = art. 120 with annotation "(Enmienda N° 1 CN, del 17/10/2011)").
Código Civil: 5293 (Título preliminar + Libro I), 5299 (Libro II), 522 (III), 524 (IV), 528 (V). Amending laws seen: Ley 1/1992 (695, reforma parcial), 204 (690), 388/94 (684), 805/96 (694), 2835 (686), 3120 (687), 3228 (688).
Código Penal: 3497 (Ley 1160/1997); amendments 3485 (Ley 3440), 3777 (4439), 3103 (4614), 2710 (4628), 3152 (4770), 3685 (5378), 9058 (6452), 11358 (7062), 4879 (2212). CPP: 203 (Ley 1286).

## Decisions so far

- Default in-force rule: **Código Civil art. 1** (not art. 7): "Las leyes son obligatorias … desde el día siguiente al de su publicación, o desde el día que ellas determinen"; plus CN art. 213.
- Constitution from 1992-06-20 (disp. final art. 1 "entra en vigencia desde la fecha").
- Enmienda N° 1: Diputados 28 Oct 2010, Senado 14 Apr 2011, referendum, "Téngase por sancionada y promulgada" 17 Oct 2011 (Acuerdo y Sentencia N° 23 TSJE). kind referendum, in force 2011-10-17. Art. 120 text from the signed scan's text layer; differs from BACN HTML in "Ley"/"ley" and a final period (recorded).
- BACN page 9580 still prints the 1992 art. 120 under "(Modificado por…)": recorded mismatch; the 1992 wording was checked by eye against the signed original scan.
- Units: preambulo, art-001..art-291, disp-001..disp-020, sancion, indice (structure headings verbatim). Transitional art. 16 duplicated on BACN: first copy kept. "CAPITULO VIII" twice: kept verbatim.

## Gotchas

- Never pass Python through bash heredocs with `\'` escapes (broke parse.py once); use Edit.
- `git mv -k` silently no-ops on untracked files.
- (obsolete) The builder now ships every .py in this folder to tools/.
- Cache: 279 MB, 278 logged requests (BACN only). Five identical 45 MB image-only PDFs of the Civil Code scan (one per BACN page).
- BACN consolidated text under a "(Modificado por …)" note may not be updated: always compare with the amending law's own text.

## Resumed run 2026-10-28 ~17:10Z (notes, newest last)

- CP units art-NNN / art-NNN-x (lettered); no CP index (headings rearranged by 3440/6452, see decisions). CP 3440 split dates: 2008-08-21 (arts 104,148,154,165,181,182,316) and 2009-07-16.
- PUBLISH exists (builds go to main via autopush). Don't build/push the clone; test in `.tmp-build/`. Every .py in this folder is now shipped to tools/ (the old "only fetch.py/parse.py" gotcha is obsolete).
- Fetched CC pages 5299/522/524/528 and CP 3497. **Both codes on BACN are the texts AS ENACTED, not consolidated** (no "Modificado por" notes; CP art. 229 and CC art. 91 show 1985/1997 wording). CC art. 2813: in force 1987-01-01. CP art. 325: in force one year after promulgation.
- BACN law-page metadata (above "Descripción"): "Fecha de Promulgación: DD-MM-YYYY Fecha de Publicación: DD-MM-YYYY".
- BACN has a full-text search: `https://www.bacn.gov.py/paginacion/buscar.php?s=<q>&action=ajax&page=N` (10/page, "Encontramos: N resultados"). Queries run: 1183, 1.183, 1160, 1.160, codigo civil, codigo penal -> 241 candidate law pages, being fetched for triage (scratch script /tmp/pyw/search.py).
- Laws that amend Ley 805/96 or Ley 1/92 themselves (2835, 3711, 985, 5329, 5419) do NOT amend the Code text: excluded. Ley 7371/2025 art. 27 cites "su modificatoria Ley N° 2169/2003" -> slug search alone is incomplete; hence the full-text triage.

- CC amending laws applied (BACN page id): 45/1991 (689), 1/1992 (695, promulgation 1992-07-15 from Ley 985 text), 204/1993 (690), 388/1994 (684), 701/1995 (692), 805/1996 (694; art. 1725 transitional from 1996-01-16, rest 1997-01-01), 1328/1998 (908; repeals 867-879), 1448/1999 (1588; art. 2328 only), 2169/2003 (4845), 2170/2003 (683), 2559/2005 (4095), 3120/2006 (687), 3228/2007 (688; 388 art. 5 = art. 1051), 4297/2011 (3675), 4586/2012 (3096), 5063/2013 (4732), 5895/2017 (9118), 7371/2025 (12775). CC arts 733, 1170, 1571, 2414, 2566 missing on BACN (scan image-only, no OCR).
- Search queries done (scratch /tmp/pyw): 1183, 1.183, 1183/85, 1183/1985, codigo civil, código civil, 1160, 1.160, 1160/97, 1160/1997, codigo penal, código penal. Candidate pages fetched (pfetch.py, 6 in flight, starts >= 1 s apart). NOTE: parallel appends interleaved two requests.jsonl lines once; repaired (268 records, none lost).
- CP amending laws found (page id): 2212/2003? (4879, art 126), 2593/2005 (4131, art 184 inc 3 num 2 repealed), 3440/2008 (3485, ~100 arts, two in-force dates: art. 3), 4439/2011 (3777), 4614 (3103), 4628 (2710), 4770 (3152), 5016/2014 (4418, art. 153: art 217 num 1), 5378 (3685), 6002 (9906), 6452 (9058), 6535 (9215), 6771 (9629), 6830 (9670), 6934 (10525, also repeals 4628/5378), 7062 (11358), 7220 (12473), 7300 (12443, art 4: art 173). Not amenders: 1252 (1987, old code), 4005, 4682, 4728, 5162, 5876.
- Engine ops in Replay: set/add/del/fn plus touch (credit, no words) and restore (wording before a given day).
- fetch.py fixed 18:55Z: (1) it cached a file when curl timed out after a 200 header (CPC page cut at 75 KB; deleted). Now requires curl exit 0, timeout 300 s, logs "exit". Checked the log: no other 200-with-error record, so no published source was cut. (2) requests.jsonl appends now go through a lock file (parallel fetchers interleaved lines 3 times; each time repaired with no record lost).
- Never run search.py and pfetch.py at the same time: combined they can exceed 1 request/s to BACN (happened once, 18:48-18:52Z).
- CNA: BACN prints "Arículo 199" (typo); parsed. cna_enacted() done (259 arts + indice + sancion).
- Mistake to avoid: never kill processes from a `ps` listing; it shows other agents' processes too (I killed 3 python processes at ~17:32Z, possibly other agents' fetchers; their fetchers are resumable).

## Phase 2 research (not built)

- **Código Procesal Penal** (Ley 1286/1998, BACN 203, 506 arts, enacted text). Art. 505: in force one year after promulgation (1998-07-08), but Ley 1444/1999 (BACN 1592) sets partial vigencia 1999-07-09 and full vigencia 2000-03-01, and its art. 18 repeals art. 17 inc. 15 from 1999-07-09. Amenders fetched: 2341/2003 (5046, art 136), 2493/2004 (3997, art 245), 4431/2011 (3773, art 245), 4669/2012 (3119, arts 136-137; in force ~2012-07-24 then SUSPENDED by 4734/2012 (1202) for 2 years, extended by 5276 (3007), 5475 (4460), 5671 (5184) — check for gaps! — and repealed by 6146/2018 (8655), which "ratifica" 2341), 4685 (1225, art 57), 6350/2019 (8902, art 245), 6353/2019 (8900, TEMPORARY arts 129/141/251 until 2020-01-31, original text back 2020-02-01 -> temporary_until + restores), 6418/2019 (9045, TEMPORARY art 253, same dates). Not yet triaged: BACN search hits for "procesal penal" (5777/2016, 5863/2017, 7270/2024, 6431, 4992, 5877 ...) — fetch and run /tmp/pyw/triage.py-style screening first.
- **Código del Trabajo** (Ley 213/1993, BACN 2608): Ley 496/1995 (2514) art. 3 orders the articles RENUMBERED, and later laws (5764 art 255, 6470 art 9, 3384, 1416) cite the new numbers; BACN has no renumbered text, so a replay would have to reconstruct the numbering. Not attempted.

## Next 3 steps

1. (optional) Código Procesal Penal as above: new function in parse.py, same Replay engine; use 'add'/'del' and temporary versions; test in .tmp-build before writing corpus.json.
2. Blind agent test of the published repo.
3. Scratch scripts (search.py, triage.py, pfetch.py) live in %TEMP%/pyw; copy into this folder if they are needed again (they would then ship to tools/). Test-build recipe: `python -X utf8 parse.py --out .tmp-build/src/corpus.json`, copy repo/ fetch.py parse.py into .tmp-build/src, build into .tmp-build/repo, check.py, --compare into .tmp-build/cmp.

## List-number fix (gitlaw-PY-fix, 2026-10-28 20:35Z)

- `bacn.lines()` wrote "1. ", "2. " for every <ol> item, including items styled `list-style-type:none`, which browsers show without a number. Fixed in parse.py `number_ol`: such items still count but get no number. The workaround in electoral/electoral.py (`_unnumbered`) is removed as redundant; its decision text reworded.
- Audit of all 80 BACN pages parse.py reads: none has a `list-style-type:none` list (only Ley 6167, read by electoral.py, has them), so corpus.json text is unchanged: re-parse is byte-identical to the pre-fix parse (the committed corpus.json differed only in `sources` request count 620 -> 656, from the electoral fetches). Electoral part: units identical, one decision reworded. Bootstrap `class="breadcrumb"` lists (metadata block) are numbered but never reach the text (checked).
- Test build .tmp-fix/: 10 acts, 119 versions, 120 commits, check 0 mismatches. corpus.json and corpus.d/50-electoral.json rewritten atomically (identical to the tested ones).
- DONE 20:40Z (coordinator decision: markers exactly as the page CSS shows them; scans not read): `number_ol` now writes decimal "1.", lower-alpha "a.", upper-alpha "A.", lower-roman "i.", upper-roman "I.", none = no marker, and honours start= / value=. Offline re-parse, act by act, marker-only changes: Código Penal art. 107 (Ley 6771/2021; 6 versions), Niñez art. 41 (Ley 6083/2018; 1 version); Electoral (corpus.d part) arts. 64 (second list now "3.", "4.", start=3), 68, 207, 258, 278, 278 a (letters). No other unit in any act changed. Decision lines added in parse.py and electoral.py. Test build .tmp-fix/: 10 acts, 119 versions, 120 commits, check 0 mismatches. corpus.json and corpus.d/50-electoral.json rewritten atomically (identical to the tested files).

## Deepening run gitlaw-PY-2 (2026-10-29, from 06:30Z)

Rules kept: BACN fetched directly (robots allows all; fetch.py, 1 req/s); SILpy never fetched (robots disallow) and Gaceta Oficial only through archives (gitlaw_common/wayback.py). corpus.json and corpus.d/50-electoral.json untouched (published acts byte-identical); every new act is its own corpus.d part with its own .PUBLISH. Test builds go to the session scratchpad, never the clone. Docs date stays 2026-10-28 (autopush takes the latest `sources[].retrieved`; the new parts carry no `sources`, BACN is already listed).

- [x] **corpus.d/60-datos-crediticios.json + 62-proteccion-datos-personales.json** (one part per act since 06:57Z; first written as one part 60-datos-personales, now removed; datos/datos.py, datos/pages.py, datos/sources.json): Ley 6534/2020 Datos Personales Crediticios (BACN 9417; v1 2020-10-28, v2 2027-11-28 = Ley 7593 art. 59 repeals art. 3 a-b, art. 4, art. 20 b (+ items 1-13), art. 21 x) and Ley 7593/2025 Protección de Datos Personales (BACN 12924; one version 2027-11-28 = 24 months after publication 2025-11-27, CC art. 339; futuro branch). pages.py numbers nested <ol> innermost-first (parse.py asserts on nesting); identical lines on all 118 pages parse.py/electoral read. Amender screen: BACN search "datos personales", "crediticios", "6534", "6.534", "7593": only 7593 changes 6534. Scratch build: 122 commits on main (+1), futuro 2 commits, check 12 acts / 122 versions / 0 mismatches / 0 trailer errors, --compare identical, the 119 published law commits unchanged (scratchpad cmp_pub.py: same messages, dates, files, act trees). PUBLISH files: 60-datos-crediticios.PUBLISH, 62-proteccion-datos-personales.PUBLISH.
- [ ] Código del Trabajo (Ley 213/1993, BACN 2608): SKIPPED. Ley 496/1995 (BACN 2514) art. 3 orders the whole Code renumbered "así como las concordancias y referencias que correspondan" after adding arts. 182 bis / 412 bis and repealing 287 and 325; later laws (1416, 5764, 6470) cite the new numbers and BACN has no renumbered text. Building it would mean inventing the numbering and the rewritten cross-references: not sourceable.
- [ ] Ley 6380/2019 (tax, BACN 9332, enacted text, 155 arts with ISC tables): SKIPPED (> 45 min). Art. 154 leaves the in-force day to an executive decree that is not on BACN and was not found in the Wayback Machine (presidencia.gov.py / set.gov.py prefixes, 0 captures); without it no version can be dated. Amenders found for later: 7067/2023 (art. 100 num. 3 h), 7508/2025 art. 21 (art. 115 num. 6), budget Ley 6873/2022 art. 275 (suspends art. 136 for 2022, no word change); budget laws 6672/7050/7609 only list 6380 among suspended exemptions.
- [x] **corpus.d/61-consumidor.json** (consumidor/consumidor.py, consumidor/sources.json): Ley 1334/1998 Defensa del Consumidor y del Usuario (BACN 897), 6 versions: 1999-04-25 enacted (art. 53: 180 days after promulgation 1998-10-27); 2004-01-13 Ley 2340/2003 (new Cap. XV arts. 53-57; old arts. 53-54 renumbered 58-59 per its art. 3; indice updated); 2013-08-29 Ley 4974/2013 art. 22 (partial repeal of 40-42 "en lo atinente al MIC": note, no word change); 2015-05-06 Ley 5427 (art. 28); 2019-09-21 Ley 6366 (arts. 4, 6, 10, 15, 29); 2020-11-05 Ley 6624 (art. 30). Searches "1334", "1334/98", "1334/1998", "1.334", "defensa del consumidor", "consumidor y del usuario"; all hits screened. Scratch build: check 13 acts / 128 versions / 0 mismatches / 0 trailer errors, --compare identical, 119 published law commits unchanged. **61-consumidor.PUBLISH written.**
- Comparison helper (scratchpad, not shipped): cmp_pub.py <published clone> <scratch build> <new act dirs> <new shorts> checks every published law commit reappears with the same message, dates, files and act trees.
- [x] **corpus.d/63-procedimientos-administrativos.json** (administrativo/administrativo.py): Ley 6715/2021 (BACN 10974), 1 version, in force 2022-09-29 (art. 90: one year after publication 2021-09-29, anniversary as for the CP). **63-...PUBLISH written.**
- [x] **corpus.d/64-acceso-informacion-publica.json** (same module): Ley 5282/2014 (BACN 3013), 1 version, in force 2015-09-18 (art. 32: one year after promulgation 2014-09-18). Searches "6715", "6715/2021", "procedimientos administrativos", "5282", "5282/2014", "5.282", "libre acceso ciudadano": no amender of either. **64-...PUBLISH written.**
- [x] Final scratch verification 06:58Z (all parts; repeated after the README edit: law history identical): build 130 commits on main (129 + docs), futuro +2, 255 tags; check.py 15 acts / 130 versions / 0 mismatches / 0 trailer errors; --compare identical (main_identical true); cmp_pub.py: 119 published law commits unchanged, 9 new-act commits touch only new folders; GITLAW_VERIFIED_PARTS_ONLY=1 build gives the same law history (main~1 7e69de9, futuro c10d000). corpus.json and 50-electoral.json untouched.
- [x] repo/README.md table: added Código Electoral (was missing) and the 5 new acts; "What it does not show" explains the Labour Code and Ley 6380 skips; Spanish section updated. repo/jurisdiction.json `build` updated.
- Mistake to avoid: BACN search output on Windows ends lines with CRLF; `$(cat list)` then passes URLs with a trailing \r and curl fails (exit 3). 101 such local failures (no network request made) were removed from .cache/requests.jsonl at 06:52Z. Strip \r (tr -d '\r') before fetching.
- NOT pushed or committed (cadence rule); the 4-hourly autopush pass will publish main with every part (all have .PUBLISH).

Next candidates (not started): Ley 3966/2010 Orgánica Municipal and Ley 879/1981 Código de Organización Judicial (many amenders each; BACN search + screen as above); Ley 6380/2019 if the vigencia decree can be sourced (Gaceta Oficial via Wayback).
