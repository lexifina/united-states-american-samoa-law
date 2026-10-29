# Peru codes part (gitlaw-PE-codes): progress

Owner of `corpus.d/50-codes.json` (+ `50-codes.PUBLISH`): Código Civil (D.Leg. 295) and Ley 29733 (protección de
datos personales). The Constitution (corpus.json) and the NCPP (60-proc) belong to other agents.
Retrieval day / docs-date: 2026-10-28.

## Status (2026-10-28, after the coordinator's "rebuild from the MINJUS edition" request)

- [x] `corpus.d/50-codes.json` written atomically; deterministic (two runs, same bytes). Later versions use `changes`.
- [x] Test build in `.tmp-build-codes` (removed afterwards) with corpus.json + 50-codes + 60-proc: 151 commits,
      check.py 0 mismatches / 0 trailer errors, `--compare` identical.
- [x] `corpus.d/50-codes.PUBLISH` written: all wording from official text-layer sources (basis in that file).

## Acts

| Act | Versions | From |
|---|---|---|
| `codigo-civil` (CC) | 26: 2012-12-25 oldest available, then Leyes 30007, 30084, 30162, 30179, 30230, 30292, 30311, 30313, 30323, 30364, 30403, 30473, 30490, 30550, 31309, 31338, 31643, 31945, 32006, 32228, D.Leg. 1297, 1377, 1384, 1626 (two dates) | 2012-12-25 |
| `proteccion-datos-personales` (LPDP) | 3: 2011-07-04 as enacted; 2013-05-08 commencement (no words); 2017-09-16 D.Leg. 1353 | 2011-07-04 |

## How the Código Civil history is built (codes/cc_history.py)

1. `cc14.py` reads the MINJUS 14th edition (gob.pe, to 1 Aug 2014) with `../proc/edition.py` (font-size split of
   body / footnote calls / footnotes; profile `cc14`: body Cambria 9.5, notes 7 pt; `N.-` numerals added to the label regex).
2. Rewind 1 Aug 2014 -> 25 Dec 2012 with the footnotes' "Texto anterior" quotes (whole article or the numeral with the
   call) and by removing incorporated paragraphs.
3. 2014 -> 2024: per article, wording before = 14th edition, after = Editora Perú NLA (FAOLEX copy, to 15 Aug 2024).
   Laws come from NLA notes + `cc_spec.HIDDEN` (laws whose own text changes an article the NLA credits to a later law).
   For articles changed twice (42, 46, 241, 243, 248, 274, 481, 667, 696) the in-between wording comes from the earlier
   law's text via anchors in `cc_spec.INTERMEDIATE`.
4. Checks (`parse_codes.py --report`): replay on 2024-08-16 == NLA text in every article (0 differ); law-text windows
   found in replayed wording for 54 unit changes, 9 below 90% — all explained (gazette-page junk inside the PDF text,
   the law's own article numbers, CPC articles, an unchanged sentence restated: art. 140 "de la voluntad", a law-given
   sumilla the NLA does not print: art. 265).
5. Why not before 2012-12-25: the edition does not quote repealed text; the last such repeal is Ley 29973 (24 Dec 2012).
   The 1984 text is only an image scan; no OCR.

## Sources (all in `sources.json`, fetched with `cfetch.py --plan`)

- MINJUS CC 14th ed.: `cdn.www.gob.pe/.../5060551-codigo-civil-minjus-bcp_n-3.pdf` (found via the MINJUS "Ediciones Oficiales" collection on gob.pe).
- Editora Perú NLA CC (FAOLEX copy). El Peruano's `obtenerDocumento` now corrupts every byte >= 0x80.
- Amending laws (`amendlaws.py SOURCES`): Congreso bulletins `Documentos/2016_2021/Boletin_de_Normas_Legales/NLYYYYMMDD.pdf`
  (exist only ~late 2016 – mid 2021), gob.pe copies (D.Leg. 1297 on MIMP, Leyes 30403/30490 on Congreso pages; found with
  `https://www.gob.pe/busquedas.json?term=N&contenido[]=normas&tipo_norma[]=14-leyes`), ADLP `Texto_Consolidado` TXM,
  the MINJUS violence compendium (Ley 30364's text of art. 667), busquedas.elperuano.pe (D.Leg. 1626).
- Not found with a text layer: Leyes 30292, 30311, 30313, 30323, 31338 (ADLP copies are scans). Their changes take the NLA wording.
- Ley 29733: ANPD/MINJUS gob.pe copy, MINSA copy, NLA Wayback captures, MINJUS compendium (Nov 2025, today's-text check),
  El Peruano pages for D.S. 003-2013-JUS and D.S. 019-2017-JUS.

## Open / limits

- CC amendments after Ley 32228 (Jan 2025): ADLP index ends at Ley 32537 (Dec 2025); D.Legs and 2026 laws can't be listed.
- Hidden intermediate wording from the five laws without text (if any of them changed an article later changed again).
- 39 articles differ editorially between the two official editions (list in --report); 2024 wording used.
- Book/section/title headings are not tracked for the CC.

## Files

`cfetch.py` (fetch wrapper), `parse_codes.py` (writes the part; `--report`, `--out`), `cc14.py`, `cc_history.py`, `cc_spec.py`,
`amendlaws.py`, `gobpdf.py` / `discover.py` / `nla.py` (discovery/debug only).

## Gotchas

- Never edit Python with backslashes through bash heredocs: `\1` became a control character twice. Use the Edit tool.
- Editora Perú notes are bold italic 8 pt; MINJUS notes are 7 pt; footnote calls 6.6 pt.
- El Peruano bulletin PDFs interleave the sumario with law text across columns: use line anchors, not whole quotes.

## WebSearch used: 8 of 8.
