# Poland (gitlaw-PL): stopped on the coordinator's instruction, 2026-10-28

**Status: not building.** lexifina/poland-law `main` already holds another session's full build, so this folder
writes no corpus.json, no corpus.d and no PUBLISH, and autopush does not pick it up.

## What the existing repo holds (checked 2026-10-28 by cloning it to C:/Users/alany/Documents/poland-law)

- `main` head: `7c0f301` "Dokumentacja, tabele, narzędzia i REPRODUCE.md" (22 commits). There is also a `sync/main`
  branch (197b872) and tags per amending act (`du/1997-483`, `du/2001-319`, `du/2006-1471`, `du/2009-946`,
  `du/2012-161/...`, `du/2013-1650`, ...).
- **Acts:** Konstytucja RP (Dz.U. 1997 nr 78 poz. 483) and the citizenship act (ustawa o obywatelstwie polskim,
  Dz.U. 2012 poz. 161). There is **no Kodeks cywilny and no Kodeks karny**.
- **Builder:** its own, not the shared gitlaw_common one: `tools/build.py`, `src.py`, `parse.py` (API HTML units),
  `gloss.py` (unified-text footnotes give per-unit credits and in-force days), `pdfparse.py`, `check_repo.py`,
  `na_dzien.py` (on-date tool), `test_repo.py`, `reproduce.py`. Its REPRODUCE.md says the files came from
  `scripts/poland-law/` in the lexifina repo, but that folder did not exist when this session started.
- **Method:** one commit per amending act on its in-force day (noon Warsaw), author `Dz.U. YYYY poz. N`
  (`du-YYYY-N@sejm.invalid`); editorial changes of each tekst jednolity are commits by "Marszałek Sejmu"; the
  Constitution's 2006 and 2009 amendments replayed from their own words, the 2001 sprostowanie as its own commit.
- **Points for whoever owns it:** its REPRODUCE.md still shows check/rebuild steps as "(not yet run)"; the
  Constitution's 1997 checkpoint is labelled "OCR" (read from the 1997 scan's text layer), which needs a look under
  the no-OCR rule; no `jurisdiction.json`.

## What this session left here

- `fetch.py` (curl, sha256 cache, requests.jsonl, 3 req/s) and an empty `.cache/` from one probe. Nothing else.
- Probe findings, in case the codes are added later: the ELI API lists for Kodeks cywilny (DU/1964/93) 113
  amending acts, 25 TK rulings and 11 unified texts (2014/121 to 2026/795), and the 1964 text is available as HTML;
  for Kodeks karny (DU/1997/553) 122 amending acts, 28 TK rulings, 1 sprostowanie and 10 unified texts
  (2016/1137 to 2026/1342). `api.sejm.gov.pl/robots.txt` returns the gateway's "Request Rejected" page; ISAP
  sits behind an Incapsula challenge, which was not touched.
- WebSearch calls used: 0.
