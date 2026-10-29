# Italy (gitlaw-IT): stopped on the coordinator's instruction, 2026-10-28

**Status: stopped. No corpus.json, no corpus.d and no PUBLISH were written, and nothing was pushed.** Autopush ignores this
folder (italy is not in its country list and there is no corpus.json), so it leaves the repo alone.

## What lexifina/italy-law already holds (another session's full build)

- `main` = `38f884d` "Documentazione, tabelle, strumenti e REPRODUCE.md": 243 commits and 533 tags (`atto/...`,
  `<act>/<date>`). It is built by its own builder (`tools/build.py`, 987 lines, plus `check_repo.py`, `test_repo.py`,
  `vigente.py` and `reproduce.py`), not by `scripts/gitlaw_common`.
- Source: the Normattiva Open Data API (dati.normattiva.it, CC BY 4.0), multivigente exports in Akoma Ntoso and JSON,
  retrieved 2026-10-28. Changes are credited from Normattiva's per-article `articoliAggiornanti` records, with an
  `Evidence:` trailer on each commit.
- Acts: the Costituzione (28 versions), every legge costituzionale (prepared collection, 1947 to 2/2026), L. 300/1970
  (35 versions), L. 241/1990 (61), D.Lgs. 196/2003, the Codice privacy (59), and D.Lgs. 82/2005 (62).
- **Not in it: the Codice civile (R.D. 262/1942) or the Codice penale (R.D. 1398/1930).**
- `sync/main` = `8587cc9` is the world-law scaffold commit ("Italy: sources, before any law").
- Its REPRODUCE.md runs `scripts/italy-law/build.py`, but that folder isn't in this checkout and has no git history
  here, so the builder survives only as the copy in the repo's `tools/`.

## What this session did before stopping

- Backed up the clone: `C:/Users/alany/Documents/italy-law-prior-main.bundle`, holding all refs. The clone at
  `C:/Users/alany/Documents/italy-law` is untouched, and an exact copy of origin.
- `fetch.py`: the same Open Data async export, set up for the Costituzione, the Codice civile, the Codice penale and the
  Codice privacy. It was stopped mid-run.
  - Cached: `costituzione.zip` (873,754 bytes) and `costituzione-json.zip` (848,733 bytes). Their sizes match the
    prior build's, but the sha256 differs, presumably from export-time metadata in the zip.
  - Not finished: the Codice civile and Codice penale exports were still in state 2 (preparing) after several minutes.
    The Codice privacy export was never started.
  - 60 requests are logged in `.cache/requests.jsonl`.

## If Italy is resumed

The prior build is the base. The Codice civile and Codice penale are the gap. Either add them to the existing
builder's `SOURCES` (it says any Open Data act works), or port it into a `corpus.json`, but only on the coordinator's
decision: a PUBLISH here would force-push `main` and prune the existing 533 tags.
