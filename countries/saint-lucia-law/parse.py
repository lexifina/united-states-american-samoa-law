"""Read the cached Revised Laws of Saint Lucia (2023) pages and write corpus.json (scripts/gitlaw_common/SCHEMA.md).

Phase 1 (first cut, written at wind-down): the Constitution's current text as one "oldest version available"
version. No network: reads only .cache/ (filled by crawl.py / fetch.py).
"""
from __future__ import annotations

import hashlib
import html
import json
import os
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import fetch  # noqa: E402

BASE = 'https://attorneygeneralchambers.com/laws-of-saint-lucia/'
NOTE = re.compile(r'\(\s*((?:Amended|Substituted|Inserted|Repealed|Deleted)\s+by[^)]*)\)')


def norm(s: str) -> str:
    s = html.unescape(s).replace(' ', ' ')
    s = s.replace('‘', "'").replace('’', "'").replace('“', '"').replace('”', '"')
    s = s.replace('–', '—')
    return re.sub(r'\s+', ' ', s).strip()


def doc(url: str) -> str:
    t = fetch.cached(url).decode('utf-8')
    i = t.find('<section id="document">')
    return t[i:t.find('</section>', i)]


def lines_of(sec_html: str) -> tuple[list[str], list[str]]:
    """Block elements -> one line each; amendment notes are removed from the text and returned."""
    s = re.sub(r'<br\s*/?>', ' ', sec_html)
    s = re.sub(r'</td>\s*<td[^>]*>', ' ', s)
    s = re.sub(r'<td\s*/>', '', s)
    blocks = re.split(r'</?(?:p|h\d|tr|li|ol|table|tbody|colgroup|section)[^>]*>', s)
    out, notes = [], []
    for b in blocks:
        t = norm(re.sub(r'<[^>]+>', ' ', b))
        notes += NOTE.findall(t)
        t = norm(NOTE.sub('', t))
        if t:
            out.append(t)
    return out, notes


def heading_key(h: str) -> tuple[str, str] | None:
    m = re.match(r'^(\d+)([A-Z]?)\.\s+(.*)$', h)
    if m:
        return f'sec-{int(m.group(1)):03d}{m.group(2).lower()}', f's. {m.group(1)}{m.group(2)}'
    m = re.match(r'^Schedule (\d+)$', h, re.I)
    if m:
        return f'sch-{m.group(1)}', f'Schedule {m.group(1)}'
    return None


def toc(act: str) -> list[str]:
    t = fetch.cached(BASE + act).decode('utf-8')
    return list(dict.fromkeys(re.findall(r'href="/laws-of-saint-lucia/' + re.escape(act) + r'/([^"#?]*)"', t)))


def constitution() -> tuple[dict, dict, list[str]]:
    act = 'constitution-of-saint-lucia'
    units: dict[str, dict] = {}
    notes_by: dict[str, list[str]] = {}
    srcs = []
    # preamble from the act page
    a, _ = lines_of(doc(BASE + act + '/act'))
    i = next(n for n, l in enumerate(a) if l.startswith('WHEREAS the People'))
    j = next(n for n, l in enumerate(a) if l.startswith('NOW, THEREFORE'))
    units['preamble'] = {'label': 'Preamble', 'kind': 'preamble', 'text': '# Preamble\n' + '\n'.join(a[i:j + 1]) + '\n'}
    srcs.append(BASE + act + '/act')
    cur = None
    for h in toc(act):
        if h == 'act' or h.startswith('part-1-') or h.startswith('part-2-') or h.startswith('part-3-') \
                or h.startswith('part-4-') or h.startswith('part-5-') or h.startswith('part-6-'):
            continue
        url = BASE + act + '/' + h
        if fetch.cached(url) is None:
            raise SystemExit(f'not cached: {url}')
        ls, ns = lines_of(doc(url))
        srcs.append(url)
        if h.startswith('part-i'):  # Schedule 1, Parts I and II
            units[cur]['text'] += '\n'.join(ls) + '\n'
            continue
        k = heading_key(ls[0])
        if not k:
            raise SystemExit(f'no heading: {h} {ls[:1]}')
        key, label = k
        units[key] = {'label': label, 'kind': 'schedule' if key.startswith('sch') else 'section',
                      'text': '# ' + ls[0] + '\n' + '\n'.join(ls[1:]) + ('\n' if len(ls) > 1 else '')}
        notes_by[key] = ns
        cur = key
        if h == 'schedule-3':
            break
    sha = hashlib.sha256(b''.join(fetch.cached(u) for u in srcs)).hexdigest()
    return units, notes_by, [sha]


def main() -> None:
    units, notes, (sha,) = constitution()
    laws = {
        'si-1978-1901': {'label': 'S.I. 1978/1901 (U.K.)', 'title': 'The Saint Lucia Constitution Order 1978',
                         'kind': 'law', 'enacted': '1978-12-20', 'published': None,
                         'url': 'http://npc.govt.lc/files/documents/Constitution of Saint Lucia.pdf'},
        'act-17-1980': {'label': 'Act 17 of 1980', 'title': 'amending the Constitution (section 25)', 'kind': 'law',
                        'enacted': None, 'published': None, 'url': None},
        'act-2-2023': {'label': 'Act 2 of 2023', 'title': 'Constitution of Saint Lucia (Amendment) Act, 2023',
                       'kind': 'law', 'enacted': '2023-03-08', 'published': '2023-03-09',
                       'url': 'https://npc.govt.lc/laws/acts/2023'},
        'act-7-2023': {'label': 'Act 7 of 2023', 'title': 'Constitution of Saint Lucia (Amendment) (No. 2) Act, 2023',
                       'kind': 'law', 'enacted': '2023-03-22', 'published': '2023-03-27',
                       'url': 'https://npc.govt.lc/laws/acts/2023'},
    }
    corpus = {
        'country': {
            'code': 'LC', 'name': 'Saint Lucia', 'slug': 'saint-lucia', 'lang': 'en', 'tz': 'America/St_Lucia',
            'future_branch': 'future',
            'publisher': {'name': "Attorney General's Chambers of Saint Lucia (Revised Laws of Saint Lucia)",
                          'email': 'publisher@attorneygeneralchambers.invalid'},
            'default_in_force_rule': {
                'text': 'Interpretation Act, Cap. 1.06: an Act comes into operation on publication in the Gazette unless '
                        'it provides otherwise (not yet cited from the source; to verify)',
                'source': BASE + 'interpretation-act'},
            'licence_note': "Revised Laws of Saint Lucia (2023), Attorney General's Chambers of Saint Lucia; "
                            'no licence stated on the site.'},
        'sources': [{'name': 'Revised Laws of Saint Lucia (2023), Attorney General\'s Chambers',
                     'url': BASE, 'retrieved': '2026-10-28',
                     'requests': sum(1 for _ in open(HERE / '.cache' / 'requests.jsonl', encoding='utf-8')),
                     'licence': 'none stated', 'notes': 'section-level HTML; amendment notes per provision'}],
        'laws': laws,
        'acts': [{
            'slug': 'constitution', 'short': 'Constitution', 'title': 'Constitution of Saint Lucia',
            'url': BASE + 'constitution-of-saint-lucia', 'first_law': None,
            'earlier_laws': ['si-1978-1901', 'act-17-1980', 'act-2-2023', 'act-7-2023'],
            'versions': [{
                'from': '2023-03-27', 'source_url': BASE + 'constitution-of-saint-lucia', 'sha256': sha,
                'units': dict(sorted(units.items())), 'credits': {},
                'note': "Today's text from the Revised Laws of Saint Lucia (2023), dated by the in-force day of the "
                        'latest amendment it lists (Act 7 of 2023, 27 March 2023). Earlier versions are not built yet.'}]}],
        'applies': [],
        'decisions': [
            'First cut at wind-down: the Constitution is committed as one "oldest version available" version (FORK.md rule 1).',
            'The version is dated 2023-03-27, the in-force day the source gives for Act 7 of 2023, its newest listed amendment.',
            'Amendment notes such as "(Amended by Act 2 of 2023)" are removed from the text; they are the basis for '
            'crediting once older versions are built.',
            'Only Schedule 1 to the Order (the Constitution) is built; the Order itself and later instruments shown on '
            'the same pages are left out.'],
        'ai_use': ['none: text parsed by code from the official HTML; no model wrote or edited legal text.'],
    }
    tmp = HERE / 'corpus.json.tmp'
    tmp.write_text(json.dumps(corpus, ensure_ascii=False, indent=1) + '\n', encoding='utf-8', newline='\n')
    os.replace(tmp, HERE / 'corpus.json')
    print(len(units), 'units;', sum(1 for v in notes.values() if v), 'with notes')


if __name__ == '__main__':
    main()
