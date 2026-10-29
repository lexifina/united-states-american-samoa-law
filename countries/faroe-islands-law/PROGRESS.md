# Faroe Islands law (gitlaw-FO): progress / handoff

Stopped at the 00:44 UTC wind-down on 2026-10-29. **Nothing is built:** there is no corpus.json and no PUBLISH.

## Repo state (checked 2026-10-28 ~23:50 UTC)
- `lexifina/faroe-islands-law` main = only the scaffold 13de98e "Faroe Islands: sources, before any law".
- **Remote also has a `wip` branch** (ce1bf92, 23:07 UTC, author Lexifina <corpus@lexifina.com>, "Work in progress: gate findings").
  It adds only PROGRESS.md (gates 1-4 and 6 passed, gate 5 "checking") on top of the scaffold. It was NOT made by autopush,
  whose message would be "Work in progress: scripts/faroe-islands-law at ...". Another session may own this country.
  Ask the coordinator before resuming, and recheck main before any PUBLISH.
- Local clone: C:/Users/alany/Documents/faroe-islands-law (untouched).

## Probe findings (logir.fo)
- https://www.logir.fo/ answers 200 (ASP.NET) to the lexifina-watch UA, with no bot challenge.
- robots.txt: `*` disallows only /GetFile and /Content (PDF/DOC downloads and the print view). Law pages are allowed.
  /RobotsList.aspx is allowed but returns HTTP 500. https://logir.fo/v2 returns 404.
- Law page URL shape: `/Logtingslog/<nr>-fra-DD-MM-YYYY-<slug>`, `/Kunngerd/...`, `/Bekendtgorelse/...`. Pages link to
  logting.fo case files (`/mal/mal/?id=`). Search filters: Gildisstøða (Galdandi / Áður galdandi / Søgulig / Í koming)
  and Útgávustøða (Broytingarrættarregla / Høvuðsrættarregla). Old versions ("Áður galdandi") may be listed, so dated
  history may be possible. Not yet verified.
- Cached: .cache/probe/fo_home.html and fo_l86.html (Løgtingslóg 86/2026). Helper: .cache/probe/probe_txt.py.

## Exact next step
1. Settle ownership (the wip branch above).
2. Search logir.fo with GET parameters, or a search form postback, for "stýrisskipan", "heimastýri" and "dátuvernd".
   Open one consolidated main-law page and confirm that the HTML holds the full text and the list of amendments
   (`broytingar`) with links to each amending Løgtingslóg.
3. Write fetch.py (curl, sha256 cache, at most 3 req/s) and parse.py, then write corpus.json for the
   Stýrisskipanarlóg first.

## Open issues
- None filed. WebSearch calls used: 0.
