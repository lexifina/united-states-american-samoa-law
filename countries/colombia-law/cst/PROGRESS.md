# gitlaw-CO-cst progress (Colombia: Código Sustantivo del Trabajo)

Owner of `scripts/colombia-law/corpus.d/70-cst.json` (+ `70-cst.PUBLISH`) and `scripts/colombia-law/cst/` only.
Never build into the clone, never push (autopush does), never kill processes you did not start.
Started from the main agent's phase2 work (phase2/engine.py + build_cst() in phase2/parse_phase2.py), which ended
with 16 articles differing from today's text.

Commands (from scripts/colombia-law):
- `python -X utf8 cst/parse_cst.py [--report] [--out FILE]` writes corpus.d/70-cst.json atomically (cache only)
- `python -X utf8 cst/verify_cst.py [part.json] [-v]` last version vs today's text on the source page, line for line
- `sh cst/test_build.sh [--compare]` builds the part alone into cst/.tmp/build, runs check.py (and the determinism rebuild)
- `python -X utf8 cst/fetch_cst.py laws` fetches basedoc / Colpensiones pages of acts the notes name that have no day
- `python -X utf8 cst/dbg_unit.py 260 267` / `cst/dbg_grep.py <regex>` debug views of the page

## Files
- `cst/engine.py`: copy of phase2/engine.py with CST fixes (marked `cst:`): DO dates without "de"; "un (1) año
  después" vigencia; `label_num` for 391-1 / 185-A; ART_HEAD for "-1"/"-A"; whole-article derogation = absent even when a
  later act re-adds it; a quoted title's act does not take the Diario Oficial that follows it.
- `cst/parse_cst.py`: driver. Heading repairs (anchors "A"/"ART", "ARTICULO. X" + "<163A>"), text slips (Decreo,
  Decreto - Ley), KEY_FIXES dec-2351-1995 -> 1965, HAND_RULES (Dec 59/1957, Ley 3/1969, Ley 171/1961), Ley 171 notes
  set aside, Ley 100 "texto original es el siguiente" articles, art. 200 revival (C-1155-08), {empleador} (Ley 50/1990).

## Status (2026-10-28 ~20:00Z)
- [x] corpus.d/70-cst.json: 103 versions, 110 laws, 890 KB (`changes` deltas). Deterministic (two runs byte-identical).
- [x] verify_cst: 0 differences over 499 articles, no extras, no exceptions.
- [x] audit_orig.py (first version vs the source's own full 'Texto original' boxes): 201 boxes, 3 differ, all explained
  (art. 102: the box is Decreto 2663's text, before Decreto 3743 which the 1951 edition includes; arts. 323, 409: whole
  articles struck with no dated ruling, left out by decision).
- [x] test build: 108 commits, 210 tags, 0 unexplained, check 0 mismatches, --compare main_identical.
- [x] corpus.d/70-cst.PUBLISH written.
- Known limits (in decisions): Decreto 1393 de 1970 has no day in any source (art. 162 lit. d reads repealed in every
  version); 11 placeholder gaps (`--report`); undated strikes (247; whole 323, 409) left out; epigraphs from today's text
  where earlier-text boxes omit them.
- For the main agent: phase2/engine.py dates Ley 2452 de 2025 at publication (2025-04-02) but its art. 330 says "un (1)
  año después de su publicación" -> 2026-04-02 (cst/engine.py rule_from_clause has the fix). Also phase2's scan_law_dates
  can take a regulating decree's Diario Oficial for an act named inside its quoted title (fixed in cst/engine.py).
- WebSearch used: 3 of 6 (all for Decreto 1393 de 1970; nothing official found).
