# Speed experiments B: official bulk, open-data and archive routes (2026-10-29)

Agent B of the speed experiments. Each section gives what was measured (requests, seconds, records), the verdict, and
a recipe a country agent can paste. Scripts and raw results: `experiments/speedb_<country>.py` / `.json`.

## B1. Argentina: InfoLEG bulk data (datos.jus.gob.ar)

Before (argentina-law's own request log, 1,622 requests): 792 `verNorma.do` record pages, 792 `norma.htm` texts,
18 `verVinculos.do` link pages, 18 `texact.htm`, 2 bulk zips, all at a fixed 1 request a second.

Measured (`speedb_argentina.py`):
- **Three bulk files, 3 requests, 132 s** including the 10 s Crawl-Delay between them (robots.txt; `/api/` is
  Disallowed, so the CKAN API is off limits: take the links from the dataset page). Normas: 429,648 rows (49.7 MB zip,
  79 s; the server gives about 0.6 MB/s). Modificatorias: 379,163 rows. Modificadas: 383,793 rows. Newest
  `fecha_boletin` 2026-09-30, so the files lag about a month.
- **Dates: the record pages are redundant.** All 792 norms whose `verNorma.do` page was fetched are in the bulk table
  with `fecha_boletin` (and `fecha_sancion`, title, number, issuing body). parse.py already reads those dates from the
  bulk table and never parses the record pages, so 792 of 1,622 requests (49%) bought nothing.
- **Amendment links: the modificatorias table matches the verVinculos pages.** 18 pages, 4,922 links; the table has
  4,918 of them and nothing extra. The 4 missing are norms published after the table's cutoff (ids 430,801 and up).
- **Texts: not in any bulk file.** The table has only text URLs (189,321 `texto_original`, 8,701
  `texto_actualizado`). Through `host_get` (InfoLEG has no robots.txt, so no stated delay), 12 threads fetched 60
  amending-law texts of the Código Penal in 10.6 s (5.7 a second, rate climbed to 25/s, 0 throttled) against 63 s at
  the old fixed 1 a second.

Verdict: **keep the bulk route for dates and links, keep page fetches for texts only.** For a batch like
argentina-law's, 1,622 requests at 1/s (about 27 minutes) becomes 3 bulk + ~810 text requests at ~6/s (about 4.5
minutes, half of it the bulk download).

Recipe:
1. Download once per session (one request at a time, 10 s apart): the dataset page
   `https://datos.jus.gob.ar/dataset/d9a963ea-8b1d-4ca3-9dd9-07a4773e8c23` links `base-infoleg-normativa-nacional.zip`,
   `...-normas-modificatorias.zip` and `...-normas-modificadas.zip`.
2. Dates, numbers, titles: from the normas table by `id_norma`. Never fetch `verNorma.do`.
3. Who amends norm X: modificatorias rows with `id_norma_modificada == X`. Fetch `verVinculos.do?modo=2&id=X` only to
   pick up norms published after the table's newest `fecha_boletin`.
4. Texts: `texto_original` / `texto_actualizado` URLs (switch http to https) through `wayback.host_get` from a 12-thread
   pool.

## B2. Brazil: Arquivo.pt and LexML for dated federal texts

Before: Planalto refuses this machine, so brazil-law reads `web.archive.org/web/<ts>id_/` captures, under archive.org's
one rate for the whole machine (about 2 a second, 19% answered 429). One exact-URL CDX listing of the Constitution's
compiled page took **53.6 s** (1,798 digest-distinct captures, 2010 to 2026).

Measured (`speedb_brazil.py`, Arquivo.pt through `pt_captures` / `pt_get`):

| Prefix (Arquivo.pt CDX, one request each) | Seconds | Captures | Distinct URLs | Real copies (length >= 3200) | URLs with a real copy | URLs with 2+ real versions |
|---|---|---|---|---|---|---|
| planalto `ccivil_03/leis/` | 23.9 | 21,991 | 10,767 | 12,744 | 3,289 | 1,580 |
| planalto `ccivil_03/constituicao/` | 1.9 | 3,600 | 1,293 | 1,586 | 222 | 143 |
| planalto `ccivil_03/decreto-lei/` | 1.6 | 4,482 | 2,093 | 2,681 | 822 | 394 |
| planalto `ccivil_03/_ato2019-2022/` | 1.6 | 6,330 | 3,257 | 4,634 | 1,707 | 944 |
| planalto `ccivil_03/_ato2023-2026/` | 1.6 | 1,682 | 1,083 | 1,627 | 730 | 356 |
| Chamber `www2.camara.leg.br/legin/fed/` | 15.5 | 14,325 | 8,819 | 14,314 | 8,785 | 1,926 |

- `planalto.gov.br` and `www.planalto.gov.br` give the same records (Arquivo.pt normalises the host).
  `ccivil_03/emendas/` gives 0 (the amendments live under `constituicao/Emendas/`).
- **Most Planalto captures from 2010 to 2022 are bot pages** ("enable JavaScript", ~5 KB). The CDX `length` field
  tells them apart without fetching: bot copies are 1.9-3.1 KB compressed, real pages from 2.9 KB up (40-capture
  sample, one overlap each way). Real copies cluster in 2009 and 2023-2025. The Constitution's compiled page has 224
  captures but only 54 real ones (2016, 2018, 2023-2025); archive.org is deeper for that page (2010-2026).
- **Raw fetch: 49 captures in 10.2 s from 12 threads (4.8 a second, 6.2 MB)**, host rate up to 15/s with 10 backoffs
  (other agents share the host). 21 of the 49 were bot copies, which the length filter would have skipped.
- **The Chamber's legin pages are a clean second source of original texts:** 2,544 `publicacaooriginal` pages (the
  text as published in the D.O.U., including 1,686 laws, 2,121 decrees, 99 constitutional amendments) and 7,000+
  `norma` pages, none of them bot copies. www.camara.leg.br's robots.txt has an AI-bot block group, so read these from
  archives only, never live.
- **LexML (www.lexml.gov.br): a catalogue, not a text source.** robots.txt: Crawl-delay 5, `/busca/`, `/doc/`,
  `/linker/` Disallowed (the SRU API is `/busca/SRU`, so it is off limits; `/sru` answers 404/503). A `/urn/` page
  (4.0 s, 1.15 MB, most of it citing articles) gives the signing date and links to Planalto, the Senate record and the
  Chamber's `publicacaooriginal` and `norma` pages. Useful only to map a law number to its URN and to the Chamber URL;
  at one request per 5 s it suits a few hundred lookups, not a crawl. legis.senado.leg.br answers 403 to this machine.

Verdict: **Arquivo.pt with a length filter beats archive.org for Planalto pages from 2023 on and for Chamber original
texts** (listing 0.6-24 s vs 54 s; fetch ~5/s per agent vs a 2/s machine-wide share). For older Planalto states
(2010-2022), archive.org remains the only deep source. LexML: lookups only.

Recipe (Brazil):
1. List: `wayback.pt_captures('www.planalto.gov.br/ccivil_03/<dir>/', match='prefix')` once per directory; drop records
   with `int(length) < 3200`; keep one record per (urlkey, digest).
2. Original texts of amending laws: `wayback.pt_captures('www2.camara.leg.br/legin/fed/', match='prefix')`, filter
   `publicacaooriginal` (archive copies only).
3. Fetch with `wayback.pt_get(rec)` from 12 threads; still reject bodies under 6 KB or containing "enable javascript".
4. Only for a state Arquivo.pt lacks (most of 2010-2022), fall back to `wayback.captures(..., collapse='timestamp:6')`
   and `wayback.get`. Pin every capture timestamp in sources.

## B3. Peru: El Peruano from archives, the sitemap, or fewer live listings

Before: peru-law found its laws by paging busquedas.elperuano.pe's search **one day at a time**, 2,088 of its 4,158
requests, because long ranges dropped and repeated cards. The server is slow (10-35 s for some pages, 293 backoffs
on the shared host rate so far today).

Measured (`speedb_peru.py`, `speedb_peru_paging.py`, `speedb_peru_paging_old.py`; the yardstick is peru-law's own day
cards for 2026: 18,647 norms on 285 days, 232 of them laws, legislative decrees and emergency decrees):

| Route | Requests | Seconds | What it gives | 2026 laws/D.Legs/DUs covered |
|---|---|---|---|---|
| Common Crawl, 8 newest crawls, `busquedas.elperuano.pe/dispositivo/` | ~40 index blocks | 12.2 | 11,877 OK captures, 10,848 distinct norms | 120 of 232 (52%) |
| Common Crawl `/normaslegales/` (pre-2023 URL form) | | 5.4 | 864 captures, none with status 200 | 0 |
| Common Crawl `/api/archivo/file/` (the PDFs) | | 5.4 | 0 | – |
| Arquivo.pt, same four prefixes | 4 | 5.8 | 87 norm pages, 116 old-form pages, 114 issue PDFs (2020-2021) | 0 |
| archive.org CDX `collapse=urlkey`, `/dispositivo/` | 1 | 110 | 36,792 distinct norms, 2023-2026 | 109 of 232 (47%) |
| archive.org CDX, `/normaslegales/` | 1 | 113 | 28,688 distinct norms, 2017-2023 | – |
| All three archives together | | | | 156 of 232 (67%) |
| **Live search, one type, long range, paged 20 at a time** | **10** | ~200 | every card | **142 of 142 sampled (100%)** |
| Live sitemap `busquedas.elperuano.pe/sitemap.xml` | 3 | 4.3 | today's 761 norms (75 NL, 686 BO), lastmod today only | new issues only |

- An archived norm page holds the PDF link (24 of 24 Common Crawl captures, 4.2 s from 16 threads), but no archive
  holds the PDFs (token URLs), so the text still comes from the live site. Archives would replace only discovery, and
  they miss a third of the laws.
- **The cheap fix is live and needs no archive: filter the search by type and page a long range.** 2026, against the
  day cards: LEY March (1 request, 5 of 5), LEY April-June (5 requests, 95 of 95), D.Leg January-October (3 requests,
  45 of 45), DU March-May (1 request, 2 of 2): 10 requests, 0 missed, 0 repeated, where day-by-day listing takes
  ~500. Older ranges can still break: LEY 2019 reported 130 hits but its 7 pages gave 99 rows and 91 distinct; D.Leg
  June 2016-December 2018 was clean (12 requests, 209 of 209).
- Open data: diariooficial.elperuano.pe has a `/DatosAbiertos/` path but its robots.txt Disallows it;
  datosabiertos.gob.pe did not answer in the earlier sweep.

Verdict: **archives don't help Peru** (no PDFs, 67% coverage of norm pages). **Filtered long-range paging with a
self-check cuts discovery about 20 to 50 times**, and the daily sitemap covers new issues in 1-3 requests.

Recipe (Peru):
1. For each type you need (`tipoDispositivo=LEY`, `DECRETO LEGISLATIVO`, `DECRETO DE URGENCIA`, ...) and for
   `tipoPublicacion=NL` and `EX`, page `?fechaIni=A&fechaFin=B&...&start=0,20,40...` over a quarter or a year.
2. Read `totalHits` from the page data and the ops from both `\"op\",\"<op>\"` and `/dispositivo/NL/<op>` (the page
   data serialises repeated strings as references, so one pattern alone misses most cards).
3. Accept the range only if rows == distinct ops == totalHits; otherwise halve it and retry. Single days only as the
   last resort.
4. New issues: `wayback.sitemap_urls('https://busquedas.elperuano.pe/sitemap.xml')` daily (today's norms only).
5. PDFs: the `urlPDF` (`/api/archivo/file/<token>/*/<op>.pdf`) from the card, live through `host_get`.

## B4. Albania: a bulk or sitemap route for QBZ (qbz.gov.al)?

Before: albania-law made 734 QBZ API requests over 26 minutes (22:55-23:21 UTC, fixed 3 a second in fetch.py, with
parsing in between): 40 listing pages, then `/acts/{id}/versions` and `/acts/{id}/relations` for each law with
versions.

Probes (`speedb_albania.py`, one request each, 0.4-0.9 s):
- No robots.txt and no sitemap.xml: both paths serve the app's HTML, and so do ELI paths (`/eli/ligj/...`). No
  OpenAPI description at any of five usual paths.
- The list caps the page size at 100 (`size=200` and up answer 400 "size duhet të jetë ndërmjet 1 dhe 100"), and
  ignores `sort=versions,desc`, `hasVersions` and `minVersions`. The `versions` count is already in every list item,
  so acts with none can be skipped without a request.
- One act's record doesn't embed versions or relations (`expand`/`include` ignored), and there is no all-versions or
  all-relations endpoint (`/versions`, `/relations`: 404). `rdf` is null.
- Archives: Common Crawl (4 newest crawls) and Arquivo.pt hold 0 captures of `qbz.gov.al/api/`.

**So there is no bulk route: the speed-up is the thread pool.** `speedb_albania_parallel.py` ran the whole crawl
through `host_get`: 40 listing pages in 5.6 s (8 threads, 3,907 laws, 383 with versions), then 766 versions and
relations requests in 47.3 s (12 threads, 16.2 a second, rate up to 25/s, 0 throttled). **806 requests in 53 s**,
against 269 s at the old fixed 3 a second and 26 minutes as actually run.

Recipe (Albania):
1. `host_get(f'{API}/acts?type=Ligj&size=100&page={n}')` for n in 0-39 from 8 threads (size can't exceed 100).
2. Keep items with `versions > 0`; fetch `/acts/{id}/versions` and `/acts/{id}/relations` for them from 12 threads.
3. Then the version `.docx` files (`word.url`) the same way. Write the URL list first and run one fetch in the
   background; never fetch inside the parse loop.
