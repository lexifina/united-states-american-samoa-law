"""gitlaw-MX parser: the Constitución Política de los Estados Unidos Mexicanos (CPEUM) from the Cámara de Diputados'
consolidated PDFs (LeyesBiblio pdf/1.pdf, pdf/1_<ddmmyy>.pdf, pdf/CPEUM.pdf), every distinct copy the Internet
Archive holds from 2006 to 2026, into corpus.d/10-constitucion.json. Reads only .cache/ (fetch.py fills it).

    python -X utf8 parse.py            # write corpus.d/10-constitucion.json (atomically) and print a summary
    python -X utf8 parse.py --verify   # also print the checks against the newest copy

How a history is made from copies:
- Each copy says which DOF reform it runs to ("Última reforma publicada DOF dd-mm-yyyy"). Copies cut off by the
  archive at exactly 1 MiB are dropped; for each reform date the newest copy is used.
- Units: preámbulo, estructura (the Título/Capítulo/Sección headings), art-001..art-136, the 1917 transitorios and
  one unit per reform decree's transitorios. The publisher's notes ("Párrafo reformado DOF ...") are taken out of
  the text and kept for credits.
- Between two copies, every changed unit is credited from its own notes (any copy from then on): a note date that
  falls in the gap names the decree published that day. Several decrees on one day: the one whose title names the
  article, if exactly one does. No note date: the decree whose title names the article, if exactly one in the gap
  does. Otherwise the change is unexplained (publisher). A decree's own transitorios unit is credited to it.
- Each credited change takes effect on its decree's in-force day, read from the decree's first transitorio; when
  none can be read, Código Civil Federal art. 3 (three days after publication). Unexplained changes are dated on the
  copy's last-reform day.
"""
from __future__ import annotations

import datetime as dt
import difflib
import hashlib
import json
import os
import re
import sys
import unicodedata
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
CACHE = HERE / '.cache'
OUT = HERE / 'corpus.d' / '10-constitucion.json'
sys.path.insert(0, str(HERE))
import reforms  # noqa: E402

LEYES = 'https://www.diputados.gob.mx/LeyesBiblio/'
CRONO_URL = 'https://web.archive.org/web/20261009051049id_/https://www.diputados.gob.mx/LeyesBiblio/ref/cpeum_crono.htm'
TRUNCATED = 1048576
MONTHS = {m: i + 1 for i, m in enumerate(
    'enero febrero marzo abril mayo junio julio agosto septiembre octubre noviembre diciembre'.split())}
MONTHS['setiembre'] = 9
NUMWORDS = {'un': 1, 'uno': 1, 'dos': 2, 'tres': 3, 'cuatro': 4, 'cinco': 5, 'seis': 6, 'siete': 7, 'ocho': 8,
            'nueve': 9, 'diez': 10, 'quince': 15, 'veinte': 20, 'treinta': 30, 'cuarenta': 40, 'cuarenta y cinco': 45,
            'sesenta': 60, 'noventa': 90, 'ciento veinte': 120, 'ciento ochenta': 180, 'trescientos sesenta y cinco': 365}


def cache_path(url: str) -> Path:
    return CACHE / hashlib.sha256(url.encode('utf-8')).hexdigest()


def capture_url(c: dict) -> str:
    return 'https://web.archive.org/web/%sid_/%s' % (c['timestamp'], c['original'])


# ---------------------------------------------------------------- text normalisation

def norm(s: str) -> str:
    s = unicodedata.normalize('NFC', s)
    s = s.replace('\xa0', ' ').replace('­', '').replace('\t', ' ')
    s = re.sub(r'[‘’‚´`]', "'", s)
    s = re.sub(r'[“”„«»]', '"', s)
    s = re.sub(r'[‐-―−]', '-', s)
    s = re.sub(r'(?<![\w.])(?:V{2,}|E{3,})(?![\w])', '……', s)  # 2013 copies print "……" glyphs as "VVV"/"EEE"
    s = s.replace('…', '...')
    s = re.sub(r'\.(?:\s?\.){2,}', '... ', s)  # runs of dots / ellipses ("……….." vs "………" vs "...")
    s = re.sub(r'\s+', ' ', s).strip()
    s = re.sub(r'\s+([,;:])', r'\1', s)
    # dashes used as parentheses are spaced unevenly from copy to copy ("exclusivismos - atenderá" / "exclusivismos-
    # atenderá"); hyphenated words ("político-electoral") have no space and are left alone
    s = re.sub(r'(?<=\w)\s*-\s+(?=\w)|(?<=\w)\s+-\s*(?=\w)', ' - ', s)
    s = re.sub(r'(?<=\d-\d\d)- (?=\d{4}\b)', '-', s)  # "05-02- 1917"
    return s


DATE = re.compile(r'(\d{1,2})-(\d{1,2})-(\d{4})')


def note_dates(note: str) -> set[str]:
    out = set()
    for d, m, y in DATE.findall(note):
        try:
            out.add(dt.date(int(y), int(m), int(d)).isoformat())
        except ValueError:
            pass
    return out


# ---------------------------------------------------------------- PDF -> paragraphs

# What starts a paragraph: a fracción/inciso/apartado label, an article, an ordinal transitorio.
LABEL = re.compile(r'^(?:[IVXL]+\.|[A-Z]\.|[a-z]\)|\d{1,2}\.|Art[íi]culo\s+\d|ART[ÍI]CULO\b|'
                   r'(?:PRIMER|SEGUND|TERCER|CUART|QUINT|SEXT|S[ÉE]PTIM|OCTAV|NOVEN|D[ÉE]CIM)[OA]S?\b|'
                   r'(?:Primer|Segund|Tercer|Cuart|Quint|Sext|S[ée]ptim|Octav|Noven|D[ée]cim)[oa]\.)')
HEADING_LINE = re.compile(r'^(T[íi]tulo|TÍTULO|TITULO|Cap[íi]tulo|CAPÍTULO|CAPITULO|Secci[óo]n|SECCIÓN|SECCION)\s+\S+$')


def bold_line(span: dict) -> bool:
    return 'Bold' in span['font'] or bool(span['flags'] & 16)


def extract(path: str) -> dict:
    """One copy -> {'reform': 'YYYY-MM-DD', 'paras': [{'t', 'notes', 'bold', 'centered'}]}."""
    import fitz  # PyMuPDF
    fitz.TOOLS.mupdf_display_errors(False)
    doc = fitz.open(path)
    paras: list[dict] = []
    cur = None
    reform = None

    def close():
        nonlocal cur
        if cur is not None:
            cur['t'] = norm(' '.join(cur['lines']))
            del cur['lines']
            if cur['t']:
                paras.append(cur)
        cur = None

    lines = []
    for pno, page in enumerate(doc):
        width = page.rect.width
        for b in page.get_text('dict')['blocks']:
            for ln in b.get('lines', []):
                spans = ln['spans']
                text = ''.join(s['text'] for s in spans)
                x0, y0, x1, y1 = ln['bbox']
                if y0 < 104:
                    if reform is None:
                        m = re.search(r'(?:ltimas? [Rr]eformas?|Nueva Ley) DOF\s*(\d{1,2}-\d{1,2}-\d{4})', text)
                        if m:
                            reform = min(note_dates(m.group(0)))
                    continue
                if (y0 > 735 and re.fullmatch(r'\s*(\d+ de \d+)?\s*', text)) or (y0 > 700 and re.fullmatch(r'\s*\d+ de \d+\s*', text)):
                    continue
                first = next((s for s in spans if s['text'].strip()), spans[0])
                lines.append((pno, x0, y0, x1, text, first, width))
    # The right margin: the commonest right edge of long lines. Justified text fills it on every line but a
    # paragraph's last, so a short line ends a paragraph (some copies leave out the blank line between two).
    edges = {}
    for pno, x0, y0, x1, text, first, width in lines:
        if 0.8 * width < x1 < width - 40:
            edges[round(x1)] = edges.get(round(x1), 0) + 1
    right = max(edges, key=lambda e: (edges[e], e)) if edges else 540
    last = None  # (page, y0, x1) of the last body line in the open paragraph
    for pno, x0, y0, x1, text, first, width in lines:
        if not text.strip():
            close()
            continue
        italic = bool(first['flags'] & 2) or 'Italic' in first['font']
        if italic and first['size'] <= 9.0:
            # a publisher note: belongs to the paragraph above it
            target = cur if cur is not None else (paras[-1] if paras else None)
            if target is not None:
                if target.get('_note_open'):
                    target['notes'][-1] += ' ' + text.strip()
                else:
                    target['notes'].append(text.strip())
                    target['_note_open'] = True
            close()
            continue
        if paras and paras[-1].get('_note_open'):
            paras[-1].pop('_note_open')
        bold = bold_line(first)
        # Headings and the "Publicado en el DOF" line are centred, bold or not in body size; an indented fracción's
        # short last line can also sit mid-page, so body-size plain text never counts.
        centered = (abs((x0 + x1) / 2 - width / 2) < 40 and x0 > 100 and width - x1 > 100
                    and (bold_line(first) or abs(first['size'] - 10) > 0.6))
        if HEADING_LINE.match(text.strip()) and bold:
            close()
            paras.append({'t': norm(text), 'notes': [], 'bold': True, 'centered': True, 'heading': True})
            continue
        if cur is not None and cur['lines']:
            same_line = last and last[0] == pno and abs(y0 - last[1]) < 3
            short = not centered and last and last[2] < right - 20
            if not same_line and (
                    cur.get('centered') != centered
                    or ((short or re.search(r'[.;:]\s*$', cur['lines'][-1])) and LABEL.match(text.strip()))
                    or (short and last[0] != pno and re.search(r'[.;:]\s*$', cur['lines'][-1]))):
                close()
        if cur is None:
            cur = {'lines': [], 'notes': [], 'bold': bold, 'centered': centered}
        cur['lines'].append(text)
        if last and last[0] == pno and abs(y0 - last[1]) < 3:
            last = (pno, y0, max(x1, last[2]))
        else:
            last = (pno, y0, x1)
    close()
    for p in paras:
        p.pop('_note_open', None)
    # A paragraph that is only a label ("I.", "A.", "a)") belongs to the paragraph after it.
    out = []
    for p in paras:
        if out and re.fullmatch(r'([IVXL]+|[A-Z]|[a-z]|\d+)[.)]', out[-1]['t']) and not out[-1]['notes']:
            q = out.pop()
            p = dict(p, t=q['t'] + ' ' + p['t'], bold=q['bold'] or p['bold'])
        out.append(p)
    return {'reform': reform, 'paras': out, 'pages': doc.page_count}


# ---------------------------------------------------------------- paragraphs -> units

ART = re.compile(r'^Art[íi]culo\s+(\d{1,3})\s*(?:o|º|°)?\s*\.?-?(?:\s|$)')
PUB = re.compile(r'^Publicad[oa] en el Diario Oficial de la Federaci[óo]n,? el (?:d[íi]a )?(\d{1,2}|1o\.?|primero)\s*(?:o\.)?\s+de\s+'
                 r'([a-zA-Z]+)\s+(?:de|del)\s+(?:año\s+)?(\d{4})', re.I)


def spanish_date(d: str, m: str, y: str) -> str | None:
    d = d.lower().rstrip('.').rstrip('o')
    d = 1 if d in ('1', 'primer', 'primero', '') else int(d)
    mm = MONTHS.get(m.lower())
    if not mm:
        return None
    try:
        return dt.date(int(y), mm, d).isoformat()
    except ValueError:
        return None


def segment(paras: list[dict]) -> dict:
    """-> {'units': {key: {'label', 'kind', 'lines', 'notes'}}, 'decrees': [(key-less) {date, title, start}], 'dropped': [...]}"""
    i = 0
    n = len(paras)
    dropped = []
    while i < n and not paras[i]['t'].startswith('El C. Primer Jefe'):
        dropped.append(paras[i]['t'])
        i += 1
    units: dict[str, dict] = {}

    def unit(key, label, kind):
        return units.setdefault(key, {'label': label, 'kind': kind, 'lines': [], 'notes': []})

    def add(u, p):
        u['lines'].append(p['t'])
        u['notes'].extend(p['notes'])

    pre = unit('preambulo', 'Preámbulo', 'preamble')
    while i < n and not (paras[i].get('heading') and paras[i]['t'].lower().startswith('t')):
        add(pre, paras[i])
        i += 1
    est = unit('estructura', 'Títulos, capítulos y secciones', 'structure')
    cur = None
    last = 0
    in_heading = False
    while i < n:
        p = paras[i]
        t = p['t']
        if re.fullmatch(r'Art[íi]culos Transitorios', t, re.I) and last >= 130:
            break
        m = ART.match(t)
        if m and (int(m.group(1)) == last + 1 or (p['bold'] and int(m.group(1)) > last)):
            last = int(m.group(1))
            num = re.match(r'Art[íi]culo\s+(\d+\s*(?:o|º|°)?)', t).group(1).replace(' ', '')
            cur = unit(f'art-{last:03d}', f'Artículo {num}.' if not num[-1].isdigit() else f'Artículo {num}', 'art')
            in_heading = False
            add(cur, p)
        elif p.get('heading') or (in_heading and p['centered'] and p['bold']):
            in_heading = True
            add(est, p)
        else:
            in_heading = False
            if cur is None:
                add(est, p)
            else:
                add(cur, p)
        i += 1
    t17 = unit('transitorios-1917', 'Artículos transitorios (1917)', 'transitional')
    while i < n and not paras[i]['t'].upper().startswith('ARTÍCULOS TRANSITORIOS DE DECRETOS'):
        add(t17, paras[i])
        i += 1
    i += 1
    # reform decrees: each block runs from its title paragraph (just before "Publicado en el DOF el ...") to the next
    anchors = [j for j in range(i, n) if PUB.match(paras[j]['t'])]
    starts = [a - 1 for a in anchors]
    while i < (starts[0] if starts else n):
        dropped.append(paras[i]['t'])  # "A partir del 3 de septiembre de 1993"
        i += 1
    decrees = []
    for k, s in enumerate(starts):
        e = starts[k + 1] if k + 1 < len(starts) else n
        m = PUB.match(paras[s + 1]['t'])
        decrees.append({'date': spanish_date(*m.groups()), 'title': paras[s]['t'], 'paras': paras[s:e]})
    return {'units': units, 'decrees': decrees, 'dropped': dropped}


# ---------------------------------------------------------------- decree list, in-force days

def load_decrees() -> list[dict]:
    rows = reforms.rows(cache_path(CRONO_URL).read_bytes())
    out = []
    for r in rows:
        num = r['num'] if r['num'] is not None else 0
        pdf = next((l for l in r['links'] if re.search(r'dof/CPEUM_(?:fe_)?(?:ref|orig)_[^/]*\.pdf$', l) and '_ima' not in l),
                   next((l for l in r['links'] if l.endswith('.pdf')), None))
        out.append({'num': num, 'key': 'cpeum-1917' if num == 0 else f'decreto-cpeum-{num:03d}',
                    'dof': r['dof'], 'name': norm(r['name']), 'title': norm(r['title']),
                    'url': LEYES + 'ref/' + pdf if pdf and not pdf.startswith('..') else
                    (LEYES + pdf[3:] if pdf else LEYES + 'ref/cpeum_crono.htm')})
    out.sort(key=lambda d: (d['dof'], d['num']))
    return out


def law_key(d: dict) -> str:
    return d['key']


def add_days(day: str, n: int) -> str:
    return (dt.date.fromisoformat(day) + dt.timedelta(days=n)).isoformat()


def in_force(dof: str, paras: list[dict]) -> tuple[str, str]:
    """(in-force day, the rule used) from the decree's first transitorio that speaks of entry into force."""
    seen_trans = False
    for p in paras:
        t = p['t']
        if re.fullmatch(r'(?:ART[ÍI]CULOS?\s+)?TRANSITORIOS?\s*:?\.?', t, re.I):
            seen_trans = True
            continue
        if not seen_trans or not re.search(r'(?i)vigor|vigencia|surtir[áa]', t):
            continue
        low = t.lower()
        clause = re.split(r',?\s+(?:con excepci[óo]n|salvo|excepto|sin perjuicio|y en su caso|en tanto)|;', low)[0]
        if re.search(r'(?:al|el) d[íi]a siguiente (?:al|de)(?: (?:la|de))? (?:su|la) publicaci[óo]n', clause) \
                or re.search(r'a partir del d[íi]a siguiente', clause):
            return add_days(dof, 1), 'día siguiente al de su publicación'
        if re.search(r'(?:el (?:mismo )?d[íi]a|a partir de la fecha|a partir del d[íi]a|en la fecha) de su publicaci[óo]n', clause) \
                or re.search(r'a partir de su publicaci[óo]n', clause):
            return dof, 'día de su publicación'
        m = re.search(r'a los ([a-z ]+?|\d+) d[íi]as(?: naturales)?\b(?![^.]{0,40}h[áa]biles)[^.]{0,60}?publicaci[óo]n', clause)
        if m and (m.group(1).strip() in NUMWORDS or m.group(1).isdigit()):
            k = int(m.group(1)) if m.group(1).isdigit() else NUMWORDS[m.group(1).strip()]
            return add_days(dof, k), f'a los {m.group(1).strip()} días de su publicación'
        m = re.search(r'(?:el|a partir del?)\s+(?:d[íi]a\s+)?(\d{1,2}|primero)\s*(?:o\.?|º)?\s+de\s+([a-z]+)\s+(?:de|del)\s+(?:año\s+)?(\d{4})', clause)
        if m:
            d = spanish_date(*m.groups())
            if d:
                return d, 'fecha fija'
        break
    return add_days(dof, 3), 'Código Civil Federal art. 3 (tres días después de su publicación)'


# ---------------------------------------------------------------- titles naming articles

def title_articles(title: str) -> set[int]:
    """Article numbers a decree's own title names ("se reforman los artículos 41, 54 y 60 ...")."""
    t = title.split(' de la Constituci')[0]
    out = set()
    for m in re.finditer(r'(?i)art[íi]culos?\s+(.*?)(?=$)', t):
        for x in re.findall(r'\b(\d{1,3})\s*(?:o\.|º|°)?', m.group(1)):
            if 1 <= int(x) <= 136:
                out.add(int(x))
        break
    return out


NOTE_LINE = re.compile(r'(?i)(?:reformad|adicionad|derogad|recorrid|original|erratas?|reforma\b|declarad|aclarad)[^\n]*'
                       r'DOF:?\s*\d{1,2}-\d{1,2}-\d{4}')


def coverage(path: str, units: dict) -> dict:
    """An independent check of one copy against the units made from it: the copy's body text read a second way
    (PyMuPDF plain text, below the page header, publisher notes taken out by their wording), with every space removed,
    must contain every unit paragraph, and the paragraphs must account for (nearly) all of it."""
    import fitz
    fitz.TOOLS.mupdf_display_errors(False)
    doc = fitz.open(path)
    body = []
    for page in doc:
        clip = fitz.Rect(0, 104, page.rect.width, 735)
        for ln in page.get_text('text', clip=clip).split('\n'):
            if re.fullmatch(r'\s*\d+ de \d+\s*', ln):
                continue
            if NOTE_LINE.search(ln) and len(ln) < 260 and not re.match(r'\s*(Art[íi]culo \d|[IVX]+\.)', ln):
                continue
            body.append(ln)
    flat = re.sub(r'\s+', '', norm(' '.join(body)))
    paras = [re.sub(r'\s+', '', l) for u in units.values() for l in u['lines']]
    missing = [p[:80] for p in paras if p not in flat]
    covered = sum(len(p) for p in paras if p in flat)
    return {'paragraphs': len(paras), 'missing': missing, 'body_chars': len(flat), 'unit_chars': covered,
            'share': round(covered / max(1, len(flat)), 4)}


def all_coverage(states: list[dict]) -> dict:
    with ProcessPoolExecutor(max_workers=min(8, os.cpu_count() or 2)) as ex:
        res = list(ex.map(coverage, [c['path'] for c in states],
                          [{k: {'lines': u['lines']} for k, u in c['units'].items()} for c in states]))
    return {'copies': len(res), 'paragraphs': sum(r['paragraphs'] for r in res),
            'missing': sum(len(r['missing']) for r in res), 'min_share': min(r['share'] for r in res),
            'min_share_copy': states[min(range(len(res)), key=lambda i: res[i]['share'])]['timestamp']}


def title_fits(title: str, art: int | None) -> bool:
    """Could this decree have changed this unit, by its own title? A title that lists articles fits only those
    articles; one that names none ("diversas disposiciones") fits any unit. Units other than articles fit only titles
    naming no article or naming transitorios."""
    named = title_articles(title)
    if art is None:
        return not named or bool(re.search(r'(?i)transitori', title))
    return not named or art in named


# ---------------------------------------------------------------- main

def unit_text(u: dict) -> str:
    return ''.join(l + '\n' for l in u['lines'])


def load_captures() -> list[dict]:
    caps = json.loads((CACHE / 'caps-constitucion.json').read_text(encoding='utf-8'))
    for c in caps:
        p = cache_path(capture_url(c))
        c['path'] = str(p)
        c['size'] = p.stat().st_size if p.exists() else 0
    return caps


def parse_all(caps):
    good = [c for c in caps if c['size'] and c['size'] != TRUNCATED]
    with ProcessPoolExecutor(max_workers=min(8, os.cpu_count() or 2)) as ex:
        res = list(ex.map(extract, [c['path'] for c in good]))
    for c, r in zip(good, res):
        c.update(r)
        c['sha256'] = hashlib.sha256(Path(c['path']).read_bytes()).hexdigest()
    return good


def build(verify: bool = False) -> dict:
    caps = load_captures()
    dropped_trunc = [c['timestamp'] for c in caps if c['size'] == TRUNCATED]
    good = parse_all(caps)
    # newest copy per reform date
    by_reform: dict[str, dict] = {}
    for c in good:
        if c['reform'] and (c['reform'] not in by_reform or c['timestamp'] > by_reform[c['reform']]['timestamp']):
            by_reform[c['reform']] = c
    states = [by_reform[r] for r in sorted(by_reform)]
    for c in states:
        c.update(segment(c['paras']))
    decrees = load_decrees()
    by_date: dict[str, list[dict]] = {}
    for d in decrees:
        by_date.setdefault(d['dof'], []).append(d)

    # decree transitorios units: identify each block with a numbered decree of that DOF day
    block_text: dict[str, list[dict]] = {}
    unmatched_blocks = []
    errata: dict[str, dict] = {}
    for c in states:
        used = set()
        for b in c['decrees']:
            if re.match(r'(?i)fe de erratas?\b', b['title']):
                # An erratum printed in the DOF that corrects a decree's text: a publication of its own.
                key = f'fe-de-erratas-{b["date"]}'
                if key not in errata:
                    errata[key] = {'num': None, 'key': key, 'dof': b['date'], 'name': b['title'], 'title': b['title'],
                                   'erratum': True, 'url': LEYES + 'pdf/CPEUM.pdf'}
                dmy = f'{b["date"][8:10]}-{b["date"][5:7]}-{b["date"][:4]}'
                n = sum(1 for k in c['units'] if k.startswith(key))  # two errata printed on one day
                ukey = key if not n else f'{key}-{n + 1}'
                c['units'][ukey] = {'label': f'Fe de erratas (DOF {dmy})' + (f', {n + 1}' if n else ''), 'kind': 'transitional',
                                   'lines': [p['t'] for p in b['paras']],
                                   'notes': [x for p in b['paras'] for x in p['notes']], 'decree': key}
                continue
            cands = [d for d in by_date.get(b['date'], []) if d['num'] not in used]
            if not cands:
                unmatched_blocks.append((c['timestamp'], b['date'], b['title'][:80]))
                continue
            best = max(cands, key=lambda d: (difflib.SequenceMatcher(None, d['name'][:240].lower(), b['title'][:240].lower()).ratio(), -d['num']))
            used.add(best['num'])
            key = f'transitorios-{b["date"]}-{best["num"]:03d}'
            dmy = f'{b["date"][8:10]}-{b["date"][5:7]}-{b["date"][:4]}'
            c['units'][key] = {'label': f'Transitorios, reforma {best["num"]} (DOF {dmy})',
                               'kind': 'transitional', 'lines': [p['t'] for p in b['paras']],
                               'notes': [x for p in b['paras'] for x in p['notes']], 'decree': best['key']}
            block_text[best['key']] = b['paras']  # newest copy wins (states are in order)
    decrees = sorted(decrees + list(errata.values()), key=lambda d: (d['dof'], d['num'] or 0, d['key']))
    force = {}
    for d in decrees:
        if d['key'] in block_text:
            force[d['key']] = in_force(d['dof'], block_text[d['key']])
        else:
            force[d['key']] = (add_days(d['dof'], 3), 'Código Civil Federal art. 3 (tres días después de su publicación)')

    # notes per unit, across every copy (dates only)
    notes_from: list[dict[str, set[str]]] = []
    for c in states:
        notes_from.append({k: set().union(*[note_dates(x) for x in u['notes']]) if u['notes'] else set()
                           for k, u in c['units'].items()})

    first = states[0]
    events = []  # (day, order, unit, text|None, credits, state index)
    stats = {'credited_notes': 0, 'credited_title': 0, 'credited_self': 0, 'unexplained': 0}
    unexplained = []
    for k in range(1, len(states)):
        a, b = states[k - 1], states[k]
        # Decrees published after the last copy's reform up to this copy's; errata up to the day the copy was captured.
        seen = f'{b["timestamp"][:4]}-{b["timestamp"][4:6]}-{b["timestamp"][6:8]}'
        gap = [d for d in decrees if a['reform'] < d['dof'] <= (seen if d.get('erratum') else b['reform'])]
        keys = sorted(set(a['units']) | set(b['units']))
        for u in keys:
            ta = unit_text(a['units'][u]) if u in a['units'] else None
            tb = unit_text(b['units'][u]) if u in b['units'] else None
            if ta == tb:
                continue
            later = set().union(*[nf.get(u, set()) for nf in notes_from[k:]])
            cred = []
            art = int(u[4:]) if u.startswith('art-') else None
            dec_self = b['units'].get(u, {}).get('decree') if tb is not None else None
            if dec_self is not None and any(d['key'] == dec_self for d in gap):
                cred = [d for d in gap if d['key'] == dec_self]
                stats['credited_self'] += 1
            else:
                hit_dates = sorted({d['dof'] for d in gap} & later)
                for day in hit_dates:
                    same = [d for d in gap if d['dof'] == day]
                    if len(same) > 1:
                        named = [d for d in same if title_fits(d['name'], art)]
                        same = named if len(named) == 1 else []
                    cred += same
                if cred:
                    stats['credited_notes'] += 1
                elif art is not None and not hit_dates:
                    named = [d for d in gap if art in title_articles(d['name'])]
                    if len(named) == 1:
                        cred = named
                        stats['credited_title'] += 1
            if cred:
                day = max(force[d['key']][0] for d in cred)
            else:
                day = b['reform']
                stats['unexplained'] += 1
                unexplained.append((b['reform'], u))
            events.append([day, k, u, tb, [law_key(d) for d in cred]])

    # Per unit, a later copy's change can't take effect before an earlier one: clamp.
    clamped = []
    last_day: dict[str, str] = {}
    first_day = force[max((d for d in decrees if d['dof'] <= first['reform'] and d['num']), key=lambda d: d['num'])['key']][0]
    for e in events:
        floor = max(last_day.get(e[2], first_day), first_day)
        if e[0] < floor:
            clamped.append((e[2], e[0], floor))
            e[0] = floor
        last_day[e[2]] = e[0]
    events.sort(key=lambda e: (e[0], e[1]))

    def mk(u, text, c):
        src = c['units'][u]
        return {'label': src['label'], 'kind': src['kind'], 'text': text}

    versions = [{'from': first_day, 'source_url': capture_url(first), 'sha256': first['sha256'],
                 'units': {u: mk(u, unit_text(x), first) for u, x in sorted(first['units'].items())},
                 'credits': {},
                 'note': f'Oldest copy available: Cámara de Diputados consolidated text, last reform DOF {first["reform"]}, '
                         f'Internet Archive capture {first["timestamp"]}.'}]
    state = {u: unit_text(x) for u, x in first['units'].items()}
    i = 0
    while i < len(events):
        day = events[i][0]
        grp = []
        while i < len(events) and events[i][0] == day:
            grp.append(events[i])
            i += 1
        changes, credits = {}, {}
        for e in grp:
            _, k, u, text, cred = e
            changes[u] = None if text is None else mk(u, text, states[k])
            if cred:
                credits[u] = sorted(set(credits.get(u, [])) | set(cred))
        for u, x in list(changes.items()):
            old = state.get(u)
            new = None if x is None else x['text']
            if old == new:
                changes.pop(u)
                credits.pop(u, None)
                continue
            if new is None:
                state.pop(u, None)
            else:
                state[u] = new
        if not changes:
            continue
        k = max(e[1] for e in grp)
        c = states[k]
        if day == versions[-1]['from']:
            v = versions[-1]
            v['changes'].update(changes)
            for u, ls in credits.items():
                v['credits'][u] = sorted(set(v['credits'].get(u, [])) | set(ls))
            continue
        versions.append({'from': day, 'source_url': capture_url(c), 'sha256': c['sha256'], 'changes': changes,
                         'credits': credits})
    final = {u: unit_text(x) for u, x in states[-1]['units'].items()}
    report = {
        'copies': len(caps), 'truncated_dropped': dropped_trunc, 'parsed': len(good), 'states': len(states),
        'reforms': [c['reform'] for c in states], 'versions': len(versions), 'events': len(events), 'stats': stats,
        'clamped': clamped, 'unmatched_blocks': unmatched_blocks,
        'final_matches_newest_copy': final == state, 'newest_copy': states[-1]['timestamp'],
        'newest_copy_coverage': coverage(states[-1]['path'], states[-1]['units']),
        'all_copies_coverage': all_coverage(states),
        'unexplained': unexplained,
        'force_rules': {n: r for n, (_, r) in force.items()},
    }
    return {'states': states, 'decrees': decrees, 'force': force, 'versions': versions, 'report': report}


def corpus(res: dict) -> dict:
    states, decrees, force, versions = res['states'], res['decrees'], res['force'], res['versions']
    first = states[0]
    laws = {}
    for d in decrees:
        key = law_key(d)
        dmy = f'{d["dof"][8:10]}-{d["dof"][5:7]}-{d["dof"][:4]}'
        laws[key] = {
            'label': 'Constitución de 1917 (DOF 05-02-1917)' if d['num'] == 0 else
                     f'Fe de erratas (DOF {dmy})' if d.get('erratum') else f'Decreto de reforma {d["num"]} (DOF {dmy})',
            'title': d['name'], 'kind': 'law', 'enacted': None, 'published': d['dof'], 'url': d['url'],
            'temporary_until': None, 'restores': None,
            'note': ('An erratum the Diario Oficial de la Federación printed to correct the published text of a decree; '
                     'the Cámara de Diputados prints it with the decrees.') if d.get('erratum') else None}
    earlier = [law_key(d) for d in decrees if d['dof'] <= first['reform']]
    rules = {}
    for d in decrees:
        if d['dof'] > first['reform']:
            rules.setdefault(force[d['key']][1], []).append(d['key'])
    act = {
        'slug': 'constitucion', 'short': 'CPEUM',
        'title': 'Constitución Política de los Estados Unidos Mexicanos',
        'url': LEYES + 'pdf/CPEUM.pdf', 'first_law': None, 'earlier_laws': earlier, 'versions': versions}
    rep = res['report']
    decisions = [
        'Constitución: history starts at the oldest consolidated copy the Internet Archive holds (Cámara de Diputados '
        f'pdf/1.pdf captured {first["timestamp"]}, last reform DOF {first["reform"]}); 1917-2006 is not rebuilt, and the '
        f'first version names the {len(earlier)} earlier decrees.',
        f'Constitución: {len(rep["truncated_dropped"])} archived copies cut off at exactly 1 MiB were dropped '
        f'({", ".join(rep["truncated_dropped"])}); for each last-reform date the newest copy is used '
        f'({rep["states"]} copies from {rep["parsed"]} readable ones).',
        'Constitución: in-force dates come from each decree\'s first transitorio that speaks of entry into force '
        '("al día siguiente de su publicación" = DOF + 1, "el día de su publicación" = DOF, a fixed date, or "a los N '
        'días"); otherwise Código Civil Federal art. 3 (three days after publication). Counts: '
        + '; '.join(f'{r}: {len(v)}' for r, v in sorted(rules.items())) + '.',
        'Constitución: where a decree puts single provisions in force on later dates (for example the 2014 '
        'political-electoral reform, DOF 10-02-2014), the whole article takes effect on the decree\'s general date; '
        'the staggered dates are in the decree\'s transitorios unit.',
        'Constitución: credits come from the publisher\'s paragraph notes ("Párrafo reformado DOF dd-mm-yyyy", in copies '
        'from 2013 on, read for every unit across all later copies): a note date inside the gap between two copies names '
        'the decree published that day. Several decrees that day, or no note date: the decree whose own title names '
        'the article, only if exactly one fits. Otherwise the change is unexplained and dated on the copy\'s '
        f'last-reform day. Counts: {rep["stats"]}.',
        'Constitución: units are the preámbulo, the headings (estructura), articles 1-136, the 1917 transitorios and one '
        'unit per reform decree\'s transitorios as the publisher prints them; the publisher\'s notes and cover page are '
        'left out of the text.',
        'Constitución: copies before 2013 print the transitorios of only some earlier decrees; transitorios the '
        'publisher added later for decrees before the gap arrive as unexplained publisher changes.',
    ]
    cov, allc = rep['newest_copy_coverage'], rep['all_copies_coverage']
    decisions += [
        'Constitución: a copy prints a decree\'s wording from its publication day, but each change here takes effect '
        'only on its decree\'s in-force day, so no wording appears before its decree applies.',
        'Constitución: errata ("Fe de erratas") that the DOF printed and the publisher reproduces with the decrees are '
        'laws of their own, dated by Código Civil Federal art. 3; one (DOF 25-06-2009) corrects art. 16.',
        'Constitución: when two decrees were published on the same day and a note names that day, the change is '
        'credited only if exactly one decree\'s title fits the article (a title listing other articles does not fit; '
        '"diversas disposiciones" fits any); otherwise it is unexplained, as for art. 41 on DOF 02-06-2026.',
        f'Constitución, verification: the last version equals the units read from the newest copy (Internet Archive '
        f'{rep["newest_copy"]}, last reform DOF 07-10-2026): {rep["final_matches_newest_copy"]}. Read a second way '
        f'(plain text, notes removed), that copy contains all {cov["paragraphs"]} unit paragraphs verbatim, which '
        f'cover {cov["share"]:.2%} of its body text (the rest is the cover page and wrapped note lines); across all '
        f'{allc["copies"]} copies used, {allc["paragraphs"]} paragraphs, {allc["missing"]} missing, lowest coverage '
        f'{allc["min_share"]:.2%}.',
    ]
    if rep['clamped']:
        decisions.append(f'Constitución: {len(rep["clamped"])} unit changes from a later copy would have taken effect '
                         'before a change from an earlier copy to the same unit; they were moved to that later day: '
                         + ', '.join(f'{u} {a}->{b}' for u, a, b in rep['clamped'][:20]) + '.')
    sources = [{
        'name': 'Cámara de Diputados, LeyesBiblio: Constitución Política de los Estados Unidos Mexicanos (texto vigente, '
                'consolidated PDFs), read through the Internet Archive Wayback Machine',
        'url': LEYES + 'pdf/CPEUM.pdf', 'retrieved': '2026-10-28', 'requests': logged_requests(r'LeyesBiblio/pdf/(?:1[._]|CPEUM)'),
        'licence': 'Public legal text; Cámara de Diputados del H. Congreso de la Unión, Secretaría de Servicios '
                   'Parlamentarios. Archived copies: Internet Archive.',
        'notes': f'{rep["copies"]} distinct archived copies (CDX digests) 2006-2026; captures used: '
                 + ', '.join(c['timestamp'] for c in states) + '.'},
        {'name': 'Cámara de Diputados: reformas constitucionales por orden cronológico (ref/cpeum_crono.htm)',
         'url': LEYES + 'ref/cpeum_crono.htm', 'retrieved': '2026-10-28', 'requests': 1,
         'licence': 'Public information, Cámara de Diputados.', 'notes': 'Internet Archive capture 20261009051049.'}]
    return {
        'country': {
            'code': 'MX', 'name': 'Mexico', 'slug': 'mexico', 'lang': 'es', 'tz': 'America/Mexico_City',
            'future_branch': 'futuro',
            'publisher': {'name': 'Cámara de Diputados (LeyesBiblio)', 'email': 'leyesbiblio@diputados.invalid'},
            'default_in_force_rule': {
                'text': 'Código Civil Federal art. 3: laws bind and take effect three days after publication in the '
                        'Diario Oficial de la Federación; art. 4: a law that fixes its own start day binds from that day',
                'source': LEYES + 'pdf/2_110121.pdf'},
            'licence_note': 'Texto: Cámara de Diputados del H. Congreso de la Unión, Secretaría de Servicios '
                            'Parlamentarios (LeyesBiblio), copias del Internet Archive.'},
        'sources': sources, 'laws': laws, 'acts': [act], 'applies': [], 'decisions': decisions,
        'ai_use': ['Claude Code (Claude Opus 5.5, claude-opus-5-5) wrote fetch.py, reforms.py and parse.py. No model '
                   'output is used as legal text, dates or credits: all come from the cached official copies by '
                   'deterministic code.']}


def logged_requests(pattern: str) -> int:
    """How many logged requests (archive.org CDX listings and captures) touched these files."""
    n = 0
    for line in (CACHE / 'requests.jsonl').read_text(encoding='utf-8').splitlines():
        if re.search(pattern, json.loads(line).get('url', '')):
            n += 1
    return n


def write_atomic(path: Path, data: dict) -> None:
    path.parent.mkdir(exist_ok=True)
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1, sort_keys=False) + '\n', encoding='utf-8', newline='\n')
    os.replace(tmp, path)


def main(argv):
    res = build()
    rep = res['report']
    write_atomic(OUT, corpus(res))
    (HERE / '.tmp').mkdir(exist_ok=True)
    (HERE / '.tmp' / 'parse-report.json').write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding='utf-8')
    print(json.dumps({k: v for k, v in rep.items() if k not in ('unexplained', 'force_rules', 'reforms')}, ensure_ascii=False)[:3000])
    print('unexplained', len(rep['unexplained']))


if __name__ == '__main__':
    main(sys.argv[1:])
