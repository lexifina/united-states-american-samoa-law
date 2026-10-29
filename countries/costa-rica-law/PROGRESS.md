# Costa Rica (gitlaw-CR): stopped, another session owns this country

Checked 2026-10-28 (gitlaw-CR, following WAVE.md / FORK.md rule 4 and the coordinator's instruction).

- lexifina/costa-rica-law is NOT a scaffold. Branches: `main` (scaffold commit f9df0439 plus 41d724be
  "Costa Rica: work in progress", 2026-10-28 20:12 UTC, README-only change), `wip` (head 4f82cd6c, 2188 commits)
  and `sync/main` (head b1dbbf04, 1221 commits).
- `wip` is a full SINALEVI build by another session: "77 norms (76 Leyes and 1 constitutions), 2550 versions",
  1880-04-27 to 2026-10-07, layout `constitucion/1949/` and `ley/<number>/`, tool `tools/in_force_on.py`,
  authors `<law>@sinalevi.invalid`, publisher `SINALEVI (Procuraduria General de la Republica)`. Its builder is
  not in this repo's `scripts/` (no *.py mentions sinalevi), so it lives in that session's own workspace.
- Therefore: no corpus.json, no corpus.d/, no PUBLISH written here. Nothing fetched beyond a probe of the
  SINALEVI home and search pages (about 8 requests; the new site is an ASP.NET/Kendo app, old SCIJ
  `nrm_texto_completo.aspx` URLs return 500 on pgrweb.go.cr and 404 on sinalevi.go.cr).
- Local clone at C:/Users/alany/Documents/costa-rica-law (untouched, origin/main checked out).
- Resume only if the coordinator reassigns Costa Rica; then coordinate with the owner of the `wip` build.
