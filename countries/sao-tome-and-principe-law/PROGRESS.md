# São Tomé and Príncipe (gitlaw-ST) progress: HANDOFF (wind-down 2026-10-29 ~00:35 UTC)

## Done
- [x] Repo is a scaffold (ls-remote: only main, 5f4870b "sources, before any law"), checked 2026-10-28. Re-check before PUBLISH.
- [x] Found official texts despite the register's "none": the Assembleia Nacional's old site parlamento.st
  ("Legislação Constitucional" page) linked one zipped PDF (text layer) per constitutional law. Read via
  pinned archive.org id_ captures (Feb 2007), listed in sources.json.
- [x] corpus.json written: act `constituicao`, 6 versions, all full official texts:
  1975-11-05 (Constituição Política, first_law), 1980-02-07 (Lei 1/80), 1982-12-31 (Lei 2/82),
  1987-12-31 (Lei 1/87, arts 47-51 only), 1990-09-20 (Lei 7/90), 2003-02-28 (Lei 1/2003, DR n.º 2 of 29 Jan 2003 +30 days).
- [ ] PUBLISH not written: 2003 text not yet diffed word-by-word against gov.st copy; currentness after 2003 unverified.

## Sources and cache
- sources.json: pinned captures (name, url, ts). fetch.py downloads them into .cache/dl/ (shared wayback client).
- .cache/dl/*.zip (Assembleia PDFs), govst_constistp.pdf (government copy of the 2003 text, same file as parlamento.st/Lei/constistp.zip),
  fao117335.pdf (FAOLEX copy of the Assembleia 2003 PDF; not used).
- .cache/probe1.txt, dre_cdx.txt, parl_cdx.txt: CDX listings of parlamento.st, gov.st (*.gov.st), dre.gov.st.

## Scripts
- `python -X utf8 fetch.py` (resumable), `python -X utf8 parse.py` (writes corpus.json atomically), `python -X utf8 inspect.py` (lists units whose last line lacks punctuation = leaked headings).

## Open issues / next steps (in order)
1. parse.py: 1980 art-037 still ends with leaked subheading "COMISSÃO PERMANENTE DA ASSEMBLEIA POPULAR NACIONAL" (check its indent in .cache/x/L1_80/*.txt and the subheading rule near `indent(...) >= 15`). Check 1990 art-040 / 2003 art-041 last line (no final punctuation; maybe source).
2. Write verify.py: compare 2003 units against govst_constistp.pdf text (word sequence), record result; then re-check ls-remote and write PUBLISH.
3. Lei 1/87 first block (alíneas b,i,r,t,u of an unnumbered article) deliberately not applied; see decisions.
4. Phase 1 core acts: dgrn.gov.st/leis/Lei/ has official Diário da República PDFs archived 2025-05-15: Código do Trabalho (Dr_2019_n_22), Código da Família (Dr_n_2018_153), Código do Notariado (Dr_n_2018_92), Código da Estrada, Código de Custas, Registo Predial/Comercial. Also impostos.financas.gov.st (IRS/IRC/IVA laws) and backstp.gov.st/uploads/Dr_*. Check text layers (no OCR).
5. repo/README.md (English first, then Portuguese) from the scaffold README + SOURCES.md; copy jurisdiction.json with build set.
