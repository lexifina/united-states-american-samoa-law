# Andorra (gitlaw-AD): progress and handoff

Status 2026-10-29 ~00:40 UTC: **probe done, nothing parsed or built**. The run was stopped by the coordinator's wind-down.
I wrote no corpus.json, corpus.d/ or PUBLISH, so autopush only snapshots this folder to wip.

Slug `andorra`, repo `lexifina/andorra-law` (PRIVATE), tz Europe/Andorra, lang ca, future branch `futur`, on-date tool
`repo/tools/vigent_el.py` (not written yet).

## Checklist
- [x] WAVE.md, FANOUT.md, BRIEF.md, SCHEMA.md, memory/git_for_law.md read
- [x] Scaffold check: lexifina/andorra-law main = 7b0efc6 "Andorra: sources, before any law", the only commit. It is cloned at
      C:/Users/alany/Documents/andorra-law and untouched. Its README/SOURCES.md list only BOPA; fold them into repo/README.md.
- [x] Probe BOPA, Portal jurídic and the Consell General (below)
- [ ] fetch.py: BOPA API + documents blob + Portal jurídic pages (curl, sha256 cache, requests.jsonl, at most 3 req/s)
- [ ] parse.py: Constitució, Codi penal, Llei 29/2021
- [ ] repo/README.md (English first, then Catalan), LICENSE, jurisdiction.json, tools/vigent_el.py
- [ ] Build in .tmp-build, check.py, --compare, then PUBLISH

## Sources probed (2026-10-28/29)
| Source | Status | What it gives | Dated versions | Amendment notes | robots | Licence |
|---|---|---|---|---|---|---|
| BOPA SPA www.bopa.ad | 200 | React app; the backend is `https://bopaazurefunctions.azurewebsites.net/api/*`, with public function keys in `/static/js/main.22d85f68.js` | gazette as published, 1989 onwards | n/a | `Disallow:` (allows all) | not yet read (BOPA avís legal) |
| BOPA search API | 200 | POST `/api/GetPaginatedDocuments2Indexes?code=<function key: read it from the site's own script at run time; never store it>` with JSON `{"textSearch":"Codi penal","temaFilter":[],"dateFilter":[],"organismeFilter":[],"butlletiFilter":"","anyFilter":[],"size":5,"skip":0,"orderBy":"search.score() desc, DataPublicacioButlleti desc","searchMode":1}` returns `{totalCount, paginatedDocuments[{document:{metadata_storage_path, sumari, nomDocument, numButlleti, anyButlleti, dataPublicacioButlleti, dataArticle, organisme...}}]}` | each document as full-text HTML at `https://bopadocuments.blob.core.windows.net/bopa-documents/<yyy><nnn>/html/<nomDocument>.html` (yyy = year-1988, nnn = bulletin number, both zero-padded; pdf/xml/epub at documents.bopa.ad/bopa-documents/...) | — | — | — |
| Portal jurídic d'Andorra https://portaljuridicandorra.ad/L<yyyy><nnn> (e.g. /L2005009 Codi penal, /L2021029 data protection) | 200 | Run by the BOPA service (Govern + Consell General). **Current consolidated text only** ("Text refós sense caràcter oficial") | no | **yes, per article**: `img.icona-info title="• Modificat per l'article 2 de la Llei 18/2013, del 10 d'octubre, ..."` (also "Afegit per", in the TOC; each note appears twice) | /tiki-index.php disallowed; /L... SEF pages allowed | Avís legal: "Tots els drets estan reservats ... Només està autoritzat l'ús personal ... ús comercial no està permès." Record exactly; the repo stays private |
| Wayback CDX for portaljuridicandorra.ad/L2005009 | 200 | 124 captures, 2025-05-01 onwards (dense from July 2026); L2021029: 2 captures (2025-07) | snapshots only | — | — | — |
| www.consellgeneral.ad/ca/activitat-parlamentaria/lleis-aprovades | 403 (login redirect) | not usable; seu.consellgeneral.ad not probed | | | | |

## Findings for the plan
- No source gives dated versions. History must be **replayed from the gazette**: the original text from BOPA HTML, then each
  amending law (BOPA HTML) on its in-force day, checked end to end against today's Portal jurídic text.
- The Portal's per-article notes give the credits and the list of amending laws. For the Codi penal (Llei 9/2005) there are
  about 25 laws: 17/2007, 29/2007, 15/2008 (61 articles), 87/2010, 91/2010, 18/2012, 18/2013, 40/2014, 19/2014, 11/2016,
  17/2016, 15/2017, 34/2018, 37/2018, 15/2019, 17/2019, 11/2020, 13/2020, 33/2021, 6/2022, 20/2022, 30/2022, 45/2022,
  18/2024 and 1/2025. Roughly 218 article changes. That is likely over the 45-minute limit unless amending laws quote whole
  articles; check partial ("apartat") modifications first.
- The Codi penal's original disposició final sisena says it takes effect "al cap de sis mesos de ser publicat íntegrament al BOPA".
- The Constitució (1993) has never been amended, so expect 1 version. Its BOPA publication and in-force day still need
  confirming from the text. It is the fastest first act.
- Llei 29/2021 (data protection): get its Portal page /L2021029 and the notes, then the BOPA original.
- Wayback/Common Crawl captures of the Portal (2025 onwards) can verify intermediate replay states for 2025–2026 only.

## Exact next step
1. Write fetch.py. Use BOPA search (`textSearch` "Constitució del Principat d'Andorra", "Llei 9/2005 qualificada del Codi
   penal", "Llei 29/2021 qualificada de protecció de dades") to get each nomDocument, then fetch the HTML from the blob
   path. Also fetch the Portal pages /L2005009 and /L2021029, plus the Constitution's Portal page (id unknown; try IndexPerAnys for 1993).
2. Build the Constitution first (1 version, first_law = the Constitution), then Llei 29/2021, then decide on the Codi penal.

## Local state
- Cache: `.cache/probe/` (main.js, s1.json, Portal pages L2005009/Objecte/AdvertenciaLegal, pj.html), plus the
  wayback CDX records in `.cache/`. About 2 MB. `.cache/.gitignore` = `*`.
- No background processes running. WebSearch calls used: 0 of 3. No ISSUES.
