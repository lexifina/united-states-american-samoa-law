---
name: small-country-law-repos
description: "Git-for-law private repos for small countries (Estonia, Liechtenstein, Luxembourg), started 2026-10-28; status, paths, and how to resume"
metadata:
  node_type: memory
  type: project
  originSessionId: 49bef9f7-2c1f-4f30-a0b0-ac70b21dbff7
  modified: 2026-10-28T15:27:58.513Z
---

On 2026-10-28 the user asked to "start on the private git repos for some of the smaller countries, using the standards already established". The standard is [[git-for-law]], with the Swiss build as the model ([[swiss-law-history]]). The countries were picked from the research register ([[world-law-sources]]) for official sources that have dated versions naming the amending law.

The builds were run by background sub-agents from session 49bef9f7. Each builder lives in the main repo under `scripts/<country>-law/` and is uncommitted ([[commits-by-hand]]). Each local repo is at `C:/Users/alany/Documents/<country>-law`. Each GitHub repo is PRIVATE under lexifina, and nothing pins it in global-law yet. Each folder also has `build.py` (takes `--today`), `reproduce.py`, `check_repo.py`, and `repo/` with README, LICENSE and tools.

**Luxembourg: DONE.** lexifina/luxembourg-law, main `765778d`, 121 commits and 183 tags.
- Source: Legilux XML, CC BY 4.0.
- Acts: the Constitution, from the 1868 text through 38 consolidations to 2026, and the Covid-19 law of 17 July 2020 with 32 versions. Most other laws keep only 2–3 versions on Legilux.
- The 2023 Constitution is one labelled replacement commit, credited to law A 29 (its Art. 4) and naming A 26–28.
- 4 typesetting commits and 1 unexplained commit ("Roi Grand-Duc" became "Grand-Duc", 2020-05-19) are authored by `Service central de législation (Legilux)`.
- 2 changes are credited by date only, and their commits say so.
- Pre-1970 commits are clamped to 1970-01-01; the real date is in the `In-force:` trailer.
- Checks: 5,661 article comparisons with 0 mismatches. Builds are deterministic: a third build reproduced `765778d`.
- The committer email is `luxembourg-law@lexifina.com`, as in the Swiss repo.
- Open: chapter headings appear only in the READMEs; law A 438 is retroactive, so it is dated before adoption.

**Estonia: DONE.** lexifina/estonia-law, main `cf1f1fd`, 59 commits and 87 tags.
- Source: Riigi Teataja's public API, `https://www.riigiteataja.ee/public-api/api/v1/akt/<group>/redaktsioonid` and `/akt/<id>/xml`. The old `/akt/<id>.xml` returns the single-page app.
- Acts: PS, the Constitution (group 151381; the 1992 original plus 7 versions); RKVS, the Riigikogu Election Act (155356; 29 versions); IKS, the Personal Data Protection Act (1045568; 6 versions).
- Causes come from amendment marks (muutmismärge) on each section dated that day.
- 83 unexplained section changes are labelled "Riigi Teataja" commits, mostly RKVS spacing, U+FFFD characters from the source, and editorial changes. One RKVS change has two candidate acts and is credited to neither.
- Checks: 4,670 files compared with 0 mismatches; 42 of 42 versions match the official text. Builds are deterministic.
- The committer is `estonia-law@`. The future-changes branch is `tulevik`. The text is exempt from copyright under AutÕS § 5 p 3.

**Liechtenstein: DONE.** lexifina/liechtenstein-law, main `6b06cc1`, 99 commits plus 1 documentation commit, 143 tags.
- Source: Lilex `/konso/<id>/meta`, `/konso/html/<id>?version=n` and `/chrono/html/<id>`.
- Acts: LV, the Verfassung (1921015000; 41 versions); VRG, the Volksrechtegesetz (1973050000; 19 versions); StGHG, the Staatsgerichtshofgesetz (2004032000; 9 versions).
- 55 file changes with no footnote naming a law are authored by `Rechtsdienst der Regierung (Lilex)`.
- Checks: 7,628 files with 0 mismatches, and 69 of 69 versions match word for word (4 equal only with the amending-law excerpts in LGBl order). The rebuild is hash-identical.
- check_repo.py now reads blobs through one `git cat-file --batch` per version (it used to run one `git show` per file); a full check takes about 7 minutes.

**Malta** belongs to another session (gitlaw-high-to-low): lexifina/malta-law, local `C:/Users/alany/Documents/malta-law`. Don't start it. Its versions on legislation.mt go back only to December 2020.

Not done for any of these:
- /watch reader pages
- adding them to global-law, which needs a coordinated rebuild and repin
- making any repo public, which happens only when the user says
