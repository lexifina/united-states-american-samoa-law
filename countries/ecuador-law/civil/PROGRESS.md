UPDATED 2026-10-28T19:30Z

# Ecuador Código Civil (gitlaw-EC-civil): progress

Owner of `corpus.d/50-civil.json` only. Scripts here in `civil/`; tests in `civil/.tmp/` (gitignored).

## Status

- [x] Base: Codificación 2005-010, RO Supl. 46, 24-VI-2005 (`base.py`): 2,424 articles + disp. transitoria + disp. final + `titulos`.
- [x] Amendment index: Lexis 2017 (WIPO) + Ediciones Legales 2025 (gob.ec), both read only.
- [x] Replay (`replay.py`): 22 versions; 13 acts applied from RO text layers (errata 2005 x2, 0001-11-SIN-CC, 2012 x4, COMF 2014, Ley Reformatoria 2015, COGEP (in force 2016-05-22), COAm (2018-04-12), 56-09-IN/22); 9 recorded NOT APPLIED (7 image-only 2019-2024, 2 with unreachable suplemento PDFs 2006/2010).
- [x] `parse_civil.py` writes the part atomically; deterministic (two runs byte-identical).
- [x] Test build with corpus.json + part in `.tmp/build`: check.py 0 mismatches, 0 trailer errors; `--compare` identical.
- [x] `reconcile_civil.py`: vs Ediciones 2025, 66 of 2,428 articles disagree, all classified in decisions.
- [x] `corpus.d/50-civil.PUBLISH` written (every version's wording from a gazette text layer; gaps marked).
- [x] autopush 19:30Z: main 18fbab6 (CRE + CC, 2 acts, 32 versions, 34 commits), check 0 mismatches.
- [ ] README: `README_civil.md` holds the section for repo/README.md (owned by the Constitution agent); fold it in.

## Commands

    python -X utf8 civil/fetch_civil.py        # 25 URLs from civil/sources_civil.json
    python -X utf8 civil/parse_civil.py        # writes corpus.d/50-civil.json (CIVIL_OUT=... to test elsewhere)
    python -X utf8 civil/reconcile_civil.py    # writes civil/reconcile_civil.json

## Findings

- Since about 2020 the Registro Oficial prints laws passed by the Asamblea as scanned signed pages (text layer = running heads only). Court rulings in Ediciones Constitucionales vary (EC 15/2022 has text, EC 96/2019 is images).
- RO portal: the "Primer Suplemento" links for 274 (2006-05-19) and 285 (2010-09-23) serve the ordinary edition.
- General renaming clauses (COGEP DR 1ª etc.) not applied; Ediciones applies COGEP's "Código de Procedimiento Civil" one, Lexis does not.
- No reform after 17-VI-2025 found (1 web search; RO site search pagination unreliable). WebSearch used: 2.
