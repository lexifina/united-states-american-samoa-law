"""The Constitution of 18 February 2006: parse the Journal officiel texts into units.

    v1  JO numéro spécial, 18 February 2006: the Constitution as promulgated.
    v2  v1 with the replacement articles of Loi n° 11/002 (JO of 1 February 2011), from its promulgation day.
    v3  JO numéro spécial, 5 February 2011: "textes coordonnés" as revised by Loi n° 11/002 of 20 January 2011.

Leganet holds two typesettings that both carry the header of the JO numéro spécial of 5 February 2011:
Droit Public/Constitution.2011.pdf (Word 2007, April 2011) and JO/2011/JOS.05.02.2011.pdf (PDFCreator, August 2012,
titled "Constitution de la RDC _Révisée_"). They differ in punctuation and capitals in 83 units. The Journal officiel's
own site (journalofficiel.cd/textes-phares/constitution, legal_status "in_force") agrees with the first in 78 of them
and with the second in none, so v3 is read from the first. verify_jo.py repeats that comparison.
"""
from __future__ import annotations

import re

from textlib import flat, norm_chars, paragraphs, pdf_text

LEGANET = 'https://www.leganet.be/Legislation'
SRC_2006 = LEGANET + '/JO/2006/JO.18.02.2006.pdf'
SRC_2011 = LEGANET + '/Droit%20Public/Constitution.2011.pdf'
SRC_2011_REPRINT = LEGANET + '/JO/2011/JOS.05.02.2011.pdf'  # not used for text: see the module docstring
JO_SITE = 'https://journalofficiel.cd/textes-phares/constitution'
SRC_LAW_11_002 = LEGANET + '/JO/2011/JOS.01.02.2011.pdf'

HEADER = re.compile(r'^\s*(Journal Officiel\b.*Constitution.*|\d{1,3}|_{3,}|E-mail.*|Sites?\s*:.*|www\..*)\s*$', re.I)
ART = re.compile(r'^\s*Articles?\s+(\d+)(?:er|ère)?\b\s*[,.:]?\s*(.*)$')
STRUCT = re.compile(r'^\s*(TITRE|Chapitre|CHAPITRE|Section|SECTION|Paragraphe|PARAGRAPHE)\s+([0-9IVX]+(?:er|ère|e)?)\s*:?\s*(.*)$')
# a heading that ends on one of these words wraps onto the next line ("... et au" / "Gouvernement.")
HEAD_TAIL = re.compile(r'\b(?:et|ou|de|des|du|la|le|les|au|aux|à|entre)$', re.I)
NOTE = re.compile(r'\((?:modifiée?|révisée?)\s+par l’article.*?\)', re.I | re.S)


def _lines(url: str) -> list[str]:
    text = norm_chars(pdf_text(url))
    lines = [l for l in text.split('\n') if not HEADER.match(l)]
    return lines


def parse(url: str) -> dict[str, dict]:
    lines = _lines(url)
    start = next(i for i, l in enumerate(lines) if l.strip().startswith('Le Sénat a proposé'))
    end = next(i for i in range(start, len(lines)) if re.match(r'^\s*(Fait à Kinshasa|Joseph KABILA)', lines[i]))
    body = lines[start:end]
    # join the annotation that follows an article or heading onto one line before splitting, then drop it
    joined = '\n'.join(body)
    joined = NOTE.sub('', joined)
    body = joined.split('\n')

    units: dict[str, dict] = {}
    structure: list[str] = []
    key, label, buf = 'formule', 'Formule de promulgation', []
    kind = 'formula'

    def flush():
        if key is None:
            return
        paras = paragraphs(buf)
        if not paras:
            return
        heading = f'# {label}'
        units[key] = {'label': label, 'kind': kind, 'text': '\n'.join([heading] + paras) + '\n'}

    i = 0
    while i < len(body):
        l = body[i]
        s = l.strip()
        m = ART.match(l)
        if s == 'PREAMBULE':
            flush()
            key, label, kind, buf = 'preambule', 'Préambule', 'preamble', []
        elif m and (m.group(2).strip() == ''):
            flush()
            n = int(m.group(1))
            key, label, kind, buf = f'art-{n:03d}', 'Article 1er' if n == 1 else f'Article {n}', 'art', []
        elif STRUCT.match(l) and len(s) < 160:
            # a heading: continuation lines are indented upper-case (TITRE) or lower-case words with no full stop
            head = s
            while i + 1 < len(body):
                nxt = body[i + 1].strip()
                if not nxt or ART.match(body[i + 1]) or STRUCT.match(body[i + 1]):
                    break
                if (head.endswith('entre le pouvoir') or HEAD_TAIL.search(head)
                        or (head.isupper() and nxt.isupper())):
                    head = head + ' ' + nxt
                    i += 1
                else:
                    break
            structure.append(re.sub(r'\s+', ' ', head).replace(' :', ' :'))
        else:
            buf.append(l)
        i += 1
    flush()
    units['structure'] = {'label': 'Intitulés (titres, chapitres, sections, paragraphes)', 'kind': 'structure',
                          'text': '# Intitulés\n' + '\n'.join(_tidy_heading(h) for h in structure) + '\n'}
    return units


def _tidy_heading(h: str) -> str:
    h = re.sub(r'\s*:\s*', ' : ', h, count=1)
    return re.sub(r'\s+', ' ', h).strip()


def same(a: dict, b: dict) -> bool:
    return flat(a['text']) == flat(b['text'])


GARBLED = re.compile(r'[\u0340-\u03ff]')
AMENDED = (71, 110, 126, 149, 197, 198, 218, 226)
OLD_P5 = 'Paragraphe 5 : De la fin du mandat de député national ou de sénateur'


def parse_law_11_002() -> tuple[dict[str, dict], str]:
    """The replacement articles of Loi n° 11/002 (art. 1er) and the new heading of § 5 (art. 2), from the JO of
    1 February 2011. MuPDF reads the two columns in order. The exposé des motifs on
    page 1 has a broken font encoding; its lines are dropped (they are not part of the operative text)."""
    import fitz  # PyMuPDF keeps line-end hyphens; pdftotext's raw mode drops them (Kasaï-Occidental)
    from fetch import cache_path as cp
    doc = fitz.open(stream=cp(SRC_LAW_11_002).read_bytes(), filetype='pdf')
    raw = '\n'.join(page.get_text() for page in doc)
    text = norm_chars(raw)
    lines = [l for l in text.split('\n') if not GARBLED.search(l) and not re.fullmatch(r'\s*\d{1,2}\s*', l)
             and not l.strip().startswith('Dans cette perspective, la présente révision')]
    body = '\n'.join(lines)
    a = body.index('sont modifiés comme suit :') + len('sont modifiés comme suit :')
    b = re.search(r'\nArticle 2\s*\n', body).start()
    ops = body[a:b].strip()
    ops = re.sub(r'^«\s*', '', ops)
    ops = re.sub(r'\s*»\s*\.?\s*$', '', ops)
    parts = re.split(r'(?:^|\n|\s)Article (\d+) :\s*', ops)
    out: dict[str, dict] = {}
    for num, chunk in zip(parts[1::2], parts[2::2]):
        n = int(num)
        paras = paragraphs(chunk.split('\n'))
        label = f'Article {n}'
        out[f'art-{n:03d}'] = {'label': label, 'kind': 'art', 'text': '\n'.join([f'# {label}'] + paras) + '\n'}
    assert sorted(out) == [f'art-{n:03d}' for n in AMENDED], sorted(out)
    m = re.search(r'est modifié comme suit :\s*(Paragraphe 5 : .*?)\.?\s*\nArticle 3', body[b:], re.S)
    return out, re.sub(r'\s+', ' ', m.group(1)).strip()


def versions() -> list[dict]:
    """v1 as promulgated; v2 = v1 + Loi 11/002 on its promulgation day; v3 = the JO's coordinated text."""
    from textlib import sha256
    v1 = parse(SRC_2006)
    law, p5 = parse_law_11_002()
    v2 = {k: dict(u) for k, u in v1.items()}
    v2.update(law)
    st = v2['structure']['text']
    assert OLD_P5 in st, 'old § 5 heading not found'
    v2['structure'] = dict(v2['structure'], text=st.replace(OLD_P5, _tidy_heading(p5)))
    v3 = parse(SRC_2011)
    # where the coordinated text says the same thing with other line breaks, keep the earlier lines
    for k, u in v3.items():
        if k in v2 and same(u, v2[k]):
            v3[k] = v2[k]
    out = [
        {'from': '2006-02-18', 'source_url': SRC_2006, 'sha256': sha256(SRC_2006), 'units': v1,
         'credits': {}},
        {'from': '2011-01-20', 'source_url': SRC_LAW_11_002, 'sha256': sha256(SRC_LAW_11_002), 'units': v2,
         'credits': {k: ['loi-11-002'] for k in sorted(v2) if v2[k] != v1.get(k)}},
    ]
    changed = sorted(k for k in set(v2) | set(v3) if v2.get(k) != v3.get(k))
    out.append({'from': '2011-02-05', 'source_url': SRC_2011, 'sha256': sha256(SRC_2011), 'units': v3,
                'credits': {},
                'note': ('Textes coordonnés published by the Journal officiel (numéro spécial, 5 February 2011). '
                         f'They differ from the promulgated wording in {len(changed)} units (punctuation, capitals, '
                         'spelling and a few small words such as articles and conjunctions); no law made these '
                         'differences, so they are committed by the publisher as unexplained. The Journal officiel '
                         'lists this text as the one in force.')})
    return out


if __name__ == '__main__':
    import sys
    v1, v2 = parse(SRC_2006), parse(SRC_2011)
    print(len(v1), len(v2))
    missing = [f'art-{n:03d}' for n in range(1, 230) if f'art-{n:03d}' not in v1 or f'art-{n:03d}' not in v2]
    print('missing', missing)
    diff = [k for k in sorted(set(v1) | set(v2)) if k not in v1 or k not in v2 or not same(v1[k], v2[k])]
    print('differ', diff)
    if '-v' in sys.argv:
        import difflib
        for k in diff:
            a = v1.get(k, {}).get('text', '').splitlines()
            b = v2.get(k, {}).get('text', '').splitlines()
            print('\n'.join(difflib.unified_diff(a, b, k, k, lineterm='', n=0)))
