"""Build corpus.json for the Philippines from the cache only (no network). Deterministic: same cache, same bytes.

    python -X utf8 parse.py

Sources are the Official Gazette's own pages, read through pinned Internet Archive `id_` captures (fetch.py).
"""
from __future__ import annotations

import hashlib
import html
import json
import os
import re
from pathlib import Path

import fetch

HERE = Path(__file__).resolve().parent
RETRIEVED = '2026-10-28'

ROMAN = {'I': 1, 'II': 2, 'III': 3, 'IV': 4, 'V': 5, 'VI': 6, 'VII': 7, 'VIII': 8, 'IX': 9, 'X': 10, 'XI': 11,
         'XII': 12, 'XIII': 13, 'XIV': 14, 'XV': 15, 'XVI': 16, 'XVII': 17, 'XVIII': 18}


# ---------------------------------------------------------------- HTML -> blocks

def norm(s: str) -> str:
    s = html.unescape(s)
    s = s.replace(' ', ' ').replace('​', '')
    s = s.replace('“', '"').replace('”', '"').replace('‘', "'").replace('’', "'")
    s = s.replace('″', '"').replace('′', "'")
    s = re.sub(r'[ \t\r\n]+', ' ', s)
    return s.strip()


def blocks(raw: bytes) -> list[tuple[bool, str]]:
    """The entry-content of an Official Gazette page as (centered?, line) pairs, one per <p> or <br> line."""
    t = raw.decode('utf-8')
    i = t.index('<div class="entry-content">')
    j = t.index('<!-- .entry-content -->', i)
    t = t[i:j]
    t = re.sub(r'<(script|style)\b.*?</\1>', '', t, flags=re.S | re.I)
    out = []
    for m in re.finditer(r'<(p|h[1-6]|li)\b([^>]*)>(.*?)</\1>', t, flags=re.S | re.I):
        attrs, inner = m.group(2), m.group(3)
        centered = bool(re.search(r'align="center"|text-align:\s*center', attrs, flags=re.I))
        for part in re.split(r'<br\s*/?>', inner, flags=re.I):
            line = norm(re.sub(r'<[^>]+>', '', part))
            if line:
                out.append((centered, line))
    return out


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


# ---------------------------------------------------------------- the 1987 Constitution

PART_RE = re.compile(r'^([A-D])\.\s+(.+)$')


def constitution():
    url, raw = fetch.read('constitution')
    bl = blocks(raw)
    # Start at the centered PREAMBLE heading that follows the page's table of contents; stop at "Ratified:".
    k = next(n for n, (c, l) in enumerate(bl) if c and l == 'PREAMBLE')
    units: dict[str, dict] = {}
    order: list[str] = []
    dropped: list[str] = []
    art = None
    art_title = None
    part = None
    key = 'preamble'
    units[key] = {'label': 'Preamble', 'kind': 'preamble', 'lines': ['# Preamble']}
    order.append(key)
    pending_title = False
    for c, line in bl[k + 1:]:
        if line.startswith('Ratified:'):
            break
        m = re.fullmatch(r'ARTICLE ([IVX]+)', line)
        if c and m:
            art = ROMAN[m.group(1)]
            part = None
            pending_title = True
            key = f'art-{art:02d}'
            units[key] = {'label': f'Article {m.group(1)}', 'kind': 'article', 'lines': [], 'roman': m.group(1)}
            order.append(key)
            continue
        if c and pending_title:
            art_title = line
            units[key]['title'] = line
            pending_title = False
            continue
        if c:
            pm = PART_RE.match(line)
            if pm and art == 9:
                part = pm.group(1).lower()
                dropped.append(f'Article IX part heading "{line}"')
                continue
            dropped.append(f'Article {units[f"art-{art:02d}"]["roman"]} subheading "{line}"')
            continue
        sm = re.match(r'SECTION (\d+)\.', line)
        if sm:
            n = int(sm.group(1))
            roman = units[f'art-{art:02d}']['roman']
            key = f'art-{art:02d}' + (f'-{part}' if part else '') + f'-sec-{n:02d}'
            if key in units:
                raise SystemExit(f'duplicate unit {key}')
            lab = f'Article {roman}' + (f'-{part.upper()}' if part else '') + f', Section {n}'
            units[key] = {'label': lab, 'kind': 'section', 'lines': [f'# {lab}']}
            order.append(key)
        units[key]['lines'].append(line)
    out = {}
    for key in order:
        u = units[key]
        if u['kind'] == 'article':
            if not u['lines']:
                continue  # an article heading whose words all sit in its sections
            u['lines'] = [f'# {u["label"]}'] + u['lines']
        out[key] = {'label': u['label'], 'kind': u['kind'], 'text': '\n'.join(u['lines']) + '\n'}
    return url, raw, out, dropped


# ---------------------------------------------------------------- Republic Act No. 10173

def ra_10173():
    url, raw = fetch.read('ra-10173')
    bl = blocks(raw)
    units: dict[str, dict] = {}
    key = None
    dropped = []
    for c, line in bl:
        if line.startswith('Approved,'):
            break
        sm = re.match(r'(?:SECTION|SEC\.?) (\d+)\s*\.', line)  # s. 22 is printed "SEC 22."
        if sm and not c:
            n = int(sm.group(1))
            key = f'sec-{n:02d}'
            if key in units:
                raise SystemExit(f'duplicate unit {key}')
            units[key] = {'label': f'Section {n}', 'kind': 'section', 'lines': [f'# Section {n}']}
        if key is None:
            continue
        if c:
            dropped.append(line)
            continue
        units[key]['lines'].append(line)
    out = {k: {'label': u['label'], 'kind': u['kind'], 'text': '\n'.join(u['lines']) + '\n'} for k, u in units.items()}
    return url, raw, out, dropped


# ---------------------------------------------------------------- corpus

def main() -> None:
    c_url, c_raw, c_units, c_dropped = constitution()
    d_url, d_raw, d_units, d_dropped = ra_10173()
    corpus = {
        'country': {
            'code': 'PH', 'name': 'Philippines', 'slug': 'philippines', 'lang': 'en', 'tz': 'Asia/Manila',
            'future_branch': 'future',
            'publisher': {'name': 'Official Gazette of the Republic of the Philippines',
                          'email': 'publisher@officialgazette.gov.ph.invalid'},
            'default_in_force_rule': {
                'text': 'Executive Order No. 200 (1987), s. 1, amending Civil Code art. 2: "Laws shall take effect after '
                        'fifteen days following the completion of their publication either in the Official Gazette or '
                        'in a newspaper of general circulation in the Philippines, unless it is otherwise provided."',
                'source': fetch.PLAN['eo-200'][1]},
            'licence_note': 'Official Gazette of the Republic of the Philippines (officialgazette.gov.ph): "All content is '
                            'in the public domain unless otherwise stated." Under Republic Act No. 8293 (Intellectual '
                            'Property Code), s. 176, no copyright subsists in any work of the Government of the Philippines.',
        },
        'sources': [
            {'name': 'Official Gazette of the Republic of the Philippines (officialgazette.gov.ph), read through Internet Archive id_ captures',
             'url': 'https://www.officialgazette.gov.ph', 'retrieved': RETRIEVED, 'requests': len(fetch.PLAN),
             'licence': 'Public domain ("All content is in the public domain unless otherwise stated"; RA 8293 s. 176)',
             'notes': 'The site answers this machine with a Cloudflare challenge, so each page is read from a pinned '
                      'archive.org capture: ' + '; '.join(f'{k} {fetch.archive_url(*v)}' for k, v in fetch.PLAN.items())},
            {'name': 'Internet Archive Wayback Machine', 'url': 'https://web.archive.org', 'retrieved': RETRIEVED,
             'requests': None, 'licence': 'Internet Archive terms of use', 'notes': 'Raw id_ captures, no banner.'},
        ],
        'laws': {
            'constitution-1987': {
                'label': '1987 Constitution', 'title': 'The Constitution of the Republic of the Philippines',
                'kind': 'referendum', 'enacted': '1987-02-02', 'published': None,
                'url': fetch.PLAN['constitution'][1], 'temporary_until': None, 'restores': None,
                'note': 'Ratified in the plebiscite of 2 February 1987; Art. XVIII, s. 27: it "shall take effect '
                        'immediately upon its ratification".'},
            'ra-10173': {
                'label': 'Republic Act No. 10173', 'title': 'Data Privacy Act of 2012', 'kind': 'law',
                'enacted': '2012-08-15', 'published': '2012-08-24',
                'url': fetch.PLAN['ra-10173'][1], 'temporary_until': None, 'restores': None, 'note': None},
        },
        'acts': [
            {'slug': 'constitution', 'short': '1987 Const.',
             'title': 'The Constitution of the Republic of the Philippines (1987)',
             'url': 'https://www.officialgazette.gov.ph/constitutions/1987-constitution/',
             'first_law': 'constitution-1987', 'earlier_laws': [],
             'versions': [{'from': '1987-02-02', 'source_url': c_url, 'sha256': sha(c_raw), 'units': c_units,
                           'credits': {}}]},
            {'slug': 'data-privacy-act', 'short': 'RA 10173',
             'title': 'Data Privacy Act of 2012 (Republic Act No. 10173)',
             'url': 'https://www.officialgazette.gov.ph/2012/08/15/republic-act-no-10173/',
             'first_law': 'ra-10173', 'earlier_laws': [],
             'versions': [{'from': '2012-09-08', 'source_url': d_url, 'sha256': sha(d_raw), 'units': d_units,
                           'credits': {}}]},
        ],
        'applies': [],
        'decisions': [
            'The Official Gazette is the source of every text; it blocks this machine with a Cloudflare challenge, so '
            'each page is read from its newest archive.org capture with HTTP 200 (pinned in fetch.py).',
            'The 1987 Constitution has never been amended, so it has one version, in force 2 February 1987, the day of '
            'the plebiscite (Art. XVIII, s. 27; De Leon v. Esguerra, G.R. No. 78059, 31 August 1987).',
            f'Constitution: the Gazette page prints Article headings and subheadings as centered lines. Article '
            f'headings become each file\'s first line; Article IX\'s part letters (A to D) are kept in the keys and '
            f'labels because its sections restart in each part; the other {len([d for d in c_dropped if "part heading" not in d])} '
            f'subheadings (for example "Principles", "State Policies") are left out of the files.',
            'Constitution: the closing "Ratified: February 2, 1987" line, the table of contents and the page\'s '
            '"Source: CDAsia" line are not provision text and are left out.',
            'Data Privacy Act: Republic Act No. 10173 was approved on 15 August 2012; s. 45 makes it take effect '
            '"fifteen (15) days after its publication in at least two (2) national newspapers of general '
            'circulation". It was published on 24 August 2012, so it took effect on 8 September 2012. The '
            'publication day is from secondary reporting (Bloomberg Law), as no official page found gives it.',
            'Data Privacy Act: no amending Act was found on the Official Gazette; it has one version. Section 44 '
            'amends s. 7 of RA 9372, which is outside this repository.',
            f'Data Privacy Act: the title block, enacting clause, chapter headings ({len(d_dropped)} centered lines) and '
            'the signature blocks after s. 45 are left out of the files.',
            'Typesetting is normalised once: no-break spaces become spaces, runs of white space collapse, and curly '
            'quotes become straight quotes. Italics and bold are dropped. Dashes are kept as printed.',
        ],
        'ai_use': ['Claude Code (Claude Opus 5.5, claude-opus-5-5) wrote fetch.py and parse.py and chose the sources. '
                   'No model wrote or edited legal text: every word is parsed by code from the Official Gazette pages.'],
    }
    tmp = HERE / 'corpus.json.tmp'
    tmp.write_text(json.dumps(corpus, ensure_ascii=False, indent=1, sort_keys=False) + '\n', encoding='utf-8', newline='\n')
    os.replace(tmp, HERE / 'corpus.json')
    print('constitution', len(c_units), 'units; dropped', len(c_dropped))
    print('ra 10173', len(d_units), 'units; dropped', len(d_dropped))


if __name__ == '__main__':
    main()
