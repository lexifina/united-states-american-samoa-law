"""Angola git-for-law: read the cached Diário da República PDFs (born-digital text layers only) and write
corpus.d/*.json in the gitlaw_common SCHEMA.md format. No network; same cache gives the same bytes.

    python -X utf8 scripts/angola-law/parse.py
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import unicodedata
from pathlib import Path

import fitz  # PyMuPDF

HERE = Path(__file__).resolve().parent
CACHE = HERE / '.cache'
SOURCES = json.loads((HERE / 'sources.json').read_text(encoding='utf-8'))


def cached(url: str) -> Path:
    return CACHE / hashlib.sha256(url.encode('utf-8')).hexdigest()


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


# ------------------------------------------------------------------ PDF -> logical lines

COL_SPLIT = 298  # two-column Diário da República page; left column x 51..293, right 305..547


def page_lines(pdf: Path) -> list[dict]:
    """Every text line of the gazette in reading order, without mastheads, running heads, footers and footnotes."""
    d = fitz.open(pdf)
    out = []
    for pno, pg in enumerate(d):
        rows = []
        for b in pg.get_text('dict')['blocks']:
            for ln in b.get('lines', []):
                # 7 pt footnotes and 4-6 pt note markers (digits) are dropped; a small alphabetic span right after
                # body text is an ordinal superscript ("n.os", "2.os") and is kept.
                sp = ln['spans']
                spans = [s for i, s in enumerate(sp) if s['size'] >= 7.5
                         or (i > 0 and sp[i - 1]['size'] >= 7.5 and s['text'].strip().isalpha())]
                text = ''.join(s['text'] for s in spans)
                if not text.strip():
                    continue
                x0, y0, x1, y1 = ln['bbox']
                x0 = min(s['bbox'][0] for s in spans)
                x1 = max(s['bbox'][2] for s in spans)
                if y0 < 62 or y0 > 795:  # running head (page number, title, series) and print-run footer
                    continue
                if pno == 0 and y0 < 320:  # first-page masthead: title, price, subscription box
                    continue
                size = max(s['size'] for s in spans)
                if size > 11.5:  # mastheads, SUMÁRIO / issuing-body banners
                    continue
                col = 0 if x0 < COL_SPLIT else 1
                left = 51 if col == 0 else 305
                rows.append({'page': pno, 'col': col, 'y': round(y0, 1), 'x0': x0 - left, 'x1': x1 - left,
                             'size': size, 'bold': any('Bold' in s['font'] or '-Bd' in s['font'] for s in spans),
                             'text': text})
        rows.sort(key=lambda r: (r['col'], r['y'], r['x0']))
        out += rows
    return out


MARK = re.compile(r'^(\d+\.(?:\d+\.)*\s|\d+\.\s*\[|[a-z]{1,2}\)\s|[ivxlc]+\)\s|[ivxlc]+\.\s|—\s|-\s|\(\d+\)\s)')
STRUCT = re.compile(r'^(LIVRO|PARTE|TÍTULO|CAPÍTULO|SECÇÃO|SUBSECÇÃO|DIVISÃO|ANEXO)\b', re.I)
ARTICLE = re.compile(r'^ARTIGO\s+(\d+)\.\s*[º°]\s*(?:-\s*([A-Z]))?\s*$')  # 4 CPP headings print "°"


def is_heading(r: dict) -> bool:
    """Article numbers and titles are set in 8 pt; structural headings are centred, their titles bold."""
    if r['size'] < 9.5:
        return True
    t = r['text'].strip()
    if r['x0'] > 20 and STRUCT.match(t) and len(t) < 40:
        return True
    return r['bold']


def join(a: str, b: str, vocab: frozenset = frozenset()) -> str:
    if a.endswith('\xad'):
        return a[:-1] + b
    if a.endswith('-') and b.startswith('-'):
        return a + b[1:]
    # A hard hyphen at the line end that only breaks a word ("exe-" / "cução"): joined without it when the whole word
    # is printed somewhere in the same gazette; otherwise it is a compound ("político-" / "militar") and kept.
    m = re.search(r'(\w+)-$', a)
    n = re.match(r'([a-zà-ÿ]\w*)', b)
    if m and n and (m.group(1) + n.group(1)).lower() in vocab:
        return a[:-1] + b
    if a.endswith(('-', '—', '/')) and not a.endswith(' -'):
        return a + b
    return a + ' ' + b


def norm(s: str) -> str:
    s = unicodedata.normalize('NFC', s.replace('\xa0', ' ').replace('\xad', ''))
    s = s.replace('–', '—').replace('“', '«').replace('”', '»').replace('’', "'")
    s = s.replace('“', '«').replace('”', '»').replace('\t', ' ')
    s = re.sub(r'\s+', ' ', s).strip()
    s = re.sub(r'(\d)\.\s+º', r'\1.º', s)
    return s


def paragraphs(rows: list[dict]) -> list[tuple[str, str]]:
    """[(kind, text)] with kind 'h' (heading line, wrapped titles joined) or 'p' (one body paragraph)."""
    out: list[list] = []
    vocab = frozenset(w.lower() for r in rows for w in re.findall(r'\w+', r['text'].replace('\xad', '')))
    for r in rows:
        t = r['text'].rstrip()
        head = is_heading(r)
        if head:
            st = t.strip()
            prev = out[-1] if out else None
            cont = (prev and prev[0] == 'h' and not ARTICLE.match(st) and not STRUCT.match(st)
                    and (prev[1].count('(') > prev[1].count(')')  # an open "(title" wraps
                         or (not prev[1].startswith('(') and not ARTICLE.match(prev[1]) and not st.startswith('(')
                             and not STRUCT.match(prev[1]) and abs(prev[2] - r['size']) < .3)))
            if cont:
                prev[1] = join(prev[1], st)
            else:
                out.append(['h', st, r['size']])
            continue
        st = t.lstrip()
        starts = 10 <= r['x0'] <= 18 or (r['x0'] > 18 and MARK.match(st) and not (out and out[-1][0] == 'p'
                                                                                and out[-1][1].endswith('\xad')))
        if out and out[-1][0] == 'p' and not starts:
            out[-1][1] = join(out[-1][1], st, vocab)
        else:
            out.append(['p', st, r['size']])
    return [(k, norm(t)) for k, t, _ in out if norm(t)]


# ------------------------------------------------------------------ paragraphs -> units

def key_for(num: int, letter: str | None) -> str:
    return f'art-{num:03d}' + (f'-{letter.lower()}' if letter else '')


def units_from(paras: list[tuple[str, str]], start: int, end: int, preamble: bool) -> tuple[dict, list[str]]:
    """Articles between paras[start:end]; structural headings go to the 'estrutura' unit, one per line."""
    units: dict[str, dict] = {}
    struct: list[str] = []
    pending: list[str] = []
    cur = None
    i = start
    if preamble:
        cur = 'preambulo'
        units[cur] = {'label': 'Preâmbulo', 'kind': 'preamble', 'lines': ['# Preâmbulo']}
    while i < end:
        kind, t = paras[i]
        m = ARTICLE.match(t) if kind == 'h' else None
        if m:
            k = key_for(int(m.group(1)), m.group(2))
            label = f'Artigo {int(m.group(1))}.º' + (f'-{m.group(2)}' if m.group(2) else '')
            title = ''
            if i + 1 < end and paras[i + 1][0] == 'h' and paras[i + 1][1].startswith('('):
                title = ' ' + paras[i + 1][1]
                i += 1
            if k in units:
                raise SystemExit(f'duplicate {k} at {t!r}')
            units[k] = {'label': label, 'kind': 'art', 'lines': [f'# {label}{title}']}
            if pending:
                struct.append(' | '.join(pending) + f' | {label}')
                pending = []
            cur = k
        elif kind == 'h' and (STRUCT.match(t) or (pending and not t.startswith('('))):
            if STRUCT.match(t) and t.upper().startswith('ANEXO'):
                cur = None
                pending.append(t)
            else:
                pending.append(t)
        elif cur is None and pending and pending[0].upper().startswith('ANEXO'):
            n = len([u for u in units if u.startswith('anexo-')]) + 1
            cur = f'anexo-{n:02d}'
            units[cur] = {'label': pending[0].title() if False else ' — '.join(pending), 'kind': 'annex',
                          'lines': ['# ' + ' — '.join(pending)]}
            pending = []
            units[cur]['lines'].append(t)
        elif cur is not None:
            if pending and cur.startswith('anexo-'):
                units[cur]['lines'].append('## ' + ' — '.join(pending))
                pending = []
            units[cur]['lines'].append(t)
        else:
            raise SystemExit(f'text outside any unit: {t[:80]!r}')
        i += 1
    if pending:
        struct.append(' | '.join(pending))
    out = {k: {'label': v['label'], 'kind': v['kind'], 'text': '\n'.join(v['lines']) + '\n'} for k, v in units.items()}
    if struct:
        out['estrutura'] = {'label': 'Estrutura (títulos, capítulos e secções)', 'kind': 'structure',
                            'text': '# Estrutura\n' + '\n'.join(struct) + '\n'}
    return out, struct


def find(paras, pred, start=0) -> int:
    for i in range(start, len(paras)):
        if pred(paras[i]):
            return i
    raise SystemExit('marker not found')


# ------------------------------------------------------------------ acts

def constitution() -> dict:
    src = SOURCES['constituicao']
    paras = paragraphs(page_lines(cached(src['url'])))
    # The republication follows Lei 18/21's own articles and signatures: "CONSTITUIÇÃO DA REPÚBLICA DE ANGOLA",
    # "Preâmbulo", the articles, the constituent assembly's approval formula, then Annexes I-III (each closed by the
    # same formula), then the list of constituent legislators, which is not law text and is left out.
    s = find(paras, lambda p: p[0] == 'h' and p[1].endswith('Preâmbulo'))
    e = find(paras, lambda p: p[1].startswith('Vista e aprovada pela Assembleia Constituinte'), s)
    a = find(paras, lambda p: p[0] == 'h' and p[1] == 'ANEXO I', e)
    last = max(i for i, p in enumerate(paras) if p[1].startswith('Vista e aprovada pela Assembleia Constituinte'))
    z = last + 1
    while z < len(paras) and paras[z][1].startswith('O Presidente da '):
        z += 1
    units, _ = units_from(paras, s + 1, e, preamble=True)
    ann, _ = units_from(paras, a, z, preamble=False)
    units.update({k: v for k, v in ann.items() if k != 'estrutura'})
    units['formula-final'] = {'label': 'Fórmula de aprovação', 'kind': 'final',
                              'text': '# Fórmula de aprovação\n' + '\n'.join(t for _, t in paras[e:a]) + '\n'}
    return units


def code(slug: str, title_line: str, stop_line: str | None) -> dict:
    src = SOURCES[slug]
    pdf = cached(src['url'])
    paras = paragraphs(page_lines(pdf))
    s = find(paras, lambda p: p[1].upper() == title_line)
    if stop_line:
        e = find(paras, lambda p: p[1].startswith(stop_line), s)
        # step back over the approving law's closing signatures, which the Gazette prints after the code
        while paras[e - 1][1].startswith(('O Presidente', 'Dias dos Santos', 'Lourenço', 'Publique-se',
                                           'Promulgada', 'Vista e aprovada')):
            e -= 1
    else:
        e = len(paras)
        while paras[e - 1][1].startswith(('O Presidente', 'Dias dos Santos', 'Lourenço', 'Publique-se',
                                           'Promulgada', 'Vista e aprovada', '(')):
            e -= 1
    units, _ = units_from(paras, s + 1, e, preamble=False)
    return units


def dump_part(name: str, part: dict) -> None:
    d = HERE / 'corpus.d'
    d.mkdir(exist_ok=True)
    tmp = d / (name + '.json.tmp')
    tmp.write_text(json.dumps(part, ensure_ascii=False, indent=1, sort_keys=False) + '\n', encoding='utf-8',
                   newline='\n')
    os.replace(tmp, d / (name + '.json'))


def main() -> None:
    meta = json.loads((HERE / 'meta.json').read_text(encoding='utf-8'))
    acts = {
        'constituicao': constitution,
        'codigo-penal': lambda: code('codigo-penal', 'CÓDIGO PENAL ANGOLANO', 'Lei n.º 39/20'),
        'codigo-processo-penal': lambda: code('codigo-processo-penal', 'CÓDIGO DO PROCESSO PENAL ANGOLANO', None),
    }
    only = sys.argv[1:] or list(acts)
    for slug in only:
        units = acts[slug]()
        pm = meta['parts'][slug]
        src = SOURCES[slug]
        act = dict(pm['act'])
        act['versions'] = [{**v, 'source_url': src['url'], 'sha256': sha(cached(src['url'])), 'units': units}
                           for v in pm['versions']]
        part = {k: v for k, v in pm.items() if k not in ('act', 'versions', 'file')}
        part['acts'] = [act]
        dump_part(pm['file'], part)
        print(slug, len(units), 'units')


if __name__ == '__main__':
    main()
