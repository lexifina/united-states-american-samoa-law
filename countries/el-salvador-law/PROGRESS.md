# El Salvador (gitlaw-SV): progress

Agent: gitlaw-SV, 2026-10-28/29. Stopped at the 00:44 UTC wind-down while still probing sources.

## Status

- [x] Scaffold check: `lexifina/el-salvador-law` main = 14420b2 "El Salvador: sources, before any law" only (checked 2026-10-28). Clone at `C:/Users/alany/Documents/el-salvador-law` (scaffold only, untouched).
- [ ] fetch.py / parse.py: not written.
- [ ] corpus.json: none. No build, no PUBLISH.
- Phase 1 target: Constitución 1983 + reform acuerdos, Código Penal (DL 1030/1997), Código Civil (1860).

## Probe results (asamblea.gob.sv, 2026-10-28, about 10 requests)

- robots.txt: standard Drupal 9; only /admin, /search, /user, /core, /profiles disallowed. Legislation paths are allowed.
- `/leyes-y-decretos/constitucion` (200): links the consolidated PDF
  `https://www.asamblea.gob.sv/sites/default/files/2026-05/1.%20CONSTITUCI%C3%93N%20DE%20LA%20REP%C3%9ABLICA.pdf` (not yet fetched; check text layer).
- `/leyes-y-decretos/acuerdos-de-reforma-a-la-constitucion` (200): tables filled by DataTables from
  `/leyes-y-decretos/acuerdos-reforma-constitucion-ajax?estado=R|P|N` (Ratificados / Pendientes / No ratificados; found in the aggregated JS, library `legislacion/acuerdos.datatable`).
  Those endpoints returned **HTTP 500** ("The website encountered an unexpected error") to curl. Next try: add `X-Requested-With: XMLHttpRequest` and a Referer of the acuerdos page; DataTables may also send `draw/start/length` params. Otherwise use Common Crawl / Wayback captures of the ajax URL.
- `/leyes-y-decretos/busqueda-decretos` is the Índice Legislativo search (not yet probed). Old Índice detail pages were `/decretos/details/<id>` with a reform list (Diario Oficial number, tomo, date) and per-reform documents; check whether they still exist or use Common Crawl captures.
- Probe files are in `.cache/probe/` (gitignored).

## Next steps

1. Get the acuerdos list (ajax with XHR headers, or CC/Wayback). Each row has acuerdo no., emission date, publication date, acuerdo doc and ratification decree.
2. Probe busqueda-decretos for Código Penal and Código Civil detail pages; record whether each reform has its own text (PDF/DOC with text layer) and DO dates.
3. Imprenta Nacional Diario Oficial (imprentanacional.gob.sv) PDFs for reform texts where the Asamblea lacks them; no OCR on scans.
4. Default in-force rule: Cn. art. 140: a law takes effect 8 days after publication in the Diario Oficial unless it says otherwise (verify text from the PDF before citing).
5. History must be rebuilt by replaying reforms against the consolidated text (source has no point-in-time versions); check replay end to end.

## Open issues

- Ajax 500 above. No WebSearch calls used (0 of 3).
