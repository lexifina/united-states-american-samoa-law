# Panama (gitlaw-PA): progress and handoff

Stopped at the coordinator's wind-down (2026-10-29, about 00:40 UTC). The probe is done. No act has been fetched or parsed yet, so there is no `corpus.json` and no `PUBLISH`.

## Checklist
- [x] Read WAVE.md, FANOUT.md, BRIEF.md, SCHEMA.md and memory/git_for_law.md
- [x] Cloned the scaffold to `C:/Users/alany/Documents/panama-law`. It is untouched; autopush owns it.
- [x] Probed the sources (below) and found Legispan's public JSON API
- [ ] fetch.py: copy the shape of `scripts/peru-law/fetch.py` (curl, sha256 cache, requests.jsonl, polite rate)
- [ ] Phase 1 acts: the Constitution of 1972 with its 1978, 1983, 1994 and 2004 reform acts; the Código Civil; Ley 81 de 2019
- [ ] parse.py, then corpus.json, a test build in `.tmp-build`, check.py, and PUBLISH
- [ ] repo/README.md (English, then Spanish), repo/LICENSE, repo/jurisdiction.json, repo/tools/en_vigor_el.py (copy `scripts/chile-law/repo/tools/en_vigor_el.py`)

WebSearch calls used: 0 of 4.

## Sources probed (2026-10-28/29, curl, UA lexifina-watch/1.0)

| Source | Result |
|---|---|
| legispan.asamblea.gob.pa | 200. An Angular SPA with no robots.txt (the SPA answers that path). Its **public JSON API needs no auth**: see below |
| www.gacetaoficial.gob.pa | Incapsula bot challenge on `/`. robots.txt is `Disallow:` (empty). Don't touch the challenge; the same gazette PDFs are on Legispan's S3 |
| www.organojudicial.gob.pa | 403, a WAF. Try Common Crawl or archive.org through `scripts/gitlaw_common/wayback.py` |
| www.asamblea.gob.pa | 200, an ordinary site |

### Legispan public API (found in JS chunks 990 and 7999)
Base `https://legispan.asamblea.gob.pa/api`. The admin routes (`/norm`, `/type-norm`, ...) answer 401. The public routes sit under `/search`:
- `GET /search/norm?page=&limit=&sortKey=publishedAt&sortOrder=desc`: 57,571 norms. Filters: `q`, `number`, `type[type]` (for example `CONSTITUCION POLITICA`, `LEY`, `ACTO LEGISLATIVO`), `authority[authority]`, `publishedAt_start`, `publishedAt_end`, `promulgation[number]` (gazette no.), `lawBranches`, `keywords`, `topics`.
  - Each item's `original` has `id`, `type.type`, `number`, `year`, `title`, `publishedAt`, `promulgation{number (Gaceta no.), publishedAt}`, `gazetteId`, `content` (the gazette's text layer, OCR-like with headers), `normUrl` (PDF on s3-legispan), `lawUrl` (`.../law.pdf`).
- `GET /search/type-norm?limit=0`, `/search/norm-status`, `/search/law-branch`, `/search/keyword`, `/search/topic`, `/search/commission`, and `GET /search/gazette?limit=` (gazettes with `contentUrl` PDF and `norms[]`).
- The detail page uses `getPublicNormById` (probably `GET /search/norm/<id>`; **not yet tried**). The UI shows "Afecta a" and "Afectada por" tables from `normValues.affects` and the affected-by list, plus `records` (actas) and `procedureUrl`. **This is the amendment graph**: it says which law modifies which. Legispan holds **no consolidated, dated versions** (the register says "Not consolidated"). History must therefore be rebuilt by replaying the amending acts from their gazette text, then checked against a current consolidated text (for example the Asamblea's Constitution "texto único").

## Exact next step
1. `curl -s "https://legispan.asamblea.gob.pa/api/search/norm?type%5Btype%5D=CONSTITUCION%20POLITICA&limit=50"` to list the Constitution's norms, then fetch `/search/norm/<id>` to confirm the detail route and the `affects` and affected-by fields.
2. Do the same for `type[type]=ACTO LEGISLATIVO` (the 1978, 1983 and 2004 reform acts; 1994 is Acto Legislativo 1 de 1994), for `q=Codigo Civil`, and for `type[type]=LEY&number=81&publishedAt_start=2019`.
3. Decide per act: if the texts in `content` are clean enough (a text layer, no OCR; the brief forbids OCR), replay the reform acts. Otherwise build only what Legispan's text layer supports, and name the gaps.

## Cache
`.cache/` holds only `.gitignore` so far. The Legispan JS bundles were saved outside the repo (a temp dir) and are only for finding the API; no law text is cached.

## Open issues
None in the shared builder (nothing has been built yet). No background processes are running.
