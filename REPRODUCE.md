# How this repository was made (American Samoa)

This file is written by the build on 2026-11-13, the day the source data was retrieved.

## Sources

| Source | Address | Retrieved | Licence |
| --- | --- | --- | --- |
| American Samoa Government: Revised Constitution with the 2022 Constitutional Convention proposed amendments (marked draft, 6 Sept 2022) | <https://www.americansamoa.gov/_files/ugd/4bfff9_637c7079564f4812ae2c848e48753e7d.pdf> | 2026-10-29 | Official government text; no reuse terms stated on the page. U.S. government works and official legislative texts are not subject to copyright protection. |
| American Samoa Government: Workmen's Compensation Commission reimbursement policy notice | <https://www.americansamoa.gov/_files/ugd/4bfff9_1bc87458e18b4a19a6a845ac583b39cd.pdf> | 2026-11-11 | Official government policy text; no reuse terms stated on the source page. |
| Secretary of American Samoa: American Samoa Administrative Code, 2024 edition | <https://www.osas.as/_files/ugd/4c56eb_f41f45536a644a6db0b7226f85244552.pdf> | 2026-11-13 | Official government rules text; no reuse terms stated on source pages. |
| Secretary of American Samoa: American Samoa Administrative Code, 2024 edition | <https://www.osas.as/_files/ugd/4c56eb_96385b11dd024dfcac532e3d1eab44f5.pdf> | 2026-11-13 | Official government rules text; no reuse terms stated on source pages. |
| Secretary of American Samoa: American Samoa Administrative Code, 2024 edition | <https://www.osas.as/_files/ugd/4c56eb_3051fa88218c4ddc9a687f45773305f5.pdf> | 2026-11-13 | Official government rules text; no reuse terms stated on source pages. |
| Secretary of American Samoa: American Samoa Administrative Code, 2024 edition | <https://www.osas.as/_files/ugd/4c56eb_4fb914c716a44aeaa5ee66c900750acb.pdf> | 2026-11-13 | Official government rules text; no reuse terms stated on source pages. |
| Secretary of American Samoa: American Samoa Administrative Code, 2024 edition | <https://www.osas.as/_files/ugd/4c56eb_ee7505b87f00426497c4e8d07f7d3318.pdf> | 2026-11-13 | Official government rules text; no reuse terms stated on source pages. |
| Secretary of American Samoa: American Samoa Administrative Code, 2024 edition | <https://www.osas.as/_files/ugd/4c56eb_c516ff39976742db9d5acfdabb2d7e11.pdf> | 2026-11-13 | Official government rules text; no reuse terms stated on source pages. |

Every word of law in this repository comes from these sources. Lexifina reads them and records each act's dated versions, and the laws that made each change, in one corpus file. This repository is built from that file.

## What is in it

| Act | Title | Versions | Span |
| --- | --- | ---: | --- |
| `constitution` | Revised Constitution of American Samoa | 1 | 2022-09-06 to 2022-09-06 |
| `workmen-compensation-travel-reimbursement` | Reimbursement Policy for Other Allowable Travel Expenses | 1 | 2023-01-09 to 2023-01-09 |
| `asac-02-03` | American Samoa Administrative Code, Title 2, Chapter 3 – Government Records Management | 1 | 1987-08-04 to 1987-08-04 |
| `asac-03-01` | American Samoa Administrative Code, Title 3, Chapter 1 – Election Contributions and Expenses | 1 | 1985-05-02 to 1985-05-02 |
| `asac-05-02` | American Samoa Administrative Code, Title 5, Chapter 2 – Economic Development Planning Commission | 1 | 1987-10-12 to 1987-10-12 |
| `asac-06-02` | American Samoa Administrative Code, Title 6, Chapter 2 – Rental Space of Market Place for Bingo Games | 1 | 1983-07-01 to 1983-07-01 |
| `asac-13-01` | American Samoa Administrative Code, Title 13, Chapter 1 – Student Financial Aid | 1 | 1988-05-25 to 1988-05-25 |
| `asac-13-02` | American Samoa Administrative Code, Title 13, Chapter 2 – Tuition Rates and Fees at American Samoa Community College | 1 | 1983-12-28 to 1983-12-28 |
| `asac-19-01` | American Samoa Administrative Code, Title 19, Chapter 1 – Commercial Transportation | 1 | 2023-07-19 to 2023-07-19 |
| `asac-19-02` | American Samoa Administrative Code, Title 19, Chapter 2 – Commercial Transportation Chapter 2 | 1 | 2023-07-19 to 2023-07-19 |

The build made 10 commits:

| Commits | Kind |
| ---: | --- |
| 10 | baseline texts where the record starts |
| 0 | named laws, court decisions and treaties |
| 0 | changes no amendment note explains, credited to the publisher |
| 0 | corrections to the existing record |
| 0 | printing or layout changes |

Other counts:
- 0 commits on the branch `future`: laws not yet in force on 2026-11-13.
- 0 commits dated 1 January 1970: in force before 1970, with the real day in their `In-force` trailer.
- 0 laws in the record.
- 10 tags.

## Dates

Each commit is dated at noon (Pacific/Pago_Pago) on the day the change took effect. The other dates, enacted and published, are trailers.

When a law gives no date of its own, the default rule applies: The Revised Constitution took effect on 1 July 1967 (Art. V, Sec. 11); this text is the in-force Constitution as it stood when the 2022 Constitutional Convention marked its proposed amendments. https://www.americansamoa.gov/_files/ugd/4bfff9_637c7079564f4812ae2c848e48753e7d.pdf

## How the history is built

`tools/build.py` turns the corpus into this history in one pass: one commit per law, on the day it took effect. The same corpus always gives the same commit hashes. `tools/check_repo.py` reads every version back from git and compares it with the corpus. `tools/on.py` shows the law as it stood on any date. The corpus format is described in `tools/SCHEMA.md`.

- Corpus: sha256 `d37750944a221d5d25045be8046526f5b7be763aaca0574eee5a423e62db2866` (249538 bytes).
- Builder blob hashes (`git hash-object`): `build.py` `63170edd89e92292ac248dae17d79e486e4e9f19`, `check.py` `e340718c28cd5b0edbe37bdeab1aac31427ada66`, `on.py` `4a8aa1c9a5e6bd8cc831b90a6e68c5a6f448a13c`.
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
- The Workmen's Compensation Commission approved the revisions on 7 December 2022; its notice dated 28 December 2022 expressly puts all changes into effect on 9 January 2023.
- One current source version; earlier reimbursement rules are not included. Native PDF text is preserved without word corrections; table row spans and column spans follow the published table. Page-number footers are omitted.
- Source images: zero normative images, zero referenced, zero omitted. Seven decorative letterhead images on notice page 1 are excluded.
- asac-02-03: one chapter snapshot from the Secretary's 2024 Code edition, dated 1987-08-04 from the chapter's express history note "eff 4 Aug. 87". Earlier wording is not reconstructed. Source front matter, history notes and native wording are retained. Source images 0, referenced 0, omitted 0.
- asac-03-01: one chapter snapshot from the Secretary's 2024 Code edition, dated 1985-05-02 from the chapter's express history note "eff 2 May 85". Earlier wording is not reconstructed. Source front matter, history notes and native wording are retained. Source images 0, referenced 0, omitted 0.
- asac-05-02: one chapter snapshot from the Secretary's 2024 Code edition, dated 1987-10-12 from the chapter's express history note "eff 12 Oct 87". Earlier wording is not reconstructed. Source front matter, history notes and native wording are retained. Source images 0, referenced 0, omitted 0.
- asac-06-02: one chapter snapshot from the Secretary's 2024 Code edition, dated 1983-07-01 from the chapter's express history note "eff 1 Jul 83". Earlier wording is not reconstructed. Source front matter, history notes and native wording are retained. Source images 0, referenced 0, omitted 0.
- asac-13-01: one chapter snapshot from the Secretary's 2024 Code edition, dated 1988-05-25 from the chapter's express history note "eff 25 May 88". Earlier wording is not reconstructed. Source front matter, history notes and native wording are retained. Source images 0, referenced 0, omitted 0.
- asac-13-02: one chapter snapshot from the Secretary's 2024 Code edition, dated 1983-12-28 from the chapter's express history note "eff 28 Dec 83". Earlier wording is not reconstructed. Source front matter, history notes and native wording are retained. Source images 0, referenced 0, omitted 0.
- asac-19-01: one chapter snapshot from the Secretary's 2024 Code edition, dated 2023-07-19 from the chapter's express history note "eff 19 July 2023". Earlier wording is not reconstructed. Source front matter, history notes and native wording are retained. Source images 0, referenced 0, omitted 0.
- asac-19-02: one chapter snapshot from the Secretary's 2024 Code edition, dated 2023-07-19 from the chapter's express history note "eff 19 July 2023". Earlier wording is not reconstructed. Source front matter, history notes and native wording are retained. Source images 0, referenced 0, omitted 0.

## What AI did and did not do

The source readers and builders were developed under Lexifina's direction with coding assistants, including Claude Code and Codex.

No model wrote, translated or corrected legal text. No model runs at build time. Every word of law in this repository comes from the official sources above.

The commit messages are written by `build.py` from the source data.

Model use at data-build time:
- none
- A model wrote the deterministic parser and inspected the native-text table layout; it did not author or correct legal wording.
- A model wrote the native-text extraction and validation scripts. No legal words were authored, corrected or transcribed from images.
