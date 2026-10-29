# Madagascar (gitlaw-MG) progress

Repo: lexifina/madagascar-law (private). tz Indian/Antananarivo, lang fr, future branch `futur`.
Clone (autopush owns it): C:/Users/alany/Documents/madagascar-law. Test builds: `.tmp-build/` (gitignored).

## Checklist
- [x] Probe (2026-10-28). Not a Peachjam LII country: the source is CNLEGIS (cnlegis.gov.mg), official, direct.
- [x] fetch.py: CNLEGIS search POST pairs + uploads, curl --compressed, sha256 cache, 1 req/s, requests.jsonl
- [x] parse.py (+ cnparse.py, the line/article parser from the earlier CNLEGIS build of this repo) -> corpus.json
- [x] Constitution: 4 versions (1998-04-10 baseline from LC 98-001; LC 2007-001; LC 2009-001 art. 15 replay; 2010)
- [x] Loi 2014-006 (cybercriminalité): 2 versions (as enacted 2014-09-10; art. 20 by Loi 2016-031, 2017-04-19, replay)
- [x] Loi 2014-038 (données personnelles): 1 version (as enacted 2015-07-22; CNLEGIS lists no amendment)
- [x] Code du travail: 2 versions (Loi 2003-044 HTML, 2005-02-23; Loi 2024-014 official PDF via pdftotext, 2024-11-06)
- [x] verify.py: letters-and-digits of each official text == units in source order (7 versions, incl. both Code du travail texts); the 2 replays change
      only the target unit and equal the quoted words. verification.json: all_equal true.
- [x] .tmp-build: check.py 0 mismatches / 0 trailer errors; --compare rebuild main_identical true (10 commits, 17 tags; 4 acts, 9 versions)
- [x] PUBLISH written
- [ ] Code pénal: not possible (see below)
- [ ] Phase 2: more acts with CNLEGIS "Modifié par" notes whose amendments are clean article replacements

## Sources
| Source | Status | Notes |
|---|---|---|
| cnlegis.gov.mg | 200, direct | robots.txt: GPTBot disallowed, `*` allowed. No terms of use published. Each record's official French HTML (`html_fichier_fr`) is in the search JSON; `notes` carry "Modifié par ..." amendment links; `etat_txt` "En vigueur". No consolidated texts, no dated versions: history = the acts themselves + replays. Texts since ~1998; older records have no HTML. |
| cnlegis.gov.mg/uploads/O62-041-VF.pdf | 200, text layer | Ordonnance 62-041 art. 3/4: the default in-force rule (one clear day after JO arrival; urgency on posting). |
| Code pénal | none | CNLEGIS has only amending laws (pre-1998 without text); 1 WebSearch found no official consolidated text-layer Code pénal (only a 1974 print via LLMC). |

Cache: ~3.5 MB, 32 requests. WebSearch used: 1 of 4. No archive.org / Common Crawl used.

## Notes
- The scaffold clone already held a Constitution history from an earlier CNLEGIS builder (its own tools/build.py;
  4 commits, same texts, same char counts 64369/59059/73921). The shared-builder build replaces it once PUBLISH is
  seen (force-push by autopush). File names change from `article-015.md` to `art-015.md`. global-law does not pin it.
- In-force days: JO date + 2 (earliest under Ord. 62-041 art. 3) where no clause; LC 2007-001 / 2009-001 urgency
  clauses -> promulgation day; 2010 Constitution art. 164 -> promulgation.

## Handoff (2026-10-29 00:40 UTC, run stopped)
- corpus.json = 4 acts, verified (verification.json all_equal), PUBLISH written. Autopush last pushed main 817637b (3 acts);
  the 4-act corpus builds clean locally (.tmp-build 3351757) and should reach main on the next autopush pass.
- Next step: Phase 2 below. No open bugs. No background processes running.
- Code de la communication (Loi 2016-029) blocked: its amendment Loi 2020-006 has no text on CNLEGIS (14-byte HTML).

## Phase 2 candidates
- Search CNLEGIS `notes` for "Modifié" chains on post-1998 laws with HTML (Loi 2014-025 signature électronique, as enacted; others via CNLEGIS notes).
