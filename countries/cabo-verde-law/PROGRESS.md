# Cabo Verde (gitlaw-CV): progress and handoff

Owner: gitlaw-CV. Spec: CV row in scripts/africa-law/QUEUE.md (pt, futuro, vigente_em). Wound down 2026-10-29 ~00:40 UTC.

## Status (2026-10-29, gitlaw-finisher)
- corpus.json: written by parse.py; Constitution only (3 versions: 1999-11-23, 2000-02-14, 2010-05-03). **Preview only,
  NO PUBLISH**: the 2010 text does not fully verify against the current official text (below).
- **Column bug FIXED.** `parse.pdf_text` now reads the BO PDFs with PyMuPDF column by column (columns=True; the AN
  edition keeps pdftotext, columns=False). Bands are cut by blocks wider than 60% of the page or centred across the
  gutter; each band is read left then right; on a band ending at such a block, left blocks lying wholly below the
  right column go after it (the hymn page). Inside a block: lines on one baseline are merged (PyMuPDF splits
  justified lines at wide gaps), then joined by geometry (label-only line + text; justified line reaching the right
  edge + not indented, or within a hanging indent after an item's first line; multi-line capital headings), never
  before an item/article/epígrafe after a clause end. Repeated hyphen ("cabo-"/"-verdiano") and hyphen + capital
  ("Procurador-"/"Geral") are one hyphenated word; ligature + space ("qualiﬁ car", "conﬁ -") closed.
  parse.py is deterministic (two runs, same sha256). Decisions text updated.
- Effect vs the old pdftotext corpus (unit by unit): 2010 arts. 78º-80º now in the right order; compound hyphens
  that pdftotext silently dropped are restored as printed (cabo-verdiano, mantém-se, Procurador-Geral,
  Primeiro-Ministro, Vice-Chefe, decretos-legislativos, bem-estar, ...; "Primeiro-Vice-Presidente" is how both the BO
  and the AN edition print it); the hymn (anexo) is one verse per line, and 2010 adds the score title "Cântico da
  Liberdade". Nothing else changed.
- `verify.py --an` (2010 vs the AN 4th edition): 50 -> 47 articles differing; arts. 78-80 now match. Of the 47, 41 are
  AN-side artefacts (its own word splits "asse gurem"; heading second lines attached to the article before;
  "Primeiro Ministro" / "decretos-lei" spelling; its typo "21." in art. 208; the signature in art. 295). **6 are real
  wording differences**: arts. 88, 91, 168 (alínea lettering), 181 (AN "o Provedor de Justiça"), 203 (AN "do
  Vice-Chefe ... das Forças Armadas"; BO "o Vice-Chefe ... das Força / e) Armadas"), 226 (BO n. 5 ends "próprios,
  designadamente:", AN "próprios."). These are presumably the rectification in BO I Série nº 28, 26 Jul 2010, which
  the AN edition says it includes; its text is still not found.
- **1999 checked for the same problem: none.** Its two independent readings (old pdftotext, new column-aware PyMuPDF)
  agree word for word except restored hyphens, so no column interleaving. New `verify.py` sequence check (numbers and
  alíneas in order inside each article): 1999 breaks only at art. 65 (the "a) ... a)" printing error the 2000
  rectification corrects; clean in the 2000 version) and art. 81 (printed "2 A paternidade" without full stop). 2010
  breaks only at art. 91 (one of the 6 above).
- Local build (empty scratch repo, docs-date 2026-10-28): 3 commits, 5 tags; check.py 0 mismatches, 0 trailer errors;
  --compare identical. Remote main still the scaffold (47e484c).
- **To PUBLISH:** find the BO I Série nº 28/2010 rectification text and add a 2010-07-26 version crediting it (or,
  per the earlier handoff option, commit the 6 differences from the AN edition as an unexplained publisher change
  dated 2010-07-26 naming the rectification in the note — a judgment call for the user); then re-run verify.py --an
  (expect only AN-side artefacts) and PUBLISH.
- Dependency: PyMuPDF (fitz) 1.26.6 is now needed by parse.py.

## Sources (all cached in .cache/, logged in .cache/requests.jsonl)
- Tribunal Constitucional, Leis Constitucionais (https://www.tribunalconstitucional.cv/index.php/leis-constitucionais/):
  11 PDFs via WP File Download (`admin-ajax.php?...wpfd_category_id=199&wpfd_file_id=N`). 1992 (3368) and 1995 (3371)
  are image scans with no text layer (left out, no OCR). Text layers: 1999 republication (3370), rectification of
  14 Feb 2000 (3367), 2010 republication (3369).
- Assembleia Nacional 4th edition of the Constitution (2010), hosted by CNPD (GDLeisRepublica.pdf): states the 2010
  text was **rectified by BO I Série nº 28, 26 Jul 2010**. That rectification text is NOT yet found. Diffs vs. the BO
  (likely rectification): art. 88/91/168 alínea lettering, art. 181 ("o Provedor de Justiça"), art. 203
  ("do Vice-Chefe ... das Forças Armadas"), art. 208, art. 226. Without the BO 28/2010 text these can't be credited:
  either find it (BOE id unknown; Wayback has only 307 of boe.incv.cv/Bulletins/Download/*) or commit them as
  "unexplained" publisher changes dated 2010-07-26 from the AN edition, naming the rectification in the note.
- Data protection (CNPD, https://www.cnpd.cv/legislacao/): Lei 41/VIII/2013 with full republication of Lei
  133/V/2001 (in force 30 days after 17 Sep 2013), Lei 121/IX/2021 with republication (30 days after 17 Mar 2021).
  Both text layers, cached. Not parsed yet. The 2001 original is only in an English translation (not used).
- Penal Code: MoJ official 2004 edition of DL 4/2003 (in force 1 Jul 2004, art. 10) on UNODC SHERLOC, text layer,
  cached. Later amendments (DL 4/2015, BO I/69 11 Nov 2015 = boe.incv.cv/Bulletins/Download/2096, and later) not
  archived in Wayback; Common Crawl index returned nothing (cc_crawls empty at the time). Penal Code can go to a
  corpus.d part without .PUBLISH until a current text is found.
- boe.incv.cv terms ("É proibida a cópia ... sem a prévia autorização da INCV"): fetched only the home, terms, FAQ and
  one listing page while probing; from now on only via archive.org / Common Crawl.

## Checklist
- [x] Probe sources, fetch.py (curl cache, archive.org via gitlaw_common/wayback.py)
- [x] parse.py: Constitution 1999 + 2000 rectification (3 fixes, asserted against the rectification text) + 2010
- [x] verify.py: punctuation check, word-level cross-check with the AN 2010 edition
- [x] Fix column reading order (above) — done 2026-10-29; verify.py sequence check added
- [ ] the 2010-07-26 rectification version (blocks PUBLISH)
- [ ] Data protection act (two republications) in parse.py
- [ ] repo/README.md (English then Portuguese), repo/LICENSE, repo/jurisdiction.json (from the scaffold), tools/vigente_em.py
- [ ] Test build in .tmp-build, check.py, then PUBLISH
- [ ] Penal Code (corpus.d part, preview)

## Known source quirks (keep as printed, list in decisions)
- 1999: "PARTE VI" printed twice; art. 220º n. 4 text layer puts "compulsivamente" at the paragraph end; several
  paragraphs without final full stop (arts. 39, 77, 169, 254).
- 1999: art. 81º "2 A paternidade" printed without the full stop after the number.
- 2010: art. 203º "o Vice-Chefe de Estado Maior das Força / e) Armadas" split as printed; hymn line "do tamanho do ma".
