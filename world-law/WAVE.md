# World wave: rules for every new-country agent (beyond South America and Africa)

Follow `scripts/africa-law/FANOUT.md`, which applies everywhere, not only to Africa:
- the shared rules in `scripts/south-america-law/BRIEF.md`;
- FAST ARCHIVE ACCESS: Common Crawl first, then the shared archive.org client;
- SPEED RULE: up to 3 requests a second on official sites.

The Peachjam adapter applies only if your country has a Laws.Africa LII.

## Your country

- Your folder is `scripts/<slug>-law/` and the repo is `lexifina/<slug>-law`, already a private scaffold.
- The push loop discovers your folder automatically once `corpus.json` or `corpus.d/` exists, and pushes within about a minute.
- Never push yourself, and never kill processes you didn't start.

## Language

Build in the text's official language. The README is English first, then that language. No right-to-left or CJK scripts for now.

## Sources

Official APIs and dated point-in-time versions are best. Where an official API exists, use it: it is the fastest route.
- **Spain:** BOE API, with consolidated texts and point-in-time versions per block (`/datosabiertos/api/legislacion-consolidada`).
- **France:** Légifrance LEGI open data dumps (Etalab 2.0) on echanges.dila.gouv.fr. Each article version comes with its dates and the amending text.
- **Austria:** RIS OGD API (data.bka.gv.at); Bundesrecht has dated versions.
- **Italy:** Normattiva, with multi-version texts (`!vig=` dates) and its open data.
- **Portugal:** DRE (diariodarepublica.pt) consolidated legislation, with ELI `/cons/YYYYMMDD/` dated versions.
- **Finland:** Finlex open data (opendata.finlex.fi), with consolidated versions.
- **Czechia:** e-Sbírka (e-sbirka.gov.cz), with dated versions per paragraph.
- **Mexico:** Cámara de Diputados "Leyes Federales Vigentes", with reform histories and the DOF.
- **Costa Rica:** SINALEVI (sinalevi.go.cr), with versions per norm.
- **Other countries:** use the source in `scripts/world-law/register.json` for your country, and check its `pit` and `amend` columns.

## Phase 1

The Constitution plus 2 core acts: the Civil Code, plus the Penal Code or the data protection law. Then keep going deeper while the source is good. Skip any act that would take more than 45 minutes to source.

## Reporting

Keep `PROGRESS.md` current. End with a report of at most 10 lines.

## CADENCE CHANGE (2026-10-29): read the section of that name at the end of scripts/south-america-law/BRIEF.md. No pushes for hours; verify builds locally.

## SPEED RULE 2 (user, 2026-10-29 14:30 UTC): replaces SPEED RULE and per-agent sleeps
The user wants fetching accelerated; agents reading a few files a minute is not acceptable.
- **Official sites:** use `wayback.host_get(url, cache)` from a thread pool of 8-16. One adaptive rate per host, shared by every process on the machine: it starts at 4 requests a second, climbs to 25, and halves with a 30 s pause only when the host answers 429/503 or times out. Drop your own sleeps and fixed rates. Hosts whose robots.txt states a Crawl-delay (IMPO 10 s) keep it, with one thread: get round a slow host through Common Crawl or archive copies, not faster live requests. robots.txt Disallow is always obeyed. LeyChile test: 60 pages in 9 s, no pushback.
- **Common Crawl works again:** index.commoncrawl.org is still down, but `wayback.cc_captures()` now reads Common Crawl's index files from the data host (cluster.idx, cached once per crawl for the whole machine, ~120 MB) and `cc_get()` reads pages by byte range with no rate limit: use 16 threads. Try it before archive.org: 140 MalawiLII records in under 10 s.
- **archive.org** stays at its shared adaptive rate (~2 a second for the whole machine; it answers 429 above that). Use it only for what Common Crawl lacks. Do not rotate IPs or proxies.
- Never get round a bot challenge, login or paywall.
- **Fetch in bulk, in the background:** write the list of URLs first, then run one fetch.py with a thread pool (host_get / cc_get) in the background and parse while it runs. Never fetch a handful of files per tool call; across all agents that averaged about 5 requests a minute today.
- **Bulk and open-data routes first** (dumps, APIs, open data), then Common Crawl, then live pages, and archive.org last.
- **Alternative hosted archives:** read scripts/world-law/ALT-SOURCES.md first. The legalize.dev repos (open-data licences) hold reconstructed histories, e.g. Belgium from Justel. Constitute and FAOLEX are for finding sources only.

- **Arquivo.pt (user-approved 2026-10-29, max speed):** `wayback.pt_captures(url, match="prefix")` lists up to 100,000 captures in one call (5,000 Planalto captures in 1 s), and `wayback.pt_get(rec)` fetches the raw page (40 pages in 7 s from 12 threads, no throttling). It uses host_get's adaptive rate. Try it right after Common Crawl and **before archive.org**, above all for Lusophone and Latin American official sites (Planalto, IMPO, ...). Record it as a source ("Arquivo.pt, capture <ts>").
- **Never publish personal emails (user rule 2026-10-29).** The machine's global git email is personal, so any commit made outside autopush or build.py must set `user.email` explicitly (Lexifina <slug-law@lexifina.com>). Agents still never commit or push.
