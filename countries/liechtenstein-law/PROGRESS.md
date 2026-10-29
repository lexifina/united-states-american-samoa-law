# Liechtenstein git-for-law: progress

Private repo: https://github.com/lexifina/liechtenstein-law (PRIVATE, never make public). Local: `C:\Users\alany\Documents\liechtenstein-law`.
Builder: this folder. Rules: `memory/git_for_law.md`; model: `scripts/swiss-law/`.

## Acts (source: Lilex, https://www.gesetze.li)
- LV, Verfassung, LGBl. 1921 Nr. 15, LR 101: `https://www.gesetze.li/konso/1921015000/meta` (41 versions, 1921-10-24 to 2026-01-01)
- VRG, Volksrechtegesetz, LGBl. 1973 Nr. 50, LR 161: `.../konso/1973050000/meta` (19 versions, 1973 to 2012-12-01; Lilex has none later)
- StGHG, Staatsgerichtshofgesetz, LGBl. 2004 Nr. 32, LR 173.10: `.../konso/2004032000/meta` (9 versions, earliest text 2009-11-03)

## Cache
`scripts/liechtenstein-law/.cache/` (self-gitignored): one file per URL (sha256 of the URL, first 32 hex) holding the raw
bytes of the act meta pages, every `/konso/html/<id>?version=<n>` page and every `/chrono/html/<id>` page (plus some
unused `/chrono/<id>` pages from exploration). Retrieved 2026-10-28. All builds run with `--offline`.

## Checklist
1. [x] Research source, terms (no terms on gesetze.li beyond the "Rechtshinweis"; URG Art. 5 makes laws and official collections free), legalize-dev prior art
2. [x] build.py, reproduce.py, check_repo.py, repo/README.md, repo/LICENSE, repo/tools/stand_am.py
3. [x] First build pushed (force-pushed since; nothing pins this repo)
4. [x] check_repo: 69 versions (7628 files) 0 mismatches; 69 word-for-word, 0 mismatches (4 equal only with excerpt order by LGBl)
5. [x] Record check result: `python -X utf8 check_repo.py` (without --no-record) -> writes verification.json (~9 min)
6. [x] `python -X utf8 build.py --offline` (rebuild with verification.json), then `python -X utf8 build.py --offline --verify-rebuild` (records the rebuild result in verification.json)
7. [x] Remove the work-in-progress note from repo/README.md; `python -X utf8 build.py --offline` again (final); then `--verify-rebuild` once more must print main_identical true (do not record again, or rebuild after)
   - careful: --verify-rebuild rewrites verification.json; final sequence = check (record) -> build -> verify-rebuild (records) -> build -> verify-rebuild and confirm `main_identical: true` (its write is idempotent once stable)
8. [x] `cd C:\Users\alany\Documents\liechtenstein-law && git push -f origin main --tags`
9. [x] Final report to coordinator

## Last pushed
main 6b06cc1 (2026-10-28), final: check recorded (7628 files, 0 mismatches), rebuild hash-identical, WIP note removed. DONE.

## Known issues / decisions
- 55 file changes are "Änderung ohne Nachweis" (no footnote names a law of that version): Lilex's own spelling/punctuation fixes (e.g. "binnen14"/"binnen 14" flip-flops), VRG 2008 "im allgemeinen"->"im Allgemeinen", the LV renumberings of 2003 (art 99bis), VRG 82bis (1996), the removal of LV's transitional excerpts in 2009. Committed by "Rechtsdienst der Regierung (Lilex)", never credited to a law.
- LGBl. 1978 Nr. 3: Lilex and the printed gazette header say issued/in force 1977-01-11, before the law's date 1977-11-24. Kept as given, Date-note trailer.
- Two laws on one provision on one day (LV Art. 63 1989, Art. 93 2008): committed with the later LGBl, Also-amended-by trailer.
- Excerpts of amending laws at the end: Lilex orders them by in-force day, the repo/stand_am by LGBl number (StGHG 2018.271 vs 2018.211).
- Committer is `Lexifina <liechtenstein-law@lexifina.com>` (the per-corpus pattern used by swiss/uk/us repos).
- Pre-1970 commits clamped to 1970-01-01 UTC, seconds apart; stand_am reads the `In-force:` trailer.
