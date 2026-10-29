# Spain (gitlaw-ES) progress

## Status, 2026-10-28: STOPPED before building. Waiting for a coordinator decision.

lexifina/spain-law is **not a scaffold**. Its `main` already holds a complete build of Spanish state law from the BOE
consolidated-legislation API, made by another session with its own builder (shipped in the repo's `build/`: fetch.py,
parse.py, boe.py, build.py, check_repo.py, reproduce.py, test_repo.py). The `scripts/spain-law` folder that builder's
REPRODUCE.md names is not in this checkout.

- main head `513d8526e6` (docs commit), law-head `56dbb7491c`. 16,737 commits; 8,774 Estatal norms; 397,165 block
  versions, 1835-11-27 to 2026-10-28.
- Its check_repo.py reports 397,165 block versions checked on their dates, 0 differ, 0 word differences from the XML;
  a rebuild gave the same law-head hash; test_repo 6/6.
- Branches: main, law-head, sync/main (= the old "Spain: sources, before any law" scaffold commit a5f41c152f).
- Tool: tools/eslaw.py (`on DATE PATH`, `log PATH`), not en_vigor_el.py. No future branch (295 future versions left out), no tags.

Every act in the gitlaw-ES brief is already there (commits touching each folder on main):

| Act | Path | Files | Commits |
| --- | --- | --- | --- |
| Constitución 1978 | estatal/constitucion/1978/BOE-A-1978-31229 | 211 | 5 |
| Código Civil | estatal/real-decreto/1889/BOE-A-1889-4763 | 2,445 | 77 |
| Código Penal (LO 10/1995) | estatal/ley-organica/1995/BOE-A-1995-25444 | 986 | 58 |
| LOPDGDD (LO 3/2018) | estatal/ley-organica/2018/BOE-A-2018-16673 | 170 | 7 |
| LEC (Ley 1/2000) | estatal/ley/2000/BOE-A-2000-323 | 1,084 | 94 |
| LECrim (1882) | estatal/real-decreto/1882/BOE-A-1882-6036 | 1,235 | 52 |
| Estatuto de los Trabajadores (RDL 2/2015) | estatal/real-decreto-legislativo/2015/BOE-A-2015-11430 | 179 | 46 |

## Why nothing was built here

- autopush discovers this folder as soon as `corpus.json` or `corpus.d/` exists, rebuilds the clone with
  gitlaw_common, and once `PUBLISH` exists force-pushes `main` with `--prune`. That would replace the 8,774-norm
  history with a 7-act one. So no corpus.json, corpus.d/ or PUBLISH has been written.
- Options for the coordinator:
  1. Keep the existing build as Spain's corpus (recommended: same source, far wider, checked clean) and only add
     `tools/en_vigor_el.py`, a future branch and tags through its own builder.
  2. Build the 7 acts with gitlaw_common into a different repo or path, preview only, never PUBLISH.
  3. Replace main (destructive; needs the user's go-ahead and the other session's agreement).

## Local state

- Clone: C:/Users/alany/Documents/spain-law (main at 513d8526e6, untouched).
- Cache: none. Requests made: 2 probes to the BOE API (metadatos and texto/indice for BOE-A-1978-31229), both HTTP 200.
- WebSearch calls used: 0 of 4.
