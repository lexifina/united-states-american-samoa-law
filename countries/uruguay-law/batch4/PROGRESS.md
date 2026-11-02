# gitlaw-UY-4: progress

Owner of `scripts/uruguay-law/corpus.d/70-batch4.json` (+ `70-batch4.PUBLISH`) and `scripts/uruguay-law/batch4/`.

- fetch: `python -X utf8 scripts/uruguay-law/batch4/fetch4.py [slugs]` or `--path P...` (one process; IMPO 10.5 s/request, robots Crawl-Delay 10; shared `.cache`). Log: batch4/.tmp/fetch.log.
- build the part: `python -X utf8 scripts/uruguay-law/batch4/batch4.py [slugs] [--dry]` (writes the part atomically + batch4/verification.json); `--vigencia <slug>` lists amending laws' days; `--count` IMPO paths needed/missing.
- batch4.py reuses batch2.build_one and batch 3's readings unchanged (re-installs batch3._install once with batch 4's original-text prefixes) and adds one reading in its own process: a run of incisos an earlier law added ("Incisos 2º), 3º) y 4º) anteriormente agregado/s por") is inserted like impo_history's single "Inciso 3º)", with an assertion that the text grew by exactly that many paragraphs (`inciso_runs`).

## Faster sources checked first (2026-10-29)
- legalize-dev/legalize-uy (cloned to scratchpad/uy4): 10,155 of 10,158 commits are `[bootstrap]` one-file snapshots of IMPO's consolidated text (2026), dated by the base law's publication, IMPO notes dropped; no code files. Words equal IMPO for 620/623 articles compared (18.331, 16.060, 17.250; the other 3 only append signatories). No history and no amending laws -> not used as a text source (decision recorded); not needed for discovery either (IMPO's notes give it).
- Common Crawl (6 crawls of 2026): HTML pages of IMPO only (8,281 under leyes-originales/, 206 under codigo-rural/), no `?json=true`; the rebuild reads IMPO's JSON notes, so not used.
- So all text is IMPO JSON, fetched live at the crawl delay: ~340 requests, about 1 h for all six acts (each act well under 45 min).

## Acts (candidates and choice)
- [x] Ley 18.381 (acceso a la información pública): 4 versions.
- [x] Ley 17.514 (violencia doméstica): 3 versions. (The brief's "Ley 18.172" is a Rendición de Cuentas, not a violence law; Ley 17.514 is the domestic-violence law 19.580 amends.)
- [x] Ley 19.580 (violencia hacia las mujeres basada en género): 7 versions.
- [x] Ley 19.574 (lavado de activos): 8 versions.
- [ ] Código de Minería (codigo-mineria/15242-1982, in force 1982-04-01 art. 135): fetching.
- [ ] Código Rural (codigo-rural/10024-1941, in force 1942-06-14 art. 291): queued.
- Skipped: Ley 16.736 (1996 budget law, 808 articles, 342 notes: well over 45 min and little standalone use). CGP already built (batch 2).

## Status
- 15:30Z: four laws written to 70-batch4.json; interim scratch build of 16 acts: check.py 0 mismatches, 0 trailer errors; all 189 published act tags have identical act trees.
