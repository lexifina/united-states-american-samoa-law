# Peru procedure part (gitlaw-PE-proc): progress

Owner of `corpus.d/60-proc.json`: Nuevo Código Procesal Penal (Decreto Legislativo 957, 2004), act slug
`codigo-procesal-penal`, short `NCPP` ("CPP" is taken by the Constitution). Retrieval day / docs-date 2026-10-28.
Don't edit corpus.json, corpus.d/50-codes.json or anything outside `proc/`. Test only in `proc/.tmp/`.

## Status (2026-10-28 ~20:30Z)

- [x] Source found: MINJUS official editions on gob.pe (text layer). The 8th (Dec 2024, current to 2024-11-17)
      quotes the wording before every amendment ("Texto anterior a la modificación"), nested back to 2004.
- [x] `edition.py` (PyMuPDF: body >= 6.8 pt, calls = small spans on a body line, notes = small lines on their own),
      `history.py` (rewind each provision newest-first; full and partial quotes, "(...)" segments, lead-in/literal paths).
- [x] `parse_proc.py` writes the part atomically; deterministic (two runs, same bytes). 0 problems.
- [x] Checkpoints against the 2018, 2020 and 2022 MINJUS editions: 570/598, 561/597, 583/602 provisions equal word
      for word; the rest are edition typos/capitalisation/"(sic)"/placeholders, art. 425 numbering (editions
      disagree), 473-A not split in the 2020 edition. Printed by `parse_proc.py --report` and in decisions.
- [x] Staged entry into force: 34 district start days (MINJUS map 2021, credited to D.S. 013-2005-JUS calendar,
      no-words commits on disp-final-01); 2006-02-01 numeral-4 commencement; ~90 "vigencia adelantada" notes as
      no-words commits quoting the note.
- [x] Test build (.tmp/country with corpus.json + 50-codes + 60-proc): 125 commits, check 0 mismatches,
      --compare identical. NCPP: 76 versions, 63 laws.
- [x] `corpus.d/60-proc.json` written 20:24Z, rewritten ~20:45Z (preview only; autopush preview 0b8a3b9 at 20:25Z
      included it; main leaves it out). Final test build: 125 commits, 0 mismatches, --compare identical.
- [x] Coordinator request (~20:30Z): `forward.py` replays Leyes 32181 + 32182 (in force 2024-12-12), 32255
      (2025-03-11), 32374 (2025-06-08) from Congreso ADLP `Documentos/2021_2026/ADLP/Texto_Consolidado/N-TXM.pdf`
      (text layer). The El Peruano bulletin folder `Boletin_de_Normas_Legales` exists only for 2016_2021 (404 for
      2024-2025 dates in both folders). Every inserted paragraph is checked word for word in the law's text.
- [x] parse_proc.py now asserts the state after the last 8th-edition version equals the edition text exactly
      (603/603). Part rewritten ~21:05Z: 79 versions, 67 laws, deterministic; test build 129 commits, check 0
      mismatches, --compare identical.
- [x] `corpus.d/60-proc.PUBLISH` written (Paraguay basis, per coordinator), naming what is missing.
- [ ] Not found: laws after Ley 32537 (Congreso index ends 26 Dec 2025) and decretos legislativos after Nov 2024
      (D.Leg. 1735 Feb 2026 and Ley 32735 Jul 2026 named by a web search). busquedas.elperuano.pe search is a
      client-side app (query params `fechaIni`/`fechaFin`/`start`; the text query param was not found); its
      dispositivo pages work if an id is known (`/dispositivo/NL/<id>`). Adding a law = one entry in forward.LAWS.

## Files

- `pfetch.py`: wrapper on `../fetch.py` (shared cache `../.cache`, log, UA, `--compressed`), 1.5 s per host.
  `--plan` fetches `sources.json`.
- `edition.py`, `history.py`, `parse_proc.py` (see above). `--report` prints checkpoints/problems; `--out P` writes elsewhere.
- `.tmp/`: probes and test builds (gitignored).

## Findings worth sharing

- MINJUS (gob.pe) official editions of codes have text layers and "Texto anterior" footnotes: likely the same for
  other MINJUS editions (Código Civil 14th ed. 2014, Constitución editions) — useful for the codes helper.
- Congreso hosts daily El Peruano "Boletín de Normas Legales" PDFs: `leyes.congreso.gob.pe/Documentos/2016_2021/Boletin_de_Normas_Legales/NLYYYYMMDD.pdf`.
- El Peruano dispositivo pages (busquedas.elperuano.pe/dispositivo/NL/<id>) carry "Fecha de publicación".

## WebSearch used: 3 of 5.

Files added for the forward replay: `forward.py` (LAWS table: law, published, in force, splice operations).
