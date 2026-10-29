"""The 1992 Constitution: split a text (e-TAR original, e-TAR consolidated edition, or the Seimas lrs.lt page) into
units, and replay the amending laws whose consolidated edition no archive holds."""
import re

ROMAN = {r: i for i, r in enumerate(
    'I II III IV V VI VII VIII IX X XI XII XIII XIV XV'.split(), 1)}
ART = re.compile(r'^(\d{1,3}) straipsnis$')
SKIRSNIS = re.compile(r'^([IVX]+) SKIRSNIS$')
NOTE_HEAD = re.compile(r'^((Straipsnio|Straipsnio dalies|Straipsnio punkto|Preambulės) (pakeitim|papildym)\w*'
                       r'|(Papildyta|Pakeista|Išbraukta) straipsnio (dalimi|punktu|dalis|punktas)\w*)[^:]*:', re.I)
NOTE_CONT = re.compile(r'^(Nr\. |\d{4}-\d{2}-\d{2}, (Žin|skelbtas|paskelbta)|Lietuvos Respublikos (Konstitucinis Teismas|Seimas), '
                       r'(Nutarimas|Įstatymas)$|Lietuvos Respublikos Konstitucinio Teismo pirmininkas, Pranešimas$)')
LAWNO = re.compile(r'Nr\. ([IVX]+-\d+)')
TAR_NOTE = 'TAR pastaba.'
REFERENDUM_WORDS = 'Lietuvos Respublikos piliečių priimta 1992 m. spalio 25 d. referendume'


def split(paras: list[str], kind: str) -> tuple[dict, dict]:
    """Units {key: {'label','kind','text'}} and per-unit amendment notes {key: [law numbers]} (consolidated texts
    print them after each article; the original has none). `kind` is 'tar' or 'lrs'."""
    # the body starts at the referendum line above the preamble (the title lines are typeset differently by each
    # publisher and are carried by the act's title instead)
    # (the 2006 lrs.lt page prints it unbracketed, run on with its publication note, so it is matched by its words)
    # (before 2008 it is split over two lines, so there the body is taken from the preamble's first words)
    start = next((i for i, p in enumerate(paras) if REFERENDUM_WORDS in p), None)
    if start is None:
        start = paras.index('LIETUVIŲ TAUTA') - 1
    units, notes, order = {}, {}, []
    cur = None
    buf: list[str] = []
    in_note = False

    def flush():
        nonlocal buf
        if cur is not None:
            units[cur]['lines'] = buf
        buf = []

    def new(key, label, kind_, head):
        nonlocal cur, in_note
        flush()
        cur = key
        in_note = False
        units[key] = {'label': label, 'kind': kind_, 'head': head}
        order.append(key)
        notes.setdefault(key, [])

    i = start + 1
    n = len(paras)
    new('preambule', 'Preambulė', 'preamble', '# Preambulė')
    buf.append(f'({REFERENDUM_WORDS})')
    while i < n:
        p = paras[i]
        if p == 'LIETUVOS RESPUBLIKOS' and i + 1 < n and paras[i + 1].startswith('AUKŠČIAUSIOSIOS TARYBOS'):
            break  # the 1992 signature block; the consolidated text's change list follows it
        if p.startswith('LIETUVOS RESPUBLIKOS AUKŠČIAUSIOSIOS TARYBOS PIRMININKAS'):
            break
        m = SKIRSNIS.match(p)
        if m and i + 1 < n:
            num = ROMAN[m.group(1)]
            new(f'skirsnis-{num:02d}', f'{m.group(1)} skirsnis', 'chapter', f'# {p}')
            buf.append(paras[i + 1])
            i += 2
            continue
        if p == 'BAIGIAMIEJI NUOSTATAI':
            new('skirsnis-15', 'Baigiamieji nuostatai', 'chapter', f'# {p}')
            i += 1
            continue
        m = ART.match(p)
        if m:
            num = int(m.group(1))
            new(f'art-{num:03d}', f'{num} straipsnis', 'art', f'# {p}')
            i += 1
            continue
        if NOTE_HEAD.match(p):
            in_note = True
            rest = p.split(':', 1)[1] if ':' in p else ''
            notes[cur] += LAWNO.findall(rest)
            i += 1
            continue
        if p.startswith(TAR_NOTE) or p.startswith('Pastaba.'):
            in_note = True
            i += 1
            continue
        if in_note:
            if NOTE_CONT.match(p):
                notes[cur] += LAWNO.findall(p)
                i += 1
                continue
            in_note = False
        buf.append(p)
        i += 1
    flush()
    out = {}
    for k in order:
        u = units[k]
        lines = u['lines']
        if k == 'preambule':  # TAR sets the closing word on its own line, lrs.lt on the line before
            joined = []
            for l in lines:
                if l in ('KONSTITUCIJĄ', 'KONSTITUCIJA') and joined:
                    joined[-1] += ' ' + l
                else:
                    joined.append(l)
            lines = joined
        text = '\n'.join(([u['head']] if u['head'] else []) + lines) + '\n'
        out[k] = {'label': u['label'], 'kind': u['kind'], 'text': text}
    return out, notes


def body(unit: dict) -> list[str]:
    """The paragraphs of a unit without its heading line."""
    lines = unit['text'].rstrip('\n').split('\n')
    return lines[1:] if lines[0].startswith('# ') else lines


def make(key: str, label: str, kind: str, head: str | None, lines: list[str]) -> dict:
    return {'label': label, 'kind': kind, 'text': '\n'.join(([head] if head else []) + lines) + '\n'}


def quoted(paras: list[str]) -> list[list[str]]:
    """The quoted blocks of an amending law: runs of paragraphs from one opening „ to its closing “."""
    out, cur = [], None
    for p in paras:
        if cur is None and p.startswith('„'):
            cur = [p[1:]]
        elif cur is not None:
            cur.append(p)
        else:
            continue
        if cur and cur[-1].endswith('“'):
            cur[-1] = cur[-1][:-1]
            out.append(cur)
            cur = None
    return out
