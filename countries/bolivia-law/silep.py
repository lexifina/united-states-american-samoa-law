"""Read one SILEP `norma/<id>/ley_actualizada` page (an Internet Archive raw capture) into units.

SILEP (Sistema de Información Legal del Estado Plurinacional, Vicepresidencia) shows each act as its
consolidated text ("Texto Ordenado"), one `div.color-bloque` per article, with headings between the
blocks. A modified, inserted or repealed article carries a dropdown whose `h4.titulo-mensaje` names the
LAST law that affected it ("Modificado por Ley Nº 1768 de ...", "Derogado por ley Nro. 060 de 25/11/2010",
"Insertado por ley Nro. 400 - ...", "Declarado Inconstitucional por SCP 206 de 05/02/2014").

parse(html) -> dict(meta, items) where items is the document order of
    ('heading', {'paras', 'mods'}) and ('block', {'id', 'paras', 'mods'}).
Only the cached bytes are read; nothing here touches the network.
"""
from __future__ import annotations

import html as _html
import re
from html.parser import HTMLParser

BLOCK_TAGS = {'div', 'p', 'br', 'li', 'tr', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'table', 'ul', 'ol'}


class _Text(HTMLParser):
    """Paragraphs of an HTML fragment: block-level tags break paragraphs; everything else is inline."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.paras: list[str] = []
        self.cur: list[str] = []

    def _flush(self) -> None:
        s = norm(''.join(self.cur))
        if s:
            self.paras.append(s)
        self.cur = []

    def handle_starttag(self, tag, attrs):
        if tag.lower() in BLOCK_TAGS:
            self._flush()

    def handle_endtag(self, tag):
        if tag.lower() in BLOCK_TAGS:
            self._flush()

    def handle_data(self, data):
        self.cur.append(data)

    def close(self):
        super().close()
        self._flush()


def norm(s: str) -> str:
    s = s.replace(' ', ' ').replace('​', '').replace('﻿', '').replace('\r', ' ').replace('\n', ' ').replace('\t', ' ')
    s = s.replace('“', '"').replace('”', '"').replace('„', '"').replace('«', '"').replace('»', '"')
    s = s.replace('‘', "'").replace('’', "'").replace('–', '-').replace('—', '-').replace('‑', '-')
    s = re.sub(r' {2,}', ' ', s).strip()
    return s


def paras(fragment: str) -> list[str]:
    p = _Text()
    p.feed(fragment)
    p.close()
    return p.paras


META = {
    'numero': r'Número de Ley :</b>([^<]*)<',
    'promulgacion': r'Fecha Promulgación : &nbsp;</b><span>([^<]*)<',
    'titulo': r'Titulo : </b>([^<]*)<',
    'estado': r'Estado:</b>\s*&nbsp;<span[^>]*>([^<]*)<',
    'gaceta': r'Nro Gaceta : </b>([^<]*)<',
}

SEG = '<!--grupo vigente en documento-->'


def parse(raw: bytes) -> dict:
    t = raw.decode('utf-8')
    if '<p class="fuente">' not in t:
        raise ValueError('truncated capture: no closing "Fuente" line')
    meta = {k: norm(_html.unescape(m.group(1))) if (m := re.search(rx, t)) else None for k, rx in META.items()}
    body = t[t.index('<div class="ley">'):t.index('<p class="fuente">')]
    segs = body.split(SEG)
    items: list[tuple[str, dict]] = []
    for seg in segs[1:]:
        seg = seg.split('<!-- grupo abrogados-->')[0]
        mods = [norm(_html.unescape(m)) for m in re.findall(r'<h4 class="titulo-mensaje">(.*?)</h4>', seg, re.S)]
        seg_nomods = re.sub(r'<div class="btn-group">.*?</ul></div>', '', seg, flags=re.S)
        m = re.search(r'<div class="color-bloque" id="(\d+)">', seg_nomods)
        if m:
            rest = seg_nomods[m.end():]
            rest = re.sub(r'<div data-url=[^>]*></div>', '', rest, count=1)
            rest = re.sub(r'<!--.*?-->', '', rest, flags=re.S)
            ps = paras(rest)
            items.append(('block', {'id': m.group(1), 'paras': ps, 'mods': mods}))
        else:
            frag = re.sub(r'<!--.*?-->', '', seg_nomods, flags=re.S)
            ps = paras(frag)
            if ps:
                items.append(('heading', {'paras': ps, 'mods': mods}))
            elif mods:
                raise ValueError(f'modification note with no text: {mods}')
    return {'meta': meta, 'items': items}


MOD_RX = [
    ('modificado', re.compile(r'^Modificado por Ley N[º°o]\s*(\d+)\s+de\s+(.*)$')),
    ('derogado', re.compile(r'^Derogado por ley Nro\.\s*(\d+)\s+de\s+(\d\d)/(\d\d)/(\d{4})$')),
    ('insertado', re.compile(r'^Insertado por ley Nro\.\s*(\d+)\s*-\s*(.*)$')),
    ('scp', re.compile(r'^Declarado Inconstitucional por SCP\s*(\d+)\s+de\s+(\d\d)/(\d\d)/(\d{4})$')),
]
MONTHS = {m: i + 1 for i, m in enumerate('Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec'.split())}


def mod_info(msg: str) -> dict:
    """{'kind', 'number', 'date' (ISO promulgation date, or None), 'title' (or None)} for one SILEP note."""
    for kind, rx in MOD_RX:
        m = rx.match(msg)
        if not m:
            continue
        if kind == 'modificado':
            d = re.search(r'([A-Z][a-z]{2}) (\d\d) (\d{4})', m.group(2))
            date = f'{d.group(3)}-{MONTHS[d.group(1)]:02d}-{d.group(2)}' if d else None
            return {'kind': kind, 'number': int(m.group(1)), 'date': date, 'title': None}
        if kind in ('derogado', 'scp'):
            return {'kind': kind, 'number': int(m.group(1)), 'date': f'{m.group(4)}-{m.group(3)}-{m.group(2)}', 'title': None}
        return {'kind': kind, 'number': int(m.group(1)), 'date': None, 'title': m.group(2).strip()}
    raise ValueError(f'unknown SILEP note: {msg!r}')
