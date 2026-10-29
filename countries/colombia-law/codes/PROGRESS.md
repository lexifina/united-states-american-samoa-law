# gitlaw-CO-codes progress (Colombia: Código Civil + Ley 1581 de 2012)

Helper on Colombia. Owns only `scripts/colombia-law/corpus.d/50-codes.json` (+ `50-codes.PUBLISH`) and
`scripts/colombia-law/codes/`. The Constitution (corpus.json, parse.py, fetch.py) belongs to the main Colombia agent.
Never build into the clone, never push (autopush does), never kill processes you did not start.

Commands (from scripts/colombia-law):
- `python -X utf8 codes/parse_codes.py [--report]` writes corpus.d/50-codes.json atomically (cache only, no network)
- `python -X utf8 codes/verify_today.py` checks today's text of both acts against the source pages
- `sh codes/test_build.sh` builds the part alone into .tmp-build-codes/ and runs check.py
- `sh codes/compare_build.sh` builds the old full-units layout and the `changes` layout and runs build.py --compare
- `python -X utf8 codes/dbg_unit.py 117 318` prints the rebuilt states of CC articles
- `python -X utf8 codes/fetch_codes.py laws|old|url <u>` (2.1 s spacing, shared cache/log)

## Status (2026-10-28 ~18:30Z)
- [x] corpus.d/50-codes.json: CC 113 versions (23 note-only), Ley 1581 2 versions (1 note-only), 120 laws.
      Since 18:32Z every version after the first is written as `changes` (SCHEMA "Large acts"): 81 MB -> 1.5 MB.
      compare_build.sh: build.py --compare says identical (121 commits, 235 tags, same history tip); the main tips
      differ only in data/corpus.sha256 and REPRODUCE.md's corpus hash, as the corpus bytes differ by design.
      check.py 0 mismatches; verify_today.py unchanged result. 50-codes.PUBLISH kept.
- [x] Test build: 121 commits, 235 tags, 0 unexplained, check 0 mismatches; parse deterministic (only the shared
      request count changes between runs while other agents fetch)
- [x] verify_today.py: all 2,672 "ARTÍCULO N" CC articles and 30 Ley 1581 articles match today's source text, except
      arts. 50, 196, 208, 636 (tacit/organic derogation, words kept by decision)
- [x] corpus.d/50-codes.PUBLISH written (main now includes the part)
- [x] Laws: no key shared with corpus.json, so no label conflict; court labels use "Sentencia C-NNN de YYYY"

## Open / known limits
- 25 reconstruction gaps (placeholder line '[La fuente no da el texto vigente en esta fecha.]'): mostly acts the
  source names without giving the text they left (Ley 92 de 1938 on arts 348-369, Ley 57/153 de 1887 on 1045,
  Ley 67 de 1930 on 483-484) and garbled earlier-text boxes (1658, 2543). `--report` lists them.
- Undated strikes (arts 669, 1119, 1527; 312): struck words left out of every version.
- Old acts without a vigencia clause in any cached page use the default rule (pre-1913: publication; from 1913:
  publication + 2 months). Includes Decreto 2820 de 1974 (-> 1975-04-04), Ley 45 de 1936, Ley 153 de 1887, CST.
- Size solved by `changes` versions (1.5 MB). `--full-units` still writes the old layout, for comparison only.
- titulos.md holds today's headings throughout (source gives no heading history).

## Sources
- basedoc codigo_civil (+83 pages + js), ley_1581_2012: cached by ../fetch.py (reused, not refetched)
- basedoc pages of amending acts (base + last page), codigo_procedimiento_civil, codigo_menor, decreto_0538_2020
- normativa.colpensiones.gov.co/colpens/docs/<act>.htm: Avance Jurídico copy of pre-1992 acts (heading dates and
  vigencia clauses only); found with 1 WebSearch (ICBF's copy returns an empty shell)
- SUIN-Juriscol: Angular micro-frontend, not used
- WebSearch calls used: 1 of 8
