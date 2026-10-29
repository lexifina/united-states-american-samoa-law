# Estonia git-for-law: progress

Builder for the private repo `lexifina/estonia-law` (https://github.com/lexifina/estonia-law, PRIVATE; never make
it public). Local repo: `C:\Users\alany\Documents\estonia-law`. Shared rules: memory `git_for_law.md`; model is
`scripts/swiss-law`. Do not commit in the lexifina repo (user commits by hand).

## Acts (Riigi Teataja group ids, in `ACTS` in build.py)

- PS, Eesti Vabariigi põhiseadus: group 151381 (7 versions 2002-06-01..2026-03-01; first commit 1992-07-03)
- RKVS, Riigikogu valimise seadus: group 155356 (29 versions 2002-07-18..2024-10-01)
- IKS, Isikuandmete kaitse seadus: group 1045568 (6 versions 2019-01-15..2026-10-01)

Source API (found in the riigiteataja.ee SPA bundle; old `/akt/<id>.xml` URLs now return the SPA):
`https://www.riigiteataja.ee/public-api/api/v1/akt/<group>/redaktsioonid`, `/akt/<id>/xml`, `/akt/<id>/txt`.

## Cache

`scripts/estonia-law/.cache/` (self-gitignored, files named by sha256 of the URL). Holds every version list, every
version XML and txt, and the XML of every amending act. All builds run with `--offline` now. Retrieved 2026-10-28.

## Checklist

1. [x] build.py (fetch, parse, states, attribution, git writer, tables), seisuga.py tool, LICENSE, README (WIP note)
2. [x] reproduce.py (manifest data/versioonid.json + REPRODUCE.md; `--compare A B` records determinism)
3. [x] First build pushed (WIP).
4. [x] check_repo.py (fixed: signature stripped; now passes all) —: git vs XML passes for all 3 acts (0 mismatches); XML vs official txt passes for PS and RKVS;
   IKS algtekst version 104012019011 fails only on the trailing signature "Eiki Nestor / Riigikogu esimees" printed in
   the txt. Fix: in `note_texts()` also strip the signature (find where it is in the XML: maybe an HTMLKonteiner
   or `allkiri*` elements; or strip a trailing "<name>\nRiigikogu esimees" block in `official()`), then rerun.
5. [x] Determinism: build twice into empty scratch folders, then
   `python reproduce.py --compare A B` (writes verification.json 'determinism').
6. [x] `python -X utf8 check_repo.py --repo <A> --write` (writes verification.json 'check').
7. [x] Remove the WIP note from repo/README.md (and the "to be finished" in its check section).
8. [x] Final build into the real repo, rebuild into scratch, compare HEAD hashes again (should be identical),
   run check_repo on the real repo, then `git -C ../estonia-law push -f origin main --tags`.
9. [x] Report back to the coordinator.

## Commands (from scripts/estonia-law)

```sh
S=<scratch>; python -X utf8 build.py --offline --today 2026-10-28 --repo $S/ee-a
python -X utf8 build.py --offline --today 2026-10-28 --repo $S/ee-b
python reproduce.py --compare $S/ee-a $S/ee-b
python -X utf8 check_repo.py --repo $S/ee-a --write
python -X utf8 build.py --offline --today 2026-10-28 --repo C:/Users/alany/Documents/estonia-law
git -C C:/Users/alany/Documents/estonia-law push -f origin main --tags
```

## Known issues / decisions (all documented in REPRODUCE.md)

- 82 unexplained section changes in RKVS (typesetting, U+FFFD in RT's own XML for 3 versions, editorial removal of
  citation lists and spent amending provisions) and 1 in IKS (§ 75 replaced by "[Käesolevast tekstist välja jäetud.]"):
  committed by "Riigi Teataja", labelled, never credited to a law.
- RKVS § 48⁴ on 2017-01-01: marks name two acts; labelled commit by Riigi Teataja naming both.
- Two in-version days: PS § 156 dual wording (2005-10-17) and RKVS § 7(3) minister title (2014-07-01).
- Committer email is `estonia-law@lexifina.com` (corpus-named, as Swiss uses swiss-law@).

## Last pushed

FINAL: main cf1f1fd479d12242fd66bb5b97d93b71e196a300, law tip e161614 (59 commits, 87 tags), force-pushed 2026-10-28.
An independent rebuild gave the same main hash and tags; check_repo on the real repo: all checks passed.
