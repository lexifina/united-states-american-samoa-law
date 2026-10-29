# How this repository was made (American Samoa)

This file is written by the build on 2026-10-29, the day the source data was retrieved.

## Sources

| Source | Address | Retrieved | Licence |
| --- | --- | --- | --- |
| American Samoa Government: Revised Constitution with the 2022 Constitutional Convention proposed amendments (marked draft, 6 Sept 2022) | <https://www.americansamoa.gov/_files/ugd/4bfff9_637c7079564f4812ae2c848e48753e7d.pdf> | 2026-10-29 | Official government text; no reuse terms stated on the page. U.S. government works and official legislative texts are not subject to copyright protection. |

Every word of law in this repository comes from these sources. Lexifina reads them and records each act's dated versions, and the laws that made each change, in one corpus file. This repository is built from that file.

## What is in it

| Act | Title | Versions | Span |
| --- | --- | ---: | --- |
| `constitution` | Revised Constitution of American Samoa | 1 | 2022-09-06 to 2022-09-06 |

The build made 1 commits:

| Commits | Kind |
| ---: | --- |
| 1 | first version of an act |
| 0 | one law on its in-force day |
| 0 | changes no amendment note explains, credited to the publisher |

Other counts:
- 0 commits on the branch `future`: laws not yet in force on 2026-10-29.
- 0 commits dated 1 January 1970: in force before 1970, with the real day in their `In-force` trailer.
- 0 laws in the record.
- 1 tags.

## Dates

Each commit is dated at noon (Pacific/Pago_Pago) on the day the change took effect. The other dates, enacted and published, are trailers.

When a law gives no date of its own, the default rule applies: The Revised Constitution took effect on 1 July 1967 (Art. V, Sec. 11); this text is the in-force Constitution as it stood when the 2022 Constitutional Convention marked its proposed amendments. https://www.americansamoa.gov/_files/ugd/4bfff9_637c7079564f4812ae2c848e48753e7d.pdf

## How the history is built

`tools/build.py` turns the corpus into this history in one pass: one commit per law, on the day it took effect. The same corpus always gives the same commit hashes. `tools/check_repo.py` reads every version back from git and compares it with the corpus. `tools/on.py` shows the law as it stood on any date. The corpus format is described in `tools/SCHEMA.md`.

- Corpus: sha256 `5f4a62ff4ebbd72bf883291b900f1035e9638844824e5139058a1913db849ab2` (50985 bytes).
- Builder blob hashes (`git hash-object`): `build.py` `a4faa25af85facb64b956b372f6b528aafdd7ec1`, `check.py` `3e59cb6f05eccb94a9ec14431a7f6781221e83ef`, `on.py` `644a6c0857fbcc72562032b58d57aa113fee0641`.
- Python 3.12.10; git version 2.46.0.windows.1.

## Checks

Not yet run for this build.

No second build of this corpus has been compared yet.

## Decisions made by hand

- The source is a marked draft: new language underlined, language to be deleted struck through. The in-force text is the unmarked words plus the struck-through words; underlined words were dropped. Marks were read from the PDF drawing geometry (thin filled rectangles beside the text baseline: just below it is an underline, above it a strike-through), not from the text layer.
- The version is dated 2022-09-06, the date printed on the draft, as the oldest version available; the text was in force then, so far as the draft shows, and the proposals were unratified drafts.
- Front matter (table of contents, the Convention summary of amendments) and the draft certificate of the 2022 Convention delegates were left out; the attestation of the Secretary of the Interior is kept.
- Three places where the marks left a stray word or mark were repaired by hand against the rendered page: Art. II Sec. 4 "two one senators" became "two senators" (the new word "one" was not underlined), Art. II Sec. 2 "Faganeanea, :" became "Faganeanea:", and Art. II Sec. 9 "for his approval If" became "for his approval. If".
- Hyphenation at line ends was joined; spacing left by dropped words was closed up; sections are one unit each, with the preamble and each article heading as their own units. Source typos (for example "Section I." for Section 1) are kept.
- Where dropping an underlined run removed a paragraph end, the lost closing full stop was restored on the last paragraph of these sections: art-01-sec-12, art-03-sec-03, art-04-sec-11. The blanks of the oath (Art. V Sec. 6) were underlined spaces and are shown as ____.
- The 2022 proposals are recorded only as a pending note in the README; whether Congress or the Secretary of the Interior has approved any of them was not confirmed.

## What AI did and did not do

The scripts that read the sources and build this repository were written by Claude Code running Claude Opus 5.5 (`claude-opus-5-5`) under Lexifina's direction.

No model wrote, translated or corrected legal text. No model runs at build time. Every word of law in this repository comes from the official sources above.

The commit messages are written by `build.py` from the source data.

Model use at data-build time:
- none
