"""Writes repo/README.md, LICENSE and jurisdiction.json for a US-state first build.

    from state_docs import write_docs; write_docs(folder, spec)

spec keys: name, code (two letters), slug (united-states-texas), acts [{folder, title, versions, history}],
source (markdown), dates (markdown bullets), limits (markdown bullets), domain, licence (LICENSE text before the
Lexifina paragraph), build (jurisdiction.json "build" line), date (retrieval day).
"""
import json
from pathlib import Path


def write_docs(folder, s):
    d = Path(folder) / 'repo'
    d.mkdir(parents=True, exist_ok=True)
    rows = '\n'.join(f"| `{a['folder']}/` | {a['title']} | {a['versions']} | {a['history']} |" for a in s['acts'])
    readme = f"""# {s['name']}: law history in git

The statute law of {s['name']} as a git repository: one file per section, committed with the official publisher named as author. It follows the shared design of [lexifina/global-law](https://github.com/lexifina/global-law).

**What is in it now (a first build, not complete)**

| Folder | Act | Versions | History |
| --- | --- | ---: | --- |
{rows}

Nothing else of {s['name']}'s law is in it yet.

## Where the text comes from

{s['source']}

## Dates

{s['dates']}

## What it does not show

{s['limits']}

## How it is checked

- Every unit is read back from git on its day and compared with the corpus (`tools/check_repo.py`; results in `REPRODUCE.md`).
- Each source file is identified by its sha256, in `data/versions.json`.

## What "author" means

Each commit is authored by the publisher ({s['publisher']}) because this first build holds one version of each act, the oldest version available. The committer is always Lexifina.
"""
    (d / 'README.md').write_text(readme, encoding='utf-8', newline='\n')
    lic = s['licence'].rstrip() + """

The arrangement of this repository, its tables, commit messages and tools are by Lexifina and may be reused under the Creative
Commons Attribution 4.0 International licence (https://creativecommons.org/licenses/by/4.0/). This repository is not legal advice
and not an official publication.
"""
    (d / 'LICENSE').write_text(lic, encoding='utf-8', newline='\n')
    j = {"path": "us-" + s['code'].lower(), "code": s['code'], "name": s['name'], "level": "state",
         "repo": f"https://github.com/lexifina/{s['slug']}-law", "build": s['build'], "register_date": s['date']}
    (d / 'jurisdiction.json').write_text(json.dumps(j, indent=2) + "\n", encoding='utf-8', newline='\n')
