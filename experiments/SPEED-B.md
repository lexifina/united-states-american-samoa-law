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
