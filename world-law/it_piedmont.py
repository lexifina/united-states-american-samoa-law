"""Piedmont (italy-piedmont-law), gitlaw-scraper-dell 2026-10-30. Private; never published.

Source: Arianna (Consiglio regionale del Piemonte). The catalogue is Regione Piemonte's open dataset "Arianna - Leggi
regionali storiche e vigenti, regolamenti regionali" (CC BY 4.0, api.smartdatanet.it, listed on dati.gov.it); each
law's text in force comes from the text service the dataset names (URNTESTO, serviziweb.csi.it normacat), one plain
text per law. Arianna's robots.txt disallows /dwd/ and /leggistatutarie/, where the Statute is: the Statute is left out.

    python -X utf8 scripts/world-law/it_piedmont.py fetch          # one request at a time, 3.2 s apart
    python -X utf8 scripts/world-law/it_piedmont.py parse
    python -X utf8 scripts/world-law/it_piedmont.py publish <part> ...
    python -X utf8 scripts/world-law/it_piedmont.py letters <part>
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import re
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import it_fetch  # noqa: E402
import it_regions as R  # noqa: E402

SLUG = 'piedmont'
HOST = 'arianna.cr.piemonte.it'
CATALOGUE = 'https://api.smartdatanet.it/api/Arianna_17116/download/17116/all'
DOCS_DATE = '2026-10-30'
PART_SIZE = 50
MONTHS = ['gennaio', 'febbraio', 'marzo', 'aprile', 'maggio', 'giugno', 'luglio', 'agosto', 'settembre', 'ottobre',
          'novembre', 'dicembre']

SRC = {
    'host': HOST,
    'publisher': 'Consiglio regionale del Piemonte, Arianna - Banca Dati Normativa',
    'short': 'Arianna (Consiglio regionale del Piemonte)',
    'url': 'https://arianna.cr.piemonte.it/',
    'licence': 'CC BY 4.0 (Regione Piemonte open dataset "Arianna - Leggi regionali storiche e vigenti"); '
               'L. 633/1941 art. 5: official acts are not protected.',
    'licence_note': ('Source: Consiglio regionale del Piemonte, Arianna - Banca Dati Normativa, '
                     'https://arianna.cr.piemonte.it/ (open dataset "Arianna - Leggi regionali storiche e vigenti, '
                     'regolamenti regionali", Regione Piemonte, CC BY 4.0)'),
    'source_notes': ('The open dataset lists every regional law in force with a link to its text in force; each text '
                     'was read from that link.'),
    'in_force_rule': ('Statuto della Regione Piemonte, art. 47: laws enter into force on the fifteenth day after '
                      'publication in the Bollettino Ufficiale, unless they set another term. Not used for dating: '
                      'each text is dated the day it was read.'),
    'history': 'current-only',
    'history_note': ' in the open dataset',
    'source_md': ('Arianna, the legislation database of the Consiglio regionale del Piemonte, '
                  '<https://arianna.cr.piemonte.it/>. The list of laws is Regione Piemonte\'s open dataset "Arianna - '
                  'Leggi regionali storiche e vigenti, regolamenti regionali" (CC BY 4.0), which names, for every '
                  'regional law in force, the address of its consolidated text in force ("testo vigente"); each text '
                  'here is the plain text served at that address. The Statute is not included yet.'),
    'files_md': ('`<act>/art-005.md` is Art. 5, `art-005-bis.md` Art. 5 bis; `intestazione.md` holds the title and '
                 'anything printed before the first article. Headings of titles, chapters and sections stay in the '
                 'file of the article they stand before; articles quoted inside an amending provision stay in the '
                 'article that quotes them. Acts are named `lr-<year>-<number>`.'),
    'official_md': 'The binding text is the one published in the Bollettino Ufficiale della Regione Piemonte.',
    'terms_md': ('The dataset is published by Regione Piemonte under the Creative Commons Attribution 4.0 licence, '
                 'https://creativecommons.org/licenses/by/4.0/. Arianna\'s own pages carry a CC BY-NC-SA 3.0 IT '
                 'notice for the site\'s content; the law texts themselves are official acts outside copyright '
                 '(art. 5 above).'),
    'scope_note': 'The Statute, regulations and repealed laws are not included yet.',
}


def catalogue() -> list[dict]:
    b = it_fetch.get(CATALOGUE, timeout=600)
    rows = list(csv.DictReader(io.StringIO(b.decode('utf-8')), delimiter=';'))
    laws = [r for r in rows if r['TIPO'] == 'legger' and r['TESTO'] == 'vigente'
            and re.match(r'^\d{4}-\d{2}-\d{2}$', r['DATA'] or '') and r['NUMERO'].isdigit()]
    laws.sort(key=lambda r: (r['DATA'][:4], int(r['NUMERO'])))
    return laws


def text_url(r: dict) -> str:
    return r['URNTESTO'].replace('http://', 'https://', 0)


def fetch():
    laws = catalogue()
    n = 0
    for r in laws:
        R.wait_cpu()
        try:
            it_fetch.get(text_url(r), timeout=120)
        except it_fetch.Stopped as e:
            print('STOPPED', e, flush=True)
            return
        n += 1
        if n % 50 == 0:
            print(n, 'of', len(laws), flush=True)
    print('done', n, flush=True)


# ---------------------------------------------------------------- parse

ART = re.compile(r'^Art\.\s*(\d+)(?:\.(\d+))?\s*\.?\s*((?:bis|ter|quater|quinquies|sexies|septies|octies|novies|nonies|decies|'
                 r'undecies|duodecies|terdecies|quaterdecies|quinquiesdecies)\b)?', re.I)


NULL = re.compile(r'[ \t]+null[ \t]*$', re.M)   # the text service prints "null" where a paragraph has no note


def paragraphs(t: str) -> list[str]:
    t = t.replace('\r\n', '\n').replace('\r', '\n')
    t = NULL.sub('', t)
    return [x for x in (R.clean_line(re.sub(r'\s+', ' ', p)) for p in re.split(r'\n\s*\n', t)) if x]


def units_of(t: str) -> dict:
    units: dict[str, dict] = {}
    cur_key, cur_label, cur = 'intestazione', 'Intestazione', []
    quotes = 0
    pending_heads: list[str] = []

    def flush():
        if cur:
            k, n = cur_key, 2
            while k in units:
                k, n = f'{cur_key}-dup{n}', n + 1
            units[k] = {'label': cur_label, 'kind': 'preamble' if cur_key == 'intestazione' else 'art',
                        'text': '\n'.join(cur) + '\n'}

    for p in paragraphs(t):
        m = ART.match(p)
        if m and quotes % 2 == 0 and cur_key != 'pending':
            flush()
            n1, n2, suf = m.group(1), m.group(2), m.group(3)
            base = f'art-000-{n1}' if (len(n1) > 1 and n1.startswith('0')) else f'art-{int(n1):03d}'
            cur_key = base + (f'-{int(n2):02d}' if n2 else '') + (f'-{suf.lower()}' if suf else '')
            cur_label = f'Art. {n1 if n1.startswith("0") else int(n1)}' + (f'.{n2}' if n2 else '') + \
                (f' {suf.lower()}' if suf else '')
            cur = pending_heads + [p]
            pending_heads = []
            quotes = 0
        elif quotes % 2 == 0 and re.match(r'^(TITOLO|Titolo|CAPO|Capo|SEZIONE|Sezione|PARTE|Parte)\s+[IVXLC\d]+\b', p) \
                and cur_key != 'intestazione':
            pending_heads.append(p)
        else:
            if pending_heads:
                cur.extend(pending_heads)
                pending_heads = []
            cur.append(p)
        if cur_key != 'intestazione':
            quotes += p.count('"')
    cur.extend(pending_heads)
    flush()
    return units


def law_key(r: dict) -> str:
    return f'lr-{r["DATA"][:4]}-{int(r["NUMERO"])}'


def label(r: dict) -> str:
    y, m, d = r['DATA'].split('-')
    return f'L.R. {int(d)} {MONTHS[int(m) - 1]} {y}, n. {int(r["NUMERO"])}'


def act_of(r: dict) -> tuple[dict, dict] | None:
    url = text_url(r)
    b = it_fetch.get(url)
    if not b or not b.strip():
        return None
    t = b.decode('utf-8')
    units = units_of(t)
    if not any(u['kind'] == 'art' for u in units.values()):
        return None
    key = law_key(r)
    title = R.clean_line(r['TITOLO'])
    law = {'label': label(r), 'title': title[:300], 'kind': 'law', 'enacted': r['DATA'],
           'published': r['DATAPUB'] if re.match(r'^\d{4}-\d{2}-\d{2}$', r['DATAPUB'] or '') else None,
           'url': r['URNPAGINA'].replace('http://', 'https://'), 'temporary_until': None, 'restores': None,
           'note': None}
    v = {'from': DOCS_DATE, 'source_url': url, 'sha256': hashlib.sha256(b).hexdigest(), 'units': units, 'credits': {}}
    act = {'slug': key, 'short': f'L.R. {int(r["NUMERO"])}/{r["DATA"][:4]}', 'title': f'{label(r)}: {title}'[:400],
           'url': law['url'], 'first_law': None, 'earlier_laws': [key], 'versions': [v]}
    return act, {key: law}


def decisions() -> list[str]:
    return [
        'Every regional law the open dataset lists as in force ("vigente") is included; regulations, repealed laws '
        'and the Statute are not.',
        'Each law is recorded by its text in force on the retrieval day only, as its oldest version available, dated '
        'that day and credited to Arianna as publisher.',
        'The text service ends each paragraph that has no editor\'s note with the word "null"; that token is '
        'dropped.',
        'Units: one file per article, split where a paragraph begins "Art. <n>" outside a quotation; headings of '
        'titles, chapters and sections go with the next article; the title before the first article is the '
        'intestazione.',
    ]


AI_USE = ['A model (Claude) wrote the fetch and parse code; it wrote no law text. Every word of law comes from the '
          'texts Arianna\'s open dataset links to.']


def parse(limit_parts: int | None = None):
    laws = catalogue()
    plan = [(f'30-leggi-{i // PART_SIZE + 1:02d}', laws[i:i + PART_SIZE]) for i in range(0, len(laws), PART_SIZE)]
    done = []
    for name, members in plan:
        if (R.folder(SLUG) / 'corpus.d' / f'{name}.PUBLISH').exists():
            done.append(name)
            continue
        if not all(it_fetch.path_for(text_url(r)).exists() or it_fetch.path_for(text_url(r)).with_suffix('.404').exists()
                   for r in members):
            break
        part = {'country': R.country_block(SLUG, SRC), 'laws': {}, 'acts': []}
        for r in members:
            x = act_of(r)
            if x:
                part['acts'].append(x[0])
                part['laws'].update(x[1])
        if not part['acts']:
            continue
        if name == '30-leggi-01':
            part.update(sources=[R.source_block(SRC, DOCS_DATE)], decisions=decisions(), ai_use=AI_USE)
        R.write_part(SLUG, name, part)
        done.append(name)
    print('parts ready:', done)
    return done


# ---------------------------------------------------------------- letters check (raw bytes, no paragraph logic)

def letters_check(slug: str, part_name: str) -> list[str]:
    part = json.loads((R.folder(slug) / 'corpus.d' / f'{part_name}.json').read_text(encoding='utf-8'))
    probs = []
    for act in part['acts']:
        for v in act['versions']:
            raw = it_fetch.path_for(v['source_url']).read_bytes()
            if hashlib.sha256(raw).hexdigest() != v['sha256']:
                probs.append(f'{act["slug"]}: sha256 differs')
                continue
            src = R.letters(NULL.sub('', raw.decode('utf-8').replace('\r', '')))
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
