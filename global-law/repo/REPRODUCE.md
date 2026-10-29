# How this repository was made, and how to make it again

This file records exactly how the repository was built: what it was built from, the commands, the software, the
decisions made by hand, and what an AI model did and did not do. Anyone with Python and git, and read access to the
three corpus repositories, can rebuild it and check it hash for hash.

## Short version

```sh
git clone --recurse-submodules https://github.com/lexifina/global-law && cd global-law
python -m unittest discover -s tests -v                       # {{TESTS}} checks, described below
python tools/build.py ../rebuilt --date 2026-10-28             # the same build, from the published corpus repos
git -C ../rebuilt log --format=%H                              # the same hashes as `git log --format=%H` here
```

On 28 October 2026 two builds into separate empty folders gave the same {{COMMITS}} commit hashes, from the first commit
(the jurisdiction tree, dated 1 January 1970) to the last (this documentation). The build reads the corpus
repositories as they are published, so it rebuilds hash for hash for as long as those repositories are at the commits
listed below.

## What it is built from

This repository contains no legal text of its own. It is built from three repositories, each with its own
REPRODUCE.md recording how its text was obtained. At this build they were at these commits, which are the commits this
repository pins at its head:

| Path here | Repository | Commit |
| --- | --- | --- |
{{PINS}}

The build reads each repository's commits on the first-parent line of its default branch, with their authors, dates
and message trailers, and its tags. It reads no file contents and makes no other network requests.

## The build, step by step

The build script is `tools/build.py`. It is the same file as `scripts/global-law/build.py` in Lexifina's own
repository (git blob `{{BUILD_BLOB}}`). The reading tool `tools/law.py` has blob
`{{LAW_BLOB}}`, and the tests `tests/test_law.py` have blob
`{{TEST_BLOB}}`.

1. `python scripts/global-law/build.py <out> --date 2026-10-28 --site-data saas-webpage/app/watch/global-law/_data/global.json`
   - makes a bare clone of each corpus repository into `<out>/.git/corpus-cache/`
   - writes the first commit (the jurisdiction tree, `manifest.json` and `.gitmodules`)
   - writes one commit for each corpus commit, in in-force order, each moving that corpus's pin
   - copies each corpus's tags under its path
   - writes the last commit with the README, this file, the tools and the tests
   - and, with `--site-data`, writes the timeline that the page at lexifina.com/watch/global-law reads
2. The same command into a second empty folder. `git log --format=%H` was identical in both: {{COMMITS}} commits.
3. `git submodule update --init`, then `python -m unittest discover -s tests -v`. All {{TESTS}} tests passed.
4. `git push --force -u origin main` and `git push --force origin --tags` published it to GitHub. It is a private
   repository.
5. A fresh `git clone --recurse-submodules` from GitHub, then the tests again. All passed.

The build and the tools use only the Python standard library and git. They were run with Python 3.12.10 and git
2.46.0 on Windows 11. No AI model or other service is involved in building or reading the history.

## How the history is derived

Everything below is done by `tools/build.py`, deterministically. The same corpus commits give the same hashes.

- **Paths.** Each corpus sits at country (ISO 3166-1), then level, then corpus:
  - `de/bund/grundgesetz`
  - `gb/uk/send`
  - `us/federal/usc`

  A sub-national level would use its ISO 3166-2 code, for example `us/ca`. Each folder above a corpus holds a
  `jurisdiction.json` naming it and listing its children.
- **Order.** The corpora's commits are merged by their in-force date, keeping each corpus's own order. Each
  corpus records its in-force date in a trailer:
  - `In-force:` for the US and UK corpora
  - `In-Kraft:` for the Grundgesetz

  A corpus commit without one (a starting edition, or documentation) is placed by its author date.
- **Commits.** There is one commit here for each corpus commit.
  - The author name, address and date are the corpus commit's. For the Grundgesetz before 1970 that date is the
    clamped 1970 date, because git cannot store earlier dates.
  - The committer is `Lexifina <global-law@lexifina.com>`, with the same date.
  - Where a date would fall before its parent's, it is raised to the parent's date, so the commit dates never go
    backwards.
  - The trailers are `Corpus`, `Corpus-commit`, `Law`, `In-force` and `Kind` (law, baseline or documentation). The
    tools rely on `In-force`, never on the commit date.
- **Tags.** Each corpus tag is copied as `<path>/<tag>`, for example `de/bund/grundgesetz/gesetz/36`, pointing at
  the commit here that moved the corpus to the tagged commit.

## Decisions made by hand

1. **Folders above the corpora, not repositories.** Nested repositories would make every change ripple up through
   each level's pin. Folders give the same tree with one level of submodules.
2. **One commit here per corpus commit,** rather than one per day. That way each commit is one law taking effect,
   and its author is that law.
3. **The build reads the published repositories by default.** An earlier build read a local checkout and pinned a
   commit that had not been pushed, so a fresh clone could not fetch it. Building from local checkouts
   (`--local`) is kept for trying a corpus change before it is pushed. Such a build is not published.
4. **What is not in git.** Two things the Lexifina readers show are computed data rather than history:
   - which other provisions use a defined term or cite a section
   - notifications for a followed section

   Neither is in this repository. A later law's retroactive reach is in the corpus commit messages only, and does not
   change the text shown on earlier dates.

## What an AI model did

This repository was built on 28 October 2026 in **Claude Code**, Anthropic's coding tool, by the model **Claude Opus
5.5** (model id `claude-opus-5-5`). The model was working from a goal set by the user at Lexifina: to design a git
repository of "global law", with jurisdictions inside it and the law of each inside those, built from Lexifina's
existing corpus repositories, then to test it and publish a page about it.

The model:

- **Chose the design** described above and in the README, after reading the three corpus repositories' commits,
  trailers and tags.
- **Wrote all the code and text in this repository:** `tools/build.py`, `tools/law.py`, `tests/test_law.py`, the
  README and this file.
- **Ran the commands listed above** and checked the results: the tests, two builds compared hash for hash, and a
  fresh clone from GitHub.

The model did **not**:

- **Write or change any legal text.** This repository holds none. The text is in the corpus repositories, where it
  was copied by their own scripts from the official publishers, as their REPRODUCE.md files record.
- **Take part in building or reading the history.** No AI model is called by the build, the tools or the tests.

The user decided the scope, the owner (the Lexifina organisation) and that the repository is private. The work was not
reviewed line by line by a lawyer. For anything that matters, the legislation itself should be read.

## The tests

`tests/test_law.py` has {{TESTS}} tests:

- **The tree.** Every level describes itself and its children, and the head pins each corpus at its latest commit.
- **The timeline.**
  - It is in in-force order, with one commit here per corpus commit.
  - Each commit moves exactly one pin.
  - Commit dates never go backwards.
- **Readings on a date.**
  - The US small business debtor limit is $7.5 million in 2021, gone in May 2022, back in July 2022 and gone in
    July 2024.
  - Grundgesetz Art. 12a appears from 28 June 1968, and Art. 91e from 27 July 2010.
  - Nothing is in force before 24 May 1949.
  - Every corpus matches being read on its own at six dates.
- **Against each corpus's own tools.**
  - Grundgesetz: six articles at seven dates from 1949 to 2017 agree with the corpus's `tools/stand_am.py`.
  - UK: every version in the corpus's `data/history.json`, rendered by the corpus's own builder, equals the file
    read here on that version's date.
- **The reader's questions.**
  - `log`: every law that changed a file, in order, with its in-force, enacted or made, and published dates.
  - Dates that differ: the SEND Regulations were made on 4 June and came into force on 1 September 2014.
  - `blame` names the law in each jurisdiction, and `words` credits each word: the restored §1182(1) to Pub. L.
    117-151, Art. 79 to both 1949 and 1954, one word of reg. 13(3) to the 2020 coronavirus regulations.
  - Copied tags point at the matching state.
  - A plain `git ls-tree` and `git show` gives the same text as the tools.
  - A date window lists laws from two countries in order.

## Changes to this repository after it was published

- **28 October 2026.** The repository moved from a personal account to the Lexifina organisation, and the corpus
  repositories followed. It was rebuilt with the new addresses and force-pushed, and later with this file and the
  build script added.
