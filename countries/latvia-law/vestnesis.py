"""Read an act as first published in the official gazette (www.vestnesis.lv/ta/id/<id>) into likumi.py's units.

Used where likumi.lv's base version ("Pamata" redakcija) has no archived capture: the gazette publication is the act
as enacted, the official text. The 1990s pages are plain paragraphs: part headings ("VISPĀRĪGĀ DAĻA"), chapter
headings ("I nodaļa" + title), articles ("1.pants. Heading" + paragraphs), "Pārejas noteikumi" with numbered items,
then the adoption line, the President's signature and place and date.
"""
from __future__ import annotations

import html
import re

import likumi


def parse_original(raw: bytes, title: str) -> dict:
    # the 1998 markup nests <p> and <font> badly (an article heading can fall outside its <p>), so paragraphs are
    # cut at every <p> tag in the raw HTML instead of by a parser's tree
    doc = raw.decode('utf-8', 'replace')
    doc = re.sub(r'<script.*?</script>|<style.*?</style>', ' ', doc, flags=re.S | re.I)
    paras = []
    for chunk in re.split(r'<(?:p|h[1-6])(?=[\s>])[^>]*>', doc, flags=re.I):
        t = likumi.norm(html.unescape(re.sub(r'<[^>]+>', ' ', chunk)))
        if t:
            paras.append(t)
    start = next(i for i, p in enumerate(paras) if p == title)  # the act's title line opens the text
    paras = paras[start + 1:]
    units, order, used = {}, [], set()
    cur = None
    section = None

    def open_unit(key, label, kind, first):
        nonlocal cur
        cur = {'label': label, 'kind': kind, 'lines': [first]}
        units[key] = cur
        order.append(key)
        used.add(key)

    i = 0
    while i < len(paras):
        line = paras[i]
        low = line.lower()
        if line.startswith('Tiesību aktu un oficiālo paziņojumu oficiālā publikācija') or line.startswith('Izdruka no oficiālā izdevuma'):
            break
        m_ch = re.fullmatch(r'([IVXLC]+)\s*nodaļa', line)
        m_ch2 = re.fullmatch(r'([IVXLC]+\s*nodaļa)\s+(\S.*)', line)
        m_art = re.match(r'(\d+)\.\s*pants\.', line)
        if low in ('vispārīgā daļa', 'sevišķā daļa', 'vispārējā daļa'):
            open_unit(likumi.heading_key(line, used), line, 'heading', line)
            cur = None
        elif m_ch:
            # chapter number, then its title over one or more paragraphs (appended below until the next unit)
            open_unit(likumi.heading_key(line, used), line, 'heading', line)
        elif m_ch2:
            # "IX nodaļa Noziegumi pret ..." in one paragraph: number and title are separate lines, as on likumi.lv
            open_unit(likumi.heading_key(line, used), m_ch2.group(1), 'heading', m_ch2.group(1))
            cur['lines'].append(m_ch2.group(2))
        elif low.startswith('pārejas noteikumi'):
            open_unit('parejas-noteikumi', line, 'heading', line)
            cur = None
            section = 'pn'
        elif m_art and section is None:
            open_unit(likumi.art_key(m_art.group(1)), f'{m_art.group(1)}. pants', 'art', line)
        elif section == 'pn' and re.match(r'(\d+)\.\s', line):
            n = re.match(r'(\d+)\.\s', line).group(1)
            open_unit(likumi.art_key(n, 'parejas-noteikumi'), f'Pārejas noteikumu {n}. punkts', 'transitional', line)
        elif line.startswith('Likums stājas spēkā') and section == 'pn':
            # the act's own in-force clause after the transitional provisions: likumi.lv shows it with the adoption line
            open_unit('zz-pienemts', 'Pieņemšanas ziņas', 'enactment', line)
        elif line.startswith('Likums Saeimā pieņemts'):
            if 'zz-pienemts' in units:
                units['zz-pienemts']['lines'].append(line)
            else:
                open_unit('zz-pienemts', 'Pieņemšanas ziņas', 'enactment', line)
            cur = None
        elif line.startswith('Valsts prezidents'):
            open_unit('zz-paraksti', 'Paraksti', 'signatures', line)
            cur = None
        elif line.startswith('Rīgā '):
            open_unit('zz-vieta-datums', 'Izsludināšanas vieta un datums', 'enactment', line)
            cur = None
        elif cur is not None:
            cur['lines'].append(line)
        else:
            raise ValueError(f'unplaced paragraph: {line[:80]}')
        i += 1
    out = {k: {'label': u['label'], 'kind': u['kind'], 'text': '\n'.join(u['lines']) + '\n', 'events': [],
               'parent': None} for k, u in units.items()}
    return {'version': None, 'units': out, 'removed': {}, 'order': order}
