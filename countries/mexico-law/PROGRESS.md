# gitlaw-MX: Mexico progress (gitlaw-MX-2, updated 2026-10-29 06:05 UTC)

Repo lexifina/mexico-law (PRIVATE, never change), clone `C:/Users/alany/Documents/mexico-law` (owned by autopush; it built a `preview` at 05:02 UTC from an earlier corpus). Slug mexico, tz America/Mexico_City, lang es, future branch `futuro`, on-date tool `repo/tools/en_vigor_el.py`. Rules: scripts/world-law/WAVE.md -> scripts/africa-law/FANOUT.md -> scripts/south-america-law/BRIEF.md (CADENCE CHANGE: no pushes, autopush every 4 h; verify locally).

Remote check before PUBLISH (read-only `git ls-remote`, 05:58 and 06:03 UTC): `main` = ee03ec1a "Mexico: sources, before any law" (the scaffold); `preview` 4948834, `wip` e08777b.

## Checklist

- [x] Probe (2026-10-28; table below)
- [x] Constitution source: 98 distinct archived copies cached (`.cache/caps-constitucion.json`), decree list `ref/cpeum_crono.htm`
- [x] reforms.py: decree 73 bug fixed ("REFORMAS y Adiciones…" title; keyword list now includes "reforma"); 285 decrees + the 1917 original; `name` = the decree's own title (first paragraph of the cell)
- [x] parse.py for the CPEUM -> `corpus.d/10-constitucion.json` (part carries `country`; there is no corpus.json)
- [x] Scratch build + check.py (0 mismatches, 0 trailer errors) + `--compare` (identical) -> `corpus.d/10-constitucion.PUBLISH`
- [x] repo/README.md (English + español), repo/LICENSE, repo/jurisdiction.json, repo/tools/en_vigor_el.py
- [x] LFPDPPP: 7 copies fetched (2011-2025) + ref/lfpdppp.htm; `parse_lfpdppp.py` -> `corpus.d/20-lfpdppp.json`; verified -> `corpus.d/20-lfpdppp.PUBLISH`. One act, 3 versions: 2010 law as enacted (in force 2010-07-06, first_law decreto-dof-2010-07-05), the 2025 law (DOF 20-03-2025, in force 2025-03-21; 72 unit changes credited by the copy's own "Nueva Ley DOF 20-03-2025" cover), reform DOF 14-11-2025 (art. 4 by note + its transitorios; in force 2025-11-15). Last version == 2025-12-12 copy; coverage 0 missing in all 3 copies used. Copy 20250405014229 (same date as 20251115044107) prints paragraphs without blank lines and is not used.
- [ ] Código Penal Federal: 57 captures listed (`pdf/9.pdf`, `pdf/CPF.pdf`), not fetched
- [ ] Código Civil Federal: 21 captures listed, not fetched

## Constitution build (verified)

- 98 copies, 8 truncated at 1 MiB dropped (20190923002305, 20200918083844, 20210125021153, 20210927164804, 20220516151601, 20230608153526, 20230925125132, 20241203191611); newest copy per last-reform date -> 78 states, 2006-04-07 .. 2026-10-07.
- 117 versions (2006-04-08 .. 2026-10-08), 138 commits, 237 tags, 120 laws with commits (reforms 167-285 + Fe de erratas DOF 25-06-2009), 17 unexplained publisher commits, nothing on `futuro`.
- Units: preambulo, estructura (headings), art-001..art-136, transitorios-1917, `transitorios-<DOF date>-<reform no.>` per decree, `fe-de-erratas-<date>[-n]`.
- Credits: 413 unit changes from paragraph notes, 120 decree-transitorios units to their own decree, 0 by title alone, 142 unexplained unit changes (Cámara proofreading 2008/2013/2014, old transitorios added 2020, 3 same-day two-decree ambiguities: art. 73 2011-10-12, art. 43 2021-05-17, art. 41 2026-06-02).
- In force (reforms 167-285): day after publication 116, same day 2, "a los 120 días" 1 (reform 193); default CCF art. 3 only for the 2009 erratum.
- Verification: replayed last version == units of the 2026-10-10 copy; independent plain-text read of that copy contains all 4,100 paragraphs verbatim (99.94% of body chars); all 78 copies: 223,778 paragraphs, 0 missing, min coverage 99.65%.
- Scratch build: `C:/Users/alany/AppData/Local/Temp/claude/C--Users-alany-Documents-lexifina/f78588c6-2cad-4776-8ba7-4e66c11c682c/scratchpad/mx/b1`, main df2824133a79, check 0/0, compare identical. `corpus.d/10-constitucion.json` sha256 bfb051fa7363b381… (parse is deterministic: two runs, same bytes).
- Known limits (in README/decisions): staggered per-provision in-force dates (e.g. 2014 electoral reform) not split; text between copies only as fine as the notes allow; 1917-2006 not rebuilt.

## Probe results (2026-10-28)

| Source | Status | Use |
|---|---|---|
| www.diputados.gob.mx (LeyesBiblio) | TCP connect timeout from this machine | Read only through archive.org `id_` captures (`gitlaw_common/wayback.py`) |
| Common Crawl index | timed out 23:00-00:30 UTC | not used |
| www.dof.gob.mx | connect timeout | not used |
| legislacion.scjn.gob.mx | Buscar.aspx 200; ASP.NET encrypted params | not explored |
| sidof.segob.gob.mx | 200 | not explored |
| lex-mx (prior art) | current text only, daily since 2026 | reconciliation only; never copy |

## Files

- `fetch.py`: `list|texts <act>`, `refs <act>`, `url <url> [ts]`; all via wayback.py into `.cache/`.
- `reforms.py`: decree-row parser for Diputados reform tables.
- `parse.py`: CPEUM parser (`python -X utf8 parse.py`, ~35 s, 8 processes); report in `.tmp/parse-report.json`.
- `parse_lfpdppp.py`: LFPDPPP parser (reuses parse.py); report in `.tmp/parse-lfpdppp-report.json`.
- `.tmp/`: scratch debug scripts (dbg2.py diff tool, resid.py coverage residue) — not shipped.
- `.cache/`: 183 MB, requests logged in requests.jsonl.

## Combined scratch build (both parts, docs-date 2026-10-29)

141 commits, 243 tags, 122 laws, 17 unexplained; check.py 0 mismatches / 0 trailer errors; `--compare` identical (main 784cc011 in scratch b1; c81ff073 after README edits in b3). Remote main still the scaffold ee03ec1a at 06:06 UTC. Nothing pushed or committed.

## Next

1. CPF: `fetch.py texts codigo-penal-federal` (57 captures, not fetched). `parse_lfpdppp.segment_law` is the generic federal-law segmenter; for the codes it needs "Artículo 85 Bis/Ter…" articles (parse.ART only takes plain numbers: extend it and key `art-085-bis`), Libro/Título headings, and the reform list `ref/cpf.htm` (decree crediting by note dates as in parse.py, several decrees per gap).
2. Same for the Código Civil Federal (21 captures).
3. Possible refinement: same-day two-decree changes (CPEUM art. 43 2021, art. 73 2011) could be split by fetching each decree's DOF PDF (`ref/dof/CPEUM_ref_NNN_*.pdf`) and matching its "para quedar como sigue" text.

## Coordinator (2026-10-29)
Added the folder-level PUBLISH (main is pushed only when it exists).
