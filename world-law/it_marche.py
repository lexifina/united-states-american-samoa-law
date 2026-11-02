"""Marche (italy-marche-law), gitlaw-scraper-dell 2026-10-30. Private; never published.

Source: the Consiglio regionale delle Marche's "Banca dati delle leggi e dei regolamenti regionali"
(www.consiglio.marche.it/banche_dati_e_documentazione/leggi/), archive of texts in force ("archivio vigente"): the
chronological index by year, then one page per law with its text in force (original or consolidated) and editor's
notes per article. One request at a time, 3.2 s apart.

    python -X utf8 scripts/world-law/it_marche.py fetch
    python -X utf8 scripts/world-law/it_marche.py parse
    python -X utf8 scripts/world-law/it_marche.py publish <part> ...
    python -X utf8 scripts/world-law/it_marche.py letters <part>
"""
from __future__ import annotations

import hashlib
import html
import json
import re
import sys
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import it_fetch  # noqa: E402
import it_regions as R  # noqa: E402

SLUG = 'marche'
HOST = 'www.consiglio.marche.it'
BASE = 'https://www.consiglio.marche.it/banche_dati_e_documentazione/leggi/'
STATUTO = BASE + 'dettaglio.php?arc=vig&idl=1595'
DOCS_DATE = '2026-10-30'
PART_SIZE = 50
MONTHS = ['gennaio', 'febbraio', 'marzo', 'aprile', 'maggio', 'giugno', 'luglio', 'agosto', 'settembre', 'ottobre',
          'novembre', 'dicembre']

SRC = {
    'host': HOST,
    'publisher': 'Consiglio regionale delle Marche, Banca dati delle leggi e dei regolamenti regionali',
    'short': 'the Consiglio regionale delle Marche\'s law database',
    'url': BASE,
    'licence': 'L. 633/1941 art. 5: official acts are not protected. Site terms (Note legali): pages may be '
               'downloaded for personal, non-commercial use.',
    'licence_note': ('Source: Consiglio regionale delle Marche, Banca dati delle leggi e dei regolamenti regionali, '
                     'archivio dei testi vigenti, https://www.consiglio.marche.it/banche_dati_e_documentazione/leggi/'),
    'source_notes': 'The archive of texts in force: chronological index by year and one page per law.',
    'in_force_rule': ('Statuto della Regione Marche, art. 31 (laws enter into force on the fifteenth day after '
                      'publication unless they set another term). Not used for dating: each text is dated the day '
                      'it was read.'),
    'history': 'current-only',
    'history_note': ' in its archive of texts in force (its other archive holds each law only as first published)',
    'source_md': ('The law database of the Consiglio regionale delle Marche, '
                  '<https://www.consiglio.marche.it/banche_dati_e_documentazione/leggi/>, archive of texts in force '
                  '("archivio dei testi vigenti"): for each regional law, its original text or, when it has been '
                  'amended, its consolidated text, with editor\'s notes naming the amending laws. The notes are not '
                  'copied. Each text here is the page of one law in that archive.'),
    'files_md': ('`<act>/art-005.md` is Art. 5, `art-005-bis.md` Art. 5 bis; `preambolo.md` holds anything printed '
                 'before the first article. Headings of titles, chapters and sections stay in the file of the '
                 'article they stand before. Acts are named `lr-<year>-<number>`; the Statute is `statuto/`.'),
    'official_md': 'The binding text is the one published in the Bollettino Ufficiale della Regione Marche.',
    'terms_md': ('The site\'s legal notes ("Note legali") say its pages may be downloaded only for personal, '
                 'non-commercial use unless stated otherwise. The law texts are official acts outside copyright '
                 '(art. 5 above); this repository is free and non-commercial and credits the source.'),
    'scope_note': 'Regulations and the amending statutory laws are not included.',
}


def get(url: str) -> str:
    b = it_fetch.get(url, timeout=120)
    return b.decode('cp1252', 'replace') if b else ''


YEARS = list(range(1971, 2027))


def year_url(y: int) -> str:
    return BASE + f'cronologico.php?arc=vig&anno={y}'


ITEM = re.compile(r'<a href="(dettaglio\.php\?arc=vig&idl=\d+)"[^>]*>LEGGE REGIONALE (\d{1,2}) (\w+) (\d{4}), n\. ?(\d+)'
                  r'</a></strong><br><i>(.*?)</i></li>', re.S)


def catalogue(fetch: bool = False) -> list[dict]:
    out = []
    for y in YEARS:
        u = year_url(y)
        if not fetch and not it_fetch.path_for(u).exists():
            continue
        t = get(u)
        i = t.find('<strong>Leggi regionali</strong>')
        if i < 0:
            continue
        j = t.find('</ul>', i)
        seg = t[i:j if j > 0 else None]
        for m in ITEM.finditer(seg):
            href, d, mon, yy, n, title = m.groups()
            mon = mon.lower()
            if mon not in MONTHS:
                continue
            out.append({'url': BASE + href, 'date': f'{yy}-{MONTHS.index(mon) + 1:02d}-{int(d):02d}', 'num': int(n),
                        'title': R.clean_line(html.unescape(re.sub(r'<[^>]+>', ' ', title)))})
    out.sort(key=lambda r: (r['date'][:4], r['num']))
    seen, res = set(), []
    for r in out:
        k = (r['date'][:4], r['num'])
        if k not in seen:
            seen.add(k)
            res.append(r)
    return res


def fetch():
    get(STATUTO)
    for y in YEARS:
        try:
            get(year_url(y))
        except it_fetch.Stopped as e:
            print('STOPPED', e, flush=True)
            return
    laws = catalogue()
    print(len(laws), 'laws', flush=True)
    for i, r in enumerate(laws):
        R.wait_cpu()
        try:
            get(r['url'])
        except it_fetch.Stopped as e:
            print('STOPPED', e, flush=True)
            return
        if i % 50 == 0:
            print(i, flush=True)
    print('done', flush=True)


# ---------------------------------------------------------------- parse

NOTE = re.compile(r'<strong>\s*Not[ae]\s+relativ[ae][^<]*</strong>\s*<hr>\s*<i>.*?</i>', re.S | re.I)


def body_of(t: str) -> str:
    i = t.find('<h2>Sommario</h2>')
    if i < 0:
        return ''
    j = t.find('</div>', i)
    k = t.find('<div class="col-lg-4', j)
    return t[j + 6:k if k > 0 else None]


def lines_html(s: str) -> list[str]:
    s = re.sub(r'(?i)<br\s*/?>|</?(span|div|center|p|li|tr|h\d|table|ul|ol)\b[^>]*>|</br>', '\x01', s)
    s = re.sub(r'<[^<>]*>', '', s)
    s = s.replace('<b\x01', '\x01').replace('<', ' ')
    s = html.unescape(s)
    return [x for x in (R.clean_line(re.sub(r'\s+', ' ', p)) for p in s.split('\x01')) if x]


ANCH = re.compile(r'<a name="#?(art|tit|cap|sez)([0-9]+)"', re.I)


def units_of(t: str) -> dict:
    b = NOTE.sub('', body_of(t))
    units: dict[str, dict] = {}
    pieces = []
    last = 0
    marks = list(ANCH.finditer(b))
    pieces.append(('pre', b[:marks[0].start()] if marks else b))
    for i, m in enumerate(marks):
        end = marks[i + 1].start() if i + 1 < len(marks) else len(b)
        pieces.append((m.group(1).lower() + m.group(2), b[m.start():end]))
    # the opening tag before an anchor (<center>, <div ...>) sits in the previous piece: harmless (no text)
    pending: list[str] = []
    cur = None
    for name, seg in pieces:
        ls = lines_html(seg)
        if name.startswith('art') and name != 'art0' and ls:
            head = ls[0]
            m = re.match(r'(?i)^Art(?:icolo)?\.?\s*(\d+)\s*(bis|ter|quater|quinquies|sexies|septies|octies|novies|'
                         r'decies|undecies|duodecies)?\b', head)
            if m:
                key = f'art-{int(m.group(1)):03d}' + (f'-{m.group(2).lower()}' if m.group(2) else '')
                lab = f'Art. {int(m.group(1))}' + (f' {m.group(2).lower()}' if m.group(2) else '')
            elif re.match(r'(?i)^Articolo unico', head):
                key, lab = 'art-001', 'Articolo unico'
            else:
                key, lab = f'art-x{len(units):03d}', head[:40]
            k, n = key, 2
            while k in units:
                k, n = f'{key}-dup{n}', n + 1
            units[k] = {'label': lab, 'kind': 'art', 'text': '\n'.join(pending + ls) + '\n'}
            pending = []
            cur = k
        elif name in ('pre', 'art0'):
            if ls:
                if 'preambolo' in units:
                    units['preambolo']['text'] += '\n'.join(ls) + '\n'
                else:
                    units['preambolo'] = {'label': 'Preambolo', 'kind': 'preamble', 'text': '\n'.join(ls) + '\n'}
        else:
            pending.extend(ls)
    if pending:
        if cur:
            units[cur]['text'] += '\n'.join(pending) + '\n'
        else:
            units['preambolo'] = {'label': 'Preambolo', 'kind': 'preamble', 'text': '\n'.join(pending) + '\n'}
    return units


def label(r: dict) -> str:
    y, m, d = r['date'].split('-')
    return f'L.R. {int(d)} {MONTHS[int(m) - 1]} {y}, n. {r["num"]}'


def act_of(r: dict, slug: str | None = None) -> tuple[dict, dict] | None:
    raw = it_fetch.get(r['url'])
    if not raw:
        return None
    t = raw.decode('cp1252', 'replace')
    units = units_of(t)
    if not any(u['kind'] == 'art' for u in units.values()):
        return None
    key = slug and 'ls-2005-1' or f'lr-{r["date"][:4]}-{r["num"]}'
    lab = 'Legge statutaria 8 marzo 2005, n. 1' if slug else label(r)
    law = {'label': lab, 'title': r['title'][:300], 'kind': 'law', 'enacted': r['date'], 'published': None,
           'url': r['url'], 'temporary_until': None, 'restores': None, 'note': None}
    v = {'from': DOCS_DATE, 'source_url': r['url'], 'sha256': hashlib.sha256(raw).hexdigest(), 'units': units,
         'credits': {}}
    act = {'slug': slug or key, 'short': 'Statuto' if slug else f'L.R. {r["num"]}/{r["date"][:4]}',
           'title': ('Statuto della Regione Marche (Legge statutaria 8 marzo 2005, n. 1)' if slug
                     else f'{lab}: {r["title"]}')[:400],
           'url': r['url'], 'first_law': None, 'earlier_laws': [key], 'versions': [v]}
    return act, {key: law}


def decisions() -> list[str]:
    return [
        'Every regional law in the database\'s archive of texts in force (chronological index, section "Leggi '
        'regionali") is included, with the Statute; regulations and the statutory laws that amend the Statute are not.',
        'Each law is recorded by its text in force on the retrieval day only, as its oldest version available, dated '
        'that day and credited to the database as publisher.',
        'A law whose page does not read back letter for letter (a few pages hold tables with broken markup) is left '
        'out.',
        'The editor\'s notes printed after each article ("Nota relativa all\'articolo ...") are not copied.',
        'Units: anything before the first article (preambolo), one file per article; headings of titles, chapters '
        'and sections go with the next article.',
    ]


AI_USE = ['A model (Claude) wrote the fetch and parse code; it wrote no law text. Every word of law comes from the '
          'Consiglio regionale delle Marche\'s pages.']


def parse():
    laws = catalogue()
    plan = [(f'30-leggi-{i // PART_SIZE + 1:02d}', laws[i:i + PART_SIZE]) for i in range(0, len(laws), PART_SIZE)]
    ready = []
    if it_fetch.path_for(STATUTO).exists():
        a = act_of({'url': STATUTO, 'date': '2005-03-08', 'num': 1, 'title': 'Statuto della Regione Marche'},
                   slug='statuto')
        if a:
            part = {'country': R.country_block(SLUG, SRC), 'laws': a[1], 'acts': [a[0]],
                    'sources': [R.source_block(SRC, DOCS_DATE)], 'decisions': decisions(), 'ai_use': AI_USE}
            R.write_part(SLUG, '10-statuto', part)
            ready.append('10-statuto')
    for name, members in plan:
        if not all(it_fetch.path_for(r['url']).exists() or it_fetch.path_for(r['url']).with_suffix('.404').exists()
                   for r in members):
            break
        part = {'country': R.country_block(SLUG, SRC), 'laws': {}, 'acts': []}
        for r in members:
            x = act_of(r)
            if x and not act_problems(x[0]):
                part['acts'].append(x[0])
                part['laws'].update(x[1])
            elif x:
                print('left out (text does not read back cleanly):', x[0]['slug'], flush=True)
        if part['acts']:
            R.write_part(SLUG, name, part)
            ready.append(name)
    print('parts ready:', ready, 'of', len(plan) + 1)
    return ready


# ---------------------------------------------------------------- independent letters check (html.parser)

class Text(HTMLParser):
    """All text data of the law body, skipping the <i> that follows a "Nota relativa" heading."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out, self.skip, self.after_note, self.in_strong, self.strong = [], 0, False, False, ''

    def handle_starttag(self, tag, attrs):
        if tag == 'strong':
            self.in_strong, self.strong = True, ''
        if tag == 'i' and self.after_note:
            self.skip += 1

    def handle_endtag(self, tag):
        if tag == 'strong':
            self.in_strong = False
            if re.match(r'(?i)\s*not[ae]\s+relativ', self.strong):
                self.after_note = True
                self.out = self.out[:-1] if self.out and self.out[-1] == self.strong else self.out
        if tag == 'i' and self.skip:
            self.skip -= 1
            self.after_note = False

    def handle_data(self, d):
        if self.in_strong:
            self.strong += d
        if not self.skip:
            self.out.append(d)


def letters_check(slug: str, part_name: str) -> list[str]:
    part = json.loads((R.folder(slug) / 'corpus.d' / f'{part_name}.json').read_text(encoding='utf-8'))
    return [x for act in part['acts'] for x in act_problems(act)]


def act_problems(act: dict) -> list[str]:
    probs = []
    if True:
        for v in act['versions']:
            raw = it_fetch.path_for(v['source_url']).read_bytes()
            if hashlib.sha256(raw).hexdigest() != v['sha256']:
                probs.append(f'{act["slug"]}: sha256 differs')
                continue
            t = raw.decode('cp1252', 'replace')
            p = Text()
            p.feed(body_of(t))
            src = R.letters(''.join(p.out))
            mine = ''.join(u['text'] for u in v['units'].values())
            if Counter(src) != Counter(R.letters(mine)):
                ca, cb = Counter(src), Counter(R.letters(mine))
                probs.append(f'{act["slug"]}: source-only {dict((ca - cb).most_common(6))} '
                             f'corpus-only {dict((cb - ca).most_common(6))}')
                continue
            pos = 0
            for k, u in v['units'].items():
                lu = R.letters(u['text'])
                i = src.find(lu, pos)
                if i < 0:
                    probs.append(f'{act["slug"]} {k}: not found in order')
                    break
                pos = i + len(lu)
    return probs


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    R.below_normal()
    cmd = sys.argv[1]
    if cmd == 'fetch':
        fetch()
    elif cmd == 'parse':
        parse()
    elif cmd == 'letters':
        pr = letters_check(SLUG, sys.argv[2])
        print('\n'.join(pr[:30]) or 'clean', len(pr))
    elif cmd == 'publish':
        for name in sys.argv[2:]:
            print(name, R.publish(SLUG, SRC, name, DOCS_DATE, letters_check)[:600], flush=True)
