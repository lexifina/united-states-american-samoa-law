CHECKPOINTED 2026-10-29T01:55Z

## 2026-10-29 session (gitlaw-PE-2): Código Penal (D.Leg. 635) -> part `corpus.d/80-penal.json` (scripts in `penal/`) - HANDOFF, NO .PUBLISH

**Handoff (end of session).** `corpus.d/80-penal.json` = act `codigo-penal`: 2016 MINJUS base (31 May 2016) + 93 amending
norms replayed from their own texts (94 versions, 2016-05-31 .. 2026-07-03; last: Ley 32684). Deterministic (two runs
same sha256). Scratch build of all parts (scratchpad/pe2/b1): 254 commits, check.py 0 mismatches / 0 trailer errors,
--compare identical (tip c5d8a05). Checkpoints vs Editora Peru NLA: 30 / 34 / 41 / 41 differences, all explained in
`penal/laws.json` `explained` (printed as decisions). **Not publishable because:**
1. **Ley 31806** (art. 243-C; in force 120 days after the DS approving its reglamento) and **Ley 32329** (arts. 271-A,
   272-A; in force the day after its reglamento) are `pending`: the reglamento decrees were not found on El Peruano's
   search site (its decreto supremo index is incomplete: ~1,280 DS for 2025-26). Editora Peru prints both as in force, so
   today's text likely differs from the official consolidation until their days are sourced. Find the DS (El Peruano
   issue PDF, gob.pe MINCETUR / MININTER pages), set `in_force` + `vigencia`, drop `pending` and the 3 `explained` entries.
   **Ley 32195** stays pending (NLA itself says not in force as of 2 Jul 2026); confirm no reglamento to today.
2. Unread laws with no text found: 32545-32557, 32559 (late Dec 2025 / Jan 2026), 32732, 32740-32742 (Jul-Oct 2026) —
   `penal/.tmp/gaps2026.txt` (day-listing search; other gap numbers were Resoluciones Legislativas; 26-31 Dec 2025 and
   17-20 Jul 2026 show none of them; the 1 Aug - 30 Sep 2026 search produced no line, so redo it). Laws after
   2 Jul 2026 cannot be checked against a clean consolidation (NLA captures from Sept 2026 are corrupted).
3. D.Legs 1272, 1510-1512, 1660, 1681-1687, 1689-1693 not in El Peruano's index (1688 was found on gob.pe); none is named
   in NLA notes to the Code.
When publishing: add a README "What is in it" row + method/limits paragraphs and the jurisdiction.json `build` entry,
then write `corpus.d/80-penal.PUBLISH`.

- Base: MINJUS 12th official ed. (current to 31 May 2016), SPIJ Wayback 20170517041248 (cached). `penal/base.py` reads the body
  by font (Calibri 9 body, ClarendonBT/Calibri-Bold headings, notes 7 pt dropped): 582 units (tp-01..10, arts, dft-01..05;
  arts 262-269 printed as "Artículos 262° al 264°.- DEROGADOS" etc. are left out).
- Law texts: El Peruano's own PDF extracts. `busquedas.elperuano.pe/?fechaIni=D&fechaFin=D&tipoPublicacion=NL&ci=ONLY&start=N`
  (+`&tipoDispositivo=LEY|DECRETO LEGISLATIVO|FE DE ERRATA`) lists norms with `/api/archivo/file/<tok>/*/<op>.pdf` (text layer,
  intact accents; the HTML itself is partly U+FFFD-corrupted, only used to find the PDF). `penal/elperuano.py scan` read EVERY
  ley and D.Leg from 2016-06-01 to 2026-10-28 and kept those naming the Código Penal (`penal/.tmp/scan.jsonl`, discovery only).
- `penal/lawtext.py` cuts one norm (from the previous op number to its own) into paragraphs (2 columns, indent = new paragraph).
- `penal/nla.py` + `penal/compare.py`: word-level checks against Editora Peru NLA idNorma=2 captures 20230526 (file
  2023-01-31), 20241003 (2024-09-13), 20260204 ("actualizada 20/01/2026") and **20260816 ("actualizada 2/07/2026", clean,
  the latest official consolidation)**. Base vs 2026: 160 changed, 56 new, 9 gone articles.
- Pipeline: `elperuano.py scan` -> `.tmp/scan.jsonl`; `report.py` (cuts each norm, lists CP quotes/repeals) -> `.tmp/report.json`;
  `mklaws.py` appends new norms to `penal/laws.json` (hand fields kept: `ops` hand operations, `in_force`, `skip`);
  `parse_penal.py` replays (env `PE_DRY=1` no write, `PE_UNTIL=YYYY-MM-DD`, `PE_DIFF=1` print checkpoint diffs).
- El Peruano search gotchas: paging a long range drops/repeats cards (index holds duplicates) -> `items_split` halves
  ranges to single days; many D.Legs (1513, 1514, 1578, 1615-1621...) are in the **Edición Extraordinaria**
  (`tipoPublicacion=EX`, cards `/dispositivo/EX/<op>`) -> `items_both` lists NL + EX; TLS handshakes fail in bursts ->
  `get_retry`. Law PDFs: the first norm of an issue starts after the summary (StagSans furniture dropped).
- Fallback discovery for laws missing from the El Peruano index: Congress list (`penal/discover.py ley A-B` ->
  `.tmp/congreso_leyes.txt`) + `penal/adlp.py scan N...` (ADLP N-TXM transcription, text layer).
- Hand data in `penal/laws.json` per law: `in_force` + `vigencia` (reason), `pending` (not applied), `ops` (replace the
  automatic operations), `extra_ops` (after them), `partial_ok`, `every_quote`, `hand`/`source_note` (become decisions).
  Ops: `quote key i`, `repeal key`, `move old new` (Ley 31146 renumbering), `compose key i [[q,i]|[c,prefix]...]`,
  `drop_nth key n`, `drop_par key prefix [occurrence]`. `explained` = checkpoint differences with reasons.
- Status details: see Handoff above. Errata checked (`penal/erratas.py`, `.tmp/erratas.jsonl`): only D.Leg 1351's
  (art. 320) changes the Code. Hand operations per law are in `penal/laws.json` (`ops`, `extra_ops`, `hand`).
- Also scanned: Decretos de Urgencia of the 2019-10..2020-03 interregnum (DU 019-2019, 044-2019, 019-2020 changed the Code).
- Known so far: Ley 31146 renumbers 17 arts (hand `move` ops); Ley 32195 parts wait for its reglamento; Ley 31673 has a
  Fe de Erratas (2023-01-28); the 2016 edition's text layer reads "gramoslitro" in arts 111/124 (kept, explained).

## 2026-10-29 session (gitlaw-PE, "more core acts"): Código de Protección y Defensa del Consumidor added

- [x] New part `corpus.d/70-consumidor.json` (owner: this agent; scripts in `more/`), act `codigo-consumidor` (CPDC), 20 versions,
      20 laws: as enacted (in force 2010-10-02) -> Ley 32495 (2025-11-12). `corpus.d/70-consumidor.PUBLISH` written 01:50Z.
- [x] Backward: MINJUS 3rd official ed. (gob.pe, to 2020-11-27) "Texto anterior" notes via `more/edition.py` + `more/history.py`
      (copies of proc/ adapted: profile `cpdc`, labels "14.1.", Clarendon headings, unbolded "Texto anterior"). Hand undo:
      art. 77 (Ley 30534 text), art. 106 (2nd ed. text before D.Leg. 1390). Ed3 typos mended from ed2: art. 121, art. 42.1.
- [x] Checkpoints: ed3 point exact (182); MINJUS 2nd ed. (SPIJ Wayback 20191101065438, to 2018-05-31) 178/178 word-equal;
      Editora Peru NLA idNorma=17 (Wayback 20240819051628) 169/171 (art. 88 NLA stale on 31763; tp-05 spelling).
- [x] Forward (`more/cpdc_forward.py`): Leyes 31207, 31435 (+60 cal. days), 31467, 31537, 31601, 31763 (60 business days,
      counted -> 2023-08-29, documented), 31937, 32032, 32230, 32323, 32327, 32495 from ADLP TXM; every paragraph word-checked.
      Laws found via NLA notes, Indecopi's SPIJ export (gob.pe, Apr 2025) and Congreso index (title search; numbers 32231-32550).
- [x] Deterministic (two runs same bytes). Scratch build (all parts) 171 commits, check 0 mismatches / 0 trailer errors,
      --compare identical (history tip 0ac7e69). Verified-only build also clean.
- [x] repo/README.md: table rows for all 5 acts, CPDC checks/limits, MINJUS + Editora Peru source rows, ES line; jurisdiction.json build.
- [x] `more/sources.json` + `more/mfetch.py --plan` (23 URLs, all cached).
- Skipped (>45 min to source, per rule): **Código Penal** (MINJUS 12th ed. May 2016 on SPIJ Wayback has Texto anterior notes,
  NLA idNorma=2 to 2026-01-20 is clean, but ~83 amending laws since 2016 would each need their own text);
  **Ley General de Sociedades** (only one clean NLA capture, idNorma=15 2023-06; no edition quoting earlier text);
  **Código Procesal Civil** (no MINJUS edition on gob.pe; no identified clean NLA capture). Common Crawl index unreachable (tried once).
- NLA idNorma map (clean captures are before 2026-09; later ones are U+FFFD-corrupted): 1 Constitución, 2 Código Penal,
  3 Reglamento del Congreso, 4 Ley Org. Políticas, 5 LOE, 6 LOPE, 7 Código Procesal Constitucional, 8 Código Niños y
  Adolescentes, 12 TUO LPAG, 15 LGS, 17 CPDC, 20 TUO Transparencia, 21 Firmas digitales, 23 LPDP, 24 LO Contraloría,
  25 TUO Contrataciones, 28 LO Municipalidades, 33 LO Gobiernos Regionales, 73 D.Leg. 1350 Migraciones.

# Peru law (gitlaw-PE): progress

Slug `peru`, repo `lexifina/peru-law` (PRIVATE, never change). Clone `C:/Users/alany/Documents/peru-law` is OWNED BY autopush (don't build/push into it). tz America/Lima, lang es, future branch `futuro`. `--docs-date` 2026-10-28.
Brief: `scripts/south-america-law/BRIEF.md` (read "Changed after the restart"). Schema `scripts/gitlaw_common/SCHEMA.md`.
**Scope:** the 1993 Constitution (corpus.json) and, since 2026-10-29, the consumer code part `corpus.d/70-consumidor.json` (`more/`). Código Civil and Ley 29733 belong to gitlaw-PE-codes (`codes/`, `50-codes`), the NCPP to gitlaw-PE-proc (`proc/`, `60-proc`); don't edit their parts. Law keys `ley-<n>`, `dleg-<n>`. Never kill processes you did not start.

## Checklist

- [x] Probe sources (table below)
- [x] fetch.py (curl `--compressed` since 17:35Z, sha256(URL) cache, 1 req/s/host, requests.jsonl)
- [x] sources.json: Congreso editions (fetched 2015, 2019-02, 2019-04, 2021-05; FAILED Wayback 2005, 2006, 2018, 2022; 2020-12 capture truncated at 1 MiB)
- [x] editions.py (PyMuPDF; font/position separate body from notes) + parse.py -> corpus.json (33 versions, 39 laws)
- [x] Test build in `.tmp-build`: 40 commits, 72 tags, check.py 0 mismatches; `--compare` (.tmp-build2) identical, history tip 66912d6 (18:28Z)
- [x] verify_laws.py: 169 paragraphs of Leyes 31118..32189 (incl. all 137 of Ley 31988) found word for word in the laws' ADLP texts (1 OCR miss in Ley 26470's text layer: "Háheas")
- [x] 1993 text spot-checked on El Peruano scan (p.13 arts 192-199, p.15 DFT Segunda)
- [x] Quoted texts: full stop after the closing quote (Spanish style) is restored to the provision
- [x] repo/README.md (EN + ES), repo/LICENSE (DL 822 art. 9), repo/jurisdiction.json (build set), repo/tools/vigente_el.py
- [x] PUBLISH created 18:28Z -> autopush now pushes main + tags
- [x] autopush pushed main 6f4ec61 (BUILD_STATUS 18:29Z)
- [x] Coordinator fix (18:40Z): Ley 31988's in-force day now sourced from the official convocation, Decreto Supremo 039-2025-PCM, art. 1 (El Peruano 26 Mar 2025), cached from https://busquedas.elperuano.pe/dispositivo/NL/2384222-1 (no WebSearch needed). URL in the 2026-04-12 version note, decisions, sources and README; no news sites cited. Test build: 0 mismatches (corpus.d/50-codes.json from the helper merges in: 46 commits).
- [x] jurisdiction.json `build` and README table rows for all published parts (done 2026-10-29)
- [ ] **NEXT (optional):** estructura unit (títulos/capítulos headings, changed by 27680, 32189, maybe 31988) — not tracked yet
- [x] README "What is in it" rows for codes/proc/consumidor (2026-10-29)

## How the history is built (parse.py)

- Base: Congreso editions May 2021 (Wayback 20210707230309) and Dec 2024 (live). Same typesetting. 2021 has footnotes 1-42 with "Antes de la reforma ... texto"; 2024 has inline (*) notes quoting Ley 31988's future text.
- Backward: NOTES21 table (note id -> unit, law, scope). Gaps filled from the 2012 consolidation (GAPS): original Ch. XIV (arts 188-199), arts 191/194 pre-28607, art 91 num 3 pre-28484, art 203 num 6 pre-30305, art 40 pre-31122.
- Forward: 31280/31304/31305 from ADLP law PDFs; TC STC 918/2021 (pub 2021-11-26, effect 11-27) restores; 31414, 31507, 31878 (also art 2.4), 32135, 32145, 32188, 32189 from 2024 body; 31988 from 2024 notes, in force 2026-04-12 (election day, DS 039-2025-PCM).
- 27600 and 32265 (Fujimori signature) = no-words commits credited to preambulo.
- dft-02: last sentence "No son acumulables..." is NOT in El Peruano 30 Dec 1993 p.15 (verified on the scan), nor in the 2004-2019 editions/ADLP; appears in the 2021/2024 editions -> uncredited (unexplained) change dated 2021-05-01.
- art-039: 2024 edition applies the Ley 30904 renaming (JNJ) -> credited to ley-30904 at 2019-01-11.
- art-091: 2024 edition duplicates numeral 3 (publisher error) -> keep 2021 text.

## Checkpoints (word-level; parse.py prints them; `PE_DIFF=1` shows diffs)

- e04 (2004 capture, content as of 1995-2000): art-077 (corresponde/n), 158 (edition typo), 197 (socio económicos), declaracion (heading line): edition variants
- e12/e15: art-090 (las listas/la lista; del/de derecho), 096 (a/al Congreso), 187 (heading leak), 191 (vice-presidente); ADLP 2013 text agrees with ours on 090/096
- e19a/b: 039 (renaming), 090, 148 (contencioso administrativa)
- e21: 039 only; e24: 091 only (edition error)

## Sources (probed 2026-10-28)

| Source | Status | Notes |
|---|---|---|
| SPIJ | TCP timeout; Wayback = Angular shell | EXCLUDED (also paid) |
| leyes.congreso.gob.pe (ADLP) | 200 | `Documentos/Leyes/N.pdf` (old ones are scans), `Documentos/2016_2021/ADLP/Texto_Consolidado/N-TXM.pdf`, `2021_2026/...`. Search: discover_congreso.py (title, or `N-M` number range) |
| Congreso editions | see sources.json | 2021 & 2024 are the base |
| www3.congreso.gob.pe/diariodebates/leyesrefconstit/ | 200 | official list of reform laws; latest Ley 32265 (2025-03-22) |
| El Peruano 30 Dec 1993 scan (ADLP CONST_1993_PUBL_PERUANO.pdf, 16 pages) | 200, image only | render pages with PyMuPDF to .tmp/scan and read them for spot checks |
| tc.gob.pe STC 918/2021 | 200 | publication 26 Nov 2021 per Comisión de Constitución Opinión Consultiva 5 |

WebSearch used: 3 of 12 (dates come only from official sources: El Peruano, Congreso, TC).

## Gotchas

- The Bash tool's heredocs eat backslashes (`\\b` -> backspace, `\\t` -> tab). Edit Python with Edit/Write only.
- pdftotext default encoding is latin-1: use `-enc UTF-8`.
- ADLP search pager needs the cookie jar.

## Cache

`.cache/` (gitignored; shared with gitlaw-PE-codes). Log `.cache/requests.jsonl`.

## Pushed (by autopush)

- main: 6f4ec61 (pushed by autopush 18:29Z; history tip 66912d6 = my --compare tip), 72 tags, check 0 mismatches. preview: aee7e5a (stale). wip: autopush.
