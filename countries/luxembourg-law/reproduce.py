"""Writes data/versions.json and REPRODUCE.md into the Luxembourg law repository, from the facts of the build that made
it. Called by build.py; kept apart so the record of how the repository was made reads as one document.

The results of the checks (check_repo.py) and of the hash-for-hash rebuild are read from verification.json beside this
file, which check_repo.py and the rebuild step write; a build made before them says they have not been run."""
from __future__ import annotations

import datetime as dt
import json
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = 'http://data.legilux.public.lu/eli/'


def write_manifest(repo: Path, built: list[dict], today: str):
    """Every source file the text comes from, with its sha256, so a rebuild or a check can show it read the same bytes."""
    out = {'built': today, 'acts': [{
        'slug': b['act']['slug'], 'path': b['act']['eli'].replace('etat/leg/', ''), 'eli': DATA + b['act']['eli'],
        'versions': [{'from': s['from'], 'to': s.get('to'), 'kind': s['kind'], 'eli': s['eli'], 'xml': s['url'],
                      'sha256': s['sha256']} for s in b['sources']],
    } for b in built]}
    (repo / 'data').mkdir(exist_ok=True)
    (repo / 'data' / 'versions.json').write_text(json.dumps(out, ensure_ascii=False, indent=1) + '\n', encoding='utf-8', newline='\n')


def _verification() -> dict:
    p = HERE / 'verification.json'
    return json.loads(p.read_text(encoding='utf-8')) if p.exists() else {}


def write_reproduce(repo: Path, built: list[dict], commits: list[dict], tags: dict, requests: list[dict], today: str,
                    history_tip: str):
    blob = subprocess.run(['git', 'hash-object', str(HERE / 'build.py')], capture_output=True, text=True).stdout.strip()
    pyv = subprocess.run(['python', '--version'], capture_output=True, text=True).stdout.strip()
    gitv = subprocess.run(['git', '--version'], capture_output=True, text=True).stdout.strip()
    import lxml
    files = {r['file'] for r in requests if r['file'].exists()}
    days = sorted({dt.date.fromtimestamp(f.stat().st_mtime).isoformat() for f in files})
    queries = len({r['file'] for r in requests if r['query']})
    xmls = len({r['file'] for r in requests if not r['query']})
    changes = [c for b in built for c in b['changes']]
    count = lambda pred: sum(1 for c in changes if pred(c))
    kinds = {k: sum(1 for c in commits if c['kind'] == k) for k in ('original', 'law', 'replacement', 'typesetting', 'unexplained')}
    clamped = sum(1 for c in commits if c['day'] < '1970-01-01')
    rows = '\n'.join(
        f'| {b["act"]["short"]} | `{b["act"]["eli"]}` | {len(b["sources"])} | {b["sources"][0]["from"]} to {b["sources"][-1]["from"]} | '
        f'{sum(1 for c in b["changes"])} |' for b in built)
    unexplained = '\n'.join(f'- {c["act"]} {c["day"]}: {", ".join(c["articles"])}' for c in commits if c['kind'] == 'unexplained') or '- none'
    typeset = '\n'.join(f'- {c["act"]} {c["day"]}: {", ".join(c["articles"])}' for c in commits if c['kind'] == 'typesetting') or '- none'
    dateonly = '\n'.join(f'- {c["act"]} {c["day"]} {c["cause"]}: {", ".join(a for a, e in zip(c["articles"], c["evidence"]) if e == "date")}'
                         for c in commits if 'date' in c['evidence']) or '- none'
    v = _verification()
    check = v.get('check')
    check_text = (f'`{check["versions"]} texts checked ({check["articles"]} article files compared byte for byte), '
                  f'{check["mismatches"]} mismatches; {check["words_articles"]} articles checked word for word against the XML, '
                  f'{check["words_mismatches"]} mismatches` (run {check["run"]} against history tip `{check["history_tip"]}`).'
                  if check else '*Not yet run for this build.*')
    det = v.get('determinism')
    det_text = (f'Two builds from the same cache with `--offline --today {det["today"]}` into separate empty folders gave '
                f'identical hashes for every commit and tag: the history tip `{det["history_tip"]}` (the commit before this '
                f'documentation) and `main` were the same in both (run {det["run"]}). This documentation commit then records '
                'that result, so its own hash is checked by rebuilding with this file in place, as in the short version above.'
                if det else '*Not yet run for this build.*')

    text = f"""# How this history was made, and how to make it again

This file records exactly how the repository was built: the sources, the commands, the software, the decisions made
by hand, and what an AI model did and did not do. The build writes it, so it describes the build that made this
commit.

## Short version

```sh
git clone https://github.com/lexifina/luxembourg-law && cd luxembourg-law
pip install lxml
python -X utf8 tools/build.py --repo ../rebuilt --today {today}
git -C ../rebuilt rev-parse main        # the same hash as this repository's main
python -X utf8 tools/check_repo.py --repo ../rebuilt
```

`tools/build.py` needs Python 3.12 or later with `lxml`, and git. It reads Legilux (or its own cache, `.cache/` beside
it) and writes this repository into `--repo`. With the same Legilux data and the same `--today` it gives the same
commits with the same hashes. `data/versions.json` lists every source file with its sha256. `--offline` refuses to
touch the network and fails on anything not cached.

## Sources

All legal text and all information about changes come from **Legilux**, the official journal of the Grand Duchy of
Luxembourg (Ministère d'État, Service central de législation), under CC BY 4.0. Nothing was typed in, summarised or
rewritten. The build made {queries} SPARQL queries and read {xmls} XML files.

| What | Where |
| --- | --- |
| Each act's consolidated versions, the day each applies from and to, and its French XML | SPARQL at `https://data.legilux.public.lu/sparqlendpoint` (JOLux ontology): `jolux:Consolidation`, `jolux:isMemberOf`, `jolux:dateApplicability`, `jolux:isEmbodiedBy` |
| The act as first published in the Mémorial | the act's `…/jo` expression, French XML |
| Which law took effect on which day | each version's own `<lifecycle>` (`eventRef` dates) and `<references>` |
| Which law changed which article | each version's `<passiveModifications>` (`textualMod` source and destination) and the `<mod class="mod-start">` … `mod-end` markers in the text, with their notes |
| Each amending law's title, adoption, publication, Mémorial and entry into force | SPARQL: `jolux:title`, `jolux:dateDocument`, `jolux:publicationDate`, `jolux:isPartOf`, `jolux:dateEntryInForce` |
| The text of each version | Akoma Ntoso XML from `https://data.legilux.public.lu/filestore/…`, listed with sha256 in `data/versions.json` |

| Act | ELI | Texts | From | Article changes |
| --- | --- | ---: | --- | ---: |
{rows}

The data was retrieved on {", ".join(days) if days else today}, one request at a time at least one second apart, with
the user agent `lexifina-watch/1.0 (+https://lexifina.com; corpus@lexifina.com)`. Where Python's certificate store
rejected the server's chain, the same request was made with `curl`.

## The build, step by step

1. `python -X utf8 scripts/luxembourg-law/build.py --today {today}` in Lexifina's own repository wrote this repository.
   `tools/build.py` here is the same file as `scripts/luxembourg-law/build.py` there (git blob `{blob}`), with
   `tools/reproduce.py`, which writes this file, and `tools/check_repo.py`.
2. `python -X utf8 scripts/luxembourg-law/check_repo.py` read every text back from git with `tools/en_vigueur_au.py`'s
   own lookup, on the day each applies from, and compared it with the official XML (whose sha256 it checks first):
   {check_text}
3. {det_text}
4. `git push -f origin main --tags` published it to GitHub as a private repository.

It ran with {pyv}, lxml {lxml.__version__} and {gitv} on Windows 11. No network service other than Legilux is involved.

## How the text and the commits are derived

Everything below is done by `tools/build.py`, deterministically.

- **Texts.** For each act: the text as first published in the Mémorial, in force from the act's own entry-into-force
  date, then every consolidated version Legilux publishes as XML. The Constitution has all 38 versions from 1919; the
  Covid-19 law all 32 from 2020.
- **Text of an article.** Each article is one file, `<ELI of the act>/<ELI id of the article>.md` (for example
  `constitution/1868/10/17/n1/art_32.md`). Each alinéa, each numbered paragraph's alinéa and each list item is one line,
  with its paragraph number ("(1)") or list number ("1°", "a)", "2°bis") in front. The list number is computed from the
  list's own symbol as the official HTML prints it (struck-through items keep their number). Struck-through text
  (repealed, kept in the consolidated text only to show what was there) is left out; an article that is struck through
  or reads only "(abrogé)" is repealed and its file removed. Notes and metadata are left out. Superscripts join the
  word before them ("1<sup>er</sup>" and "1 <sup>er</sup>" both read "1er"), and a dash typed in front of a list item is
  the item's bullet. Spacing is collapsed. Nothing else is changed.
- **Article identity.** The article's `id` in the XML, without the date Legilux appends to a repealed article kept in
  the text. The ELI in each article's own metadata block is not used: in some versions it names another article.
- **Changes.** Consecutive texts are compared article by article. {len(changes)} article changes were found.
- **Cause.** For each changed article, the laws that took effect between the two versions are read from the newer
  version's lifecycle (plus any law whose modifications first appear in it). The change is credited to the one among
  them that the version links to the article, by a modification marker newly covering the article or by a modification
  whose destination is the article or its chapter. {count(lambda c: c['kind'] == 'law' and c['evidence'] != 'date')} changes were
  credited this way. Where nothing links the article:
  - a change of spacing only is a **typesetting** commit by the publisher ({count(lambda c: c['kind'] == 'typesetting')} article changes);
  - else, where exactly one law took effect that day and the destinations it names do not rule the article out, the change is
    credited to it **by date only**, with `Evidence: … date` in the commit ({count(lambda c: c['evidence'] == 'date')} article changes);
  - else the change is an **unexplained** commit by the publisher, credited to no law ({count(lambda c: c['kind'] == 'unexplained')} article changes).
  Where two laws were linked to one article on one day the build would stop; it does not happen in this data.
- **Commits.** One commit per act per law per day ({kinds['law']} law commits), one for each act's original text
  ({kinds['original']}), {kinds['replacement']} labelled replacement, {kinds['typesetting']} typesetting and
  {kinds['unexplained']} unexplained commits, in the order they took effect, then one for this documentation dated
  {today}.
  - The author is the law, named by kind, date and the last part of its ELI (`Loi du 15 mai 1919 (n1)`), at an address
    ending `@legilux.invalid` made from its ELI (`loi-1919-05-15-n1@legilux.invalid`), so `git blame` names the law.
    The original texts are by the act itself; typesetting and unexplained commits are by
    `Service central de législation (Legilux)`.
  - Author and committer dates are noon in Luxembourg on the day the text applies from (the consolidated version's
    `dateApplicability`). The committer is `Lexifina <luxembourg-law@lexifina.com>`.
  - Git cannot store dates before 1970. The {clamped} commits before 1970 (1868 to 1956) are dated 1970-01-01, one
    second apart in order, and carry the real day in `In-force:`, in a `Date-note:` and in the tags. The reader
    `tools/en_vigueur_au.py` uses `In-force:`, not the commit date.
  - Trailers: `Adopted:`, `Published:` (with the Mémorial), `In-force:`, `Law-in-force:` where the law's own entry
    into force in Legilux's metadata differs from the day its text applies, `Evidence:`, `Affecting:`, `Source:` (the
    law) and `Text:` (the consolidated version).
  - Tags: each act's days (`constitution/2023-07-01`) and each law (`loi/1919-05-15-n1`); {len(tags)} in all.

Changes credited by date only:

{dateonly}

Typesetting commits:

{typeset}

Unexplained commits:

{unexplained}

## Decisions made by hand

These choices were made when the tool was written, after looking at the data. They are in the code.

1. **The 2023 Constitution is a labelled replacement credited to law A 29.** Four laws of 17 January 2023 (Mémorial
   A 26 to A 29) revised the Constitution with effect from 1 July 2023 and renumbered it. Legilux's consolidated
   version credits the whole new text to one modification note naming A 26. Law A 29, Art. 4, renumbers the articles
   the four laws revised and provides that the text annexed to it "constitue le texte de la Constitution du Grand-Duché
   de Luxembourg"; the build quotes that article from A 29's own XML into the commit and stops if it no longer says so,
   or if the laws in force that day change. The new text is one commit, labelled a replacement, by A 29, naming the
   other three laws. The old and new numbering are different provisions under the same file names.
2. **The first text is the act as published in the Mémorial.** For both acts, the published text differs from the
   first consolidated version in exactly the articles the first amending laws changed (the four laws of 1919; law A 633
   of 2020), so the record starts at enactment.
3. **French is the text of the record**; Legilux also publishes German and Luxembourgish texts of some versions.
4. **A change is dated the day the consolidated text applies from**, not the law's own entry into force where Legilux's
   metadata differs (that is recorded in `Law-in-force:`).
5. **Typesetting and unexplained changes are committed, labelled, and never credited to a law.**
6. **Credit by date only** is used where one law took effect that day and the version links no law to the article;
   it is marked in every commit that uses it and listed above.
7. **The acts.** The Constitution, the most amended text with the longest history (38 consolidated versions, 1919 to
   2026), and the Covid-19 law of 17 July 2020, amended 31 times in four years, with every version in XML. Ordinary laws
   such as the anti-money-laundering law of 2004 have only their two or three latest consolidations in Legilux's data,
   which cannot support a history.

## What an AI model did

This repository was built on {today} in **Claude Code**, Anthropic's coding tool, by the model **Claude Opus 5.5**
(model id `claude-opus-5-5`), working from a brief set at Lexifina: a private git history of Luxembourg law to the
standard of Lexifina's other law records (US Code, Grundgesetz, UK, Switzerland).

The model:

- **Researched the source:** Legilux's SPARQL endpoint and JOLux data, its Akoma Ntoso XML, and the prior art below.
- **Wrote all the code and text in this repository:** `tools/build.py`, `tools/reproduce.py`, `tools/check_repo.py`,
  `tools/en_vigueur_au.py`, the README, this file and the licence notice, and chose the design described in them.
- **Ran the commands above** and checked the results.

The model did **not**:

- **Write or edit any legal text.** Every word of every article, every date and every law's title is copied by the
  script from Legilux. The commit messages around them are fixed templates in the script.
- **Take part in building the history.** No AI model is called when the history is built or checked.

The work was not reviewed line by line by a lawyer. Only the Journal officiel (Mémorial) is authoritative; Legilux's
consolidated texts, and so this repository, are not.

## Prior art

Checked {today}:

- [legalize-dev/legalize-lu](https://github.com/legalize-dev/legalize-lu): Luxembourg laws, regulations and the
  Constitution in Markdown from Legilux, one file per act, one commit per consolidated version dated its applicability,
  by a generic author. Its research notes (`research/RESEARCH-LU.md` in legalize-dev/legalize-pipeline) were read for
  Legilux's URI scheme and SPARQL patterns; none of its code is used.
- [SFHAJJI/lex-corpus-lu-legilux](https://github.com/SFHAJJI/lex-corpus-lu-legilux): every consolidated version as
  publisher files with metadata.

This repository differs in making each commit a law: it names the law behind each change of each article from the
version's own modification data, keeps one file per article, starts from the text as enacted, and labels what no law
explains.
"""
    (repo / 'REPRODUCE.md').write_text(text, encoding='utf-8', newline='\n')
