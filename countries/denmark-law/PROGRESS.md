# Denmark (gitlaw-DK): stopped

**Status, 2026-10-28 (about 22:40 UTC): stopped on the coordinator's order.** lexifina/denmark-law `main` already holds
another session's build. This folder deliberately has no `corpus.json`, `corpus.d/` or `PUBLISH`, so autopush builds
nothing and the existing `main` is not touched.

## What the existing repo holds (origin/main 0217682)

- 109 commits on `main` and 121 tags (`grundloven/1953-06-05`, `lbk/<year>-<number>` per consolidation, `lov/...` per
  amending act). The branch `sync/main` (a5ebbb0) is the original scaffold commit "Denmark: sources, before any law".
- Two acts, from Retsinformation (Civilstyrelsen):
  - Danmarks Riges Grundlov, LOV nr 169 af 05/06/1953: 1 version (`grundloven/`, 91 files; the 1953 commit is clamped
    to 1970-01-01 with the real day in `In-force:`).
  - Skatteforvaltningsloven, LOV nr 427 af 06/06/2005: 10 versions, the act as passed plus 9 lovbekendtgørelser
    (2005-758 to 2025-1228), with one commit per amending act on its in-force day between consolidations
    (`skatteforvaltningsloven/`, 95 files).
- Its own builder, not gitlaw_common: `tools/build.py`, `dkfetch.py`, `dkparse.py`, `paa_dato.py` (on-date tool),
  `check_repo.py`, `test_repo.py`, `reproduce.py`; plus `REPRODUCE.md`, `love.csv`, `data/versioner.json` and a root
  `corpus.json` in its own (different) format.
- Method: credits come from the amending articles each consolidation names ("Dokumentets indarbejdede forskrifter");
  ambiguous changes are committed by Retsinformation with `Candidate:` trailers. Only the `lbk/*` states are official
  text; states between consolidations are reconstructed. Retsinformation API used: `POST /api/document/eli/lta/<y>/<n>`
  (`{"isRawHtml":false}`), `/eli/lta/<y>/<n>/dan/xml` (StartDate), `/api/document/<id>/references/1`, `/timeline`.

## What this session did

- Read WAVE.md, FANOUT.md, BRIEF.md, SCHEMA.md and memory/git_for_law.md.
- Cloned lexifina/denmark-law to `C:/Users/alany/Documents/denmark-law` (an unmodified clone of origin/main; nothing
  built into it, nothing pushed).
- Probed retsinformation.dk at about 22:35-22:40 UTC: every URL (site, API, ELI XML) answered Cloudflare **522**
  (origin unreachable); api.retsinformation.dk and lovtidende.dk refused connections. Probably a night maintenance
  window. No data was fetched or cached. WebSearch calls used: 0.

## If Denmark is resumed under gitlaw_common

Planned Phase 1 was Grundloven 1953, Straffeloven and Databeskyttelsesloven (LOV nr 502 af 23/05/2018). Building
from corpus.json would replace the existing `main` on PUBLISH, so it needs the coordinator's go-ahead first, and should
carry Skatteforvaltningsloven over so nothing is lost. The existing `tools/dkfetch.py` and `dkparse.py` are a ready
fetch/parse base for Retsinformation.
