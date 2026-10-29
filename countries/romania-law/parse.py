"""Parse Romania's Phase 1 acts from the cached Portal Legislativ pages into corpus.d parts.

Reads only `.cache/` (archive.org `id_` captures of legislatie.just.ro, fetched by fetch.py through
gitlaw_common/wayback.py) and `forms.json` (the document id, date and capture timestamp of every form). Writes
`corpus.d/10-constitutia.json`, `corpus.d/20-codul-civil.json` and `corpus.d/30-codul-penal.json`, atomically.

On the portal every consolidated form ("forma consolidată") of an act is its own page, and every provision an
amendment touched carries a blue note: "(la 01-02-2014, Alin. (3) al art. 9 a fost modificat de pct. 1 al art. 245
din LEGEA nr. 187 din 24 octombrie 2012, publicată în MONITORUL OFICIAL nr. 757 ...)". The "la" date is the day the
change took effect, and the link names the amending act: that is where every credit comes from. A changed article
with no note dated after the previous version is left uncredited (the builder commits it as the publisher's).

    python -X utf8 scripts/romania-law/parse.py            # deterministic: the same cache gives the same bytes
"""
from __future__ import annotations

import hashlib
import html
import json
import os
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

HERE = Path(__file__).resolve().parent
CACHE = HERE / '.cache'
OUT = HERE / 'corpus.d'
PORTAL = 'https://legislatie.just.ro/Public/'
RETRIEVED = '2026-10-28'

MONTHS = {m: i + 1 for i, m in enumerate(['ianuarie', 'februarie', 'martie', 'aprilie', 'mai', 'iunie', 'iulie',
                                           'august', 'septembrie', 'octombrie', 'noiembrie', 'decembrie'])}

# The acts. `forms` come from forms.json; `skip` lists form ids that are not used, with the reason in DECISIONS.
ACTS = {
    'constitutia': {
        'part': '10-constitutia', 'short': 'Constituția', 'pad': 3,
        'title': 'Constituția României',
        'url': PORTAL + 'DetaliiDocument/47355',
        'in_force': '1991-12-08', 'first_law': 'constitutia-1991', 'skip': set(),
        'base_note': 'The text adopted on 21 November 1991 (Monitorul Oficial nr. 233), in force on its approval by '
                     'the national referendum of 8 December 1991.',
        # the republished text (Monitorul Oficial nr. 767 of 31 October 2003) is the revision in force on 29 October
        'form_day': {'47355': '2003-10-29'},
        'form_note': {'47355': 'The text as republished by the Legislative Council in Monitorul Oficial nr. 767 of '
                               '31 October 2003, with updated names and renumbered articles; the revision it carries '
                               'took effect on 29 October 2003.'},
        'first_form_law': 'legea-429-2003',
    },
    'codul-civil': {
        'part': '20-codul-civil', 'short': 'Codul civil', 'pad': 4,
        'title': 'Codul civil (Legea nr. 287/2009)',
        'url': PORTAL + 'DetaliiDocument/109884',
        'in_force': '2011-10-01', 'first_law': 'legea-287-2009',
        # 130143 is the republication's id, but its capture shows the current form (03.05.2026): used as a cross-check
        'skip': {'130143'},
        'base_note': 'The code as published in Monitorul Oficial nr. 511 of 24 July 2009. It never applied in this '
                     'form: Legea nr. 71/2011 amended it before it took effect on 1 October 2011, and the next '
                     'version, the same day, is the text that took effect.',
        'form_note': {'137240': 'The code as republished in Monitorul Oficial nr. 505 of 15 July 2011, the text that '
                                'took effect on 1 October 2011.'},
        'first_form_law': 'legea-71-2011',
        'cross_check': {'page': '130143', 'capture': '20260707145226'},
    },
    'codul-penal': {
        'part': '30-codul-penal', 'short': 'Codul penal', 'pad': 3,
        'title': 'Codul penal (Legea nr. 286/2009)',
        'url': PORTAL + 'DetaliiDocument/109855',
        'in_force': '2014-02-01', 'first_law': 'legea-286-2009',
        # forms dated before the code took effect (it was amended before 1 February 2014)
        'skip': {'136456', '137246'},
        'base_note': 'The code as published in Monitorul Oficial nr. 510 of 24 July 2009. It never applied in this '
                     'form: it was amended before it took effect on 1 February 2014, and the next version, the same '
                     'day, is the text that took effect.',
        'form_note': {},
        'first_form_law': None,
    },
}
PHASE1 = ('constitutia', 'codul-civil', 'codul-penal')

# Phase 2 (gitlaw-RO-2, 2026-10-29): one corpus.d part each. `republished` maps a republication form to the act that
# ordered it: a republication renumbers and rewrites without per-article notes, so its unexplained changes are
# credited to that act, as the portal's note on the republished text does.
ACTS.update({
    'codul-procedura-civila': {
        'part': '40-codul-procedura-civila', 'short': 'Codul de procedură civilă', 'pad': 4,
        'title': 'Codul de procedură civilă (Legea nr. 134/2010)',
        'url': PORTAL + 'DetaliiDocument/140271',
        'in_force': '2013-02-15', 'first_law': 'legea-134-2010', 'skip': set(),
        'base_note': 'The code as published in Monitorul Oficial nr. 485 of 15 July 2010. It never applied in this '
                     'form: Legea nr. 76/2012 amended it before it took effect on 15 February 2013 and ordered its '
                     'republication (Monitorul Oficial nr. 545 of 3 August 2012); the next version, the same day, is '
                     'the republished text that took effect.',
        'form_note': {},
        'first_form_law': 'legea-76-2012',
        # "Republicat în temeiul art. XIV din Legea nr. 138/2014" (the portal's note on the act)
        'republished': {'167140': 'legea-138-2014'},
    },
    'codul-procedura-penala': {
        'part': '50-codul-procedura-penala', 'short': 'Codul de procedură penală', 'pad': 3,
        'title': 'Codul de procedură penală (Legea nr. 135/2010)',
        'url': PORTAL + 'DetaliiDocument/120611',
        'in_force': '2014-02-01', 'first_law': 'legea-135-2010', 'skip': set(),
        'base_note': 'The code as published in Monitorul Oficial nr. 486 of 15 July 2010. It never applied in this '
                     'form: it was amended before it took effect on 1 February 2014 (mainly by Legea nr. 255/2013), '
                     'and the next version, the same day, is the text that took effect.',
        'form_note': {},
        'first_form_law': 'legea-255-2013',
        'republished': {},
    },
    'codul-muncii': {
        'part': '60-codul-muncii', 'short': 'Codul muncii', 'pad': 3,
        'title': 'Codul muncii (Legea nr. 53/2003)',
        'url': PORTAL + 'DetaliiDocument/41627',
        'in_force': '2003-03-01', 'first_law': 'legea-53-2003', 'skip': set(),
        'base_note': 'The code as published in Monitorul Oficial nr. 72 of 5 February 2003, in force on 1 March 2003 '
                     '(art. 298 alin. (1)).',
        'form_note': {'128647': 'The code as republished in Monitorul Oficial nr. 345 of 18 May 2011 under art. V of '
                                'Legea nr. 40/2011, with renumbered articles.'},
        'first_form_law': None,
        # "Republicată în temeiul art. V din Legea nr. 40/2011 ..., dându-se textelor o nouă numerotare"
        'republished': {'128647': 'legea-40-2011'},
        # the code has no marginal titles: a short line some forms print before an article is a chapter's name
        'titles': False,
    },
    'legea-190-2018': {
        'part': '70-legea-190-2018', 'short': 'Legea nr. 190/2018', 'pad': 3,
        'title': 'Legea nr. 190/2018 privind măsuri de punere în aplicare a Regulamentului (UE) 2016/679 '
                 '(Regulamentul general privind protecția datelor)',
        'url': PORTAL + 'DetaliiDocument/203151',
        'in_force': '2018-07-31', 'first_law': 'legea-190-2018', 'skip': set(),
        'base_note': 'The law as published in Monitorul Oficial nr. 651 of 26 July 2018.',
        'form_note': {},
        'first_form_law': None,
        'republished': {},
    },
})
PHASE2 = ('codul-procedura-civila', 'codul-procedura-penala', 'codul-muncii', 'legea-190-2018')

# Laws that no note names but the corpus needs (the acts themselves, and the 2003 revision).
BASE_LAWS = {
    'constitutia-1991': {
        'label': 'Constituția din 1991', 'kind': 'referendum',
        'title': 'Constituția României, adoptată de Adunarea Constituantă la 21 noiembrie 1991 și aprobată prin '
                 'referendumul național din 8 decembrie 1991',
        'enacted': '1991-11-21', 'published': '1991-11-21', 'url': PORTAL + 'DetaliiDocumentAfis/1413',
    },
    'legea-429-2003': {
        'label': 'Legea nr. 429/2003', 'kind': 'referendum',
        'title': 'Legea de revizuire a Constituției României nr. 429/2003, aprobată prin referendumul național din '
                 '18-19 octombrie 2003',
        'enacted': '2003-10-19', 'published': '2003-10-29', 'url': PORTAL + 'DetaliiDocumentAfis/47259',
        'note': 'Approved by the national referendum of 18-19 October 2003, in force on 29 October 2003, when the '
                'Constitutional Court\'s confirmation of the result was published (Monitorul Oficial nr. 758). The '
                'Legislative Council then republished the Constitution with updated names and renumbered articles '
                '(art. 152 became art. 156), as the revision required, so articles whose number moved change on this '
                'day too. The portal\'s note on the republished text credits it to this law.',
    },
    'legea-71-2011': {
        'label': 'Legea nr. 71/2011', 'kind': 'law',
        'title': 'Legea nr. 71/2011 pentru punerea în aplicare a Legii nr. 287/2009 privind Codul civil',
        'enacted': None, 'published': '2011-06-10',  # the cached pages give no date of adoption 'url': PORTAL + 'DetaliiDocumentAfis/129268',
        'note': 'It amended the Civil Code before the code took effect and ordered its republication (art. 218); the '
                'code was republished in Monitorul Oficial nr. 505 of 15 July 2011 and took effect on 1 October 2011 '
                '(art. 220). The portal credits the republished text to this law and to two '
                'rectifications (Monitorul Oficial nr. 427 and 489 of 2011), which it does not tell apart, so every '
                'change on this day that no article note explains is credited here.',
    },
    'legea-287-2009': {
        'label': 'Legea nr. 287/2009', 'kind': 'law', 'title': 'Legea nr. 287/2009 privind Codul civil',
        'enacted': '2009-07-17', 'published': '2009-07-24', 'url': PORTAL + 'DetaliiDocumentAfis/109884',
    },
    'legea-286-2009': {
        'label': 'Legea nr. 286/2009', 'kind': 'law', 'title': 'Legea nr. 286/2009 privind Codul penal',
        'enacted': '2009-07-17', 'published': '2009-07-24', 'url': PORTAL + 'DetaliiDocumentAfis/109855',
    },
    # Phase 2: dates from each act's own heading on the portal ("LEGE nr. 134 din 1 iulie 2010 ... Publicat în
    # MONITORUL OFICIAL nr. 485 din 15 iulie 2010"); checked in parse by base_heading().
    'legea-134-2010': {
        'label': 'Legea nr. 134/2010', 'kind': 'law', 'title': 'Legea nr. 134/2010 privind Codul de procedură civilă',
        'enacted': '2010-07-01', 'published': '2010-07-15', 'url': PORTAL + 'DetaliiDocumentAfis/120650',
    },
    'legea-135-2010': {
        'label': 'Legea nr. 135/2010', 'kind': 'law', 'title': 'Legea nr. 135/2010 privind Codul de procedură penală',
        'enacted': '2010-07-01', 'published': '2010-07-15', 'url': PORTAL + 'DetaliiDocumentAfis/120611',
    },
    'legea-76-2012': {
        'label': 'Legea nr. 76/2012', 'kind': 'law',
        'title': 'Legea nr. 76/2012 pentru punerea în aplicare a Legii nr. 134/2010 privind Codul de procedură civilă, '
                 'publicată în Monitorul Oficial al României, Partea I, nr. 365 din 30 mai 2012',
        'enacted': None, 'published': '2012-05-30', 'url': None,  # the cached pages give no date of adoption
        'note': 'It amended the Code of Civil Procedure before the code took effect, ordered its republication '
                '(Monitorul Oficial nr. 545 of 3 August 2012) and set its entry into force on 15 February 2013 (art. 81, '
                'as amended). Changes on that day that no article note explains are credited here.',
    },
    'legea-53-2003': {
        'label': 'Legea nr. 53/2003', 'kind': 'law', 'title': 'Legea nr. 53/2003 - Codul muncii',
        'enacted': '2003-01-24', 'published': '2003-02-05', 'url': PORTAL + 'DetaliiDocumentAfis/41627',
    },
    'legea-190-2018': {
        'label': 'Legea nr. 190/2018', 'kind': 'law',
        'title': 'Legea nr. 190/2018 privind măsuri de punere în aplicare a Regulamentului (UE) 2016/679 al '
                 'Parlamentului European și al Consiliului din 27 aprilie 2016 privind protecția persoanelor fizice în '
                 'ceea ce privește prelucrarea datelor cu caracter personal și privind libera circulație a acestor date '
                 'și de abrogare a Directivei 95/46/CE (Regulamentul general privind protecția datelor)',
        'enacted': '2018-07-18', 'published': '2018-07-26', 'url': PORTAL + 'DetaliiDocumentAfis/203151',
    },
}
# The acts a first in-force form or a republication is credited to when no article note names another act: taken from
# the notes themselves (law_of), so their labels, titles and dates are the portal's.
SEED_FROM_NOTES = ('legea-76-2012', 'legea-255-2013')

KINDS = [  # (pattern in the note's link text, key prefix, label prefix, kind)
    ('ORDONANȚA DE URGENȚĂ', 'oug', 'OUG nr.', 'decree'),
    ('ORDONANȚA', 'og', 'OG nr.', 'decree'),
    ('LEGEA', 'legea', 'Legea nr.', 'law'),
    ('DECIZIA', 'dcc', 'Decizia CCR nr.', 'court'),
]

# ------------------------------------------------------------------ HTML tree


class Node:
    __slots__ = ('tag', 'cls', 'style', 'href', 'kids')

    def __init__(self, tag, attrs):
        a = dict(attrs)
        self.tag, self.cls, self.style, self.href = tag, a.get('class') or '', a.get('style') or '', a.get('href') or ''
        self.kids = []


VOID = {'br', 'img', 'input', 'meta', 'link', 'hr', 'col', 'area', 'base', 'wbr', 'source'}


class Tree(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = Node('root', [])
        self.stack = [self.root]

    def handle_starttag(self, tag, attrs):
        n = Node(tag, attrs)
        self.stack[-1].kids.append(n)
        if tag not in VOID:
            self.stack.append(n)

    def handle_startendtag(self, tag, attrs):
        self.stack[-1].kids.append(Node(tag, attrs))

    def handle_endtag(self, tag):
        for i in range(len(self.stack) - 1, 0, -1):
            if self.stack[i].tag == tag:
                del self.stack[i:]
                return

    def handle_data(self, data):
        self.stack[-1].kids.append(data)


def text_of(n) -> str:
    if isinstance(n, str):
        return n
    return ''.join(text_of(k) for k in n.kids)


# ------------------------------------------------------------------ text normalisation

TRANS = str.maketrans({'\xa0': ' ', ' ': ' ', ' ': ' ', '​': '', '﻿': '', '\xad': '',
                       'ş': 'ș', 'ţ': 'ț', 'Ş': 'Ș', 'Ţ': 'Ț',
                       '“': '”', '″': '”', '«': '„', '»': '”',
                       '–': '-', '—': '-', '‑': '-', '−': '-',
                       '‘': "'", '’': "'", '`': "'", '\t': ' ', '\r': ' ', '\n': ' '})


def norm(s: str) -> str:
    s = s.translate(TRANS).replace('…', '...')
    s = re.sub(r'(?<=\S)\*{1,4}\)', '', s)  # footnote markers: "instanței*)."
    s = re.sub(r' +', ' ', s).strip()
    s = re.sub(r' ([,;:.)])', r'\1', s)
    s = re.sub(r'\( ', '(', s)
    return s


# ------------------------------------------------------------------ one article

BLOCK = {'S_PAR', 'S_ALN', 'S_LIT', 'S_PCT', 'S_LIN'}
# Headings of the civil code's paragraphs ("§3. Efectele divorțului ...", then "I. Efecte cu privire la ...") are
# S_PAR elements that some forms nest at the end of the article before them and others print between articles.
PRG_RE = re.compile(r'^§ ?\d+\.')
SUBHEAD_RE = re.compile(r'^[IVX]+\. [A-ZĂÂÎȘȚ]')
NOTE_RE = re.compile(r'^\(la (\d\d)-(\d\d)-(\d{4}),')


def skipped(n: Node) -> bool:
    c = n.cls
    return (c in ('TAG_COLLAPSED', 'S_SMN') or c.endswith('_SHORT')
            or 'display: none' in n.style or 'display:none' in n.style)


FOOTNOTE_RE = re.compile(r'^\*+\)')            # the publisher's footnotes: "*) În temeiul art. 220 ..."
# "NOTĂ:" then provisions of other laws reproduced after the code; the adoption formula and signatures
TAILNOTE_RE = re.compile(r'^(?:NOT[ĂA]:?|Această lege a fost adoptată\b.*)$')
JUNK_RE = re.compile(r'(?:&?lt;|<)LLNK[^>]*>\s*')  # a leaked link marker in some forms


def is_note(n: Node) -> bool:
    return n.cls == 'S_PAR' and 'blue' in n.style and bool(NOTE_RE.match(text_of(n).strip()))


# Older forms (before about 2017) print each amendment note after a rule of dashes, in black and without the
# in-force date: "---------" then "Alin. (2) al art. 287 a fost modificat de art. IX din LEGEA nr. 60 ...".
RULE_RE = re.compile(r'^[-─_=*]{5,}$')
OLD_NOTE_RE = re.compile(r'\b(?:a|au) fost \w+(?: \w+)? (?:de|prin)\b')


class Art:
    def __init__(self):
        self.lines, self.buf, self.notes, self.editorial = [], [], [], []
        self.after_rule = False
        self.heading = False
        self.stop = False

    def flush(self):
        t = norm(JUNK_RE.sub('', ''.join(self.buf)))
        if t and not self.stop:
            self.lines.append(t)
        self.buf = []

    def walk(self, node: Node):
        for k in node.kids:
            if isinstance(k, str):
                self.buf.append(k)
                continue
            if skipped(k) or (k.cls == 'S_ART' and quoted_article(k)):
                continue
            if k.cls in ('S_NTA', 'S_NTA_PAR'):  # an editorial note: not text, but it names the court rulings
                self.editorial.append(note_of(k))
                continue
            if is_note(k):
                self.notes.append(note_of(k))
                continue
            if k.cls == 'S_PAR':
                t = norm(text_of(k))
                if TAILNOTE_RE.match(t):
                    self.flush()
                    self.stop = True
                    continue
                if FOOTNOTE_RE.match(t):
                    self.flush()
                    continue
                if RULE_RE.match(t):
                    self.flush()
                    self.after_rule = True
                    continue
                if self.after_rule and OLD_NOTE_RE.search(t):
                    self.notes.append(note_of(k))
                    continue
                if PRG_RE.match(t) or (self.heading and SUBHEAD_RE.match(t)):
                    self.flush()
                    self.heading = True
                    continue
                self.heading = False
            if k.cls in BLOCK:
                self.after_rule = False
            if k.cls in BLOCK or k.tag in ('br', 'p', 'div', 'tr', 'li', 'table'):
                self.flush()
                self.walk(k)
                self.flush()
            elif k.tag == 'td':
                self.buf.append(' ')
                self.walk(k)
                self.buf.append(' ')
            else:
                self.walk(k)


def holds_article(n: Node, self_too: bool = False) -> bool:
    """Whether an element is (self_too) or contains an article (not counting articles quoted in notes)."""
    if n.cls == 'S_ART':
        return self_too and not quoted_article(n)
    if n.cls in ('S_NTA', 'S_NTA_PAR') or skipped(n):
        return False
    return any(isinstance(k, Node) and holds_article(k, True) for k in n.kids)


QUOTED_TTL_RE = re.compile(r'^Articolul\s+[IVXLC]+\s*\.?$')


def quoted_article(n: Node) -> bool:
    """An article of another act that a publisher's note reproduces ("*) NOTA ...: Art. XVII din LEGEA nr. 2/2013
    prevede: Articolul XVII ..."): it carries a Roman number, which no article of the codes does."""
    for k in n.kids:
        if isinstance(k, Node) and k.cls == 'S_ART_TTL':
            return bool(QUOTED_TTL_RE.match(norm(text_of(k))))
    return False


def note_of(n: Node) -> dict:
    t = norm(text_of(n))
    m = NOTE_RE.match(t)  # None for the older, undated notes
    links = []

    def find(x):
        for k in x.kids:
            if isinstance(k, Node):
                if k.tag == 'a':
                    h = re.search(r'Detalii(?:Document|DocumentAfis)/(\d+)', k.href)
                    links.append((h.group(1) if h else '', norm(text_of(k))))
                else:
                    find(k)
    find(n)
    return {'date': f'{m.group(3)}-{m.group(2)}-{m.group(1)}' if m else None, 'text': t, 'links': links}


INLINE_ART_RE = re.compile(r'^(?:([A-ZĂÂÎȘȚ][^.;:]{2,118}?) )?Art\. ?(\d+)\. ?- ?(\S.*)$')
ART_LINE_RE = re.compile(r'^(?:ART|Art)\.? ?(\d+(?:\.\d{3})?)(?:\^(\d+))?\.?$')
KEY_RE = re.compile(r'^Articolul\s+(\d+(?:[ .]\d{3})?)\s*(?:\^\s*(\d+))?\s*\.?\s*(?:\*+\)?)?$')  # '1 074', '2357.', '5*)'


def articles(raw: bytes, pad: int, titles: bool = True) -> tuple[dict, dict, dict]:
    """({key: unit}, {key: [amendment note]}, {key: [editorial note]}) for every article of one page."""
    s = raw.decode('utf-8', 'replace')
    i = s.find('class="S_ART"')
    i = s.rfind('<', 0, i)
    # Some acts (Legea 190/2018) print each article inside its marginal-title paragraph: <S_PAR>Definiții<S_ART>...
    j = s.rfind('<span class="S_PAR"', 0, i)
    if j >= 0 and i - j < 400 and '</span>' not in s[j:i]:
        i = j
    p = Tree()
    p.feed(s[i:])
    p.close()
    found = []        # [(article node, marginal title printed just before it, outside any article)]
    pending = [None]
    loose = [None]    # an article printed as bare paragraphs outside any article ("ART 2.655", title, text)

    def collect(n):
        for k in n.kids:
            if isinstance(k, Node):
                if k.cls in ('S_NTA', 'S_NTA_PAR') or skipped(k):
                    continue
                if k.cls == 'S_ART' and quoted_article(k):
                    continue
                if k.cls == 'S_ART':
                    found.append((k, pending[0]))
                    pending[0] = loose[0] = None
                elif k.cls == 'S_PAR' and holds_article(k):
                    # A paragraph that wraps articles: a marginal title wrapping its article (Legea 190/2018), or a
                    # heading ("§ 2. ...", a chapter) left unclosed around the articles after it. The title is the
                    # paragraph's own text before the first element.
                    head = []
                    for x in k.kids:
                        if isinstance(x, Node) and holds_article(x, self_too=True):
                            break
                        head.append(text_of(x))
                    t = norm(''.join(head))
                    if re.match(r'^(?:\*+\) ?)?NOT[ĂA]\b', t) or 'Reproducem' in t:
                        continue  # "NOTĂ: Reproducem mai jos ...": articles of other acts printed after the code
                    ok = t and title_like(t) and not PRG_RE.match(t) and not SUBHEAD_RE.match(t)
                    pending[0] = t if ok else None
                    loose[0] = None
                    collect(k)
                elif k.cls == 'S_PAR':
                    t = norm(text_of(k))
                    if ART_LINE_RE.match(t):
                        loose[0] = (ART_LINE_RE.match(t), [])
                        found.append(('loose', loose[0]))
                        continue
                    if loose[0] is not None:
                        if t:
                            loose[0][1].append(t)
                        continue
                    ok = title_like(t) and not PRG_RE.match(t) and not SUBHEAD_RE.match(t)
                    pending[0] = t if ok else None
                else:
                    if k.cls.endswith(('_TTL', '_DEN')) or k.cls in ('S_TTL', 'S_CAP', 'S_SEC', 'S_CRT', 'S_PRT', 'S_PRG'):
                        pending[0] = loose[0] = None
                    collect(k)
    collect(p.root)
    units, notes, editorial = {}, {}, {}
    order = []
    relabel = misnumbered(found)
    for a, stray_title in found:
        ttl = den = None
        body = None
        if a == 'loose':
            m, lines = stray_title
            stray_title = None
            ttl = f'Articolul {m.group(1)}' + (f'^{m.group(2)}' if m.group(2) else '')
        else:
            for k in a.kids:
                if isinstance(k, Node):
                    if k.cls == 'S_ART_TTL':
                        ttl = norm(text_of(k))
                    elif k.cls == 'S_ART_DEN':
                        den = norm(text_of(k))
                    elif k.cls == 'S_ART_BDY':
                        body = k
        m = KEY_RE.match(ttl or '')
        if not m:
            raise SystemExit(f'unexpected article title {ttl!r}')
        num = int(re.sub(r'[ .]', '', m.group(1)))
        if id(a) in relabel:
            num = relabel[id(a)]
        key = f'art-{num:0{pad}d}' + (f'-{int(m.group(2))}' if m.group(2) else '')
        ttl = f'Articolul {num}' + (f'^{int(m.group(2))}' if m.group(2) else '')
        art = Art()
        if a == 'loose':
            art.lines = list(lines)
        if body is not None:
            art.walk(body)
            art.flush()
            while len(art.lines) > 1 and SUBHEAD_RE.match(art.lines[-1]):  # a sub-heading of the next articles
                art.lines.pop()
        if stray_title and titles and (not art.lines or not title_like(art.lines[0])):
            art.lines.insert(0, stray_title)
        # The 2009 text of the Civil Code prints a few articles as plain paragraphs inside the article before them
        # ("ART.1.251", then its title and text): split them out under their own number.
        pieces = [(key, ttl, art)]
        for i in range(len(art.lines) - 1, 0, -1):
            m2 = ART_LINE_RE.match(art.lines[i])
            if m2:
                n2 = int(re.sub(r'[ .]', '', m2.group(1)))
                k2 = f'art-{n2:0{pad}d}' + (f'-{int(m2.group(2))}' if m2.group(2) else '')
                a2 = Art()
                a2.lines = art.lines[i + 1:]
                del art.lines[i:]
                pieces.insert(1, (k2, f'Articolul {n2}' + (f'^{int(m2.group(2))}' if m2.group(2) else ''), a2))
                continue
            # Older forms of the Code of Criminal Procedure print the next article run into this one, title and
            # text on one line: "Schimbarea regimului de executare" / "Art. 518. - În cazurile ...". Only the number
            # that follows this article's is split off, so a quoted "Art. N. -" stays text.
            m3 = INLINE_ART_RE.match(art.lines[i])
            if m3 and not m.group(2) and int(m3.group(2)) == num + 1 and not ART_LINE_RE.match(art.lines[i]):
                n2 = int(m3.group(2))
                a2 = Art()
                a2.lines = [m3.group(3)] + art.lines[i + 1:]
                del art.lines[i:]
                if m3.group(1):
                    a2.lines.insert(0, m3.group(1))
                elif len(art.lines) > 1 and title_like(art.lines[-1]):
                    a2.lines.insert(0, art.lines.pop())
                pieces.insert(1, (f'art-{n2:0{pad}d}', f'Articolul {n2}', a2))
        for k2, t2, a2 in pieces:
            if k2 in units:
                raise SystemExit(f'duplicate article {t2!r}')
            order.append((k2, t2, den if k2 == key else None, a2))
            units[k2] = None
    # Some forms nest an article's marginal title ("Confiscarea extinsă") at the end of the article before it.
    # Move it back when the next article opens straight into its text.
    for (_, _, _, a), (_, _, _, b) in zip(order, order[1:]):
        if len(a.lines) >= 2 and title_like(a.lines[-1]) and (not b.lines or not title_like(b.lines[0])):
            b.lines.insert(0, a.lines.pop())
    for key, ttl, den, art in order:
        head = '# ' + ttl + (' ' + den if den else '')
        units[key] = {'label': ttl.replace('Articolul', 'Art.'), 'kind': 'art', 'text': '\n'.join([head] + art.lines) + '\n'}
        if art.notes:
            notes[key] = art.notes
        if art.editorial:
            editorial[key] = art.editorial
    return units, notes, editorial


MISNUMBERED = set()  # (wrong title, corrected number) seen, for the decisions


def misnumbered(found: list) -> dict:
    """{id(article node): corrected number} for an article whose printed number repeats an earlier article's while
    its neighbours are N-1 and N+1 (the portal's typo "Articolul 158" between arts. 517 and 519): it is art. N."""
    nums = []
    for a, _ in found:
        n = None
        if a != 'loose':
            for k in a.kids:
                if isinstance(k, Node) and k.cls == 'S_ART_TTL':
                    m = KEY_RE.match(norm(text_of(k)))
                    if m and not m.group(2):
                        n = int(re.sub(r'[ .]', '', m.group(1)))
        nums.append(n)
    out, seen = {}, set()
    for i, n in enumerate(nums):
        if n is not None and n in seen and 0 < i < len(nums) - 1:
            p, q = nums[i - 1], nums[i + 1]
            if p is not None and q is not None and q - p == 2 and p + 1 not in seen:
                out[id(found[i][0])] = p + 1
                MISNUMBERED.add((f'Articolul {n}', p + 1))
                n = p + 1
        if n is not None:
            seen.add(n)
    return out


def title_like(line: str) -> bool:
    """A marginal title: short, no closing punctuation, not a numbered or lettered item."""
    return (len(line) < 120 and not re.search(r'[.;:,]$', line) and not re.match(r'^(?:\(?\d+\)|[a-z]\)|-)', line)
            and line[:1].isupper())


# ------------------------------------------------------------------ laws named in notes

LAW_RE = re.compile(r'(ORDONANȚA DE URGENȚĂ|ORDONANȚA|LEGEA|DECIZI(?:A|EI)|CURȚII CONSTITUȚIONALE)\b[^,]*?\bnr\.\s*(\d+)'
                    r'\s+din\s+(\d{1,2})\s+(\w+)\s+(\d{4})', re.I)
MO_RE = re.compile(r'MONITORUL OFICIAL(?: AL ROMÂNIEI)?(?:, PARTEA I)?,?\s+nr\.\s*(\d+)(?:\s*bis)?\s+din\s+(\d{1,2})\s+(\w+)\s+(\d{4})',
                   re.I)


def ro_date(d, mon, y) -> str:
    return f'{int(y):04d}-{MONTHS[mon.lower()]:02d}-{int(d):02d}'


def law_of(link: tuple[str, str], context: str = '') -> tuple[str, dict] | None:
    """(key, law) for the act a note's link names: LEGEA / ORDONANȚA [DE URGENȚĂ] / DECIZIA (CCR) nr. N din D,
    or a RECTIFICAREA (an official correction printed in the Monitorul Oficial)."""
    doc, t = link
    tm = LAW_RE.search(t)
    pub = MO_RE.search(t) or MO_RE.search(context)
    rect = re.search(r'RECTIFICAREA nr\. (\d+) din (\d{1,2}) (\w+) (\d{4})', t)
    if rect and pub and (not tm or rect.start() < tm.start()):
        n, y = pub.group(1), pub.group(4)
        return f'rectificare-mo-{n}-{y}', {
            'label': f'Rectificare MO nr. {n}/{y}', 'kind': 'law',
            'title': f'Rectificare la actul nr. {rect.group(1)} din {int(rect.group(2))} {rect.group(3).lower()} '
                     f'{rect.group(4)}, publicată în Monitorul Oficial al României, Partea I, nr. {n} din '
                     f'{int(pub.group(2))} {pub.group(3).lower()} {y}',
            'enacted': None, 'published': ro_date(*pub.groups()[1:]),
            'url': PORTAL + f'DetaliiDocument/{doc}' if doc else None,
            'note': 'A rectification: an official correction of the text, printed in the Monitorul Oficial.'}
    if not tm:
        return None
    kind = tm.group(1).upper()
    kind = 'DECIZIA' if kind.startswith(('DECIZI', 'CURȚII')) else kind
    for pat, prefix, label, k in KINDS:
        if kind == pat:
            break
    num, year = int(tm.group(2)), tm.group(5)
    key = f'{prefix}-{num}-{year}'
    if tm.group(4).lower() not in MONTHS:
        return None
    enacted = ro_date(tm.group(3), tm.group(4), tm.group(5))
    words = {'oug': 'Ordonanța de urgență a Guvernului', 'og': 'Ordonanța Guvernului', 'legea': 'Legea',
             'dcc': 'Decizia Curții Constituționale'}[prefix]
    title = f'{words} nr. {num} din {int(tm.group(3))} {tm.group(4).lower()} {year}'
    if pub:
        title += f', publicată în Monitorul Oficial al României, Partea I, nr. {pub.group(1)} din {int(pub.group(2))} ' \
                 f'{pub.group(3).lower()} {pub.group(4)}'
    return key, {'label': f'{label} {num}/{year}', 'title': title, 'kind': k, 'enacted': enacted,
                 'published': ro_date(*pub.groups()[1:]) if pub else None,
                 'url': PORTAL + f'DetaliiDocument/{doc}' if doc else None}


# ------------------------------------------------------------------ forms and versions


def archive_url(page: str, ts: str, afis: bool) -> str:
    return f'https://web.archive.org/web/{ts}id_/{PORTAL}{"DetaliiDocumentAfis" if afis else "DetaliiDocument"}/{page}'


def cached(url: str) -> bytes:
    p = CACHE / hashlib.sha256(url.encode('utf-8')).hexdigest()
    if not p.exists():
        raise SystemExit(f'not cached: {url}')
    return p.read_bytes()


def cc_source(rec: dict) -> tuple[str, str]:
    """(source URL, cache key) of a Common Crawl capture: the WARC file, the record's byte range and the page."""
    return (f'https://data.commoncrawl.org/{rec["filename"]}#offset={rec["offset"]}&length={rec["length"]}'
            f'&url={rec["url"]}', f'cc:{rec["filename"]}:{rec["offset"]}:{rec["length"]}')


def page_for(slug: str, f: dict, man: dict) -> tuple[str, str, str]:
    """(source URL, cache key, form id) of the capture to read for form f."""
    pin = man.get('pins', {}).get(f['id'])
    if pin:
        u = archive_url(pin['page'], pin['capture'], False)
        return u, u, f['id']
    rec = man.get('cc', {}).get(f['id'])
    if rec:
        return (*cc_source(rec), f['id'])
    rec = man.get('afis', {}).get(f['id'])  # a republication: the republished text as printed (Phase 2)
    if rec:
        return (*cc_source(rec), f['id'])
    ts = man['captures'].get(f['id']) or (man['root_capture'] if f['id'] == man['root'] else None)
    if not ts:
        raise SystemExit(f'{slug}: no capture for form {f["id"]}')
    u = archive_url(f['id'], ts, False)
    return u, u, f['id']


def load(slug: str, man: dict) -> list[dict]:
    """[{'from','url','sha','units','notes','form'}] in date order: the base text first, then each form."""
    a = ACTS[slug]
    out = []
    if man.get('base_cc'):
        url, key = cc_source(man['base_cc'])
    else:
        url = key = archive_url(man['base'], man['base_capture'], True)
    raw = cached(key)
    units, notes, editorial = articles(raw, a['pad'], a.get('titles', True))
    out.append({'from': a['in_force'], 'url': url, 'sha': hashlib.sha256(raw).hexdigest(), 'units': units,
                'notes': notes, 'editorial': editorial, 'form': man['base'], 'kind': 'baza'})
    missing = set(man.get('missing', []))
    forms = [f for f in man['forms'] if f['id'] not in a['skip'] and f['id'] not in missing
             and f['date'] >= a['in_force']]
    if slug in PHASE2:
        # The act page's id also stands, in "istoric consolidări", for its republication ("Republicarea din ..."), but
        # that page shows the newest form, so only the newest date is read from it (as 130143 for the Civil Code).
        newest = max(f['date'] for f in man['forms'])
        forms = [f for f in forms if f['id'] != man['root'] or f['date'] == newest]
    forms.sort(key=lambda f: (f['date'], int(f['id'])))
    for f in forms:
        url, key, fid = page_for(slug, f, man)
        raw = cached(key)
        units, notes, editorial = articles(raw, a['pad'], a.get('titles', True))
        out.append({'from': f['date'], 'url': url, 'sha': hashlib.sha256(raw).hexdigest(), 'units': units,
                    'notes': notes, 'editorial': editorial, 'form': fid, 'kind': f['kind']})
    return out


def drop_editorial_lines(slug: str, sts: list[dict]) -> int:
    """Remove the paragraphs listed in EDITORIAL_LINES (editorial matter the portal printed as text)."""
    n = 0
    for st in sts:
        for key, prefixes in EDITORIAL_LINES.get(slug, {}).items():
            u = st['units'].get(key)
            if not u:
                continue
            lines = u['text'].splitlines()
            keep = [l for l in lines if not l.startswith(prefixes)]
            if len(keep) != len(lines):
                n += 1
                u['text'] = '\n'.join(keep) + '\n'
    return n


# The penal code's form of 03.02.2019 and every later form print, as two black paragraphs at the end of art. 183,
# the holdings of two High Court preliminary rulings (HP) on art. 6. They are editorial matter, not the code's text.
EDITORIAL_LINES = {'codul-penal': {'art-183': ('Stabilește că, în interpretarea dispozițiilor art. 6 alin. (1)',
                                               'În interpretarea dispozițiilor art. 6 alin. (1) din Codul penal, în cazul')}}


# Phase 2: the portal's notes that some forms print as black paragraphs inside an article. A note of this kind quotes
# another act and names its gazette in capitals ("Conform art. XII ... din LEGEA nr. 2 din 1 februarie 2013, publicată
# în MONITORUL OFICIAL nr. 89 ..."); the codes' own text writes "Monitorul Oficial". NOTE_LINES lists, per act, the
# further paragraphs of such notes (quoted law text) that some forms split off.
NOTE_LINE_RE = re.compile(r'^(?:\*+\) ?)?(?:Conform|Potrivit|În conformitate cu|NOTĂ|Notă)\b.*\bMONITORUL OFICIAL\b')
NOTE_LINES = {'codul-procedura-civila': ('În procesele pornite începând cu data intrării în vigoare a prezentei legi și '
                                         'până la data de 31 decembrie 2015',)}


# A note on a Constitutional Court decision run into the provision's line: "(4) Încetat efectele juridice.. Alin. (4)
# al art. 344 și-a încetat efectele juridice începând cu data de ..., conform DECIZIEI CURȚII CONSTITUȚIONALE nr. 641
# ... publicată în MONITORUL OFICIAL ...". The provision's own words are kept; the note from its first word is cut.
CCR_NOTE_RE = re.compile(r'(?:^|(?<=[.;:,] ))(?:Alin\.|Alineatul|Art\.|Articolul|Lit\.|Litera|Pct\.|Punctul|Sintagma|'
                         r'Textul|Dispozițiile)\s[^\n]*?(?:a fost modificat|au fost modificate|și-a încetat efectele|'
                         r'și-au încetat efectele)[^\n]*\bMONITORUL OFICIAL\b')


def drop_note_lines(slug: str, sts: list[dict]) -> int:
    n = 0
    extra = NOTE_LINES.get(slug, ())
    for st in sts:
        for u in st['units'].values():
            lines = u['text'].splitlines()
            keep = []
            for l in lines:
                if NOTE_LINE_RE.match(l) or (extra and l.startswith(extra)):
                    continue
                c = CCR_NOTE_RE.search(l)
                if c and not l.startswith('#'):
                    l = re.sub(r'\.\.$', '.', l[:c.start()].rstrip())
                    if not l:
                        continue
                keep.append(l)
            if keep != lines:
                n += 1
                u['text'] = '\n'.join(keep) + '\n'
    return n


def new_notes(prev: dict, cur: dict, key: str, lo: str | None, hi: str) -> list[dict]:
    """The amendment notes of `key` in `cur` that explain a change since `prev`: dated in (lo, hi], or (for the
    older, undated notes) not printed on that article in the previous form."""
    before = {n['text'] for n in prev['notes'].get(key, [])}
    out = []
    for n in cur['notes'].get(key, []):
        if n['date']:
            if (lo is None or n['date'] > lo) and n['date'] <= hi:
                out.append(n)
        elif n['text'] not in before:
            out.append(n)
    return out


def credit_laws(ns: list[dict], laws: dict, unknown: list) -> list[str]:
    """Laws named by these notes, oldest change first (the builder puts the unit in the last one's commit)."""
    keyed = []
    for n in ns:
        got = [g for g in (law_of(link, n['text'] if len(n['links']) == 1 else '') for link in n['links']) if g]
        if not got:
            g = law_of(('', n['text']), n['text'])
            got = [g] if g else []
        if not got:
            unknown.append(n['text'])
        for k, info in got:
            if k in laws and laws[k]['label'] != info['label']:
                raise SystemExit(f'law key clash {k}')
            laws.setdefault(k, info)
            if not laws[k].get('published') and info.get('published'):  # a later note may print the gazette
                laws[k].update(published=info['published'], title=info['title'])
            keyed.append((n['date'] or '', k))
    seen, out = set(), []
    for _, k in sorted(keyed):
        if k not in seen:
            seen.add(k)
            out.append(k)
    return out


CCR_RE = re.compile(r'DECIZI(?:A|EI)(?: CURȚII CONSTITUȚIONALE)? nr\. ?(\d+) din (\d{1,2}) (\w+) (\d{4}), publicată în '
                    r'Monitorul Oficial(?: al României)?(?:, Partea I)?,? nr\. ?(\d+) din (\d{1,2}) (\w+) (\d{4})', re.I)
EFFECT_RE = re.compile(r'(?:începând cu data de|de la data de) (\d{1,2}) (\w+) (\d{4})')


def ccr_credit(cur: dict, key: str, lo: str, hi: str, laws: dict) -> list[str]:
    """A Constitutional Court decision named in the article's editorial note whose effect on the text falls in
    (lo, hi]: the day the note gives, or else 45 days after publication (Constituția art. 147 alin. (1))."""
    import datetime as dt
    out = []
    for e in cur['editorial'].get(key, []):
        t = e['text']
        if 'onstituțional' not in t:
            continue
        for m in CCR_RE.finditer(t):
            if m.group(3).lower() not in MONTHS or m.group(7).lower() not in MONTHS:
                continue
            pub = ro_date(m.group(6), m.group(7), m.group(8))
            eff = EFFECT_RE.search(t[m.end():])
            if eff and eff.group(2).lower() in MONTHS:
                day = ro_date(*eff.groups())
            else:
                day = (dt.date.fromisoformat(pub) + dt.timedelta(days=45)).isoformat()
            if not (lo < day <= hi):
                continue
            num, year = int(m.group(1)), m.group(4)
            k = f'dcc-{num}-{year}'
            laws.setdefault(k, {'label': f'Decizia CCR nr. {num}/{year}', 'kind': 'court',
                                'title': f'Decizia Curții Constituționale nr. {num} din {int(m.group(2))} '
                                         f'{m.group(3).lower()} {year}, publicată în Monitorul Oficial al României, '
                                         f'Partea I, nr. {m.group(5)} din {int(m.group(6))} {m.group(7).lower()} '
                                         f'{m.group(8)}',
                                'enacted': ro_date(m.group(2), m.group(3), m.group(4)), 'published': pub, 'url': None})
            if k not in out:
                out.append(k)
    return out


# ------------------------------------------------------------------ the corpus


def unit_of(u: dict) -> dict:
    return {'label': u['label'], 'kind': u['kind'], 'text': u['text']}


def ensure_law(key: str, sts: list[dict], laws: dict) -> str:
    """Make sure `key` is in laws: from BASE_LAWS, or else from the first note link (in any form) that names it."""
    if key in laws:
        return key
    if key in BASE_LAWS:
        laws[key] = dict(BASE_LAWS[key])
        return key
    for st in sts:
        for ns in list(st['notes'].values()) + list(st['editorial'].values()):
            for n in ns:
                for link in n['links'] + [('', n['text'])]:
                    g = law_of(link, n['text'])
                    if g and g[0] == key and g[1].get('published'):
                        laws[key] = g[1]
                        return key
    raise SystemExit(f'no note names {key}')


def build_act(slug: str, man: dict, laws: dict, report: dict) -> dict:
    a = ACTS[slug]
    sts = load(slug, man)
    report['editorial_lines'] = drop_editorial_lines(slug, sts)
    if slug in PHASE2:
        report['note_lines'] = drop_note_lines(slug, sts)
    unknown, unexplained = [], []
    base = sts[0]
    versions = [{'from': base['from'], 'source_url': base['url'], 'sha256': base['sha'],
                 'units': {k: unit_of(u) for k, u in sorted(base['units'].items())},
                 'note': a['base_note']}]
    for prev, cur in zip(sts, sts[1:]):
        keys = sorted(set(prev['units']) | set(cur['units']))
        changed = [k for k in keys if (prev['units'].get(k) or {}).get('text') != (cur['units'].get(k) or {}).get('text')]
        if not changed:
            report.setdefault('unchanged_forms', []).append(f'{cur["from"]} ({cur["form"]})')
            continue
        first = prev is base
        day = a.get('form_day', {}).get(cur['form'], cur['from'])
        lo = None if first else prev['from']
        credits = {}
        gap_days = {f['date'] for f in man['forms'] if f['id'] in set(man.get('missing', []))
                    and (lo is None or f['date'] > lo) and f['date'] < cur['from']}
        if gap_days:
            report.setdefault('gap_versions', []).append(f'{cur["from"]} carries {sorted(gap_days)}')
        late = [(k, n['date']) for k, ns in cur['notes'].items() for n in ns if n['date'] and n['date'] > cur['from']]
        if late:  # text printed before its law took effect: not seen so far; would need the anachronism rule
            raise SystemExit(f'{slug} {cur["form"]}: notes dated after the form: {late[:5]}')
        for k in changed:
            ns = new_notes(prev, cur, k, lo, cur['from'])
            # a form the portal lists but neither archive holds (or that has no text) may sit in the interval: its
            # changes arrive with this form, and their notes carry its date
            off = [n['date'] for n in ns if n['date'] and n['date'] != cur['from'] and n['date'] not in gap_days]
            if off:
                raise SystemExit(f'{slug} {cur["form"]} {k}: a note explains the change from {off}, not the form date')
            got = credit_laws(ns, laws, unknown)
            old, new = (prev['units'].get(k) or {}).get('text', ''), (cur['units'].get(k) or {}).get('text', '')
            if not got and not first and old.split() != new.split():  # not for a change of line breaks only
                got = ccr_credit(cur, k, lo, cur['from'], laws)
            if not got and first and a.get('first_form_law'):
                got = [ensure_law(a['first_form_law'], sts, laws)]
            if not got and a.get('republished', {}).get(cur['form']):
                got = [ensure_law(a['republished'][cur['form']], sts, laws)]
            if got:
                credits[k] = got
            else:
                unexplained.append(f'{day} {k}')
        v = {'from': day, 'source_url': cur['url'], 'sha256': cur['sha'],
             'changes': {k: (unit_of(cur['units'][k]) if k in cur['units'] else None) for k in changed},
             'credits': credits}
        if day == versions[-1]['from']:
            v['same_day'] = True
        if a.get('form_note', {}).get(cur['form']):
            v['note'] = a['form_note'][cur['form']]
        versions.append(v)
    report['versions'] = len(versions)
    report['unexplained'] = unexplained
    report['unknown_notes'] = sorted(set(unknown))
    report['latest'] = {'form': sts[-1]['form'], 'date': sts[-1]['from'], 'units': len(sts[-1]['units'])}
    report['_latest_units'] = sts[-1]['units']
    return {'slug': slug, 'short': a['short'], 'title': a['title'], 'url': a['url'], 'first_law': a['first_law'],
            'earlier_laws': [], 'versions': versions}


COUNTRY = {
    'code': 'RO', 'name': 'Romania', 'slug': 'romania', 'lang': 'ro', 'tz': 'Europe/Bucharest',
    'future_branch': 'viitor',
    'publisher': {'name': 'Portalul legislativ (Ministerul Justiției)', 'email': 'portal@legislatie.invalid'},
    'default_in_force_rule': {
        'text': 'Constituția României art. 78: "Legea se publică în Monitorul Oficial al României și intră în vigoare '
                'la 3 zile de la data publicării sau la o dată ulterioară prevăzută în textul ei." The corpus does '
                'not apply this rule itself: every in-force date comes from the portal\'s own note on the amended '
                'provision ("la DD-MM-YYYY") or from the date of the consolidated form.',
        'source': PORTAL + 'DetaliiDocument/47355',
    },
    'licence_note': 'Sursa: Portalul legislativ al Ministerului Justiției, https://legislatie.just.ro. Textele '
                    'oficiale ale actelor normative nu fac obiectul dreptului de autor (Legea nr. 8/1996, art. 9 '
                    'lit. b).',
}


PHASE2_START = '2026-10-29T12:00:00Z'  # requests logged before this were Phase 1's (the log is append-only)


def requests_logged(phase: int = 1) -> int:
    p = CACHE / 'requests.jsonl'
    if not p.exists():
        return 0
    n = 0
    for line in p.open(encoding='utf-8'):
        at = json.loads(line).get('at', '')
        n += (at < PHASE2_START) if phase == 1 else (at >= PHASE2_START)
    return n


def sources(man: dict) -> list[dict]:
    man = {k: v for k, v in man.items() if k in PHASE1}
    caps = sorted({ts for m in man.values() for ts in list(m['captures'].values()) + [m['root_capture'],
                                                                                    m['base_capture']]}
                  | {p['capture'] for m in man.values() for p in m.get('pins', {}).values()})
    return [
        {'name': 'Portalul legislativ (legislatie.just.ro), Ministerul Justiției', 'url': 'https://legislatie.just.ro',
         'retrieved': RETRIEVED, 'requests': 0,
         'licence': 'Official texts of normative acts are excluded from copyright protection (Legea nr. 8/1996 '
                    'privind dreptul de autor și drepturile conexe, art. 9 lit. b). Attribution: Portalul legislativ, '
                    'Ministerul Justiției.',
         'notes': 'The publisher of every text. Each consolidated form ("forma consolidată") is its own page, '
                  '/Public/DetaliiDocument/<id>; the act as first published is /Public/DetaliiDocumentAfis/<id>. '
                  'The portal closed every TLS connection from our machine, so it was read only through Internet '
                  'Archive captures (next source).'},
        {'name': 'Internet Archive, Wayback Machine (id_ raw captures of legislatie.just.ro)',
         'url': 'https://web.archive.org/', 'retrieved': RETRIEVED, 'requests': requests_logged(),
         'licence': 'Internet Archive terms of use; the captured pages are the publisher\'s.',
         'notes': f'{len(caps)} distinct capture timestamps, {caps[0]} to {caps[-1]}, pinned per form in forms.json '
                  '(and in every version\'s source_url). Read through gitlaw_common/wayback.py (one shared, adaptive '
                  'rate for the machine). Requests counts every CDX listing and page fetch in .cache/requests.jsonl.'},
    ]


DECISIONS_ALL = [
    'Romania\'s Phase 1: the Constitution, the Civil Code and the Penal Code, each from the Portalul legislativ, the '
    'only official source of consolidated texts with every past consolidated form and a note on each amended '
    'provision naming the amending act and the day the change took effect.',
    'The portal refused connections from our machine, so every page was read from Internet Archive id_ captures; '
    'each form\'s capture timestamp is pinned in forms.json and in its version\'s source_url.',
    'One file per article (art-NNN, Civil Code art-NNNN; Articolul 112^1 is art-112-1), one line per paragraph, '
    'alineat, letter, point or indent, the first line "# Articolul N"; the marginal title is the next line. Chapter '
    'and section headings, editorial notes (Notă), the publisher\'s footnotes, signatures and the amendment notes '
    'themselves are not text.',
    'Where a form nests an article\'s marginal title at the end of the article before it, or prints it between two '
    'articles, parse.py moves it back to its own article; the Civil Code\'s paragraph headings ("§3. ...") and their '
    'sub-headings ("I. ...") are dropped wherever a form nests them.',
    'Typesetting is normalised before comparing forms: cedilla ş/ţ become comma-below ș/ț (older forms use the '
    'cedilla), no-break spaces become spaces, runs of spaces collapse, “ becomes ”, « » become „ ”, en and em dashes '
    'become hyphens, footnote markers ("*)") and a leaked link marker (<LLNK ...>) are dropped.',
    'Credits come only from the portal\'s amendment notes on the changed article: from about 2017 they read "(la '
    'DD-MM-YYYY, ... a fost modificat de ... LEGEA nr. N din ...)"; older forms print the same note, undated, after a '
    'rule of dashes. A dated note counts when its date falls after the previous version and on or before this one; '
    'an undated note counts when it is new on that article. Every dated note that explains a change carries the '
    'date of the form that first shows the change, and no note is dated after its form.',
    'A changed article with no such note is credited to a Constitutional Court decision only when the article\'s own '
    'editorial note names the decision (DECIZIA nr. N ... publicată în Monitorul Oficial ...) and its effect on the '
    'text falls in the version\'s interval: the day the note states, or 45 days after publication (Constituția art. '
    '147 alin. (1)). Otherwise it stays uncredited and the builder commits it as the publisher\'s.',
    'Each version takes effect on the date of its consolidated form, which is the in-force date the notes give for '
    'the changes it carries. Forms identical to the version before them (after normalisation) add no version.',
    'The newest captures are from June and July 2026, so amendments in force after the newest form of each act '
    '(Civil Code 03.05.2026, Penal Code 26.04.2026) may be missing.',
]

AI_USE = ['Claude Code with Claude Opus 5.5 (claude-opus-5-5) wrote fetch.py and parse.py and the README; no model '
          'output is used as legal text, and no model runs at data-build or git-build time. Counts: 0 model calls '
          'in parse.py.']


def iso_ro(d: str) -> str:
    return f'{d[8:10]}.{d[5:7]}.{d[:4]}'


def phase2_sources(slug: str, man: dict) -> list[dict]:
    a = ACTS[slug]
    cc = (list(man.get('cc', {}).values()) + list(man.get('afis', {}).values())
          + ([man['base_cc']] if man.get('base_cc') else []))
    ia = sorted(set(man['captures'].values()) | {p['capture'] for p in man.get('pins', {}).values()}
                | ({man['root_capture']} if man.get('root_source') == 'ia' else set())
                | ({man['base_capture']} if not man.get('base_cc') else set()))
    out = []
    if cc:
        crawls = sorted({r['crawl'] for r in cc})
        out.append({
            'name': f'Common Crawl ({", ".join(crawls)}): captures of legislatie.just.ro for the {a["short"]}',
            'url': 'https://commoncrawl.org/', 'retrieved': '2026-10-29', 'requests': len(cc),
            'licence': 'Common Crawl terms of use (https://commoncrawl.org/terms-of-use); the captured pages are the '
                       'publisher\'s (Portalul legislativ, Ministerul Justiției).',
            'notes': f'{len(cc)} page captures, read by byte range from the WARC files (each version\'s source_url '
                     'names the WARC file, offset, length and page URL). Found with one prefix query per crawl over '
                     'the newest 40 crawls (gitlaw_common/wayback.py, reading the index files from the data host); '
                     'a capture counts only when it is complete and shows the form its document id stands for.'})
    if ia:
        out.append({
            'name': f'Internet Archive, Wayback Machine: id_ raw captures of legislatie.just.ro for the {a["short"]}',
            'url': 'https://web.archive.org/', 'retrieved': '2026-10-29', 'requests': len(ia),
            'licence': 'Internet Archive terms of use; the captured pages are the publisher\'s.',
            'notes': f'{len(ia)} captures, {ia[0]} to {ia[-1]}, for the pages Common Crawl lacked; pinned in '
                     'forms.json and in each version\'s source_url.'})
    return out


def phase2_decisions(slug: str, man: dict, report: dict) -> list[str]:
    a = ACTS[slug]
    n_cc = len(man.get('cc', {})) + len(man.get('afis', {})) + (1 if man.get('base_cc') else 0)
    n_ia = len(man['captures']) + len(man.get('pins', {})) + (0 if man.get('base_cc') else 1)
    out = [
        f'{a["short"]}: Phase 2 act (gitlaw-RO-2, 2026-10-29), one of the Portalul legislativ\'s consolidated forms per '
        f'version, as for the Phase 1 acts: {n_cc} pages read from Common Crawl captures and {n_ia} from Internet '
        'Archive captures, each pinned in forms.json and in its version\'s source_url. A capture was used only if it '
        'was complete and the page showed the form its document id stands for.',
        f'{a["short"]}: the newest form held is that of {iso_ro(report["latest"]["date"])} (the act page\'s capture '
        f'{man["root_capture"]} lists no later form); amendments in force after it may be missing.',
    ]
    newest = max(f['date'] for f in man['forms'])
    dropped = [f for f in man['forms'] if f['id'] == man['root'] and f['date'] != newest]
    if dropped:
        out.append(f'{a["short"]}: the portal links its {", ".join(f["kind"] + " of " + iso_ro(f["date"]) for f in dropped)} '
                   f'to the act page {man["root"]}, which shows the newest form, so that link is not read; the form of '
                   'the same day with its own page is.')
    via_root = [(fid, r['timestamp']) for fid, r in man.get('cc', {}).items()
                if fid != man['root'] and r['url'].rstrip('/').endswith('/' + man['root'])]
    via_root += [(fid, p['capture']) for fid, p in man.get('pins', {}).items()]
    if via_root:
        dates = {f['id']: f['date'] for f in man['forms']}
        out.append(f'{a["short"]}: forms never captured under their own id, read instead from a capture of the act page '
                   f'{man["root"]} made while each was the newest form (the page marks the form it shows): '
                   + ', '.join(f'{iso_ro(dates[f])} ({f}) at {ts}' for f, ts in sorted(via_root, key=lambda x: dates[x[0]]))
                   + '.')
    for fid, rec in sorted(man.get('afis', {}).items()):
        f = next(f for f in man['forms'] if f['id'] == fid)
        out.append(f'{a["short"]}: the republication of {iso_ro(f["date"])} ({fid}) has no page of its own that shows it '
                   '(its DetaliiDocument page shows the newest form), so it is read from DetaliiDocumentAfis/'
                   f'{fid}, the republished text as printed in the Monitorul Oficial (capture {rec["timestamp"]}); '
                   'that page carries no amendment notes.')
    if man.get('missing'):
        miss =[f'{iso_ro(f["date"])} ({f["id"]})' for f in man['forms'] if f['id'] in set(man['missing'])]
        out.append(f'{a["short"]}: forms listed by the portal that could not be read (in neither archive, or every '
                   'capture a page without the act\'s text), so not versions; their changes arrive with the next form '
                   'held and take its date, though their notes give the earlier day: ' + ', '.join(miss) + '.')
    return out


def main(slugs: list[str] | None = None):
    man_all = json.loads((HERE / 'forms.json').read_text(encoding='utf-8'))
    OUT.mkdir(exist_ok=True)
    summary = {}
    for slug, a in ACTS.items():
        if slugs and slug not in slugs:
            continue
        laws, report = {}, {}
        for k in (a['first_law'], a.get('first_form_law')):
            if k and k in BASE_LAWS:
                laws[k] = dict(BASE_LAWS[k])
        MISNUMBERED.clear()
        act = build_act(slug, man_all[slug], laws, report)
        fixed = sorted(MISNUMBERED)
        used = {act['first_law']} | {l for v in act['versions'] for ls in v.get('credits', {}).values() for l in ls}
        laws = {k: {**{'temporary_until': None, 'restores': None, 'note': None}, **v}
                for k, v in sorted(laws.items()) if k in used}
        decisions = []
        if slug == 'constitutia':
            decisions += DECISIONS_ALL
            decisions += [
                'Constituția: the 1991 text (DetaliiDocumentAfis/1413, in force on its approval by referendum on 8 '
                'December 1991) and the text republished on 31 October 2003 (DetaliiDocument/47355), dated 29 '
                'October 2003, the day the revision took effect. The portal holds no later form: the Constitution '
                'has not been amended since.',
                'Constituția 2003: the republication renumbered the articles (152 became 156), so files are keyed by '
                'each text\'s own numbering and many change on 29 October 2003; every change that day is credited '
                'to Legea nr. 429/2003, as the portal\'s note on the republished text does.',
            ]
        if slug == 'codul-civil':
            decisions += [
                'Codul civil: the first version is the code as published in 2009 (DetaliiDocumentAfis/109884), dated '
                '1 October 2011, followed the same day by the republished text in force from that day (form '
                '01.10.2011); changes no article note explains are credited to Legea nr. 71/2011, which ordered the '
                'republication, as the portal\'s own note on the code does.',
                'Codul civil, 2009 text: the portal prints arts. 1.251, 2.367 and 2.374 as plain paragraphs inside the '
                'article before them ("ART.1.251", "Art. 2.367") and art. 2.655 as bare paragraphs ("ART 2.655"); '
                'parse.py gives each its own file. Art. 2.448 is run into the last paragraph of art. 2.447 mid-line, '
                'and is left as the portal prints it, so art-2448 first appears on 1 October 2011.',
                'Codul civil: the newest capture of the 2009 text (20251206132336) is cut off at 5 MiB, so the newest '
                'complete one (20250413082055) is used. The newest form (03.05.2026, id 309285) has no capture of '
                'its own; the act\'s page 109884 shows that form and was captured on 25 June 2026 (20260625171643). '
                'Page 130143 (listed as the 2011 republication) also shows the 03.05.2026 form in its capture of 7 '
                'July 2026; parse.py checks the two agree article by article.',
            ]
        if slug == 'codul-penal':
            decisions += [
                'Codul penal: the first version is the code as published in 2009 (DetaliiDocumentAfis/109855), dated '
                '1 February 2014, followed the same day by the first in-force form (01.02.2014); its changes are '
                'credited from the article notes (Legea nr. 27/2012, 63/2012, 187/2012 and others). The forms of 01 '
                'and 02.01.2013 predate the code\'s entry into force and are not used.',
                'Codul penal: from the form of 03.02.2019 on, the portal prints two holdings of High Court '
                'preliminary rulings on art. 6 as paragraphs of art. 183; parse.py drops them as editorial matter.',
            ]
        if slug == 'codul-procedura-civila':
            decisions += [
                'Codul de procedură civilă: the first version is the code as published in 2010 '
                '(DetaliiDocumentAfis/120650), dated 15 February 2013, the day it took effect (the date of the '
                'portal\'s first in-force form and of its republication note), followed the same day by the text in force from that day (the portal\'s form of '
                '15.02.2013, the text republished in Monitorul Oficial nr. 545 of 3 August 2012); changes no article '
                'note explains are credited to Legea nr. 76/2012, which amended the code and ordered the republication. '
                'Forms dated before 15 February 2013 are not used.',
            ]
        if slug == 'codul-procedura-penala':
            decisions += [
                'Codul de procedură penală: the first version is the code as published in 2010 '
                '(DetaliiDocumentAfis/120611), dated 1 February 2014, the day it took effect (the date of the '
                'portal\'s first in-force form), followed the same day by the portal\'s first in-force form (01.02.2014); its changes are '
                'credited from the article notes, and those no note explains to Legea nr. 255/2013, the implementing '
                'law that amended the code before it took effect.',
            ]
        if slug == 'codul-muncii':
            decisions += [
                'Codul muncii: the first version is the code as published in Monitorul Oficial nr. 72 of 5 February '
                '2003 (DetaliiDocumentAfis/41627), in force on 1 March 2003 as its art. 298 alin. (1) provides.',
            ]
        if slug == 'legea-190-2018':
            decisions += [
                'Legea nr. 190/2018: the first version is the law as published in Monitorul Oficial nr. 651 of 26 July '
                '2018 (DetaliiDocumentAfis/203151), in force on 31 July 2018: its art. 16 sets entry into force 5 days '
                'after publication. Its only consolidated form (01.12.2019) adds the change made by Legea nr. 233/2019.',
            ]
        if fixed:
            decisions.append(f'{a["short"]}: some forms print a wrong article number that repeats an earlier '
                             'article\'s, between the two articles it sits between; parse.py files it under the number '
                             'in sequence: ' + ', '.join(f'"{w}" read as art. {n}' for w, n in fixed) + '.')
        if report['unexplained']:
            decisions.append(f'{a["short"]}: {len(report["unexplained"])} changed article(s) with no note naming a '
                             f'law, committed as the publisher\'s: {", ".join(report["unexplained"])}.')
        if report.get('unchanged_forms'):
            decisions.append(f'{a["short"]}: forms with no change after normalisation, so no version: '
                             f'{", ".join(report["unchanged_forms"])}.')
        cc = a.get('cross_check')
        if cc:
            other, _, _ = articles(cached(archive_url(cc['page'], cc['capture'], False)), a['pad'])
            mine = report['_latest_units']
            diff = sorted(k for k in set(other) | set(mine) if (other.get(k) or {}).get('text') != (mine.get(k) or {}).get('text'))
            report['cross_check'] = f'{cc["page"]}@{cc["capture"]}: {len(diff)} differing articles {diff[:10]}'
            if diff:
                raise SystemExit(f'{slug}: cross-check failed: {report["cross_check"]}')
            decisions.append(f'{a["short"]}: cross-check passed, the 03.05.2026 form read from two captures '
                             f'(109884@{man_all[slug]["pins"]["309285"]["capture"]} and '
                             f'{cc["page"]}@{cc["capture"]}) is identical in all {len(mine)} articles.')
        part = {}
        if slug == 'constitutia':
            part['country'] = COUNTRY
            part['sources'] = sources(man_all)
        ai_use = AI_USE if slug == 'constitutia' else []
        if slug in PHASE2:
            decisions = phase2_decisions(slug, man_all[slug], report) + decisions
            part['sources'] = phase2_sources(slug, man_all[slug])
            ai_use = [f'{a["short"]}: parsed by parse.py, which Claude Code with Claude Opus 5.5 (claude-opus-5-5) '
                      f'extended for Phase 2; no model output is used as legal text; 0 model calls in parse.py.']
        part.update({'laws': laws, 'acts': [act], 'applies': [], 'decisions': decisions, 'ai_use': ai_use})
        path = OUT / f'{a["part"]}.json'
        tmp = path.with_suffix('.json.tmp')
        tmp.write_text(json.dumps(part, ensure_ascii=False, indent=1) + '\n', encoding='utf-8', newline='\n')
        os.replace(tmp, path)
        summary[slug] = {k: v for k, v in report.items() if not k.startswith('_')}
        summary[slug]['laws'] = len(laws)
        print(slug, json.dumps(summary[slug], ensure_ascii=False)[:1500], flush=True)
    return summary


if __name__ == '__main__':
    main(sys.argv[1:] or None)   # python parse.py [slug ...]   (no slugs: every act)
