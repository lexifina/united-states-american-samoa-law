"""gitlaw-scraper-dell (2026-10-31): write repo/README.md, LICENSE, SOURCES.md and jurisdiction.json for a Sri Lanka
Provincial Council repo. Private.

    python -X utf8 lk_prov_docs.py uva|northern|central
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from lk_prov_make import PROV  # noqa: E402

FOOTER = {'uva': '"Copyright (c) 2017 Uva Provincial Council. All Rights Reserved."',
          'northern': '"Copyright (c) 2026 Northern Provincial Council, Sri Lanka"',
          'central': 'no copyright line'}


def main(p):
    c = PROV[p]
    repo = HERE.parent / f'sri-lanka-{p}-law' / 'repo'
    repo.mkdir(parents=True, exist_ok=True)
    name, council, listing, site = c['name'], c['council'], c['listing'], c['site']
    w = lambda f, t: (repo / f).write_text(t, encoding='utf-8', newline='\n')
    w('README.md', f'''# {name} (Sri Lanka): law history in git

The statutes of the {council}, Sri Lanka, as a git history: one folder per statute, one paragraph per line, so
`git blame`, `git log` and `git diff` work line by line. The text is the English text of each statute as published in
the Gazette of the Democratic Socialist Republic of Sri Lanka (Extraordinary), Part IV (A), Provincial Councils, and
posted by the {council} on its website.

It follows the shared design of [lexifina/global-law](https://github.com/lexifina/global-law).

## What this repository holds

**Statutes as published, not yet a history.** The Council posts each statute as the Gazette Extraordinary that
published it; there is no consolidated text. So each statute is one commit holding its text as published ("oldest
version available"), credited to the Council, not to an amending law. An amending statute is its own folder; its
amendments are not applied to the statute it amends.

| Folder | What |
| --- | --- |
| one folder per statute (by the short title it gives itself) | one file per section (`000-title.md` for the heading, long title and enacting words), or one file `000-text.md` with the whole statute where its sections cannot be told apart reliably |

Statutes are enacted in Sinhala and Tamil as well; this repository holds the English text only. Where a statute says
which language prevails, it says so in its own words here. A statute is left out until it can be read reliably (see
"How it is checked"); this record holds only part of the {council}'s statutes.

## Source

[{council}: statutes]({listing}), each a PDF of the Gazette Extraordinary (Part IV (A)) with a text layer. Each PDF's
sha256 is recorded with its version in `data/versions.json`.

## Dates

Each statute is dated by the day of the Gazette Extraordinary that published it, at noon in Colombo. A statute's own
section 1 says when it comes into operation (usually on the Governor's assent); that day is not derived here.

## How it is built

The text layer of each PDF (no OCR) becomes the record. Left out: the Gazette masthead, running heads and the
Sinhala/Tamil lines in legacy fonts, page labels, printing footers, the Council Secretary's publication notice, and
marginal notes where the statute is kept as one file. Where sections are split, each section file gives its marginal
note on the line before the section text.

## How it is checked

Every version is read back from git on the day it took effect and must match the corpus. A second, independent
reading of every PDF (a different PDF engine, pdftotext) must contain every paragraph of each statute whole, letter
for letter and digit for digit, with nothing in the statute's stretch of the Gazette left out. Results are in
`REPRODUCE.md`.

## What "author" means

The author of each commit is the publisher, with an e-mail address that cannot exist; the committer is always
Lexifina.

## Limits

Only the statutes as published are here: no later amendments, no consolidation, only the English text, and only the
statutes the Council posts with a text layer that pass the check. The Gazette is authoritative.

## Licence

See [LICENSE](LICENSE): official texts of a legislative nature are not protected by copyright under the Intellectual
Property Act, No. 36 of 2003, section 8. Source: {council}; Gazette of the Democratic Socialist Republic of Sri Lanka
(Department of Government Printing).
''')
    w('LICENSE', f'''Law texts

The texts in this repository are statutes of the {council} (Sri Lanka) as published, in English, in the Gazette of
the Democratic Socialist Republic of Sri Lanka (Extraordinary), Part IV (A), Provincial Councils, by the Department of
Government Printing, and posted on the Council's website ({site}).

- Copyright: the Intellectual Property Act, No. 36 of 2003, section 8, does not extend copyright protection to any
  official text of a legislative, administrative or legal nature, or to any official translation of such a text.
  Statutes of a Provincial Council are official texts of a legislative nature (Constitution, Article 154G).
- The Council's website carries {FOOTER[p]} and no terms that restrict reuse of the statutes it posts.
- The texts are reproduced without change to their wording; only the arrangement (one file per section or per
  statute, one paragraph per line) is Lexifina's. Neither the Council nor the Department of Government Printing
  endorses this repository.

Attribution: Source: {council}, {site}; Gazette of the Democratic Socialist Republic of Sri Lanka (Extraordinary),
Part IV (A).

Everything else (the git history's structure, the tools and the documentation): CC0 1.0 Universal,
https://creativecommons.org/publicdomain/zero/1.0/legalcode
''')
    w('SOURCES.md', f'''# Sources

- {council}: statutes <{listing}> (Gazette of the Democratic Socialist Republic of Sri Lanka, Extraordinary, Part IV
  (A), English text, as PDF with a text layer).

Legal basis for reuse: Intellectual Property Act, No. 36 of 2003, section 8 (official texts of a legislative nature are
not protected). See LICENSE for the attribution.
''')
    w('jurisdiction.json', json.dumps({
        'path': c['code'].lower(), 'code': c['code'], 'name': f'{name} (Sri Lanka)', 'level': 'country',
        'repo': f'https://github.com/lexifina/sri-lanka-{p}-law',
        'build': f'built: statutes of the {council} as published in the Gazette Extraordinary, English text, posted on '
                 f'the Council\'s website'}, indent=2) + '\n')
    print('docs written', repo)


if __name__ == '__main__':
    main(sys.argv[1])
