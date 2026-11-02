"""Private helper: writes repo/README.md, repo/LICENSE and repo/jurisdiction.json for a Brazilian municipal build
(copy of br_docs.py for the city tier; adds "parent" and level "municipality").

    python -X utf8 scripts/world-law/br_city_docs.py <folder> <spec.json>

spec: name, full, code (BR-SP-SAO-PAULO), slug (brazil-sao-paulo-city), parent (br-sp), official (the gazette), publisher, site, site_url,
holds (markdown: what is in it), dates (markdown), built (markdown), limits (markdown), build (jurisdiction "build" line),
terms (markdown bullet about the site's terms, may be empty).
"""
import json, sys
from pathlib import Path

COPY = ('"Não são objeto de proteção como direitos autorais de que trata esta Lei: [...] IV - os textos de tratados ou '
        'convenções, leis, decretos, regulamentos, decisões judiciais e demais atos oficiais" (Lei 9.610/1998, '
        'art. 8, IV)')


def write(folder, s):
    d = Path(folder) / 'repo'
    d.mkdir(parents=True, exist_ok=True)
    readme = f"""# {s['name']}: law history in git

The municipal law of {s['full']} (Brazil) as a git history: one file per Artigo, one paragraph per line, so `git blame`,
`git log` and `git diff` work line by line. The text is Portuguese, the only official language.

It follows the shared design of [lexifina/global-law](https://github.com/lexifina/global-law).

## What this repository holds

{s['holds']}

## Source

[{s['site']}]({s['site_url']}), published by the {s['publisher']}. Each version names the page it was taken from and
that page's sha256, in `data/versions.json`.

## Dates

{s['dates']}

## How it is built

{s['built']}

## How it is checked

Every version is read back from git on the day it took effect (`tools/check_repo.py`) and must match the corpus; an
independent letters-and-digits comparison of every version against the source page must show no difference. Results
are in `REPRODUCE.md`.

## What "author" means

The author of each commit is the law that made the text, or, for a consolidated text, the publisher, with an e-mail
address that cannot exist; the committer is always Lexifina.

## Limits

{s['limits']}

## Licence

See [LICENSE](LICENSE): Brazilian law texts are not protected by copyright (Lei 9.610/1998, art. 8, IV).
Fonte: {s['site']}, {s['publisher']}.
"""
    (d / 'README.md').write_text(readme, encoding='utf-8', newline='\n')
    lic = f"""Law texts

The texts in this repository are laws of {s['full']} as published by the {s['publisher']} ({s['site_url']}).

- Copyright: {COPY}.
{s.get('terms') or ''}- The texts are not the official version: only the {s['official']} is authoritative.

Attribution: Fonte: {s['site']}, {s['publisher']}, {s['site_url']}.

Everything else (the git history's structure, the tools and the documentation): CC0 1.0 Universal,
https://creativecommons.org/publicdomain/zero/1.0/legalcode
"""
    (d / 'LICENSE').write_text(lic, encoding='utf-8', newline='\n')
    j = {'path': s['code'].lower(), 'code': s['code'], 'name': s['name'], 'level': 'municipality', 'parent': s['parent'],
         'repo': f"https://github.com/lexifina/{s['slug']}-law", 'build': s['build']}
    (d / 'jurisdiction.json').write_text(json.dumps(j, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')


if __name__ == '__main__':
    write(sys.argv[1], json.loads(Path(sys.argv[2]).read_text(encoding='utf-8')))
