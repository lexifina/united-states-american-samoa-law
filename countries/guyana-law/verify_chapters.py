"""verify.py's word-count check for the further chapters (corpus.d/50-chapters.json, 55-companies.json,
60-chapters.json, and chapters_extra.py's 70-summary-jurisdiction.json, 75-family.json, 80-land.json): each
act's latest version against today's official text on mola.gov.gy (L.R.O. 1/2022 where the Ministry serves it; the
L.R.O. 1/2012 PDF it still serves for Caps. 10:01, 89:01, 98:01 and the later volumes).

    python -X utf8 verify_chapters.py [part.json] [--older]     (default: corpus.d/50-chapters.json)

--older also checks each act's 2012 version against its own L.R.O. 1/2012 PDF (informational). Words left out on
purpose by parse.tidy_sections (the cross-headings between sections) are added to verify.py's own left-out list.
Reads the cache only.
"""
import json
import sys
from pathlib import Path

import chapters
import chapters_extra
import chapters_more
import companies
import verify

HERE = Path(__file__).resolve().parent


def main(argv: list[str]) -> int:
    older = '--older' in argv
    argv = [a for a in argv if a != '--older']
    part = Path(argv[0]) if argv else HERE / 'corpus.d' / '50-chapters.json'
    c = json.loads(part.read_text(encoding='utf-8'))
    known = {ch['slug']: ch for ch in chapters.CHAPTERS + chapters_more.MORE + [companies.CH] + chapters_extra.ALL}
    todo = [known[a['slug']] for a in c['acts']]
    for ch in todo:   # fills parse.DROPPED (the cross-headings left out on purpose)
        if ch is companies.CH:
            companies.units()
        elif ch in chapters_more.MORE:
            chapters_more.act(ch)
        elif ch in chapters_extra.ALL:
            chapters_extra.act(ch)
        else:
            chapters.act(ch)
    orig = verify.layout._is_heading
    verify.layout._is_heading = lambda t: orig(t) or t in chapters.DROPPED
    ok = []
    for ch in todo:
        ed = 'e2022' if 'e2022' in ch['editions'] else 'e2012'
        verify.ACTS[ch['slug']] = (ch['editions'][ed], 'sec', ch.get('marker', r'An\s+Act'))
        ok.append(verify.check(c, ch['slug']))
    if older:
        for ch in todo:
            if 'e2022' not in ch['editions'] or 'e2012' not in ch['editions']:
                continue
            a = next(x for x in c['acts'] if x['slug'] == ch['slug'])
            url = ch['editions']['e2012'][0]
            v = next(x for x in a['versions'] if x['source_url'] == url)
            verify.ACTS[ch['slug']] = (ch['editions']['e2012'], 'sec', ch.get('marker', r'An\s+Act'))
            print('[2012 version against its own L.R.O. 1/2012 PDF]')
            verify.check({'acts': [{**a, 'versions': [v]}]}, ch['slug'])
    return 0 if all(ok) else 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
