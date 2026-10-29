# Changelog and improvement log

What has changed in how the corpora in this tree are collected, stored and checked, what testing found, and where each finding stands. The newest entries are first. Each entry names the corpus it concerns: US (`us/federal/usc`), Germany (`de/bund/grundgesetz`), UK (`gb/uk/send`), Switzerland (lexifina/swiss-law, not yet in this tree), or all.

Status words:
- **Fixed:** done in the corpus build or here.
- **Adopted:** a rule every corpus now follows.
- **Open:** found and reported, not yet fixed.
- **Checked:** a test that passed.

## 28 October 2026

- **Fixed (UK). Modifications not in the register are recorded by hand.** These are changes that leave the words alone and were made by notice rather than legislation. The s. 42 notices are the first: 1–31 May (signed 28 April), 1–30 June and 1–31 July 2020, under the Coronavirus Act 2020 s. 38 and Sch. 17 para. 5(6). They follow gitlaw-contracts' proposed shape:
  - Empty commits, authored by the Secretary of State for Education, with `Modifies: <provision> | modified | <from>..<to> | <effect> | set-by <authority>`, `Words-changed: no` and `Curated: yes`, plus the sources.
  - A closing commit on 1 August 2020 with `Modification-ended:`.
  - The source data is `tools/curated/modifications.json`, and `uklaw.py on` notes a modification in force on the date asked about.
  - Consecutive notices end once, after the last.
- **Fixed (UK). A version check that only looks at days with a commit hides mismatches.** A published version that changes nothing in a document has no commit of its own day. The check now compares it with the latest commit up to that day. That raised the UK test from 91 to 130 versions checked, and it found 2 real mismatches. Both were days when only a heading or the arrangement changed, which the writer did not commit. Those are now committed under legislation.gov.uk, and all 130 match. The check reads through one `git cat-file --batch`, following Germany's advice. **Every corpus should check every published version, not just the days it committed.**
- **Open (UK, in progress).** The UK corpus is being rebuilt to cover all UK legislation on legislation.gov.uk (about 200,000 documents: Acts of the UK, Scottish, Welsh and NI legislatures, older Acts, local Acts, and UK, Scottish, Welsh and NI statutory instruments). The layout is one file per document at its URI (`ukpga/2014/6.md`), written by `git fast-import`. The harvest is resumable and rate-limited. Until the rebuild is pushed, `gb/uk/send` stays pinned as it is.
- **Fixed (UK, in the rebuild).** First commits carry `Enacted:`, `Made:` or `Text-as-at:`, never `In-force:`. A temporary change that ends is credited to its instrument, with `Temporary-change-ended:`. A register entry that names no provision ("blanket amendment", "Act") can explain any provision of its document that changed that day. Subjects are cut to 72 characters. The README gives `--before="YYYY-MM-DDT23:59:59Z"` and points to `tools/uklaw.py on <date> <doc> [provision]`, which picks the version by trailer.
- **Checked (UK).** The writer's `--verify` check: at the end of each day, every changed document equals the publisher's version for that day. On a five-document test (108 commits), 101 of 101 versions were identical.
- **Fixed (UK).** Large documents are built provision by provision and then compared with legislation.gov.uk's own whole-document text for every dated version. For the Children and Families Act 2014, all 34 versions match in words and structure. Three faults were found and fixed: a provision before its first dated version takes its earliest revised text; a provision inserted later is absent before then; a provision published only as prospective reads as now. One kind of difference remains: whether a provision is marked as not yet in force before its first dated version (s. 130, 9 of 34 versions). The two provision-level files give no reliable way to tell those cases apart, so the rate will be measured on a sample and reported in REPRODUCE.md.
- **Adopted (UK).** From the US finding: a listed version that does not load is recorded in the document's metadata (`missing_versions`), never silently replaced by another version.
- **Fixed (UK, partly).** Savings and transitional provisions now use the grouped scope shape. The harvest keeps each register entry's `Savings` and `CommencementAuthority` references (87 and 94 of the Children and Families Act 2014's 674 entries). Each commit carries `Applies: <provision> | subset: as a saving or transitional provision allows | set-by <saving's URL>` and `Commenced-by: <URL>`. **Still open:** the conditions themselves (dates, classes of case) are in the words of the saving provisions and are not yet parsed into `commenced_before` / `pending_on` kinds.
- **Adopted (UK).** The README tells clones to run `git fetch --force --tags origin && git reset --hard origin/main` after a rebuild, from gitlaw-contracts' tag finding.

### Germany (de/bund/grundgesetz; federal law to follow)

- **Fixed (Germany).** Rebuilt and force-pushed at `5bb57fa`. The source is now DocPatch's own repository (c3e/grundgesetz-dev) instead of its 2018 generated snapshot. The snapshot lacked Arts. 104c and 143e–g, created by the 62nd amending law, and the 63rd amending law.
- **Fixed (Germany).** DocPatch's text was compared with the official consolidated text (Gesetze im Internet) at the same point, the 63rd amending law in 2019. 43 articles differed. Examples:
  - Art. 3(3) lacks the 1994 disability sentence.
  - Art. 76 has "drei Monaten" where the official text has "sechs Wochen".
  - Art. 104a keeps a sentence the 2006 reform deleted.
  - Art. 143c lacks its paragraph 4.
  - Art. 120 has 1969 for 1965.

  For each, the official text replaces DocPatch's from the article's last change on. Every case is listed in KORREKTUREN.md.
- **Fixed (Germany).** The 64th to 69th amending laws come from the official text in QuantLaw's daily archive, article by article, with dates from the Bundestag's Datenhandbuch (ch. 13.2) checked against the laws. The final text matches today's official Grundgesetz in all 206 articles.
- **Fixed (Germany).** The expiry of Art. 143h on 31 December 2020 (Art. 2 Satz 2 of the 65th amending law, BGBl. I 2020 S. 2048) is a commit of its own. The Datenhandbuch's "31.12.2021" is an error. Gesetze im Internet's later fix of its own text (Art. 87a, 14 September 2022: "für die Bundeswehr" restored) is folded back into the version of the law that wrote it, with a correction note.
- **Fixed (Germany).** Trailer keys are ASCII (`Verkuendet:`). The `ü` had made git reject every trailer (reported by gitlaw-contracts). Subjects are now 72 characters or fewer.
- **Adopted (Germany).**
  - REPRODUCE.md is generated by the builder.
  - `--docs-date` is required.
  - The builder refuses a non-empty foreign target and keeps `origin`.
  - Two builds gave an identical HEAD.
- **Checked (Germany).** `tools/stand_am.py` answers correctly for 8 articles at 9 dates: Art. 23 is absent on 3 October 1990 and back in 1993; Art. 143h is absent in 2021 and present in 2025.
- **Open (Germany).** Versions older than each article's last change before 2019 are DocPatch's transcription, not checked against the Bundesgesetzblatt.
- **Open (Germany, in progress).** All German federal law, about 6,600 acts, from QuantLaw's archive of Gesetze im Internet. History starts at its first real scrape, 10 June 2019 (the 2018 "init" commit is empty). The history is written with `git fast-import`. Each change is credited to the amending law in the act's "Stand" note, and a change with no new Stand note gets its own label.

### US (us/federal/usc)

- **Open (US).** Building the whole Code, titles 1 to 54 (53 is reserved; the appendices are left out), with every fix below. It runs as two resumable workers, and the repository will be rebuilt, force-pushed and repinned here when they finish.
- **Fixed (US).** The §104 dollar-adjustment parser filed every older Federal Register notice under the newest (87 F.R. 6625). Each entry now stops at the next "By notice dated", so the 2019 notice, 84 F.R. 3488 effective 1 April 2019, is its own entry. Adjusted amounts stay out of the text, because the Code prints the enacted amounts.
- **Fixed (US).** When the newest release point is listed before its files are published (119-136, whose files returned 404), the build silently dropped it and the release point before it, so titles ended at an older version. It now falls back to the newest release point that loads.
- **Fixed (US, also in the reader).** A printed version can hold a change waiting on a condition, a live change and a sunset of the first. The text on a date was replayed only up to the first change not in force, which also threw away the live change after it (11 U.S.C. §1325 in 2022). Every step is now replayed, with the step that inserted and the step that removed each line tracked, and the lines whose changes are in force are shown. All tags now match the printed text except where a change was printed before it took effect (edition-2019).
- **Fixed (US).** A section that leaves the Code keeps a file saying so, credited to the law that repealed it, instead of disappearing (3 U.S.C. §2 and §14).
- **Fixed (US).** Markdown formatting characters in the text are escaped, so "the symbol \*M\*" in 17 U.S.C. §909 no longer renders in italics.
- **Adopted (US).** `tools/uscode.py` (`on`, `diff`, `log`, `commit`) reads the history by In-force trailer, so date queries don't depend on time zone or time of day. It also handles dates before the history starts.
- **Adopted (US).** `Applies:` trailers, one line per group of cases with every condition and the provision that set it, for example `Applies: 11 U.S.C. §1182(1) | commenced-on-or-after 2020-03-27; commenced-before 2022-06-21; pending-on 2022-06-21 | set-by Pub. L. 117-151, §2(h)(2)`.
- **Adopted (US).** The generator works one section at a time with a content store on disk, refuses a target folder that is neither empty nor an earlier build, and puts the data in a release archive when it is too large to commit. The checker reads through `git cat-file --batch` and checks the nine titles in 23 seconds.

### Switzerland (lexifina/swiss-law)

- **Fixed (Switzerland).** On-date reads on the future-changes branch `kuenftig` returned future text for days between the build and the change, because the merge of `main` into `kuenftig` is dated the build day but already holds the later changes. `tools/stand_am.py` and `tools/check_repo.py` now use `git log --no-merges`.
- **Checked (Switzerland).** Every article version is read back from git on the day it took effect, and the version before it on the day before, then compared with the reader's data. With three acts: 767 checks, 0 mismatches. A second build from the same data gave identical hashes for `main` and `kuenftig`.
- **Fixed (Switzerland).** Publisher typesetting no longer counts as a change: "..." against "…", a literal "[tab]", and old `<sup>1)</sup>` footnote markers. Before the fix, these produced 28 false changes, some credited to whichever act took effect that day.
- **Fixed (Switzerland).** A change is dated by its own entry into force, from the footnote on that article or Fedlex's impact record for that article, not by the consolidated version where it first appears. For acts with structured text for only some versions, the two can be a year or more apart: SchKG Art. 6 is in force from 1 January 2020 and first appears in the version of 20 October 2020.
- **Adopted (Switzerland).** Where the wording changed but no impact record or footnote names an act, the change is labelled a correction by the publisher, committed by `Bundeskanzlei (Fedlex)` and never credited to a law.
- **Adopted (Switzerland).** The first structured version of each act has a `Consolidated:` trailer, not `In-force:`, because nothing came into force that day. Commit subjects longer than 72 characters become "N Artikel".
- **Fixed (Switzerland).** Fedlex SPARQL limits:
  - A filter on an impact's target address scans every impact, and the firewall answers HTTP 400. Impacts are read through `jolux:legalResourceSubdivisionIsPartOf`.
  - A single query over every consolidated version answers HTTP 500, so versions are read a year at a time.
- **Open (Switzerland).** Moving from three acts to the whole Classified Compilation: about 5,900 acts and treaties with German Akoma Ntoso versions, 12,182 versions in all. The repository will use one folder per SR number and git fast-import, with a tag for each amending act only.
- **Open (Switzerland).** Transitional rules (Übergangsbestimmungen) are not modelled. They will come from the amending acts' Official Compilation texts in Akoma Ntoso, stored as scope groups.

### Applicability: who a change applies to

- **Adopted (all).** Applicability is stored as groups of conditions, not as one date.
  - Each change has `in_force`; `applies_from` when application starts later than entry into force (the EU's EV and MA dates, such as the GDPR's 24 May 2016 and 25 May 2018); and `scope`, a list of groups.
  - Each group is `{conditions: [{kind, date}], words, set_by}`. Kinds are `commenced_on_or_after`, `commenced_before`, `pending_on` and `subset` (a described class of cases).
  - A case is covered if it meets every condition in at least one group: groups are alternatives (OR), conditions within a group all apply (AND).
  - Corpora write one trailer per group: `Applies: <provision> | <condition>; <condition> | set-by <provision>`.
  - "Shall not apply to cases commenced before D" is stored as `commenced_on_or_after D`.
  - Why groups: Pub. L. 117-151 §2(h)(2) reaches (a) cases commenced on or after 27 March 2020, or (b) cases commenced between that day and 20 June 2022 that were still pending on 21 June 2022. A flat list would make "pending" a condition on every case.
  - The shape follows Akoma Ntoso's `scopeMod` and `efficacyMod`. No official source surveyed publishes such conditions as data: the EU types its dates only, LegalDocML.de marks validity periods, and Fedlex JOLux gives an entry-into-force date and status.
- **Fixed (US).** 16 changes from 3 laws had a condition in the effective-date note that the structured data dropped:
  - Pub. L. 117-151 §2(h)(2), "pending on June 21, 2022".
  - Pub. L. 118-42 §544(b)(2): the §507(d) change does not apply to cases commenced before 9 March 2024. It is now `commenced_on_or_after 2024-03-09`.
  - Pub. L. 116-136.
- **Fixed (US).** Effective-date notes were attached to every change a law made in a section, even when the note concerns a different provision.
  - The CARES Act note "shall apply to any case commenced before, on, or after the date of enactment" (§1113(b)(1)(D)(i), for §101(10A)) sat on the §101(51D)(B)(iii) change made by §1113(a)(4). That would have made the 51D change retroactive.
  - Notes now reach only the changes they name. **All corpora:** key effective-date and commencement rules to the provision they name, not the section or the Act.
- **Open (Switzerland).** Transitional rules (Übergangsbestimmungen) are not modelled yet. They will come from the amending acts' Official Compilation texts in Akoma Ntoso, in the shape above.
- **Open (UK).** Commencement savings and transitional provisions should be checked against the same shape.

### Same words, different law

- **Fixed (UK).** The s. 42 "reasonable endeavours" notices are now three empty commits, for May, June and July 2020, each authored "Secretary of State for Education" with `In-force:`, `Modifies:`, `Words-changed: no` and `Curated: yes`. The authority is the Coronavirus Act 2020 s. 38 and Sch. 17 para. 5(6), a power in force from 25 March 2020 until it expired early on 9 December 2021 (S.I. 2021/1399). A closing commit on 1 August 2020 carries `Modification-ended:` and `Modifies: … | ended | …`. The data, with sources, is in `tools/curated/modifications.json`, and `uklaw.py on 2020-06-15 …` notes the modification.
- **Fixed (US, lands with the full-Code rebuild).** Each §104 notice is an empty commit on its effective date, authored "Judicial Conference of the United States", with `Words-changed: no` and one `Modifies: … | amount-adjusted | …` line per provision (several amounts joined by "; "). Files keep the printed amounts; `tools/uscode.py on DATE PATH` prints the applicable amounts on stderr. The rebuild also carries the adjustment parser fix, so each notice gets its own clauses (2019: 84 F.R. 3488). Each range closes the day before the next notice for the same provision (for example 2022-04-01..2025-03-31 under 87 F.R. 6625, then 2025-04-01.. under 90 F.R. 8941); only the newest stays open. For corpora that only append, the latest effect per provision and kind wins.
- **Proposed (all; gitlaw-global to settle).** A `Modifies:` trailer for law that changes while its words stay the same, one line per effect: `Modifies: <provision> | <modified|disapplied|amount-adjusted|applied-with-modifications> | <from>..<until|open> | <effect in words> | set-by <source>`. It goes on an empty commit on the start date, with `Words-changed: no`; an open-ended effect gets a closing empty commit when it ends. The UK implementation adds an `ended` kind for closing commits and a `Curated: yes` trailer for effects entered by hand from cited sources. Reach-backs use the existing `Applies:` groups. Empty commits do not appear in `git log -- <path>`, so tools index the trailer instead (`git log --grep`). For the MCP server's read_law: on a date, list every `Modifies:` effect that covers it and every later change whose `Applies:` groups reach back over it.

- **Open (all).** The text in force is not always the whole law, so a reader keyed to text versions alone gives the wrong answer in these cases:
  - **UK.** The s. 42 duty was reduced to "reasonable endeavours" by notices from the Secretary of State for May to July 2020, while its words stayed the same.
  - **US.** The 2022 reach-back changes the answer for cases filed in the 2022 gap, without any change to the text in force on those days.
  - **US.** The §104 notices change dollar amounts that the Code prints at their base value.
  - Readers should warn when a power to modify, or a later reach-back, covers the date asked about.
- **Fixed (US), see the US section above.** The §104 dollar adjustments were recorded but misfiled. The note parser runs one Federal Register entry into the next, so every older notice is filed under 87 F.R. 6625 (effective 1 April 2022).
  - In §101(51D) that covers 2019, 2016, 2013, 2010 and 2007; §109(e) has nine notices filed this way.
  - The 2019 notice is 84 F.R. 3488, effective 1 April 2019.
  - The US git repo leaves adjusted amounts out of its text for this reason.

### Dates and commands

- **Adopted (all).** README date commands must not depend on the reader's clock or time zone. `git rev-list --before=YYYY-MM-DD` uses the current time of day, and commits are dated noon, so the answer for the day a law took effect flips at noon. Use `--before="YYYY-MM-DDT23:59:59Z"` or an explicit offset, or a tool that picks the version by its `In-force` trailer. Fixed in Germany (b0d346e).
- **Open (UK).** The README still has `--before="D 23:59"` (local time) and bare dates.
- **Adopted (all).** Give a PowerShell form wherever a command uses `$(…)`, because PowerShell splits `git show $(…):path` into two arguments.
- **Adopted (all).** A tag named after a printed edition holds the text in force on that date, not the printed text. They differ wherever a change was printed before it took effect (28 sections in the US 2019 edition), so say so or tag both.
- **Adopted (all).** A retroactive in-force date puts a commit before its law existed (6 US changes). Keep the in-force date, show the enacted date, and explain it.
- **Adopted (Switzerland).** A branch of changes not yet in force must never be merged back into `main`. The merge commit, dated the build day, carried future text into every on-date answer. On-date tools use `--no-merges`.

### Building and pinning

- **Adopted (all).** Build and pin from the published repositories, never from a local checkout. A local build pinned an unpushed commit, and fresh clones broke.
- **Adopted (all).** The documentation commit is dated by the data's build or retrieval day, given as a required argument, so a rebuild on another day keeps the same hashes.
- **Adopted (all).** Builders refuse a non-empty target that is not an earlier build (a UK build into an existing folder doubled its history), and keep `origin` across rebuilds.
- **Adopted (all).** REPRODUCE.md is generated by each builder, with pins, counts and blob hashes filled in. US, Germany, Switzerland and this tree came out identical hash for hash on rebuild.
- **Fixed (here).** The UK pin was one commit behind `gb/uk/send` (e295f40 against 9ed31ef, documentation only). It was repinned in a150ef0.
- **Open (here).** Switzerland is not yet in the tree. Decide how first: the full SR build is about 5,900 acts, so consider a shallow submodule or a separate corpus path. Its first versions carry `Consolidated:`, which the builder must read as their date.

### This tree (global-law): deep test of real use

A fresh clone was used the way a reader would, with plain git and with `tools/law.py`, and checked against the official texts.

- **Fixed (here).** `law.py` compared dates as text, so `2022-5-1` read as December 2022, and `2022-13-45` and `yesterday` gave answers instead of errors. Dates are now checked; `today` and a time after the date are accepted.
- **Fixed (here).** A date past the end of a record gave stale text without a word: the Grundgesetz "today" was the 2017 text. Each corpus now has `record_to` and `record_note` in `manifest.json`, and every command prints a note on stderr when a date is before a record starts or after it ends.
- **Fixed (here).** "Not in force or outside the record" covered four different cases. Now each gets its own answer:
  - a mistyped path, with the closest names suggested
  - a date before the record
  - a provision not yet in force, with its first date
  - a provision repealed
- **Fixed (here).** Paths written `./us/…` or with Windows backslashes were refused.
- **Fixed (here).** `diff` from a date before a record started said "No change". It now shows the whole text arriving.
- **Fixed (here).** A reversed window for `laws` printed nothing, and a missing argument gave a traceback.
- **Fixed (here).** `law.py words` (word-level authorship, new today) took 16 s on 17 U.S.C. §115, which the Music Modernization Act rewrote whole. Unchanged lines are now matched first, and large rewrites are paired line to line, so it takes 1.3 s.
- **Fixed (here).** The tests imported the UK builder and left `__pycache__` inside the UK checkout, which then blocked `git checkout` of an older state. Tests no longer write bytecode, and the tree has a `.gitignore`.
- **Fixed (site).** Changes too close together on the /watch/global-law timeline could not be clicked apart. They now share one mark that steps through them.
- **Open (here).** Time travel with plain git is fragile:
  - `git checkout <old commit>` with `git submodule update` (or `--recurse-submodules`) leaves the folders of corpora not yet in the record, with today's files in them.
  - `tools/` disappears, because it is only in the last commit.
  - Switching back can fail.

  For now use `law.py`, or `git worktree add ../then <commit>` and `git submodule update --init` in that worktree. Possible fixes: carry the tools from the first commit, or pin each corpus from the first commit at an empty "before the record" commit.
- **Open (here).** Plain git cannot take dates before 1970. `git log --before=1960-01-01` silently returns the newest commit. The tools use the `In-force` trailer, and the README now warns plain-git users.
- **Open (here).** `git blame` and `git log -- <provision>` do not cross into a submodule from the root. Use `law.py`, or run git inside the corpus folder at its pinned commit.
- **Open (here).** The top of `git log --first-parent` shows each corpus's documentation commits ("Lexifina"), not laws. Consider keeping documentation commits out of the chronology.
- **Fixed (Germany, repinned here in 1b11b21).** The records barely overlapped: the Grundgesetz ended in 2017, and the US starts in 2018. The Grundgesetz is now rebuilt to 28 October 2026 and equals the official text, so today, at 1b11b21, all three records are current from 12 January 2018. Art. 104c (2017) is now there, and Art. 143h reads correctly: in force 8 Oct to 31 Dec 2020, then again from 25 Mar 2025. An earlier note here called it "inserted 2019", which was wrong.
- **Fixed (here).** The README now warns about plain-git time travel and dates before 1970, and says to use a worktree.
- **Fixed (here).** A provision that lapsed and came back was reported as "repealed or removed". The message now gives the day it was removed and the day it is in force again, for example Art. 143h on 2023-01-01.
- **Fixed (here).** The Grundgesetz reader test fetched tags only when there were none, so an older clone kept the tags from before Germany's force-push and compared against old text. It now force-fetches the corpus's tags (`git fetch --force --tags`). Clone users should do the same after any corpus is rebuilt; see the README.
- **Adopted (here).** A test fails if any pin is not on its corpus's published main, which catches a corpus force-push before a fresh clone breaks. A test checks that git's own trailer parser reads every in-force date. Germany passes since its ASCII-key rebuild.
- **Open (US).** Quotation marks are straight (`"debtor"`), where the official text has curly quotes. The words match.
- **Open (here).** Scale: one root commit per corpus commit, and full submodule clones. The all-UK (about 200,000 documents) and full-SR builds will need one root commit per corpus per day, and shallow or partial submodules.
- **Open (here).** No reading "as applied to a case filed on a date" yet. It waits on the US `Applies:` trailers.
- **Checked (here).**
  - A fresh clone with submodules is 4.5 MB and takes seconds. Every command answers in 0.2 to 0.6 s.
  - `git grep --recurse-submodules <term> <commit>` searches all the law in force at a world commit, across countries.
  - `git diff --submodule=diff <commit> <commit>` shows every change in every country between two dates.
  - 11 U.S.C. §1182(1) and §101(51D) today match the published Code word for word.

### Trailers

- **Fixed (Germany, 5bb57fa).** Git read no trailers on any of the 66 commits, because the key `Verkündet:` contains a non-ASCII letter and git then rejects the whole trailer block. The key is now `Verkuendet:`. `git interpret-trailers --parse` reads 72 of 73 commits, the exception being the documentation commit, and `%(trailers:key=In-Kraft)` works.
- **Fixed (here, 1b11b21).** The Germany rebuild was force-pushed, so the pin b0d346e was no longer in the corpus's history. Repinned to 5bb57fa; the UK is repinned to 9ed31ef. Every pin now matches its corpus's head. Repin to 5bb57fa before GitHub garbage-collects the old commit and fresh `git submodule update --init` fails. Test proposed: each pin must be an ancestor of its corpus's published `main`.
- **Adopted (all).** Trailer keys are ASCII letters, digits and hyphens only. Every corpus commit except the baseline and documentation commits must pass `git interpret-trailers --parse` with its date trailer present. Commits git can parse today: Switzerland 22/23, UK 11/15, US 43/45, Germany 0/66.
- **Adopted (US).** All trailer keys are ASCII, including `Applies:`. The 2017-edition baseline commit carries `Consolidated: 2018-01-12` and `Printed-in: 2017` and no `In-force:`. Both are in the US generator and land with the full-Code rebuild, which changes the US hashes, so this tree needs a repin.
- **Open (UK).** The first commit, the Royal Assent of the Children and Families Act 2014, carries `In-force: 2014-03-13`, although nothing came into force that day. Use `Enacted:` alone, or `Consolidated:` as Switzerland does.

### MCP server

- **Adopted (here).** `tools/mcp_server.py` is a Model Context Protocol server for the tree. It uses only the standard library and git, reads the repository and changes nothing; MCP.md has the setup. It offers 15 read-only tools:
  - finding things: `list_jurisdictions`, `find_provision`, `list_provisions`
  - reading the law: `read_law`, `world_on_date`, `who_wrote`, `compare_dates`
  - history: `provision_history`, `laws_between`, `changes_between`
  - search: `search_law`, `search_changes`, `phrase_history`
  - cases and records: `applies_to_case`, `law_details`

  Every answer carries the notes on where a record starts or ends. `read_law` and `provision_history` give each change's official sources to cite.
- **Checked (here).** `tests/test_mcp.py` (25 tests) speaks to the server as a client does: the handshake, every tool, errors, resources, and the applicability rules with the agreed `Applies:` format.
- **Checked (here).** Blind tests: a model given only the MCP tools answered 14 of 14 questions with known answers. Among them:
  - the law that wrote the $7.5 million in §1182(1)
  - the reach-back of Pub. L. 117-151 to a case filed in the 2022 gap
  - the amendment that wrote Art. 16a(1)
  - the change to reg. 13(3) in May 2020
  - which changes were temporary
  - and, correctly, that the record could not answer for Art. 143h at the time
- **Fixed (here), from the blind tests.**
  - `find_provision` falls back to the text when headings are only numbers (Grundgesetz "Artikel 16a"), so a topic such as "Asylrecht" finds Art. 16a.
  - `laws_between` counts the provisions each law changed.
  - `law_details` cuts long messages, with `max_message_chars` to raise the limit.
  - The server's instructions say coverage is partial and what each date means.
- **Fixed (here), from the third blind test.**
  - A plain search matches typographic dashes, quotes and spacing, so "COVID-19" finds the Code's "COVID–19". Plain queries are literal; regular expressions are opt-in.
  - `law_details` accepts a jurisdiction prefix such as `de`.
  - Where a change has no `Applies:` data, `applies_to_case` shows the scope the record states in words for that provision, for example Pub. L. 117-151's "Applies to any case that is commenced under title 11 on or after March 27, 2020".
- **Fixed (here), from the fourth blind test (adversarial questions).**
  - `applies_to_case` reads the common worded scopes in change notes ("commenced on or after March 27, 2020", "before, on, or after") as conditions, and says when it did. For 11 U.S.C. §1182(1) on 2022-07-01:
    - a case commenced on 2020-01-15 gets the text of 2020-02-19, since neither the CARES text nor Pub. L. 117-151's reaches it
    - a case commenced on 2022-05-01 gets the $7.5 million text
  - Answers no longer point to `law.py`, which a model using MCP cannot run; they name the matching tool.
  - Numeric arguments are checked, and 8-digit dates such as 20220101 are read.
- **Checked (here).** Fourth blind round, 6 of 6. The model declined to describe US privacy law the record does not hold. It found the debt brake in Arts. 109 and 115 although the word "Schuldenbremse" is not in the text. It traced Art. 143h through insertion (2020), expiry and a new Art. 143h (2025), and gave reg. 13's extent as England and Wales only.
- **Fixed (here), from the fifth blind test (a research memo).**
  - New tool `phrase_history`: when words came into the law and when they left it, at any date. For example, "COVID" entered the Grundgesetz on 2020-10-08 (Art. 143h, 65th amendment) and left on 2020-12-31. The $7,500,000 in §1182(1) was added and removed twice.
  - A search with no hits in the text now looks in the change notes and says what it found.
- **Checked (here).** Fifth blind round: a 350-word memo on subchapter V eligibility from 2019 to today, with five dated changes, laws and govinfo links, and the definition for a case commenced on 2021-06-01. All correct.
- **Fixed (here).** Popular names: `aliases.json` maps names the text never uses to provisions, each with a note:
  - Schuldenbremse → Arts. 109, 115, 143d
  - Ewigkeitsklausel → Art. 79
  - subchapter V → §§1181 ff.
  - automatic stay → §362
  - EHC plan → s. 37 and reg. 13
  - and others

  `find_provision` checks them first, and an exact name ranks above heading matches. Add entries as they come up.
- **Adopted (here).** `read_law` says when the words in force are not the whole answer:
  - when a later change reaches back over the date. In the 2022 gap, Pub. L. 117-151 reaches cases commenced on or after 2020-03-27.
  - when a `Modifies:` effect (gitlaw-contracts' proposed trailer) covers the date. It takes the latest open effect per provision and kind, honours `ended`, and says when an effect was entered by hand (`Curated: yes`).
- **Adopted (here).** A project `.mcp.json` in the tree, so Claude Code offers the server in any clone.
- **Checked (here).** Three blind rounds before that, 20 of 20 answers right. The model also said correctly where the record could not answer, for example that no official link is recorded for a Grundgesetz amendment, only its BGBl. citation.
- **Open (here).** `applies_to_case` reads `Applies:` trailers, but no corpus has them yet; the US full-Code rebuild adds them. Until then it says no scope is recorded and follows the general rule.

### Large builds

- **Adopted (all, from the US; download rate up from about 6 to 26 documents a minute).**
  - Run several workers on one queue. Each claims a unit with an atomic `mkdir <out>/.claim-<unit>` and marks it done with a file, so no unit is built twice and runs stop and restart freely. Order the queue largest first.
  - Run independent remote calls in a bounded pool (summaries 4 at a time, lookups 8 at a time) and apply the results in their original order, so the output stays deterministic.
  - Cache every lookup on disk.
  - Commit through one streamed `git fast-import`: the same hashes, 2.5 times faster.

- **Adopted (all, from Germany).** Snapshot archives have gaps (one day was missing 3,646 files). Treat an item as repealed only if it never reappears in a later snapshot; otherwise a gap becomes a false repeal and a false re-enactment.

### Tags after a force-push

- **Open (all).** A force-pushed corpus leaves stale tags in existing clones, because `git fetch --tags` does not overwrite a tag that already exists. Tools that read tags then serve the old build. After the Germany rebuild (5bb57fa), an older clone had `in-kraft/2017-07-20` at d8366ff against 023d361 on GitHub, and this tree's reader check failed 32/33. Fix: `git fetch --force --tags` (or `--prune --prune-tags`) whenever pins change, in the tests and in each README.
- **Adopted (US).** README ("How it is built") and REPRODUCE.md ("Changes to this history") say that a rebuild replaces hashes and tags, and that an existing clone runs `git fetch --force --tags origin && git reset --hard origin/main`. This lands with the full-Code rebuild.
- **Checked (Germany).** The new build is correct for Art. 143d: BGBl. I 2009 S. 2248 has "(1) Artikel 109 und 115 …" with no "Die", and BGBl. I 2017 S. 2347 has "auf Grund einer extremen Haushaltsnotlage". The old wording came from the DocPatch transcription that c3e inherited. For the text in force on 20 July 2017, 47 articles differ between the builds. Four are the articles the old build lacked (104c, 143e, 143f, 143g). 43 come from reconciliation with the official text, including content differences: Art. 3(3) 1994, Art. 76 "sechs Wochen", Art. 104a, Art. 143c(4). Each is listed in KORREKTUREN.md.
- **Open (Germany).** Reconciliation covers each article from its last change before 2019 onward. Older versions are still the DocPatch transcription; for example, Art. 143d keeps "Die Artikel" from 2009 to 2017. Checking those against the Gazette is next.
- **Adopted (all, from Germany).** Third-party transcriptions are not the law. Reconcile every version against the official gazette, and record each correction with its words, as Germany's KORREKTUREN.md does. A transcription can be wrong in substance as well as in spelling.

### Country repositories

- **Adopted (all, from research).** About 201 private placeholder repos (`lexifina/<country>-law`) record each country's official sources, what a build would need, and the transcription warning, before any law is added. Countries already being built (Estonia, Liechtenstein, Luxembourg, Malta) and the existing corpora were skipped, so no names clash.
- **Open (all placeholders).** Each placeholder's first commit is dated 2026-10-28. A real build must replace that history from scratch and force-push; it must never append, or dates on `main` run backwards and every date lookup breaks.

### Checks

- **Checked (here, 6a7bb70).** A fresh clone with `git submodule update --init` passes all 61 tests (`tests/test_law.py` and `tests/test_mcp.py`). Every pin equals its corpus's main, and `main` has no merges, no future-dated commits and no backwards dates.

- **Checked (all, 28 October 2026).** On every corpus's `main`:
  - no merge commits
  - commit dates never go backwards along `--first-parent`
  - no commit dated in the future
  - pins for the US (c9591ac) and Germany (b0d346e) match their heads.
- **Checked (US).** A rules-as-code version of 11 U.S.C. §1182(1) agrees with this tree. `tools/law.py show` gives the same wording on all five dates the provision changed: 19 February 2020, 27 March 2020, 27 March 2022, 21 June 2022 and 21 June 2024.
- **Checked (US).** Every change was verified on its in-force day: the new text present that day and the old text the day before. 274 of 274 passed.
- **Recommended (all).**
  - A mutation test of any test suite that encodes the law: in one trial, 6 of 18 deliberate errors survived, all at exact boundaries. Test the day before and the day of every in-force date.
  - A blind test: an agent given only the clone and seven questions with known answers.
