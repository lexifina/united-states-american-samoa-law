"""Reads the LeyChile cache (fetch.py) and writes scripts/chile-law/corpus.json (scripts/gitlaw_common/SCHEMA.md).

    python -X utf8 scripts/chile-law/parse.py [--acts constitucion,codigo-civil,...] [--retrieved YYYY-MM-DD]

No network: everything comes from .cache/. The same cache gives the same bytes.

How a version becomes units
  LeyChile's get_norma_json gives the text as a tree ("html") whose nodes carry the same ids ("i") as the table of
  contents ("estructura", with names such as "Artículo 19", "Disposición Transitoria PRIMERA Transitorio" and types).
  Every leaf of the tree is one unit (one file): articles, transitional provisions, the heading (Encabezado) and the
  closing formula (Promulgación). The headings of books, titles, chapters and paragraphs are kept, in order, one per
  line, in one more unit, `titulos`. Each paragraph (div.p) is one line.

How a change is credited
  Each paragraph carries the source's own amendment notes (span.n), e.g. "LEY N° 19.611 Art. único Nº 2 D.O.
  16.06.1999", often with a link to the amending norm. The versions list names, for each version, the norms that
  ended it and the day each took effect ("Modificatorias", "inicioVigencia"). A changed unit is credited to a norm
  that took effect on the version's day only when one of the unit's notes names that norm (by link, by type and
  number, or as a Rectificación by its Diario Oficial date). Anything else is left uncredited, so the shared builder
  commits it as unexplained, by the publisher.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import html as htmlmod
import json
import re
import sys
import unicodedata
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import fetch  # noqa: E402

LEYCHILE = 'https://www.bcn.cl/leychile/navegar?idNorma='
MONTHS = {'ENE': 1, 'FEB': 2, 'MAR': 3, 'ABR': 4, 'MAY': 5, 'JUN': 6, 'JUL': 7, 'AGO': 8, 'SEP': 9, 'SEPT': 9,
          'OCT': 10, 'NOV': 11, 'DIC': 12}

# Act metadata. `first` is the first version's in-force date when the act's own vigencia clause says it differs from
# LeyChile's first version day (the day of publication), with the reason, printed in `decisions`.
ACT_META = {
    'constitucion': {
        'short': 'CPR', 'title': 'Constitución Política de la República de Chile',
        'url': LEYCHILE + '242302',
        'first': ('1981-03-11', 'The Constitution of 1980 (DL 3.464, published in the Diario Oficial on 11 August 1980) '
                  'was approved by plebiscite on 11 September 1980 and, by its own Artículo final, "entrará en '
                  'vigencia seis meses después de ser aprobada mediante plebiscito", that is on 11 March 1981. '
                  'Its first version is dated 1981-03-11, not the publication day LeyChile shows. The Artículo final '
                  'makes the ninth and twenty-third transitional provisions apply from the plebiscite; that is in '
                  'the text, not in the dates.'),
        'first_law': True,
    },
    'codigo-civil': {'short': 'CC', 'title': 'Código Civil', 'url': LEYCHILE + '172986', 'first_law': False,
                     'part': 2},
    'ley-19628': {'short': 'Ley 19.628', 'title': 'Ley 19.628 sobre protección de la vida privada',
                  'url': LEYCHILE + '141599', 'first_law': True},
    'codigo-penal': {'short': 'CP', 'title': 'Código Penal', 'url': LEYCHILE + '1984', 'first_law': True},
    'codigo-comercio': {'short': 'CCom', 'title': 'Código de Comercio', 'url': LEYCHILE + '1974', 'first_law': False},
    'codigo-trabajo': {'short': 'CT', 'title': 'Código del Trabajo', 'url': LEYCHILE + '207436', 'first_law': False},
    'codigo-procedimiento-civil': {'short': 'CPC', 'title': 'Código de Procedimiento Civil',
                                   'url': LEYCHILE + '22740', 'first_law': False},
    'codigo-procesal-penal': {'short': 'CPP', 'title': 'Código Procesal Penal', 'url': LEYCHILE + '176595',
                              'first_law': True},
}

TYPE_KEY = {'LEY': 'ley', 'DL': 'dl', 'DFL': 'dfl', 'DTO': 'dto', 'DS': 'dto', 'REC': 'rec', 'RES': 'res',
            'CODIGO': 'codigo', 'COD': 'codigo', 'LEY ORG CONST': 'ley', 'LEY INTERP CONST': 'ley', 'LEY ORG': 'ley',
            'STC': 'stc', 'AUTO ACORDADO': 'aa'}
TYPE_LABEL = {'ley': 'Ley', 'dl': 'DL', 'dfl': 'DFL', 'dto': 'Decreto', 'rec': 'Rectificación', 'res': 'Resolución',
              'codigo': 'Código', 'stc': 'Sentencia TC', 'aa': 'Auto acordado'}
TYPE_KIND = {'ley': 'law', 'dl': 'law', 'dfl': 'decree', 'dto': 'decree', 'rec': 'decree', 'res': 'decree',
             'codigo': 'law', 'stc': 'court', 'aa': 'court'}


# ---------------------------------------------------------------- text

QUOTES = str.maketrans({'“': '"', '”': '"', '„': '"', '«': '"', '»': '"', '‘': "'", '’': "'", '´': "'",
                        '–': '-', '—': '-', '‒': '-', '―': '-', ' ': ' ', ' ': ' ', '​': '',
                        '\t': ' ', '﻿': ''})


def clean(s: str) -> str:
    s = htmlmod.unescape(s).translate(QUOTES)
    return re.sub(r' {2,}', ' ', s).strip()


SPAN = re.compile(r'<span class="n"[^>]*>(.*?)</span>', re.S)
HREF = re.compile(r'idNorma=(\d+)')


def paragraphs(t: str) -> tuple[list[str], list[str], set[int]]:
    """The lines of one node's html, its notes (as plain text) and the norms its notes link to."""
    notes, ids = [], set()

    def note(m):
        notes.append(clean(re.sub(r'<br\s*/?>', ' ', re.sub(r'<(?!br)[^>]+>', '', m.group(1)))))
        ids.update(int(x) for x in HREF.findall(m.group(1)))
        return ''
    t = SPAN.sub(note, t)
    # BCN's editorial notes ("NOTA" markers and their bodies) are the publisher's, not the law's text.
    t = re.sub(r'<div class="np"[^>]*>.*?</div>', '', t, flags=re.S)
    t = re.sub(r'<div class="n[ "][^>]*>.*?</div>', '', t, flags=re.S)
    lines = []
    for chunk in re.split(r'<div class="p">|</div>|<br\s*/?>|<p>|</p>|<tr[^>]*>', t):
        line = clean(re.sub(r'<[^>]+>', ' ', chunk))
        if line:
            lines.append(line)
    return lines, notes, ids


# ---------------------------------------------------------------- unit keys

UNITS = {'PRIMER': 1, 'SEGUND': 2, 'TERCER': 3, 'CUART': 4, 'QUINT': 5, 'SEXT': 6, 'SEPTIM': 7, 'SETIM': 7,
         'OCTAV': 8, 'NOVEN': 9}
TENS = {'DECIM': 10, 'VIGESIM': 20, 'TRIGESIM': 30, 'CUADRAGESIM': 40, 'QUINCUAGESIM': 50, 'SEXAGESIM': 60,
        'SEPTUAGESIM': 70, 'OCTOGESIM': 80, 'NONAGESIM': 90}
SPECIAL = {'UNDECIM': 11, 'DUODECIM': 12, 'UNIC': 1}


def plain(s: str) -> str:
    return ''.join(ch for ch in unicodedata.normalize('NFD', s) if unicodedata.category(ch) != 'Mn')


def ordinal(word: str) -> int | None:
    w = re.sub(r'[^A-Z]', '', plain(word).upper())
    if not w:
        return None
    for k, v in SPECIAL.items():
        if w.startswith(k) and len(w) <= len(k) + 2:
            return v
    n = 0
    for k, v in TENS.items():
        if w.startswith(k):
            n, w = v, w[len(k):]
            if not any(w.startswith(u) for u in UNITS):
                w = re.sub(r'^[OA]', '', w)
            break
    if not w:
        return n or None
    for k, v in UNITS.items():
        if w.startswith(k) and len(w) <= len(k) + 2:
            return n + v
    return None


SUFFIX = r'(bis|ter|quater|quáter|quinquies|sexies|septies|octies|nonies|novies|decies|[a-z])'


def slug(s: str) -> str:
    s = re.sub(r'[^a-z0-9]+', '-', plain(s).lower()).strip('-')
    return s or 'x'


def unit_key(name: str, width: int) -> tuple[str, str, str]:
    """(key, label, kind) for one leaf of the table of contents."""
    n = clean(name)
    low = plain(n).lower()
    if low.startswith('encabezado'):
        return 'encabezado', 'Encabezado', 'heading'
    if low.startswith('promulgacion'):
        return 'promulgacion', 'Promulgación', 'closing'
    if low.startswith('anexo'):
        return 'anexo', 'Anexo', 'part'
    trans = 'transitori' in low
    body = re.sub(r'(?i)\b(disposici[oó]n(es)?|art[ií]culos?|transitori[oa]s?)\b\.?', ' ', n)
    body = re.sub(r'\s+', ' ', body).strip(' .-')
    m = re.match(r'(?i)^(\d+)\s*[°ºo]?\s*(?:' + SUFFIX + r')?\b\s*(.*)$', body)
    pre = 'art-transitorio' if trans else 'art'
    if m:
        num = int(m.group(1))
        suf = slug(m.group(2)) if m.group(2) else ''
        rest = slug(m.group(3)) if m.group(3) else ''
        key = f'{pre}-{num:0{width}d}' + (f'-{suf}' if suf else '') + (f'-{rest}' if rest and rest != 'x' else '')
        label = ('Art. transitorio ' if trans else 'Art. ') + f'{num}' + (f' {m.group(2).lower()}' if m.group(2) else '')
        return key, label, 'transitional' if trans else 'art'
    words = body.split()
    if words:
        used = 1
        o = ordinal(words[0])
        if len(words) > 1 and ordinal(words[0] + words[1]) is not None:
            o, used = ordinal(words[0] + words[1]), 2
        if o is not None:
            suf = slug(' '.join(words[used:])) if len(words) > used else ''
            if trans:
                key = f'disp-transitoria-{o:03d}' + (f'-{suf}' if suf else '')
                return key, f'Disposición transitoria {" ".join(words[:used]).lower()}', 'transitional'
            if plain(words[0]).upper().startswith('UNIC'):
                return 'art-unico', 'Artículo único', 'art'
    if plain(body).upper() in ('FINAL', 'FINAL.'):
        return ('art-final' if not trans else 'art-transitorio-final'), 'Artículo final', 'art'
    return ('disp-transitoria-' if trans else 'parte-') + slug(body), n, 'transitional' if trans else 'part'


# ---------------------------------------------------------------- notes → norms

NOTE_NORM = re.compile(
    r'(?i)\b(LEY|D\.?\s?F\.?\s?L\.?|D\.?\s?L\.?|DECRETO\s+LEY|DECRETO\s+CON\s+FUERZA\s+DE\s+LEY|DTO\.?|D\.?\s?S\.?|'
    r'DECRETO|RECTIFICACI[OÓ]N|REC)\s*(?:N\s*[°º.o]*\s*)?(\d[\d.]*)')
DO_DATE = re.compile(r'D\.\s?O\.?\s*(\d{1,2})[./-](\d{1,2})[./-](\d{2,4})')


def norm_type(s: str) -> str:
    s = re.sub(r'[\s.]', '', s.upper())
    if s.startswith('DECRETOCONFUERZA') or s == 'DFL':
        return 'dfl'
    if s.startswith('DECRETOLEY') or s == 'DL':
        return 'dl'
    if s in ('DTO', 'DS', 'DECRETO'):
        return 'dto'
    if s.startswith('RECTIFICACI') or s == 'REC':
        return 'rec'
    return 'ley'


def note_refs(notes: list[str]) -> tuple[set[tuple[str, int]], set[str]]:
    refs, dates = set(), set()
    for n in notes:
        for t, num in NOTE_NORM.findall(n):
            try:
                refs.add((norm_type(t), int(num.replace('.', ''))))
            except ValueError:
                pass
        for d, m, y in DO_DATE.findall(n):
            y = int(y)
            y = y + (1900 if y > 30 else 2000) if y < 100 else y
            try:
                dates.add(dt.date(y, int(m), int(d)).isoformat())
            except ValueError:
                pass
    return refs, dates


# ---------------------------------------------------------------- one version

PART_SUFFIX = re.compile(r'(?i)\s*\(DEL ART\.?\s*\d+\s*\)')


def part_nodes(d: dict, part: int | None) -> list:
    """The html nodes of the act: the whole norm, or only the children of its article `part` when one norm fixes the
    text of several acts (DFL 1 of 2000 fixes the Código Civil in its art. 2 and five other laws in arts. 3-8)."""
    nodes = d.get('html') or []
    if part is None:
        return nodes
    top = {x['i']: x.get('n', '') for x in d.get('estructura') or []}
    hit = [x for x in nodes if re.match(rf'(?i)^articulo\s+{part}\b', plain(clean(top.get(x['i'], ''))))]
    if len(hit) != 1:
        raise SystemExit(f'part {part}: {len(hit)} top-level nodes match')
    return hit[0].get('h') or []


def read_version(raw: bytes, width: int, part: int | None = None) -> dict:
    d = json.loads(raw)
    names: dict[int, tuple[str, int | None]] = {}

    def index(nodes):
        for x in nodes:
            names[x['i']] = (x.get('n', ''), x.get('t'))
            index(x.get('h', []))
    index(d.get('estructura') or [])
    units: dict[str, dict] = {}
    heads: list[str] = []
    head_notes: list[str] = []
    head_ids: set[int] = set()

    def walk(nodes):
        for x in nodes:
            lines, notes, ids = paragraphs(x.get('t', ''))
            if x.get('h'):
                if lines:
                    heads.append(' '.join(lines))
                head_notes.extend(notes)
                head_ids.update(ids)
                walk(x['h'])
                continue
            name, _typ = names.get(x['i'], ('', None))
            if part is not None:
                name = PART_SUFFIX.sub('', name or '')
            key, label, kind = unit_key(name or (lines[0][:40] if lines else str(x['i'])), width)
            base, n = key, 2
            while key in units:
                key = f'{base}-{n}'
                n += 1
            if not lines:
                lines = ['(sin texto)']
            units[key] = {'label': label, 'kind': kind, 'text': '\n'.join(lines) + '\n', 'notes': notes, 'ids': ids,
                          'name': clean(name)}
    walk(part_nodes(d, part))
    if heads:
        units['titulos'] = {'label': 'Títulos', 'kind': 'headings', 'text': '\n'.join(heads) + '\n',
                            'notes': head_notes, 'ids': head_ids, 'name': 'Títulos'}
    meta = d.get('metadatos') or {}
    return {'units': units, 'meta': meta}


def width_for(raws: list[bytes], part: int | None = None) -> int:
    mx = 0
    for raw in raws:
        if part is not None:
            for m in re.finditer(r'Art(?:[ií]|\\u00ed)culo (\d+)[^"]{0,20}\(DEL ART\.? ?' + str(part) + r'\)', raw.decode('utf-8')):
                mx = max(mx, int(m.group(1)))
            continue
        for m in re.finditer(rb'"n": ?"Art\\u00edculo (\d+)|"n": ?"Art\xc3\xadculo (\d+)', raw):
            mx = max(mx, int(m.group(1) or m.group(2)))
    return 4 if mx > 999 else 3


# ---------------------------------------------------------------- laws

def pub_date(s: str) -> str | None:
    m = re.match(r'(\d{1,2})-([A-Z]+)-(\d{4})', s or '')
    if not m or m.group(2) not in MONTHS:
        return None
    return dt.date(int(m.group(3)), MONTHS[m.group(2)], int(m.group(1))).isoformat()


def law_key(tipo: str, nro, year: str | None, id_norma: int) -> str:
    t = TYPE_KEY.get((tipo or '').upper().strip(), slug(tipo or 'norma'))
    num = slug(str(nro or '')) if nro not in (None, '') else 'sn'
    if t == 'ley' and num != 'sn':
        return f'ley-{num}'
    return f'{t}-{num}-{year or "x"}-{id_norma}' if t in ('dto', 'res', 'rec') else f'{t}-{num}-{year or "x"}'


def law_label(tipo: str, nro, published: str | None) -> str:
    t = TYPE_KEY.get((tipo or '').upper().strip(), slug(tipo or 'norma'))
    lab = TYPE_LABEL.get(t, tipo)
    if nro in (None, ''):
        return f'{lab} s/n de {published[:4]}' if published else f'{lab} s/n'
    n = int(nro) if str(nro).isdigit() else nro
    if t == 'ley' and isinstance(n, int):
        return f'Ley {n:,}'.replace(',', '.')
    if t == 'dl' and isinstance(n, int):
        return f'DL {n:,}'.replace(',', '.') + (f' de {published[:4]}' if published else '')
    return f'{lab} {n}' + (f' de {published[:4]}' if published else '')


class Laws:
    def __init__(self):
        self.laws: dict[str, dict] = {}
        self.by_id: dict[int, str] = {}

    def add(self, m: dict, pub: str | None = None) -> str:
        idn = int(m['@idNorma'])
        if idn in self.by_id:
            return self.by_id[idn]
        pub = pub or pub_date(m.get('@fechaPublicacion', ''))
        key = law_key(m.get('@tipoNorma', ''), m.get('@nroNorma'), pub[:4] if pub else None, idn)
        t = TYPE_KEY.get((m.get('@tipoNorma') or '').upper().strip(), '')
        old = self.laws.get(key)
        if old and old['_id'] is None and old['_type'] == t and str(old['_num']) == str(m.get('@nroNorma')):
            # Known so far only from an amendment note: the same norm, now with its LeyChile id and title.
            old.update({'title': clean(m.get('@titulo') or ''), 'url': f'{LEYCHILE}{idn}', '_id': idn,
                        '_org': m.get('@organismo')})
            old['published'] = pub or old['published']
            self.by_id[idn] = key
            return key
        if key in self.laws:
            key = f'{key}-{idn}'
        self.laws[key] = {'label': law_label(m.get('@tipoNorma', ''), m.get('@nroNorma'), pub),
                          'title': clean(m.get('@titulo') or ''), 'kind': TYPE_KIND.get(t, 'law'),
                          'enacted': None, 'published': pub, 'url': f'{LEYCHILE}{idn}',
                          'temporary_until': None, 'restores': None,
                          '_id': idn, '_type': t, '_num': m.get('@nroNorma'), '_org': m.get('@organismo')}
        self.by_id[idn] = key
        return key

    def from_note(self, t: str, num: int, day: str, note: str) -> str:
        """A norm known only from an amendment note: type, number and Diario Oficial date."""
        for key, law in self.laws.items():
            if law['_type'] == t and str(law['_num']) == str(num) and (t == 'ley' or law['published'] == day):
                return key
        key = f'ley-{num}' if t == 'ley' else f'{t}-{num}-{day[:4]}' if num is not None else f'{t}-do-{day.replace("-", "")}'
        tl = {'ley': 'LEY', 'dl': 'DL', 'dfl': 'DFL', 'dto': 'DTO', 'rec': 'REC'}[t]
        label = law_label(tl, num, day) if num is not None else f'Rectificación D.O. {day[8:]}.{day[5:7]}.{day[:4]}'
        self.laws[key] = {'label': label, 'title': '', 'kind': TYPE_KIND.get(t, 'law'),
                          'enacted': None, 'published': day, 'url': None, 'temporary_until': None, 'restores': None,
                          '_id': None, '_type': t, '_num': num, '_org': None, '_note': note}
        return key

    def matches(self, key: str, refs: set, ids: set, dates: set) -> bool:
        law = self.laws[key]
        if law['_id'] in ids:
            return True
        try:
            num = int(law['_num'])
        except (TypeError, ValueError):
            num = None
        if num is not None and (law['_type'], num) in refs:
            if law['_type'] in ('ley',) or not law['published'] or law['published'] in dates or not dates:
                return True
        if law['_type'] == 'rec' and law['published'] and law['published'] in dates:
            return True
        return False


# ---------------------------------------------------------------- one act

def as_list(x):
    return fetch.as_list(x)


def act_versions(slug_: str, laws: Laws, log: list[str]) -> dict:
    meta = ACT_META[slug_]
    chain = fetch.ACTS[slug_]
    entries = []      # (day, id_norma, version entry, the entry before it in the same norm)
    listed: dict[tuple[str, str], set[str]] = {}     # (type, number) -> days the versions lists give for it
    for id_norma in chain:
        vs = fetch.versions(id_norma, offline=True)
        for i, v in enumerate(vs):
            entries.append((v['@vigenteDesde'], id_norma, v, vs[i - 1] if i else None))
            for m in as_list(v.get('Modificatorias', {}).get('Modificatoria')):
                t = TYPE_KEY.get((m.get('@tipoNorma') or '').upper().strip(), '')
                listed.setdefault((t, str(m.get('@nroNorma'))), set()).add(m.get('@inicioVigencia'))
    # A later norm in the chain (a texto refundido) replaces the earlier one from its first day.
    starts = {}
    for id_norma in chain:
        starts[id_norma] = min(e[0] for e in entries if e[1] == id_norma)
    kept = []
    for e in entries:
        later = [starts[n] for n in chain[chain.index(e[1]) + 1:]]
        if later and e[0] >= min(later):
            continue
        if e[2].get('@tipoVersion') == 'Con Vigencia Diferida por Evento':
            # A version waiting for an event, not a day (LeyChile dates it 2222-02-02): it cannot be dated.
            log.append(f'{slug_} {e[0]}: version "Con Vigencia Diferida por Evento" not dated; left out')
            continue
        kept.append(e)
    kept.sort(key=lambda e: e[0])
    raws = [fetch.fetch(fetch.version_url(e[1], e[0]), offline=True) for e in kept]
    part = meta.get('part')
    width = width_for(raws, part)
    versions = []
    prev = None
    first_law = None
    earlier: list[str] = []
    credited_before: set[str] = set()
    for (day, id_norma, entry, before), raw in zip(kept, raws):
        r = read_version(raw, width, part)
        if part is not None and prev is not None and prev['_norm'] == id_norma and not changed(prev, {'units': r['units']}):
            continue    # a version of the norm in which only its other parts changed
        md = r['meta']
        v = {'from': day, 'source_url': f'{LEYCHILE}{id_norma}&idVersion={day}',
             'sha256': hashlib.sha256(raw).hexdigest(), 'units': {}, 'credits': {}}
        for k, u in r['units'].items():
            v['units'][k] = {'label': u['label'], 'kind': u['kind'], 'text': u['text']}
        if prev is None or prev['_norm'] != id_norma:
            # The first version of a norm: the act as enacted (or re-enacted as a texto refundido).
            tipos = md.get('tipos_numeros') or [{}]
            tn = tipos[0]
            m = {'@idNorma': id_norma, '@tipoNorma': tn.get('abreviacion', ''), '@nroNorma': tn.get('numero'),
                 '@titulo': md.get('titulo_norma', ''), '@fechaPublicacion': ''}
            key = laws.add(m, md.get('fecha_publicacion') or None)
            law = laws.laws[key]
            law['published'] = md.get('fecha_publicacion') or None
            law['enacted'] = md.get('fecha_promulgacion') or None
            law['label'] = law_label(tn.get('abreviacion', ''), tn.get('numero'), law['published'])
            if law['_type'] == 'codigo':
                # A code enacted as such (e.g. "Código-PENAL"): its own title, with the year of publication.
                law['label'] = meta['title'] + (f' de {law["published"][:4]}' if law['published'] else '')
            if prev is None:
                if meta.get('first_law'):
                    first_law = key
                else:
                    earlier = [key]
            else:
                v['credits'] = {k: [key] for k in changed(prev, v)}
                v['note'] = (f'{law["label"]} replaced the text with a texto refundido, coordinado y sistematizado; '
                             'LeyChile continues the act under that norm (idNorma ' + str(id_norma) + ').')
                ren = renumbered(prev, v)
                if ren:
                    v['note'] += ' Renumbered (paired by at least half of their words shared): ' + '; '.join(
                        f'{a} became {b}' for a, b in ren[:40]) + ('; …' if len(ren) > 40 else '') + '.'
        else:
            mods = [m for m in as_list((before or {}).get('Modificatorias', {}).get('Modificatoria'))]
            on_day = [m for m in mods if m.get('@inicioVigencia') == day]
            if mods and not on_day:
                log.append(f'{slug_} {day}: modificatorias listed with other days: '
                           + ', '.join(f'{m.get("@tipoNorma")} {m.get("@nroNorma")} {m.get("@inicioVigencia")}' for m in mods))
            for m in on_day:
                if not int(m.get('@idNorma') or 0):
                    log.append(f'{slug_} {day}: a modificatoria with no norm (idNorma 0) is listed for this day')
            keys = [laws.add(m) for m in on_day if int(m.get('@idNorma') or 0)]
            late = []
            noted: set[str] = set()
            deferred: set[str] = set()
            ch = changed(prev, v)
            for k in ch:
                u = r['units'].get(k) or prev['_raw'].get(k)
                refs, dates = note_refs(u['notes'])
                hit = [l for l in keys if laws.matches(l, refs, u['ids'], dates)]
                if not hit and len(keys) == 1:
                    # A removed unit, a removed paragraph or a new unit with no notes at all cannot carry a note
                    # naming the norm; when exactly one norm took effect that day, it is that one.
                    cu = r['units'].get(k)
                    pl = set(prev['units'].get(k, {}).get('text', '').splitlines())
                    if cu is None or (k not in prev['units'] and not cu['notes']) or                             set(cu['text'].splitlines()) < pl:
                        hit = list(keys)
                if hit:
                    v['credits'][k] = hit
                elif k in r['units']:
                    old = set(prev['_raw'].get(k, {}).get('notes', []))
                    new = [n for n in r['units'][k]['notes'] if n not in old]
                    # A new note naming a norm published in the Diario Oficial on this very day explains the change
                    # by itself (Código Civil art. 7), even where get_versiones lists no norm for the day.
                    for n in new:
                        nrefs, ndates = note_refs([n])
                        if day in ndates and len(nrefs) == 1:
                            t, num = next(iter(nrefs))
                            hit.append(laws.from_note(t, num, day, n))
                        elif day in ndates and not nrefs and re.match(r'(?i)RECTIFICACI', n):
                            hit.append(laws.from_note('rec', None, day, n))
                    if hit:
                        v['credits'][k] = sorted(set(hit))
                        noted.update(hit)
                    elif not mods:
                        # Deferred entry into force: the versions list names no norm at all for this day, and the
                        # unit's new note names exactly one norm, published earlier and not yet seen in this act's
                        # history. The note is the source's own statement of which norm made the change.
                        for n in new:
                            nrefs, ndates = note_refs([n])
                            if len(nrefs) == 1 and len(ndates) == 1 and min(ndates) < day:
                                t, num = next(iter(nrefs))
                                if listed.get((t, str(num)), {day}) != {day} and day not in listed[(t, str(num))]:
                                    continue    # the versions list dates this norm's entry into force elsewhere
                                key = laws.from_note(t, num, min(ndates), n)
                                if key not in credited_before:
                                    hit.append(key)
                        if hit:
                            v['credits'][k] = sorted(set(hit))
                            deferred.update(hit)
                    if not hit and new:
                        # Say which norm the unit's new notes name, without crediting it.
                        late.append(f'{r["units"][k]["label"]}: {new[-1]}')
            if noted:
                v['note'] = ('Credited from the amendment notes, which name a norm published in the Diario Oficial on '
                             'this day, although the LeyChile versions list does not name it for this day: '
                             + ', '.join(laws.laws[l]['label'] for l in sorted(noted)) + '.')
            if deferred:
                v['note'] = (v.get('note', '') + ' ' if v.get('note') else '') + (
                    'Credited from the amendment notes: the LeyChile versions list names no norm for this day, and '
                    'the new notes on the changed provisions name a norm published earlier that takes effect here '
                    '(deferred entry into force): ' + ', '.join(
                        f'{laws.laws[l]["label"]} (D.O. {laws.laws[l]["published"]})' for l in sorted(deferred)) + '.')
            if late:
                v['note'] = (v.get('note', '') + ' ' if v.get('note') else '') + ('LeyChile shows changes from this day that no norm in force on this day explains; the '
                             'new amendment notes on them read: ' + ' | '.join(late[:12])
                             + (' | …' if len(late) > 12 else '') + '. They are left uncredited.')
            # Norms that took effect on this day but whose notes name no changed unit: record them on a unit their
            # notes name, so the builder still makes a (wording unchanged) commit for them.
            credited = {l for ls in v['credits'].values() for l in ls}
            for l in keys:
                if l in credited:
                    continue
                for k, u in r['units'].items():
                    refs, dates = note_refs(u['notes'])
                    if laws.matches(l, refs, u['ids'], dates):
                        v['credits'].setdefault(k, []).append(l)
                        break
                else:
                    log.append(f'{slug_} {day}: {laws.laws[l]["label"]} took effect but no note names it')
        credited_before.update(l for ls in v['credits'].values() for l in ls)
        if prev is not None and not changed(prev, v) and not v['credits'] and not v.get('note'):
            log.append(f'{slug_} {day}: identical to the version before; skipped')
            continue
        v['_raw'] = r['units']
        v['_norm'] = id_norma
        versions.append(v)
        prev = v
    if meta.get('first'):
        first_day, why = meta['first']
        if versions[0]['from'] < first_day and (len(versions) < 2 or versions[1]['from'] > first_day):
            versions[0]['from'] = first_day
            versions[0]['note'] = why
    for v in versions:
        v.pop('_raw')
        v.pop('_norm')
    return {'slug': slug_, 'short': meta['short'], 'title': meta['title'], 'url': meta['url'],
            'first_law': first_law, 'earlier_laws': earlier, 'versions': versions}


def changed(prev: dict, cur: dict) -> list[str]:
    pu, cu = prev['units'], cur['units']
    return sorted(k for k in set(pu) | set(cu) if pu.get(k, {}).get('text') != cu.get(k, {}).get('text'))


def words(t: str) -> set[str]:
    return set(re.findall(r'\w+', t.lower()))


def renumbered(prev: dict, cur: dict) -> list[tuple[str, str]]:
    pu, cu = prev['units'], cur['units']
    gone = [k for k in pu if k not in cu or words(pu[k]['text']) and len(words(pu[k]['text']) & words(cu[k]['text'])) * 2 < len(words(pu[k]['text']))]
    new = [k for k in cu if k not in pu or k in gone]
    out = []
    used = set()
    for a in gone:
        wa = words(pu[a]['text'])
        best, score = None, 0.0
        for b in new:
            if b in used or b == a:
                continue
            wb = words(cu[b]['text'])
            s = len(wa & wb) / max(len(wa), len(wb), 1)
            if s > score:
                best, score = b, s
        if best and score >= 0.5:
            used.add(best)
            out.append((pu[a]['label'], cu[best]['label']))
    return out


# ---------------------------------------------------------------- corpus

def requests_count() -> int:
    p = fetch.CACHE / 'requests.jsonl'
    return sum(1 for _ in open(p, encoding='utf-8')) if p.exists() else 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--acts', default='constitucion,codigo-civil,ley-19628')
    ap.add_argument('--retrieved', default='2026-10-28')
    ap.add_argument('--out', default=str(HERE / 'corpus.json'), help='written atomically: a .tmp file, then a rename')
    args = ap.parse_args()
    laws = Laws()
    log: list[str] = []
    acts = [act_versions(s, laws, log) for s in args.acts.split(',')]
    decisions = [
        'Sources: LeyChile JSON services get_versiones (the dated versions and the norms that ended each one) and '
        'get_norma_json (the text of each version). The legacy XML export (Consulta/obtxml) still answered 200 on '
        '2026-10-28, but its notes are laid out in a second text column mixed into the lines, so the JSON was used.',
        'In-force dates: each version starts on LeyChile\'s "vigenteDesde", which LeyChile sets to the amending '
        'norm\'s "inicioVigencia". Where the norm has no vigencia clause that is its publication day in the Diario '
        'Oficial (Código Civil art. 7); where it has one (for example Ley 21.504, published 2022-11-10, in force '
        '2023-05-09), LeyChile uses that day. We take LeyChile\'s day as given.',
        'Credits come only from the source: a changed unit is credited to a norm only if that norm took effect on '
        'the version\'s day (per get_versiones) and a note on the unit names it (by link, by type and number, or a '
        'Rectificación by its Diario Oficial date). A unit removed outright is credited to the norm that took effect '
        'that day only when exactly one did. Everything else is unexplained and committed by the publisher.',
        'A texto refundido (a norm that re-enacts an act, e.g. DS 100 of 2005 for the Constitution) is the act\'s next '
        'version from its first day: every unit that differs is credited to that norm, and renumbered provisions '
        '(paired by at least half of their words shared) are listed in the commit message.',
        'One file per leaf of LeyChile\'s table of contents (article, transitional provision, heading, closing); one '
        'line per paragraph; the headings of books, titles, chapters and paragraphs are kept, in order, in `titulos.md`. '
        'Amendment notes are removed from the text; NBSP, quotes and dashes are normalised.',
        'Rectificaciones (corrections published in the Diario Oficial) are commits of kind "decree", credited like a norm.',
    ]
    for a in acts:
        meta = ACT_META[a['slug']]
        if meta.get('first'):
            decisions.append(f'{a["short"]}: ' + meta['first'][1])
    cl = {
        'country': {
            'code': 'CL', 'name': 'Chile', 'slug': 'chile', 'lang': 'es', 'tz': 'America/Santiago',
            'future_branch': 'futuro',
            'publisher': {'name': 'Biblioteca del Congreso Nacional (LeyChile)', 'email': 'bcn@leychile.invalid'},
            'default_in_force_rule': {
                'text': 'Código Civil art. 7: "La publicación de la ley se hará mediante su inserción en el Diario '
                        'Oficial, y desde la fecha de éste se entenderá conocida de todos y será obligatoria." A '
                        'law\'s own rule on its vigencia overrides this (art. 7, inciso tercero).',
                'source': 'https://www.bcn.cl/leychile/navegar?idNorma=172986&idParte=8717776'},
            'licence_note': 'Fuente: Biblioteca del Congreso Nacional de Chile, LeyChile (www.bcn.cl/leychile).',
        },
        'sources': [{
            'name': 'LeyChile (Biblioteca del Congreso Nacional de Chile)', 'url': 'https://www.bcn.cl/leychile',
            'retrieved': args.retrieved, 'requests': requests_count(),
            'licence': 'Official text published by BCN LeyChile; attribution to BCN. Ley 17.336 has no explicit exclusion for legal texts (art. 88 vests works of state officials in the State): licence status to confirm.',
            'notes': 'JSON services under https://nuevo.leychile.cl/servicios/ used by the LeyChile reader: '
                     'Consulta/get_versiones and Navegar/get_norma_json, plus Navegar/get_cadena_refundidos.'}],
        'laws': {k: {kk: vv for kk, vv in v.items() if not kk.startswith('_')} for k, v in sorted(laws.laws.items())},
        'acts': acts,
        'applies': [],
        'decisions': decisions,
        'ai_use': ['None at data-build time: fetch.py and parse.py are deterministic code, written with Claude Code '
                   '(claude-opus-5-5); no model reads, writes or summarises legal text.'],
    }
    out = Path(args.out)
    tmp = out.with_name(out.name + '.tmp')
    tmp.write_text(json.dumps(cl, ensure_ascii=False, indent=1, sort_keys=False) + '\n', encoding='utf-8', newline='\n')
    tmp.replace(out)
    (HERE / 'parse.log').write_text('\n'.join(log) + '\n', encoding='utf-8', newline='\n')
    stats(cl)


def stats(c: dict):
    for a in c['acts']:
        ch = cr = 0
        for p, v in zip(a['versions'], a['versions'][1:]):
            ks = changed(p, v)
            ch += len(ks)
            cr += sum(1 for k in ks if v['credits'].get(k))
        print(f'{a["slug"]}: {len(a["versions"])} versions, {len(a["versions"][-1]["units"])} units now, '
              f'{ch} unit changes, {cr} credited, {ch - cr} unexplained')


if __name__ == '__main__':
    main()
