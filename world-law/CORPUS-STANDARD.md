# Corpus standard, v1 (draft, 2026-11-03)

What every country repository (`lexifina/<slug>-law`) must say about its dates and its law, so that global-law's
readers (`tools/law.py`, `tools/check_corpus.py`) and people reading plain git or GitHub get the same answers.

It closes four gaps found in the 3 November audit of the 710 pinned corpora:

| Gap | Measured |
|---|---|
| `Kind:` has no fixed list. It mixes what a commit *is* (a starting text, a correction) with what kind of instrument made it (decree, ustawa, legal notice). | 40+ values. `publisher` alone covers 129,168 commits in 434 corpora, and the shared builder writes it both for an act's starting text and for an unexplained change. |
| `Consolidated:` holds a date in some corpora (Switzerland, the global-law builder) and a URL in others. Corrections lack `Corrects:`. | A URL in 654 corpora. 519 Romanian corrections have no `Corrects:`. |
| Nothing says which corpora hold a history. | 341 current text only, 104 metadata only, 249 with a history. 603 corpora have no descriptor that global-law can read. |
| Dates live only in commit trailers. A download day is written as an in-force day. | 53 corpora put 30% or more of their commits on one day (22,887 commits; the Italian regions 100% on 30 Oct). |

**What it does not change.** History is never rewritten. Everything here applies to new commits and to regenerated
`data/` files. Those are documentation commits, appended by fast-forward. Readers keep reading old commits through
the mapping in section 6.

## 1. What a repository ships

| File | Status | Written by | Holds |
|---|---|---|---|
| `corpus.json` (repository root) | **required** | the builder, from the country folder | The descriptor: what this corpus is and how far its record reaches (section 2). |
| `data/acts.json` | **required** | the builder | One entry per act: its static facts (section 4). |
| `data/provisions.tsv` | **required** | the builder | One row per version of each provision file, with from, to and status (section 5). |
| `data/versions.json`, `data/laws.csv`, `data/commits.csv` | as today | the shared builder | Unchanged, plus the extra columns in section 5. |
| `data/repo.json` | deprecated | | Superseded by `corpus.json`. Keep it until the next rebuild, then drop it. |

Status: world-law-ops branch `reader-followups-dell` (head 52b31e8) already emits a root `corpus.json` with
`corpus`, `name`, `language`, `history` (`in-force` or `as-enacted`), `history_from`, `record_to`, `checked_on` and
`citation`, and it keeps a hand-made `repo/corpus.json`. What this standard adds to it: `path`, `scope`, `acts`, the
`history` values `current-only` and `metadata-only`, `future_branch` and `publisher`.

Note on names: the shared builder's **source** file in the country folder (`scripts/<slug>-law/corpus.json`, with
`laws`, `acts` and `versions`) is not the same file as the **descriptor** published at the repository root. The
builder must write the descriptor from its source. The two never have the same content.

The law files themselves carry **no dates and no metadata**: just a heading, then one paragraph per line. A date written in a
law file would turn every date correction into a text change, so `git blame` and diffs would credit lines to the
correction rather than to the law. Front matter, as Czechia uses it, is allowed only for an act's static facts (citation,
title, type, ELI), never for dates. New corpora put those facts in `data/acts.json` instead.

## 2. The descriptor: `corpus.json`

```json
{
  "corpus": "ro/national/acts",
  "path": "romania/national/acts",
  "name": "Romanian national legislation",
  "language": "ro",
  "history": "in-force",
  "scope": "selected-acts",
  "acts": 1873,
  "history_from": "1865-12-01",
  "record_to": "2026-11-01",
  "checked_on": "2026-11-02",
  "in_force_trailer": "In-force",
  "future_branch": "futuro",
  "publisher": "Portal Legislativ (Ministerul Justiției)",
  "record_note": "Optional: anything a reader must know about this record."
}
```

| Field | Required | Values |
|---|---|---|
| `corpus` | yes | ISO path `<iso2>/<level>/<kind>`, as now. |
| `path` | yes (new) | The folder in global-law, written out. The repoint loop places the corpus here, so it never guesses from the repo name (that is how `guinea/bissau`, `uae-dubai/national` and `united-states/cfr` happened). Levels are `national`, `federal`, `bund` or `union` (the EU) for the whole jurisdiction; a state or province by its English name; a municipality or regency as `<state>/<place>`. See the naming rule below. |
| `name`, `language` | yes | As now (ISO 639-1). |
| `history` | yes | One of `in-force` (dated versions from the source), `replayed` (rebuilt by applying the amending acts; add `verification`), `as-enacted`, `current-only` (today's text only) or **`metadata-only`** (new: no law text, only catalogue facts). |
| `scope` | yes (new) | `all-acts` (the whole body of law named in `name`) or `selected-acts`. |
| `acts` | yes (new) | The number of acts in the corpus. |
| `history_from` | yes | The first in-force day in the record. |
| `record_to` | yes | The day the record is complete to. After that, readers must say the record ends. |
| `checked_on` | yes | The day the text was last compared with the source. |
| `in_force_trailer` | only if not `In-force` | As now. |
| `future_branch` | yes | The branch that holds versions not yet in force. `main` holds none. |
| `publisher` | yes | The publisher's name, the same string the builder uses as author for its uncredited commits. |
| `record_note`, `citation`, `scope.default_reach`, `verification` | optional | As in MCP.md. |

### Folder naming rule (agreed 3 November, applied in the 173 moves of global-law main 1b8132e)

- A folder is named after the place, as a lowercase ASCII slug.
- A type word is kept only where it is part of the place's official name, or needed to tell two places apart:
  - `-city` is dropped for municipalities: `brazil/bahia/salvador/acts`, not `salvador-city`;
  - `-regency` is kept, because Indonesia has a kota X and a kabupaten X with the same name;
  - `-canton` is kept for the Bosnian cantons, whose official names are "Tuzla Canton" and so on.
- A first-level city keeps the name it is known by: `argentina/buenos-aires-city` (the Ciudad Autónoma, distinct from
  the province), `mexico/mexico-city`, `brazil/federal-district`. Vatican City is a country.
- A unit below a state sits under that state, as `country/state/place/acts`. The repo's own `jurisdiction.json` must
  give its real level and parent. A known data bug: the Indonesian sub-national template writes `"level": "country"` with no
  parent, for every province, regency and city (Yogyakarta, Central Java, Bojonegoro, Lamongan and the rest). The
  corpus-standard bundle sets the level and parent from the path in its single docs commit, and checks other
  countries' sub-national repos for the same fault.
- A moved corpus is listed in global-law `data/moved-paths.tsv`. Readers resolve the old path through it.
- **`jurisdiction.json` `level` is one of a closed list:**
  - `country`, or `supranational` (the EU), for top-level folders only;
  - `national`, `federal`, `bund`, `union` or `uk` for the whole-jurisdiction folder;
  - `state`, `province`, `region`, `canton`, `entity`, `territory`, `district`, `autonomous city` or
    `autonomous community` for first-level units, or `subdivision` when the source names no type;
  - `municipality` or `regency` below them.

  This list is what global-law's `tools/describe.py` writes since main 95b8164. Builders must write the same values.

  A place name is never a level. The audit of global-law 684c691 found 29 values in use, including
  `california`, `utah` and `northwest-territories`, and 142 folders below the top saying `country`.
- **`code`:**
  - ISO 3166-1 alpha-2 for a country;
  - ISO 3166-2 for a first-level unit, always with the country prefix (`US-CO`, not `CO`);
  - below that, the parent's code plus `-` and the place slug in capitals (`AR-B-ALBERTI`). These codes are not ISO,
    and readers must not present them as ISO;
  - a whole-country corpus takes the country's code (`united-states/federal/cfr` → `US`, `iso_path`
    `us/federal/cfr`).

## 3. Commit trailers

Every commit that writes law text carries a trailer block. Keys are case-sensitive. Each key appears once per commit,
except `Files:` and `Also-amended-by:`.

| Trailer | Required | Meaning |
|---|---|---|
| `Kind:` | yes | What the commit **is**: exactly one of the 8 kinds below. |
| `Law-kind:` | when `Kind: law` | What kind of instrument made it, from the list below. |
| `Law:` | when a law is named | The law's label, the same string as the commit author. |
| `In-force:` | yes, except `documentation` | The ISO day the text took effect. Never a download, build or publication day used as a stand-in. |
| `Text-as-of:` | when `In-force` isn't known | The ISO day the source showed this text (the capture day). See section 3.2. |
| `In-force-basis:` | required when `In-force` is a retrieval or capture day; otherwise recommended | One line on where `In-force` comes from: the gazette, a commencement clause, a legal notice, the `default_in_force_rule`, or `source gives no date` (next to `Text-as-of`). Nicaragua and the Micronesia corrections already write it; this is the standard key for it. |
| `Enacted:`, `Published:` | when known | ISO days. |
| `Source:` | yes | The URL of the law, or of the source page. |
| `Text-source:` | when the version has its own URL | The URL of the version the text was parsed from. **It replaces `Consolidated: <url>`.** |
| `Consolidated:` | read only | Kept for old commits. In new commits it may hold only an ISO date, or nothing. |
| `Corrects:`, `Supersedes:`, `Reason:`, `Act-path:`, `Files:` | for `Kind: correction` | The format agreed on 3 November (section 3.3). |
| `Affecting:`, `Words-changed:`, `Temporary-until:`, `Restores:`, `Also-amended-by:`, `Applies:` | as now | Unchanged. |
| `Credits:` | on a metadata-only correction whose version's credits changed (§5b) | One line per credited file: `Credits: <path> = <law label> <<evidence URL>>`, for example `Credits: lege/2003/571/art-047.md = Legea 343/2006 <https://…>`. Readers take that law as the file's author for the correction's `Corrects` range in blame, words and who_wrote. The commit's own author stays Lexifina. |
| `Retroactive:` | when `In-force` comes before `Enacted` | `yes`, plus the provision that says so. Without it, check_corpus warns. |

### 3.1 The 8 kinds

These are the same 8 that `tools/law.py` reads (agreed with global-law-fundamentals, 3 November).

| `Kind:` | Use for | Author | Readers treat it as |
|---|---|---|---|
| `law` | A change made by a named law, decree, regulation and so on. | The law's label | A law taking effect on `In-force`. |
| `baseline` | An act's first text when the law that made it isn't named: "oldest version available", a consolidation, or a current-text capture. | The publisher | Where the record starts. The text existed before; the record cannot say since when. Never "not yet in force" before it. |
| `correction` | A late-found or fixed version for days already in the record. | The publisher or the law | Overrides the ordinary version for its `Corrects:` days. |
| `uncredited` | A change to the words that no law is named for (today's "unexplained"). | The publisher | A change of text, not a law taking effect. Blame says "no law named". |
| `printing` | A printing or layout change with no change in meaning. | The publisher | Not a law. |
| `court` | A ruling that strikes, revives or conditions text. | The court and decision | Credited like a law; `Enacted:` is the decision day. |
| `treaty` | A treaty that becomes, or changes, domestic text. | The treaty | Credited like a law. |
| `documentation` | README, REPRODUCE, tools, data. | `Lexifina` | Never law. |

`Law-kind:` values: `constitution`, `constitutional-amendment`, `act`, `code`, `decree`, `decree-law`, `regulation`,
`ordinance`, `legal-notice`, `referendum`, `other`. The local name of the instrument (ustawa, zakon, lov, lbk, laki,
rozporządzenie, decreto, legge) goes in `Law:` and in `laws.csv` `label`, never in `Kind:`.

**What the shared builder changes:**
- For "oldest version available", write `Kind: baseline`.
- For "unexplained", write `Kind: uncredited`.
- A law's kind (`decree`, `referendum` and the rest) goes into `Law-kind:`, with `Kind: law`.
- A court ruling gets `Kind: court`, and a treaty `Kind: treaty`.

### 3.2 Dating rules

1. **`In-force` is when the text took effect.**
   - When the source gives only a publication day, apply the country's `default_in_force_rule` and record that in
     `decisions`, as gitlaw_common already requires.
2. **A text whose in-force day is unknown is a `baseline`.**
   - Write the capture day as `Text-as-of:`.
   - Write `In-force:` only if the source states a date this text has applied since ("en vigor desde", "Stand").
     Otherwise use the capture day, with `Text-as-of:` beside it.
   - Readers then say "the text as of D", not "in force from D".
   - This is the fix for the Italian regions, the Pakistani provinces and the US states that are now dated 29 or 30 October.
3. **`main` holds nothing in force after the build day.**
   - Later versions go to `future_branch`.
   - Today Kyrgyzstan has 498 such commits on main, Barbados 69, Florida 46 and Alabama 43.
4. **No in-force day before the act exists.**
   - An `In-force` earlier than `Enacted` needs `Retroactive:`.
   - A day before 1500 is refused unless the descriptor's `record_note` explains it.
   - France has 385 such versions today, for example year 881 for a 1988 decree.
5. **One commit per law per in-force day**, as gitlaw_common already builds it. When two laws change one file on the same
   day, each gets its own commit, in the order the source gives.
6. **An older act found later is appended as new commits.** Its files are new files. To put an older version of an
   EXISTING file into the history after newer ones, use a `correction`, never an ordinary commit.
7. **HEAD always shows the text in force today.** Some builders still append an older version of an existing file as an
   ordinary commit. That commit must be followed at once, in the same push, by a re-apply commit, which:
   - writes the current text back;
   - is credited to the law that made the current text, with that law's `In-force`;
   - carries `Kind: law` and `Re-applies: <commit that first wrote the current text>`.

   Readers then pick the right version by date (on a tie, the later commit), and blame credits no one for the
   unchanged words.

   Found 3 November: in romania-law, 26 of 160,787 files had an older version at HEAD, for example
   `lege/2003/571/art-047.md`, which showed its 2016 text while the 2023-01-06 version is in force.

### 3.3 Corrections (agreed format)

```
Kind: correction
In-force: 2026-09-01                  the first day corrected
Corrects: sb/2026/93 2026-09-01..     <act> <from>..<to>; an open end runs to the act's next ordinary commit
Supersedes: <commit>                  the version it replaces, if one
Reason: one sentence
Act-path: sb/2026/93                  the act's folder, when Files: is not given
Files: sb/2026/93.md                  one line per corrected file; may name a file whose text did not change
```

`Corrects:` is required. Without it, readers treat the commit as an ordinary version dated `In-force`.

## 4. `data/acts.json`

One entry per act. These are static facts that don't change from one version to the next.

```json
{"acts": [{
  "slug": "codul-civil", "path": "lege/2009/287",
  "id": "Legea nr. 287/2009", "eli": null,
  "title": "Codul civil", "short": "Codul civil",
  "law_kind": "code",
  "enacted": "2009-07-17", "published": "2009-07-24", "in_force": "2011-10-01",
  "repealed": null, "repealed_by": null,
  "status": "in force",
  "url": "https://legislatie.just.ro/…"
}]}
```

- `status` is one of `in force`, `repealed`, `expired`, `not yet in force` or `as captured` (for a `baseline` with no known in-force day).
- A repealed act keeps its files only if the source keeps them. Otherwise the repealing commit deletes them. Either
  way, `status` and `repealed` say so.
- This also settles Spain's repealed norms, which today are visible only in `no.md`.
- Romania's `data/acts.json` already has most of these fields; the other builders adopt the same shape.

## 5. `data/provisions.tsv`

One row per version of each provision file. Rows are sorted by `path`, then by `from`. The file is UTF-8, tab-separated, with a header row.

| Column | Meaning |
|---|---|
| `path` | File path in the corpus, for example `lege/2009/287/art-0001.md`. |
| `act` | Act slug, as in `data/acts.json`. |
| `from` | The day this version took effect (`In-force`), or for a `baseline` its `Text-as-of` day. |
| `to` | The last day it applied, or empty while it still applies. |
| `status` | `in force`, `replaced`, `repealed`, `expired` or `as captured`. |
| `kind` | One of the 8 kinds. |
| `law` | The law's label, or empty for `baseline` and `uncredited`. |
| `text_as_of` | The capture day, when the source showed this text. |
| `commit` | The corpus commit that wrote this version. |
| `text_source` | The URL the text was parsed from. |
| `sha256` | The sha256 of the source bytes, as `data/versions.json` records it. |

- **Generation:** the builder writes it from the same `versions` and `credits` that produce the commits. It is
  regenerated in the documentation commit that closes each push.
- **Why:** someone on GitHub, or anyone with plain git, can see a file's dates and status without running tools.
  `tools/law.py` reads it when present instead of rebuilding its index; France's index takes 88 s to rebuild. Readers
  fall back to the git log when it is missing or older than the pin.
- **Check:** `tools/check_corpus.py` compares it with the commits and warns on any difference.

Extra columns in the existing files:
- `data/laws.csv`: `law_kind`.
- `data/versions.json`: `to`, `status`, `text_as_of` for each version.
- `data/commits.csv`: `kind` uses the 8 kinds, plus `start`, which global-law readers treat as `law` or `baseline`
  according to whether the first version names a law.

## 5a. Images, tables and formulas that are part of the law

Found in the verify round (gitlaw-scraper-hp-omen, 3 November): every builder silently drops images. That includes:
- Norway: 1,159 in 117 acts, plus normative annexes;
- the Netherlands: 556, of which 552 are in the Omgevingsregeling;
- Liechtenstein: 71 in 13 acts (court-fee tables, interest formulas, timetables);
- Mongolia, Nauru, Paraguay, Garissa, Åland and Costa Rica.

Text-only checks can't see the loss.

1. **An image in the official text is law text.**
   - The bytes go in `<act>/assets/<sha256>.<ext>`, named by the sha256 of the source bytes. They are kept as
     published, never re-encoded, and marked `binary` in `.gitattributes`.
   - The provision file references each image at its place, with a relative link and the source's own caption or
     label: `![Table 1](assets/<sha256>.png)`.
   - Because files are named by their content, an unchanged image is stored once across versions. A changed image is a
     new file, and the link that changes in the provision text credits the law that changed it.
2. **An image that can't be kept gets a notice at its place, never a silent drop**, in this exact form:
   `[Image omitted: <source reference, e.g. official PDF p. 12>; <what it shows>; reason: <licence|not extractable|too large>]`
   An image over 25 MB counts as too large.
3. **Never OCR into law text.** A table or formula can be written as Markdown only when the source itself gives it as
   text. Otherwise keep the image. Searches can't see inside images, and readers must say so.
   - Keeping the image always meets the bar of "the image itself or a verified transcription". A transcription counts
     only where the source itself gives the same content as text.
   - Images come only from the same official source as the text, byte for byte, with their sha256 recorded.
   - **Completeness:** an act with an omitted normative image (a formula, table, map or schedule that is part of the
     law) does not count as complete, whatever the reason for the omission. It doesn't count toward the 95%
     completeness bar the builders report against. An omitted image that isn't normative (a logo, a decoration) doesn't
     count against it.
4. **`data/assets.tsv`** has one row per image file: `path`, `act`, `sha256`, `bytes`, `media_type`, `source_url`,
   `first_commit`. `data/acts.json` gives `images` and `images_omitted` for each act.
5. **Existing repos** get their images back through labelled corrections (`Kind: correction`, `Reason: image restored`,
   `Files:` the provision files, `Corrects:` the versions that held the image), never through rewrites.
   - The version in force today comes first.
   - Earlier versions that can't be restored keep an omission notice through the same correction.

## 5b. Credits proposed by a model (decided 3 November)

Where the source names no amending law, 132,948 commits are credited to the publisher. A model may propose which
law made each change, for example by reading the act's amendment notes. Its proposal is never law text, and it never
becomes a commit's author or `Law:` on its own. Instead:

1. A proposed credit is a build input, not published: `credits-proposed.tsv` in the country's build folder (settled
   4 November after the credits review; gitlaw_common `credits.py`, `README-credits.md`). Columns: `path`,
   `version_from` (the version's day, which names its commit), `proposed_law` (a key of the build's `laws`, the
   source of `data/laws.csv`), `evidence` (one line quoted from the source), `evidence_url`, `model`, `confidence`,
   `checked`.
2. It becomes a real credit only when a rule checks it: the proposed law exists; it was made by the version's day;
   that day is its commencement (the law's `in_force`/`commenced` day, or a commencement clause in the evidence,
   never a publication or retrieval day); the evidence names that provision and the law by its whole label; and the
   evidence URL is on a host the corpus already uses. A checked credit is then written as a metadata-only
   `correction` commit with a `Credits:` trailer and `Reason: credit found by a checked model proposal: <law>
   (<URL>)`, never by rewriting the original commit, and only after a reviewer signs its part off.
3. An unchecked or rejected proposal is never published, so readers never show one; they show "no law named".
4. `REPRODUCE.md` `ai_use` gives the counts for every run, by model: proposed, checked, rejected.

## 6. Reading old commits

How the `Kind:` values written before this standard map to the 8 kinds. This is also what `tools/law.py` reads.

| Written | Read as |
|---|---|
| empty, `law`, `decree`, `amendment`, `act`, `amending law`, `lov`, `lbk`, `laki`, `ustawa`, `zakon`, `rozporządzenie`, `legal notice`, `ordinance`, `several`, `enacted`, `original`, `version`, `repeal` | `law` |
| `baseline…`, `consolidated`, `current`, `current-only`, `current-text`, `consolidation`, `first published…`, `tekst jednolity (current text)` | `baseline` |
| `publisher` with the subject "oldest version available" | `baseline` |
| `publisher` with "(unexplained)" in the subject, or `Words-changed: yes` | `uncredited` |
| `unexplained`, `change no law explains`, `editorial…`, `notes only…`, `style only…`, `no act named…`, anything "… (not credited)" | `uncredited` |
| `court…` | `court` |
| `treaty` | `treaty` |
| `correction` with `Corrects:` | `correction` |
| `correction` without `Corrects:` | an ordinary version (Romania's 519) |
| `printing` | `printing` |
| `documentation`, or author `Lexifina` | `documentation` |
| anything else | `law`, with a caveat naming the kind |

`Consolidated:` is read as a date only when it holds an ISO date. Otherwise it is a source URL.

## 7. Checks (`tools/check_corpus.py`, warnings for corpora already pinned)

1. Each of these fields is present in the descriptor: `path`, `history`, `scope`, `acts`, `record_to`.
2. Every `Kind:` value is one of the 8 kinds (after the mapping in section 6, for old commits).
3. `In-force:` and `Text-as-of:` are ISO days, and a date-named trailer holds a date.
4. No `In-force` comes before `Enacted` without `Retroactive:`, and none comes before 1500.
5. Nothing on `main` is in force after `checked_on`.
6. No single day holds 30% or more of a corpus's law commits unless they are `baseline`.
7. Every correction has `Corrects:`.
8. `data/provisions.tsv` agrees with the commits.
9. The repo's `jurisdiction.json` level and parent agree with the descriptor's `path`. For example, a regency must not
   say level `country`.
10. For each act, the number of images in the source equals the images referenced plus the omission notices. Warn on
    any difference, and on any image file that no provision references.
11. Every file's text at HEAD equals the text in force on `checked_on` (rule 3.2.7). Fail for new commits; warn for
    pinned history.

New corpora fail check_corpus on items 1, 2, 3, 5, 7 and 10. Existing corpora get warnings until their next rebuild.
Item 10 also fails any new commit, in any corpus, that adds a version with more source images than referenced images
plus omission notices. History already pinned only warns.

## 8. Who does what

| Step | Owner |
|---|---|
| Write `Kind: baseline` / `uncredited` / `Law-kind:` / `Text-source:` / `Text-as-of:`; emit the root `corpus.json`, `data/acts.json` and `data/provisions.tsv`. This is one change, and with it a single new documentation commit in each repo. | gitlaw_common (shared builder). Bundle it with the held builder change (`reader-followups-dell`, 7b47fa5), so each repo takes one docs commit. |
| Read the 8 kinds, `Text-as-of`, and `data/provisions.tsv` when present. | global-law-fundamentals (`tools/law.py`, W2 and W4) |
| The checks in section 7. | check_corpus.py (W7) |
| Place each corpus by `corpus.json` `path`. | The repoint loop (global-law-main-composer) |
| Fix the dates themselves: capture days, France's early dates, laws not yet in force on main, credits to the publisher. | Each country builder, as labelled correction commits or the new trailers. Never by rewriting. |
