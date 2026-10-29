# Global law

The law of several jurisdictions as one git history. Each jurisdiction's law is its own repository, where every commit
is one law taking effect, written by that law. This repository arranges those repositories by jurisdiction and
interleaves their histories in the order the changes took force, so a single commit here is the state of all of them on
one day.

```
global-law/
├── manifest.json            every corpus: path, source repo, coverage, which trailer holds the in-force date
├── jurisdiction.json        the world, and its children
├── de/                      Germany (ISO 3166-1)
│   └── bund/                federal law
│       └── grundgesetz/     submodule: one commit per amending law since 1949
├── gb/                      United Kingdom
│   └── uk/                  UK Parliament and UK ministers (devolved legislatures go beside it)
│       └── send/            submodule: Children and Families Act 2014 Part 3 and the SEND Regulations 2014
└── us/                      United States
    └── federal/             federal law (states go beside it, for example us/ca)
        └── usc/             submodule: US Code titles 1, 3, 4, 9, 11, 13, 17, 35 and 39 since the 2017 edition
```

## Reading it

```
git clone https://github.com/lexifina/global-law && cd global-law
git submodule update --init

python tools/law.py world 2022-05-01                       what every corpus looked like that day
python tools/law.py show 2022-05-01 us/federal/usc/title-11/1182.md
python tools/law.py blame 2022-07-01 us/federal/usc/title-11/1182.md
python tools/law.py words 2022-07-01 us/federal/usc/title-11/1182.md
python tools/law.py diff 2022-05-01 2022-07-01 us/federal/usc/title-11/1182.md
python tools/law.py laws 1990-01-01 1990-12-31 de
```

Dates must be written YYYY-MM-DD. When a date falls before a record starts or after it ends, the tools say so on
stderr, because each country's record covers a different period (see `record_to` in `manifest.json`).

Plain git works too, with care:

- `git log --first-parent` is a world chronology of laws taking effect.
- `git grep --recurse-submodules <term> <commit>` searches all the law in force at that moment, in every country.
- `git diff --submodule=diff <commit> <commit>` shows every change in every country between two moments.
- Inside a corpus, `git blame` names the law that wrote each line, and `git log -p --word-diff -- <file>` shows each
  law's change word by word, which matters where a line is a whole paragraph. Blame and log do not cross from here
  into a corpus: run them in the corpus folder, or use `law.py`.
- To look around an older moment, use a separate worktree, not `git checkout` here:
  `git worktree add ../then <commit> && cd ../then && git submodule update --init`. Checking out an old commit here
  leaves the folders of corpora that did not exist yet, and the tools, which live in the last commit, disappear.
- Git cannot store dates before 1970, so `git log --before=1960-01-01` gives a wrong answer without saying so. The
  tools read the `In-force` trailer instead.
- Each corpus's own tags are copied here under its path, for example `de/bund/grundgesetz/gesetz/36`.
- After a corpus is rebuilt (its maintainers force-push), run `git submodule update --init` and, inside that corpus,
  `git fetch --force --tags`: a plain fetch keeps old tags with the same names.

Using it from an AI model: `tools/mcp_server.py` serves the same readings over MCP; see MCP.md.

## How it is built

- The first commit, dated 1 January 1970, holds the jurisdiction tree and the list of corpora, and no law.
- Every later commit moves exactly one corpus to its next commit. Its author is the law, as in the corpus, and its
  trailers name the corpus, the corpus commit, the law and the in-force date.
- The order is the in-force date, keeping each corpus's own order.
- The last commit adds this README, the tools and the tests.
- The build is deterministic. When a corpus is rebuilt, for example after a correction, this repository is rebuilt from
  scratch and force-pushed.

## Dates

Git cannot store dates before 1970, so changes to the Grundgesetz that took effect earlier carry 1970 commit dates, one
second apart, in the right order. The `In-force` trailer is authoritative and the tools use it, so
`law.py show 1956-03-19 …` works.

## What it does not show

- Each corpus covers only what its README says. A file missing on a date can mean the provision was not yet in force or
  that the corpus does not reach that far back.
- A later law that reaches back to earlier dates (retroactive application) is recorded in the corpus's commit messages
  but does not change the text shown on those earlier dates.
- `git blame` works by line, so a line changed in part is credited to the last law that touched it. `law.py words`
  credits each word instead, by comparing each version with the one before; text rewritten in place is credited to
  the law that rewrote it, even where a few of its words are the same as before.

## Tests

```
python -m unittest discover -s tests -v
```

The {{TESTS}} tests check the jurisdiction tree and the timeline, known readings in each country, and that the answers here
agree with each corpus read with its own tools. REPRODUCE.md lists them, with the exact build and a hash-for-hash
rebuild check.

## How it was made

`tools/build.py` builds this repository from the published corpus repositories, deterministically. REPRODUCE.md
records the command, the software, the commits pinned, the decisions made by hand and what an AI model did and did
not do.
