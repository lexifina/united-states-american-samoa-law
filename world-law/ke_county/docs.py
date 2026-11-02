"""Write repo/README.md, LICENSE, SOURCES.md and jurisdiction.json for one Kenyan county. Private.

    python -X utf8 docs.py <county-slug>
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from make_part import COUNTIES  # noqa: E402

county = sys.argv[1]
code, name, list_url, host = COUNTIES[county]
repo = HERE.parent.parent / f'kenya-{county}-law' / 'repo'
repo.mkdir(parents=True, exist_ok=True)
w = lambda n, t: (repo / n).write_text(t, encoding='utf-8', newline='\n')  # noqa: E731

w('README.md', f"""# {name} County (Kenya): law history in git

The Acts of the County Assembly of {name}, Kenya, as a git history: one folder per Act, one file per section, one
paragraph per line, so `git blame`, `git log` and `git diff` work line by line. The text is the English text of each
Act as published in the Kenya Gazette Supplement by the Government Printer and posted by the County Assembly of
{name} on its website.

It follows the shared design of [lexifina/global-law](https://github.com/lexifina/global-law).

## What this repository holds

**Acts as enacted, not yet a history.** The County Assembly posts each Act as the Kenya Gazette Supplement that
published it; there is no consolidated text. So each Act is one commit holding its text as enacted ("oldest version
available"), credited to the publisher, not to an amending law. An amending Act is its own folder; its amendments are
not applied to the Act it amends.

| Folder | What |
| --- | --- |
| one folder per Act (by its short title) | `000-title.md` (the Act's title, long title and enacting words), one file per section, one per Schedule |

The Acts come in parts of about fifty, in date order. An Act is left out until it can be read reliably: scans with
no text layer (no OCR is used), documents that are not Gazette Supplements (drafts, Bills, Word copies), PDFs with
tables or forms the independent check below does not find in the same order, and PDFs whose sections do not match
their own arrangement of sections. Subsidiary legislation is not included.

## Source

[County Assembly of {name}: Acts]({list_url}), each a Kenya Gazette Supplement ("{name} County Acts") printed and
published by the Government Printer, Nairobi. Each PDF's sha256 is recorded with its version in `data/versions.json`.

## Dates

Each Act is dated by the "Date of Commencement" its Supplement prints, at noon in Nairobi. Where that is not a date
(for example "See Section 1"), the Act is dated by the date of the Gazette Supplement that published it, and never
before its Date of Assent. The version note of each Act gives its number, Supplement, Date of Assent and the rule used.

## How it is built

The text layer of each PDF (no OCR) becomes one file per section. The Supplement cover, the title block (number,
Dates of Assent and Commencement), the arrangement of sections, running heads and page numbers are left out. Part
headings and section headings (bold rows or margin notes) stand above the section they head.

## How it is checked

Every version is read back from git on the day it took effect and must match the corpus. A second, independent
reading of every PDF (a different PDF engine) must contain every letter and digit of each Act in the same order, with
nothing in the body left out. Results are in `REPRODUCE.md`.

## What "author" means

The author of each commit is the publisher, with an e-mail address that cannot exist; the committer is always
Lexifina.

## Limits

Only the Acts as enacted are here: no later amendments, no consolidation, and only the Acts the County Assembly posts
with a text layer. The Kenya Gazette is authoritative. This record holds only part of {name} County's legislation.

## Licence

See [LICENSE](LICENSE): written law is excluded from copyright by the Copyright Act, 2001 (Cap. 130), s. 2. Source:
County Assembly of {name}; Kenya Gazette Supplement (Government Printer).
""")

w('LICENSE', f"""Law texts

The texts in this repository are Acts of the County Assembly of {name} (Kenya) as published, in English, in the Kenya
Gazette Supplement by the Government Printer, Nairobi, and posted on the County Assembly's website
(https://{host}).

- Copyright: the Copyright Act, 2001 (Cap. 130, Laws of Kenya), section 2, defines "literary work" and ends: "but
  does not include a written law or a judicial decision". (As printed in the revised editions of Cap. 130; see WIPO
  Lex, https://www.wipo.int/wipolex/en/legislation/details/2693.) County Acts are legislation of a county assembly
  under Articles 185 and 260 of the Constitution of Kenya.
- The County Assembly's website carries a copyright footer and no terms that restrict reuse of the Acts it posts.
- The texts are reproduced without change to their wording; only the arrangement (one file per section, one
  paragraph per line) is Lexifina's. Neither the County Assembly nor the Government Printer endorses this repository.

Attribution: Source: County Assembly of {name}, https://{host}; Kenya Gazette Supplement, Government Printer, Nairobi.

Everything else (the git history's structure, the tools and the documentation): CC0 1.0 Universal,
https://creativecommons.org/publicdomain/zero/1.0/legalcode
""")

w('SOURCES.md', f"""# Sources

- County Assembly of {name}: Acts <{list_url}> (Kenya Gazette Supplements, "{name} County Acts", as PDF with a text
  layer, printed and published by the Government Printer, Nairobi).

Legal basis for reuse: Copyright Act, 2001 (Cap. 130), s. 2, definition of "literary work" (a written law is not
included). See LICENSE for the attribution.
""")

(repo / 'jurisdiction.json').write_text(json.dumps({
    'path': code.lower(), 'code': code, 'name': f'{name} County', 'level': 'country',
    'repo': f'https://github.com/lexifina/kenya-{county}-law',
    'build': f'built: {name} County Acts as enacted, from the Kenya Gazette Supplements posted by the County Assembly of {name}',
}, indent=2, ensure_ascii=False) + '\n', encoding='utf-8', newline='\n')
print('docs written', repo)
