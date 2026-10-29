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
