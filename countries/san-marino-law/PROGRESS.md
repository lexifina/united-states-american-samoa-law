# San Marino (gitlaw-SM): handoff, 2026-10-29 00:40 UTC

Repo lexifina/san-marino-law: scaffold verified 2026-10-28 (only `main`, one commit "San Marino: sources, before any law").
Clone: C:/Users/alany/Documents/san-marino-law (autopush owns it; never push from here). No PUBLISH yet.

## Done
- `fetch.py` (curl, cache `.cache/<sha256 url>`, log `.cache/requests.jsonl`), `laws.py` (archive search by number+year
  -> scheda -> original PDF; `pdf_text`), `parse.py` (cache only -> `corpus.json`, atomic).
- corpus.json: Dichiarazione dei Diritti (L. 59/1974) as ONE "oldest version available" version, 20 units, dated
  2025-10-11 (LC 2/2025 in force). Test build in `.tmp-build`: check.py 0 mismatches.
- Cached: testi coordinati index, all Phase 1 ZIPs, original PDFs + schede of every Dichiarazione amending law.

## Sources
- consigliograndeegenerale.sm (Segreteria Istituzionale). Testi coordinati: `/on-line/documento<ID>.html` returns a ZIP of
  two text-layer PDFs: "SENZA NOTE" (current text) and the annotated one, whose notes give per provision
  "Testo originario (Legge n.X/Y)" + "Modifiche legislative" quoting every amending provision in order -> replayable.
  Archive original texts (PDF, text layer, even 1974) via scheda pages. No point-in-time versions online.
- Dichiarazione documento17085085 (agg. 26-09-2025); Codice Penale documento17088264 (agg. 27-02-2026, 271 notes);
  dati personali L.171/2018 documento17131845 (agg. 15-09-2023: check for later amendments).

## In-force dates found (Dichiarazione)
- L.59/1974: Albo 17-07-1974, no vigenza clause -> 1974-07-17. L.95/2000: addì 21-09-2000, +5. L.36/2002: addì
  28-02-2002, +15. LC 61/2005: addì 02-05-2005, +5. LRC 182/2005: with LC 183/2005 (addì 29-12-2005, +15 -> 2006-01-13).
  LC 1/2011: pubbl 25-07-2011, +15 -> 2011-08-09. LRC 1/2019: from DR 93/2019 pubbl 04-06-2019. LC 2/2025: pubbl
  26-09-2025, +15 -> 2025-10-11. Pre-2011 laws give only the promulgation ("addì") date, not the Albo date: say so.

## Next step to resume
1. Dichiarazione history: v1 = 1974 PDF text (19164leggi_2695.pdf); replay states from the quoted texts in the amending
   laws' PDFs (36/2002 arts 1-8, 95/2000, LC 61/2005, LC 1/2011, LC 2/2025 = current); the last state of each article
   = current text. Verify end state == SENZA NOTE text, then write PUBLISH (recheck scaffold first).
2. L.171/2018 and Codice Penale the same way (parse notes; full-article replacements automatic, others by hand or
   placeholder per BRIEF rule).
