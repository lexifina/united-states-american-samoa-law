# Mozambique (gitlaw-MZ, then gitlaw-BW-MZ): progress and handoff

Repo: lexifina/mozambique-law (private; remote main was still the scaffold `26162c5` on 2026-10-29). tz Africa/Maputo,
lang pt, future branch `futuro`. Clone (autopush owns it): C:/Users/alany/Documents/mozambique-law.
Mozambique has no Laws.Africa LII; only peachjam's `Cache` class is reused (read-only import in fetch.py).

## State (2026-10-29, gitlaw-BW-MZ)
- **Built and verified locally; NO PUBLISH** (preview only): today's text is not confirmed (2023 revision of art. 311(3) missing).
- corpus.json (country, sources, shared decisions) + `corpus.d/10-constituicao.json` (no `.PUBLISH`).
- Local verification, docs-date 2026-10-28 (every source retrieved 2026-10-28): 2 commits + docs, 4 tags; check.py 0 mismatches, 0 trailer errors; `--compare` rebuild identical.
- Nothing pushed or committed by this agent.

## Checklist
- [x] Probe sources (2026-10-28), see table
- [x] fetch.py; `sources.json` lists every URL (`fetch.py --all`)
- [x] parse.py -> corpus: Constituição, 2 versions
  - 2005-01-21: 2004 text (parlamento.mz PDF, 306 articles + preamble), first_law `crm-2004` (approved 2004-11-16)
  - 2018-06-12: Lei 1/2018 text (Legislação Básica PDF pp. 14-156, 313 articles + preamble); 186 units credited to `lei-2018-1`
- [x] Extraction checked: `parse.py --report` lines up the texts by heading: 128 unchanged in place, 109 same words under a new number, 70 differ; all 68 body diffs reviewed (scratch diff script in the session scratchpad), real wording changes or republication orthography (juízes, decretos-lei, "número" for "n.º"), no extraction artefacts left (no stray footers, inline list items or broken paragraphs).
- [x] repo/README.md (EN + PT summary), LICENSE, jurisdiction.json
- [ ] PUBLISH: blocked, see below
- [ ] Código Penal (Lei 24/2019): NOT built, see below
- [ ] Lei de Transacções Electrónicas (Lei 3/2017): not fetched

## Decisions (in corpus decisions too)
- Lei 26/2007 (alters 2004 art. 304, provincial assemblies deadline): only a scan -> LEFT OUT and listed missing (no "text not available" version). The 2018 text has no counterpart of that article (2018 art. 304 = "Alterações constitucionais"), so the 2018 commit is right for what it produces.
- 2023 revision of art. 311(3) (approved 3 Aug 2023, promulgated 4 Aug 2023 per CIP; CIP quotes the new wording, but no law number, BR issue or official text-layer copy) -> missing -> **no PUBLISH**.
- Headings (TÍTULO/CAPÍTULO/SECÇÃO) and the closing approval/signature formula are not units (the 2022 compilation prints "Promulgado, a 16 de Novembro de 2014" (sic)).
- Normalisation: hyphen between word chars closed up ("Procurador - Geral" -> "Procurador-Geral"), en/em dashes -> en dash, curly quotes -> straight; a line ending "-" joins without a space.

## Código Penal: why not built
- Source: official BR I Série n.º 248 (24 Dec 2019), born-digital, cached (reformar.co.mz). Two-column InDesign; paragraphs are recoverable (first-line indent / short last line), so parsing is feasible.
- The in-force day has no direct source: art. 8 says 180 days after publication; Lei 7/2020 (18 Jun 2020) extended the vacatio by 180 days "a partir da data em que a respectiva lei entraria em vigor", known only from CIP's (NGO) compilation note (Lei 7/2020 itself unreachable: opj.ces.uc.pt resets). Counting gives 2020-12-18 or a day either side depending on convention. Lei 17/2020 (BR 246, 23 Dec 2020, 2.º supl.) also amended it, content unknown.
- Next step if wanted: find Lei 7/2020 and Lei 17/2020 with a text layer (BR 116/2020, BR 246/2020); then build v1 from the sourced day (preview only until Lei 17/2020 is applied).

## Sources (all probed 2026-10-28)
| Source | Status | Use |
|---|---|---|
| parlamento.mz | 200; WP media list via `index.php?rest_route=/wp/v2/media&search=<q>` | **used**: 2004 CRM PDF; Legislação Básica (2022) |
| cconstitucional.org.mz | 200 | Historial (in force 21 Jan 2005) used; CRM 1990/2004/2018 and Lei 26/2007 PDFs are scans (not used) |
| WIPO Lex 21389 | cached | Lei 1/2018 published and in force 12 Jun 2018 |
| faolex moz117331POR.pdf | cached | BR 115/2018 scan with OCR layer -> excluded |
| reformar.co.mz | cached | Código Penal BR 248/2019 (born-digital) |
| cipmoz.org | cached | CP extracts (Lei 7/2020, 17/2020 header); 2023 CRM revision analysis |
| intic.gov.mz | not fetched | Lei 3/2017 PDFs |
| opj.ces.uc.pt | connection reset | Lei 7/2020, 18/2020 unreachable |
| inm.gov.mz | 200 | BR sold; not used |

## Cache
`.cache/` ~25 MB, requests in `.cache/requests.jsonl`. Scratch extracts in `.tmp/` (not inputs).

## Open issues
- WebSearch used: 4 of 4 (gitlaw-MZ); 0 by gitlaw-BW-MZ.
- Regex-filtered Wayback CDX queries return HTTP 500 for these domains; don't use them.
