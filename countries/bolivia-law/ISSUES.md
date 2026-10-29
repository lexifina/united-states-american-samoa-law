# Builder issues found by gitlaw-BO

## 1. A no-words-changed law with a `note` still prints the "source lists this law" line (minor)

`change_message` prints "The source lists this law for the version from this day, but none of the words of the text changed." before the law's `note`, even when the note is given. For Bolivia's rejected 2016 referendum and the rulings SCP 0084/2017 and SCP 1010/2023-S4, no consolidated source "lists" them for a version. The event is recorded from the ruling and the CIDH report, so the line is misleading. Suggestion: skip that line when `law.note` is set, because the note already says that no words changed.

Seen in the commits 2eeee8b, 7a51a7c and 1024416 of the preview build (2026-10-28).

## 2. No-words-changed commits do not name the provisions they concern (minor)

SCHEMA.md says to credit such an event to the provisions it concerns in `credits`. `plan()` then makes the group with `keys = []`, so the commit has no `Affecting:` trailer and never names the provisions (for example art. 168). Workaround used: each law's `note` names the articles. Suggestion: for a law whose credited units are all unchanged, emit `Affecting: CPE Art. 168, ...` from the credited keys.

## 3. An event needs a full copy of the units (cosmetic)

SCHEMA.md says an event "needs a version (a `from` day) of its own only if the source has one". `plan()` only makes commits from `credits` of versions after the first, though. So an event on an act with a single version needs a version of its own, holding a full copy of the units. Bolivia does this for three events (corpus.json grows by about 3 x 400 KB), and `data/versions.json` then lists 4 versions of one text. Not blocking.

## 4. autopush does not rebuild when only PUBLISH or repo/ changes (scripts/south-america-law/autopush.py)

autopush skips a build when the sha256 of corpus.json matches `.autopush.json` `built_sha`. Creating `PUBLISH` at about 17:29Z therefore left main unpushed, and BUILD_STATUS showed "unchanged since 17:25:44Z (preview pushed 96649b9)". Edits to `repo/README.md` made after the last corpus write were also not picked up. Workaround: a real corpus change (new request counts from re-running parse.py). Suggestion: key the build on corpus.json + PUBLISH + every file under repo/.

**Fixed by the coordinator (2026-10-28):** (1) no boilerplate line when a law has a note; (2) no-words commits now carry Affecting: with the credited provisions and a subject naming them; (3) a version may omit `units` and then reads as the version before it; (4) autopush now rebuilds when repo/, PUBLISH or the shared builder change. All take effect on the next autopush pass.

## 5. One publisher identity per country (minor, 2026-10-29)

`country.publisher` is the only publisher, so an act read from a different official source is credited to it. Bolivia's Código Civil (corpus.d/50-codes.json) comes from SILEP (Vicepresidencia), but its "oldest version available" commit is authored "Gaceta Oficial del Estado Plurinacional de Bolivia". Acceptable here only because SILEP's page cites "Fuente: Gaceta". Suggestion: an optional `act.publisher` {name, email} used for that act's publisher and unexplained commits.

- 2026-10-29 coordinator: per-act `publisher` is now supported by the shared builder (SCHEMA.md, "Per-act publisher").
- **Resolved 2026-10-29 (gitlaw-publisher-fix):** `parse_codes.py` sets the Código Civil's `publisher` to SILEP (Vicepresidencia del Estado), `silep@silep.invalid`. Rebuilt in an empty scratch repo: the CC commit is now authored by SILEP (a8acb72, was 9255270); the four CPE commits are unchanged (97f3e54, ea30fb8, 348f22c, 91812d8); check.py 0 mismatches, 0 trailer errors; `--compare` identical. CLOSED.
