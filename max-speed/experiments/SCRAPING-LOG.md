# Scraping experiments log

The user asked (2026-10-29): "see if we can get more creative/inventive with our scraping, keep experimenting and keep a written log."
This file holds speed and implementation material, so it belongs in the private repo lexifina/world-law-max-speed, not in a country repo. Nothing is pushed while the user's push stop holds.

**Fixed limits for every experiment:**
- No getting round bot challenges, logins or paywalls.
- No IP or proxy rotation.
- robots.txt Disallow is obeyed, and so is a stated Crawl-delay (the per-host adaptive rate applies only where no delay is stated).
- Every licence and attribution is recorded.

Each entry gives the date and time (UTC), the method, what was measured, the result, and keep/drop.

---

## 2026-10-29 14:00 to 15:00. Baseline and first fixes (coordinator)
- **Baseline:** about 5 requests a minute across all agents over 6 hours (from the requests.jsonl logs). archive.org answered 712 of 3,819 requests with 429 (19%), and its shared rate settled at about 1.9 a second. index.commoncrawl.org timed out all day over IPv4, and IPv6 had no route. data.commoncrawl.org answered byte ranges in 0.5 s.
- **Per-host adaptive rate (`wayback.host_get`):** LeyChile gave 60 pages in 9.1 s from 12 threads; the rate climbed to 19 a second with 0 pushback, against 20 s at the old 3 a second. **Keep.**
- **Common Crawl index files read directly** (cluster.idx, cached once per crawl, about 118 MB, plus cdx-*.gz byte ranges): MalawiLII `akn/mw/act/` prefix, 140 records in 9.6 s including the one-off index download; the page body came back fine. The fork measured e-seimas, 4,662 captures in 1.2 s. **Keep.** (The fork added a skip for a bad gzip block.)
- **legalize.dev repos as a source:** data licences are open (CC0, public domain or CC BY), but their quality varies. legalize-be holds real Justel wordings, though out of order and dated about 10 days after publication; usable once re-dated from Justel's notes. legalize-gr has no amendment history (6,805 of 6,851 commits only add files) and lossy text, so it serves only to find amending laws. legalize-ar has no history beyond InfoLEG. **Use with a text check every time.**

## 2026-10-29 15:40. Other web archives (coordinator)
- **Arquivo.pt** (Portuguese public web archive): its CDX API (`https://arquivo.pt/wayback/cdx?url=...&output=json`) answers in 0.35 to 0.5 s and holds Planalto (Brazil) and IMPO (Uruguay) captures from 2009 to 2025. Raw replay (`/wayback/<ts>id_/<url>`) gave a 371 KB page in 0.44 s, and 20 parallel CDX queries all came back 200 in 2.7 s. **But** its robots.txt, for `User-agent: *`, says `Disallow: /wayback` and `Crawl-delay: 5` / `Request-rate: 1/5s`, while its developer docs present the CDX API for programmatic use. **On hold:** under our robots rule this needs the user's decision before automated use. If the user approves, use it at its stated 1 request per 5 s: one CDX query lists up to 100,000 captures, so even that rate is valuable for listing.
- **Library of Congress web archive** (webarchive.loc.gov CDX): it answers with a Cloudflare challenge. **Drop** (never get round a challenge).
- **Memento TimeTravel aggregator** (timetravel.mementoweb.org): no connection from here (curl 000). Retry later.
- **DuckDB** (to query Common Crawl's columnar Parquet index over HTTPS): not installed. To try next.

## 2026-10-29 16:00. Arquivo.pt in production (coordinator)
- The user approved it: "yes, do the thing that gives us max speed". Added `pt_captures` / `pt_get` to wayback.py, routed through host_get's adaptive per-host rate.
- Measured: Planalto `ccivil_03/leis/` prefix, 5,000 captures in 1.0 s; 40 raw pages (211 KB) in 7.3 s from 12 threads; the rate climbed to 14 a second with 0 throttled. archive.org, by comparison, is about 2 a second for the whole machine with 19% 429s. **Keep: the first archive to try after Common Crawl.**

## 2026-10-29 19:40 to 19:50. Ideas 1, 2 and 9: Common Crawl Parquet, whole-host harvest, one-process parallel fetch (experimenter)
Scripts: `experiments/cc_parquet.py`, scratch in `experiments/.tmp/`.
- **Idea 1, columnar index via DuckDB 2.0 over HTTPS.** The table is sorted by `url_surtkey`, 300 files and about 1,500 row groups per crawl. Reading every file's footer once (row-group SURT min/max) costs 300 small requests, 19.5 s per crawl, and lets DuckDB open only the 1 or 2 files that hold a prefix. Measured on CC-MAIN-2026-43:
  - one host (malawilii.org, full record columns, both subsets): 27 s cold, against **0.16 s** through cluster.idx. Planalto PDFs with WARC pointers: 20 s cold, 0.2 s warm in the same connection. For one host, cluster.idx wins by 100x.
  - a whole country TLD with a MIME filter: `mw,` gave 29,110 rows over 564 hosts (488 PDFs) in 1.6 s; **`br,gov,` PDFs with status 200 across 2 crawls: 329,619 captures over 4,814 hosts (318,841 distinct digests) in 84 s.** cluster.idx cannot do that: the prefix runs past its 2,000-block cap and has no MIME column.
  - Needs `pytz` for timestamp columns (use `strftime(fetch_time, ...)` instead).
  - **Keep, for discovery only:** "which official hosts and PDFs exist under a TLD" (gov.xx, gob.xx, or a whole small country), one query per crawl. Keep cluster.idx for per-host lists.
- **Idea 2, whole-host harvest across 40 crawls (cluster.idx, 16 threads):** Planalto `ccivil_03/leis/`: 283,236 captures listed in 5.8 s (about 49,000 a second), 124,966 distinct URLs. BOE `buscar/act.php`: 94,697 in 3.1 s. ZambiaLII `akn/`: 40,335 in 4.8 s. **Deduping by content digest saves under 1% for HTML** (Planalto: 177,024 OK captures, 176,089 distinct url+digest pairs; BOE 90,687 vs 90,643; ZambiaLII 27,597 vs 27,434) because page chrome changes on every capture: one fixed ZambiaLII expression URL (`eng@2011-04-15`) has 12 digests. **Listing: keep. Digest dedup: drop for HTML.** Dedup on extracted law text after fetching, or fetch one capture per URL per year and expand only where the text changes. For PDFs it works better (3% duplicates across .gov.br).
- **Idea 9, many byte ranges from one curl process (`curl --parallel -K list`):** neither Git Bash's curl 8.17 nor Windows curl 8.21 is built with HTTP/2, so this is HTTP/1.1 keep-alive inside one process. Against a thread pool that starts one curl per range (11.6/s at 16 threads, 21.8/s at 32, 25/s at 64), one process managed 36/s at 16, 91/s at 50 and 130/s at 100, all 206. Gotchas: a trailing `next` in the config aborts every transfer ("no URL specified"); options reset after each `next`, so the user agent goes in every block; use forward slashes in output paths.
- **Then data.commoncrawl.org blocked this machine (19:48 UTC): CloudFront 403 "Request blocked" on every request**, index blocks and paths files alike. Cause: about 2,400 range requests in roughly 40 s from my tests (peaks of 130/s), on top of other agents' cc_get traffic. **Danger for every agent:** `_cc_captures_files` treats the 403 HTML page as a bad gzip block and skips it, so `cc_captures` silently returns **0 records** while blocked (all six newest crawls returned 0 for Planalto right after). `cc_get` raises on the gzip step. Check one request by hand before believing an empty Common Crawl result. A probe runs once a minute (`.tmp/cc_unblock.log`) to measure how long the block lasts.
  - **Rule from this:** keep Common Crawl's CDN to about 25 requests a second for the whole machine (the thread-pool level, which ran clean for hours). The 100+/s one-process figure is real but CloudFront's rate rule caps it, so do **not** use `--parallel` above ~20 against data.commoncrawl.org.
  - **Block length, measured:** 403 at 19:48, 19:49:29 and 19:50:29; 200 again at 19:51:29. So about three minutes, a short rolling window. No agent needs to stop for long, but every Common Crawl list made during a block must be redone.
  - **HTTP/2:** neither curl build has it, and Python's `h2` is not installed (httpx 0.28 is, and Python TLS works now). Not tried further: CloudFront's rate cap, not connection setup, is the limit.

## 2026-10-29 20:00 to 20:30. Ideas 3 to 8 and 10 (experimenter)
- **Idea 3, Wayback CDX collapse and field limits** (ZambiaLII `akn/zm/act/19` prefix, status 200): no collapse 5,124 rows (624 KB); `collapse=digest` 4,643 (9% fewer); `collapse=timestamp:4` (one per URL per year) 2,024 (60% fewer); `collapse=urlkey` (one row per distinct URL) 797 rows, 50 KB. Each request took 60 to 190 s, all of it queueing: archive.org's shared rate stood at 0.35 a second with 855 throttled answers machine-wide. `captures()` already defaults to `collapse='digest'`. **Keep, no code change:** list URLs with `collapse='urlkey'`, find versions with `collapse='timestamp:4'` (or `:6` for monthly), then expand only the URLs whose text changed. That turns one huge list into a small one plus targeted follow-ups.
- **Idea 4, sitemaps: the big win of this round.** Probed 36 official legislation hosts for robots.txt `Sitemap:` lines or `/sitemap.xml`, then walked whole sitemap trees through host_get (8 threads):
  | Host | URLs | Requests | Time |
  |---|---|---|---|
  | www.fedlex.admin.ch (ELI, every language) | 384,305 | 41 | 13.7 s |
  | www.finlex.fi (laws and case law) | 369,848 | 94 | 32.3 s |
  | retsinformation.dk (ELI, with lastmod) | 200,007 | 22 | 9.1 s |
  | legilux.public.lu (ELI) | 100,132 | 12 | 9.9 s |
  | wetten.overheid.nl (every BWBR id) | 47,172 | 1 | 0.8 s |
  | static.slov-lex.sk ZZ (every Zbierka act) | 26,604 | 99 | 73 s (10 throttles, rate fell to 2/s) |
  | www.registroficial.gob.ec (every edition) | 25,982 | 19 | 6.2 s |
  | www.legislation.gov.uk | 6,032 child sitemaps | | not walked: Crawl-delay 5 means 8.4 h |
  | www.bcn.cl | 70,803 child sitemaps, including leychile `navegar?idNorma` | | not walked (70k requests) |

  No sitemap (404 or HTML): BOE, Planalto, e-seimas, Riigi Teataja, gesetze-im-internet, Légifrance, RIS, Irish Statute Book, NZ, Canada justice, ISAP, njt.hu, likumi.lv, InfoLEG, DRE, SUIN, Diputados MX. Planalto, RIS, njt.hu, likumi.lv, Gaceta VE and Diputados MX timed out (90 to 178 s). **Keep. Added `wayback.sitemap_urls()`** (plus `robots_rules()` and `robots_allows()`): host or sitemap URL in, every page URL out, gzip-aware, obeys a stated Crawl-delay (one request at a time) and drops Disallowed URLs. Retested through the new function: Legilux 100,116 URLs in 5.2 s (16 Disallowed dropped), Retsinformation 200,007 in 5.3 s with 200,000 lastmods.
- **Idea 5, CKAN open-data portals** (26 portals, one `package_search` each, 13 threads, about 2 minutes, mostly waiting on dead portals): 13 answered. Leads: **open.canada.ca**: "Consolidated federal Acts and regulations, Bulk XML (PIT, point in time)", OGL-Canada, data on github.com/justicecanada/laws-lois-xml (already in register.json). **datos.gob.ar**: "Base Infoleg de Normativa Nacional" plus the modificadas/modificatorias tables, CC BY 4.0 (argentina-law already uses it). **opendata.swiss**: "Amtliche Sammlung des Bundesrechts (BS/AS) 1947-2018" from the Federal Archives (`amtsdruckschriften.bar.admin.ch` ZIPs and a 1.3 MB classification 7z at sfa-laboratory.ch). Not in swiss-law yet; licence field empty, so read the Readme.pdf before use. **data.gov.il**: all bills and a parliamentary OData feed. **data.gov.uk**: "Legislation API". No response or no CKAN: catalog.data.gov, datos.gob.mx, dados.gov.br, data.gov.cz, data.gv.at, eesti, data.gov.sg, datos.gov.co, datosabiertos.gob.pe; opendata.go.ke and opendata.government.bg timed out. **Keep as a 2-minute discovery sweep per new country; little that country agents did not already have.**
- **Idea 6, Hugging Face and Zenodo:**
  - HF API, 8 searches in 6.2 s: 616 datasets. **About 600 of them are from two accounts, `endomorphosis/ipfs_<country>_laws` and `justicedao/ipfs_<country>_laws_ir`: one per country** (Malawi: 5,361 instruments with title, text, dates and source_url, snapshot 2026-10-09; licence "other", per source). Each is **one snapshot, not a history**, but its `source_url` column is a ready list of official URLs for nearly every country. DuckDB read the Malawi parquet over HTTPS in 2.2 s. **edithatogo/corpus-legislation-nz-historical**: 164 parquet files (240 MB) of NZ versions, including superseded ones, with version-dated legislation.govt.nz URLs (`/act/imperial/1828/14/en/2007-09-03/`). Its RIGHTS.md says "source-specific review required"; NZ legislation itself is Crown copyright under CC BY 4.0, so use it as a version-URL list and take the text from legislation.govt.nz. Also: vGassen Dutch BWB XML (PDDL), sakhadib Bangladesh acts (CC BY 4.0). Multi_Legal_Pile is NC: never.
  - Zenodo (5 searches, 26 s; its search ORs the words, so mostly noise). **Find: Corpus des Deutschen Bundesrechts (C-DBR), CC0, 25 quarterly snapshots of all German federal law from 2020-05-18 to 2026-10-04** (XML, TXT, CSV; about 1.5 GB each). Quarterly snapshots give checkpoints for germany-law's history, not every version. Not mentioned in germany-law yet. Unauthenticated Zenodo pages are capped at 25 records.
  - **Keep for discovery and checkpoints. Never copy text without checking its official source and licence.**
- **Idea 7, predictable PDF URLs** (Greece ΦΕΚ blob store `fek/01/<YYYY>/<YYYY>01<NNNNN>.pdf`): container listing is off (`ResourceNotFound`), so enumerating by pattern is the only way. 143 of 150 numbers existed for 2020 (80.7 MB). **But the store caps this machine at about 0.5 MB/s in total:** 2 streams 0.43 MB/s, 8 streams 0.50 MB/s, a single small file at 5 a second. host_get through 16 threads managed only 0.4 files a second, with 25 "throttles" that were really 90 s timeouts on 2 to 11 MB PDFs, so the adaptive rate halved itself for nothing. **Keep the pattern; use 2 threads with a 300 s timeout for big-PDF hosts.** More threads only make timeouts. About 43 GB a day at that cap.
- **Idea 8, other national web archives with CDX** (robots.txt checked first):
  - NLNZ web archive (`ndhadeliver.natlib.govt.nz/webarchive/cdx`): pywb CDX in JSON; `legislation.govt.nz/act/public/` gave 3,683 captures of 1,798 URLs from 2008-07 to 2026-10 in 4 s. **On hold:** robots.txt answers 403 and the archive's front page serves a bot-management script, so ask the user before any automated use (as with Arquivo.pt). Replay not tried.
  - Estonian web archive (`veebiarhiiv.digar.ee/a/cdx`): open CDX in JSON, Riigi Teataja from 2012, but robots.txt says `Disallow: /a/`. **Drop unless the user approves.**
  - Dropped: Archive-It (403, robots `Disallow: /`, Crawl-delay 10), Stanford SWAP (403), vefsafn.is (robots `Disallow: /`, timeout), NLB Singapore (202 challenge-like), UK Web Archive and Australian Web Archive (the CDX path returns the app's HTML page, no public CDX), webarchive.lu (404). No connection: webarchiv.cz, haw.nsk.hr, bac-lac.gc.ca, the Slovenian archive, Memento TimeTravel.
- **Idea 10, gazette feeds** (20 guessed URLs): working feeds were BOE (13 items), legislation.gov.uk Atom (20 per page), **gesetze-im-internet Aktualitätendienst (243 items: which laws changed lately)** and **recht.bund.de BGBl I+II (500 items)**. The rest were 404s or HTML. **Keep for incremental updates once a corpus exists; not useful for history.** Find feeds through each site's page links, not by guessing.

## 2026-10-29 20:30. Added to gitlaw_common/wayback.py (new functions only; nothing existing changed)
- `cc_ok()`: one HEAD request; False while CloudFront blocks the machine. Call it before trusting an empty `cc_captures()`.
- `robots_rules(host)`, `robots_allows(url, disallow)`: `User-agent: *` Crawl-delay, Disallow (with `*` and `$`) and Sitemap lines.
- `sitemap_urls(root, cache, threads=8, with_lastmod=False)`: see idea 4.
- `cc_table_query(prefix, crawls, where, columns)`: the Parquet index through DuckDB, for TLD-wide discovery. It needs `duckdb` (installed here, 2.0.0) and caches each crawl's row-group ranges in the shared `gitlaw-cc-index` folder (300 footer requests, about 20 s, 8 threads). Tested: `mw,gov,` PDFs, 130 captures in 23.6 s including the footer fetch; `parliament.gov.mw` over 2 crawls, then `cc_get` on a result (73 KB).

## Ideas queue (status after 2026-10-29 20:30)
Done: 1 (keep for TLD discovery), 2 (keep listing, drop digest dedup for HTML), 3 (keep collapse modes), 4 (keep, in wayback.py), 5 (keep as a sweep), 6 (keep for discovery and checkpoints), 7 (keep, bandwidth-bound), 8 (NLNZ and Estonia need a user decision; the rest dropped), 9 (HTTP/1.1 one-process: real, but capped by CloudFront), 10 (keep for updates).
Next:
11. Walk the HF `ipfs_<country>_laws` `source_url` columns into per-country URL lists for agents that lack a catalogue (one parquet per country; DuckDB reads one in about 2 s).
12. Run `cc_table_query` over each target country's gov TLD for PDFs and HTML under law-looking paths (`/lei`, `/ley`, `/act`, `/eli/`, `/gazette`, `/boletin`) to find official hosts nobody has listed.
13. Change-only fetching: from a whole-host listing, fetch the newest capture per URL, then fetch older captures only where `length` moves by more than a threshold (a cheap stand-in for text change, since digests always change).
14. Ask the user about the NLNZ and Estonian archive CDX (robots).

## Ideas queue (original)
1. Common Crawl columnar index (Parquet, `cc-index/table/cc-main/warc/`) queried with DuckDB over HTTPS range reads: every capture of a host in one query, filtered by MIME and status.
2. Whole-host Common Crawl harvest: list every URL under an official legislation host across 20+ crawls, then dedupe by content digest (one fetch per distinct version, not per capture).
3. Wayback CDX `collapse=digest` and `fl=` field limits: fetch only distinct content versions, cutting archive.org requests.
4. sitemap.xml and robots.txt Sitemap: lines on official sites: list every law URL in one request instead of crawling.
5. Open-data catalogues (CKAN data.gov.* portals): find official legislation dumps and APIs per country.
6. Hugging Face and Zenodo legal corpora (MultiLegalPile, national corpora): check licence and dating; use only as a source of dated official text.
7. Predictable official PDF URL patterns (like Greece's ΦΕΚ blob store): list them by pattern, then fetch with host_get.
8. Other national web archives with open CDX: the UK Web Archive, Bibliothèque nationale, the Australian Web Archive (Trove), the Icelandic and Croatian archives. Check robots and terms for each.
9. HTTP/2 multiplexing (`curl --parallel --parallel-max N`) under host_get's rate, for hosts that allow it.
10. Gazette RSS and Atom feeds for new laws: incremental updates without crawling.
