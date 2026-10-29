# American Samoa: law history in git

The in-force Revised Constitution of American Samoa as a git repository: one file per section, committed with the American Samoa Government as its publisher. It follows the shared design of [lexifina/global-law](https://github.com/lexifina/global-law).

**What is in it now**

| Folder | Act | Versions | History |
| --- | --- | ---: | --- |
| `constitution/` | Revised Constitution of American Samoa (in force since 1 July 1967, as amended) | 1 | One version: the text as it stood when the Government's marked draft of 6 September 2022 was made |

That is all the law this repository holds today. Nothing else of American Samoa's law (the American Samoa Code Annotated, regulations, court decisions) is in it.

## Where the text comes from

The only official copy found online is a **marked draft** on americansamoa.gov: the Revised Constitution with the proposed amendments of the 2022 Constitutional Convention shown in the text itself. New language is underlined and language to be deleted is struck through (the draft's own legend). The PDF's text layer mixes both kinds of words, so this build reads the marks from the PDF's drawing geometry (the thin rules beside each line of text) and keeps:

- unmarked words, and
- struck-through words, which are the words in force today.

Underlined words, the proposed new language, are **left out**. The draft's front matter (contents and the Convention's summary of amendments) and the Convention delegates' certificate are also left out; the Secretary of the Interior's attestation of 1967 is kept.

## Pending: the 2022 Constitutional Convention proposals (not in the text)

The Convention's marked proposals would, among other things: let the Governor appoint the Chief Justice and Associate Justices subject to Legislature confirmation (now the Secretary of the Interior appoints); bar the Secretary from reviewing High Court decisions and from approving veto overrides; add seats in the House (to 22) and Manu'a senators (to 5); give the Swains Island delegate a vote; add an impeachment process; and rename "Government of American Samoa" to "American Samoa Government". None of these is part of the text here. Whether any has taken effect (approval by the voters, the Secretary of the Interior and Congress) was not confirmed. If one has, the in-force text will change from the day it took effect, and a new version will be added then.

## Dates

- The single version is dated **6 September 2022**, the date printed on the source. It is the oldest version available: the Constitution took effect on 1 July 1967, but the draft is the only text archived here and does not say on which dates earlier amendments took effect, so no earlier history is given.
- The first commit is credited to the publisher as "oldest version available".

## What it does not show

- Any amendment history, and the Constitution as it stood before September 2022.
- Corrections by hand: a few places where the marks left a stray word or lost a full stop are repaired (listed in `REPRODUCE.md` under decisions). Source spellings, including "Section I." for Section 1 in Article II and "1aws" in Art. II Sec. 3, are kept.
- Nothing here is an official publication.

## How it is checked

- Every unit is read back from git on its day and compared with the corpus (`tools/check_repo.py`; results in `REPRODUCE.md`).
- The source is identified by its sha256, in `data/versions.json`.
