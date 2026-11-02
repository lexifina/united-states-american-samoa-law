"""Writes repo/README.md, LICENSE, jurisdiction.json for a first build. Usage: fb_docs.py <slug> <code> <Name> <json spec file>"""
import json, sys
from pathlib import Path
slug, code, name, spec = sys.argv[1:5]
s = json.load(open(spec, encoding='utf8'))
d = Path(__file__).resolve().parents[1] / f'{slug}-law' / 'repo'
d.mkdir(parents=True, exist_ok=True)
rows = '\n'.join(f"| `{a['folder']}/` | {a['title']} | {a['versions']} | {a['history']} |" for a in s['acts'])
readme = f"""# {name}: law history in git

The law of {name} as a git history: one file per provision, one commit per law on the day it took effect, and the law that made each change as the commit's author. `git blame` names the law behind every paragraph; `git log` lists every change; picking a date gives the text in force that day.

It follows the shared design of [lexifina/global-law](https://github.com/lexifina/global-law).

**What is in it now (a first build, not complete)**

| Folder | Act | Versions | History |
| --- | --- | ---: | --- |
{rows}

**Language.** {s['language']}

**Source.** {s['source']}

## Dates

{s['dates']}

## How it is checked

Every version is read back from git on the day it took effect and on the day before (`tools/check_repo.py`) and must match `corpus.json`; results are in `REPRODUCE.md`.

## What "author" means

The author of a commit is the law that made the change, with an e-mail address that cannot exist (`<law key>@{s['domain']}.invalid`). {s['author_note']} The committer is always Lexifina.

## Limits

{s['limits']}
"""
(d/'README.md').write_text(readme, encoding='utf8', newline='\n')
(d/'LICENSE').write_text(s['license'].rstrip()+"""

Lexifina's own contributions (the arrangement of the history, the commit messages, the tables and the
tools) are dedicated to the public domain under CC0 1.0 Universal: https://creativecommons.org/publicdomain/zero/1.0/
""", encoding='utf8', newline='\n')
(d/'jurisdiction.json').write_text(json.dumps({"path": code.lower(), "code": code, "name": name, "level": "country",
  "repo": f"https://github.com/lexifina/{slug}-law", "build": "built",
  "register": "https://claude.ai/artifact/DdS9F6yqpPZtV2i7FGQhYZ", "register_date": "2026-10-28"}, indent=2)+"\n", encoding='utf8', newline='\n')
