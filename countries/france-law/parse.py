"""Writes France's corpus (corpus.json + corpus.d/*.json) from the LEGI files extract.py replayed into .cache/.

Reads only .cache/legi/<text dir>/article/** (one XML file per article version: NUM, ETAT, DATE_DEBUT, DATE_FIN, the
text in BLOC_TEXTUEL/CONTENU and the LIENS to the texts that created, modified, abrogated or transferred it) and
.cache/legi-texts/<cid>/ (the title records of those texts, from `extract.py --titles`). No network.

    python -X utf8 parse.py                  # every act in ACTS
    python -X utf8 parse.py constitution     # only the parts holding these act slugs
    python -X utf8 parse.py --report         # also print every credit decision to .tmp-build/credits-<slug>.tsv

The crediting rule (tested in test_parse.py, explained in `decisions`):
- A new wording of an article (a LEGI article version starting on day D) is credited to the texts named by its own
  amendment links (CREATION/CREE, MODIFICATION/MODIFIE, TRANSFERT/TRANSFERE, DEPLACEMENT/DEPLACE, either direction)
  that were signed on or before D and that the article's previous version did not already carry: LEGI repeats an
  article's older amendment links on its later versions, so a link inherited from the previous version says nothing
  about this change. Of what is left, only the latest signing date counts. Nothing left = unexplained.
- An article that ends without a successor is credited to its own abrogation or transfer links (ABROGATION/ABROGE,
  TRANSFERT/TRANSFERE, DEPLACEMENT/DEPLACE) signed on or before the day it ends, again without inherited links and
  without the links that created this version, latest signing date only. Nothing left = unexplained.
"""
from __future__ import annotations

import hashlib
import html
import json
import os
import re
import sys
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
CACHE = HERE / '.cache'
LEGI = CACHE / 'legi'
TEXTS = CACHE / 'legi-texts'
DOCS_DATE = '2026-10-28'   # the last LEGI increment fetched (LEGI_20261028-212713) and the day of retrieval
OPEN = '2999-01-01'
PLACEHOLDER = '[La source ne donne pas le texte en vigueur à cette date.]\n'

CREATE = {'CREATION', 'CREE', 'MODIFICATION', 'MODIFIE', 'TRANSFERT', 'TRANSFERE', 'DEPLACEMENT', 'DEPLACE'}
REMOVE = {'ABROGATION', 'ABROGE', 'TRANSFERT', 'TRANSFERE', 'DEPLACEMENT', 'DEPLACE'}
ENDED = {'ABROGE', 'ABROGE_DIFF', 'TRANSFERE', 'DISJOINT', 'PERIME', 'ANNULE'}

# Each act: its directory in .cache/legi, the LEGITEXT id Légifrance uses for its consolidated text, and the day its
# history starts here (see START_REASONS). Parts are written in this order; corpus.json carries the country block.
ACTS = [
    {'part': None, 'dir': 'JORFTEXT000000571356', 'legitext': 'LEGITEXT000006071194', 'slug': 'constitution',
     'short': 'Constitution', 'title': 'Constitution du 4 octobre 1958', 'start': '1958-10-05',
     'url': 'https://www.legifrance.gouv.fr/loda/id/LEGITEXT000006071194', 'first_law_cid': 'JORFTEXT000000571356',
     'earlier': []},
    {'part': '20-code-civil', 'dir': 'LEGITEXT000006070721', 'legitext': 'LEGITEXT000006070721', 'slug': 'code-civil',
     'short': 'Code civil', 'title': 'Code civil', 'start': '1994-01-01',
     'url': 'https://www.legifrance.gouv.fr/codes/texte_lc/LEGITEXT000006070721', 'first_law_cid': None,
     'earlier': []},
    {'part': '30-code-penal', 'dir': 'LEGITEXT000006070719', 'legitext': 'LEGITEXT000006070719', 'slug': 'code-penal',
     'short': 'Code pénal', 'title': 'Code pénal', 'start': '1994-03-01',
     'url': 'https://www.legifrance.gouv.fr/codes/texte_lc/LEGITEXT000006070719', 'first_law_cid': None,
     # the four laws of 22 July 1992 that enacted the new Code pénal, and the law that adapted the rest of the law
     # to it and fixed its entry into force (art. 373: 1 March 1994)
     # (cids as LEGI's links name them: lois n° 92-683, 92-684, 92-685, 92-686 and 92-1336)
     'earlier': ['JORFTEXT000000359434', 'JORFTEXT000000540288', 'JORFTEXT000000359433', 'JORFTEXT000000722860',
                 'JORFTEXT000000177662']},
]

START_REASONS = {
    'constitution': 'The Constitution starts on 1958-10-05, the day it was published and took effect, as enacted: every '
                    'LEGI version in force that day carries no amendment link, so the first commit is the Constitution '
                    'itself.',
    'code-civil': 'The Code civil starts on 1994-01-01, not 1804. LEGI holds the Code civil from 1804-03-21, but its '
                  'older history is incomplete: for every year before 1994, articles that provably existed then (an '
                  'amendment link on a later version is dated before that year) have no LEGI version covering it '
                  '(19 at 1993-01-01, 20 at 1985-01-01, 51 at 1975-01-01, 336 at 1900-01-01; for example art. 59 and '
                  'art. 459, whose first LEGI versions are of 1993 and 1988). From 1994-01-01 every such case is a '
                  'law signed earlier that took effect later, or a gap in one article that is marked below. The text '
                  'in force on 1994-01-01 is committed as the oldest version available, credited to no law.',
    'code-penal': 'The Code pénal starts on 1994-03-01, the day the new Code pénal took effect (loi n° 92-1336 du '
                  '16 décembre 1992, art. 373). LEGI also dates 30 article versions from 1992-07-23: the wording of the '
                  'laws of 22 July 1992 that loi n° 92-1336 amended before the code as a whole took effect (for '
                  'example art. 131-6, amended by its art. 341). They are left out. The text in force on 1994-03-01 '
                  'is committed as the oldest version available, naming the five laws that made it.',
}

NATURE = {  # LEGI nature -> (key prefix, label, kind)
    'LOI': ('loi', 'Loi', 'law'), 'LOI_CONSTIT': ('loi-constitutionnelle', 'Loi constitutionnelle', 'law'),
    'LOI_ORGANIQUE': ('loi-organique', 'Loi organique', 'law'), 'ORDONNANCE': ('ordonnance', 'Ordonnance', 'law'),
    'DECRET': ('decret', 'Décret', 'decree'), 'DECRET_LOI': ('decret-loi', 'Décret-loi', 'decree'),
    'ARRETE': ('arrete', 'Arrêté', 'decree'), 'DECISION': ('decision', 'Décision', 'court'),
    'CONSTITUTION': ('constitution', 'Constitution', 'law'), 'LOI_PROGRAMME': ('loi', 'Loi de programme', 'law'),
}
# Changes made by referendum (the people adopted the text): the Constitution itself (28 September 1958), the 1962 law on
# electing the President by universal suffrage (arts. 6 and 7) and the 2000 five-year term (art. 6).
# (cids as LEGI's links name them: the Constitution, loi n° 62-1292, loi constitutionnelle n° 2000-964)
REFERENDUM = {'JORFTEXT000000571356', 'JORFTEXT000000684037', 'JORFTEXT000000219201'}
MONTHS = ['janvier', 'février', 'mars', 'avril', 'mai', 'juin', 'juillet', 'août', 'septembre', 'octobre',
          'novembre', 'décembre']


# ---------------------------------------------------------------- reading

def clean(s: str) -> str:
    s = html.unescape(s)
    s = s.replace(' ', ' ').replace(' ', ' ').replace('­', '')
    s = s.replace('’', "'").replace('‘', "'").replace('“', '"').replace('”', '"')
    s = re.sub('[‐‑‒–—―−]', '-', s)
    return re.sub(r'\s+', ' ', s).strip()


def text_of(contenu: str) -> str:
    """One paragraph or line per line: <p>, <div> and <br/> end a line; other tags (sup, em) are dropped."""
    s = re.sub(r'<\s*br\s*/?\s*>|</?\s*(p|div)(\s[^>]*)?>', '\n', contenu, flags=re.I)
    s = re.sub(r'<[^>]+>', '', s)
    lines = [clean(l) for l in s.split('\n')]
    lines = [l for l in lines if l]
    return '\n'.join(lines) + '\n' if lines else ''


class Link:
    __slots__ = ('type', 'cid', 'num', 'date', 'nature', 'numtexte', 'text')

    def __init__(self, e: ET.Element):
        self.type = e.get('typelien') or ''
        self.cid = e.get('cidtexte') or ''
        self.num = (e.get('num') or '').strip()
        self.date = e.get('datesignatexte') or ''
        self.nature = e.get('naturetexte') or ''
        self.numtexte = (e.get('numtexte') or '').strip()
        self.text = clean(e.text or '')

    @property
    def ident(self) -> tuple[str, str]:
        return (self.cid or f'{self.nature}|{self.numtexte}|{self.date}', self.num)


class Version:
    __slots__ = ('id', 'num', 'd', 'f', 'etat', 'text', 'links', 'path', 'sha')

    def __init__(self, path: Path):
        raw = path.read_bytes()
        self.path = path
        self.sha = hashlib.sha256(raw).hexdigest()
        t = ET.fromstring(raw)
        m = t.find('META/META_SPEC/META_ARTICLE')
        self.id = t.findtext('META/META_COMMUN/ID')
        self.num = (m.findtext('NUM') or '').strip()
        self.d, self.f = m.findtext('DATE_DEBUT'), m.findtext('DATE_FIN')
        self.etat = m.findtext('ETAT') or ''
        c = t.find('BLOC_TEXTUEL/CONTENU')
        inner = ''
        if c is not None:
            inner = (c.text or '') + ''.join(ET.tostring(x, encoding='unicode') for x in c)
        self.text = text_of(inner)
        self.links = [Link(e) for e in t.iter('LIEN') if e.get('typelien') in CREATE | REMOVE]


def read_act(act: dict) -> list[Version]:
    return [Version(p) for p in sorted((LEGI / act['dir'] / 'article').glob('**/*.xml'))]


# ---------------------------------------------------------------- keys and labels

def unit_key(num: str, width: int) -> str:
    n = num.strip()
    if n.upper() == 'PREAMBULE':
        return 'preambule'
    m = re.fullmatch(r'([LRDA])?\*?\s*(\d+(?:-\d+)*)(?:\s*-?\s*([A-Za-z]+))?', n)
    if not m:
        return 'art-' + re.sub(r'[^a-z0-9]+', '-', n.lower()).strip('-')
    pre, nums, suf = m.groups()
    parts = nums.split('-')
    key = ('art-' if not pre else pre.lower() + '-') + '-'.join(
        [parts[0].zfill(width)] + [p.zfill(3) for p in parts[1:]])
    return key + ('-' + suf.lower() if suf else '')


def unit_label(num: str) -> str:
    return 'Préambule' if num.upper() == 'PREAMBULE' else f'Article {num}'


def fr_date(d: str) -> str:
    y, m, j = d.split('-')
    return f'{"1er" if j == "01" else str(int(j))} {MONTHS[int(m) - 1]} {y}'


class Laws:
    """Law records keyed by the amending text's cid; keys and labels depend only on that text's own data."""

    def __init__(self):
        self.seen: dict[str, list[Link]] = defaultdict(list)

    def note(self, l: Link):
        self.seen[l.ident[0]].append(l)

    def title_record(self, cid: str) -> dict | None:
        d = TEXTS / cid
        if not d.exists():  # a text built here keeps its own record with its articles
            d = LEGI / cid / 'texte' / 'version'
        if not d.exists():
            return None
        files = sorted(d.glob('*.xml'))
        pick = next((p for p in files if p.stem == cid), None)
        recs = []
        for p in ([pick] if pick else files):
            t = ET.parse(p).getroot()
            recs.append({'nature': t.findtext('META/META_COMMUN/NATURE') or '',
                         'num': (t.findtext('META/META_SPEC/META_TEXTE_CHRONICLE/NUM') or '').strip(),
                         'date': t.findtext('META/META_SPEC/META_TEXTE_CHRONICLE/DATE_TEXTE') or '',
                         'publi': t.findtext('META/META_SPEC/META_TEXTE_CHRONICLE/DATE_PUBLI') or '',
                         'title': clean(t.findtext('META/META_SPEC/META_TEXTE_VERSION/TITREFULL') or ''),
                         'debut': t.findtext('META/META_SPEC/META_TEXTE_VERSION/DATE_DEBUT') or ''})
        recs.sort(key=lambda r: (r['debut'], r['title']))
        return recs[0]

    def build(self) -> tuple[dict[str, str], dict[str, dict]]:
        """(ident -> key, key -> law record), deterministic: idents sorted, collisions get the cid's tail."""
        ident_key, laws = {}, {}
        for ident in sorted(self.seen):
            ls = self.seen[ident]
            rec = self.title_record(ident) if ident.startswith(('JORFTEXT', 'LEGITEXT')) else None
            nature = (rec or {}).get('nature') or Counter(l.nature for l in ls).most_common(1)[0][0]
            num = (rec or {}).get('num') or Counter(l.numtexte for l in ls).most_common(1)[0][0]
            date = (rec or {}).get('date') or max(l.date for l in ls)
            if nature == 'LOI' and any('constitutionnelle' in l.text.lower() for l in ls):
                nature = 'LOI_CONSTIT'
            if nature == 'LOI' and rec and rec['title'].lower().startswith('loi constitutionnelle'):
                nature = 'LOI_CONSTIT'
            prefix, label, kind = NATURE.get(nature, (re.sub(r'[^a-z0-9]+', '-', nature.lower()).strip('-') or 'texte',
                                                      nature.capitalize() or 'Texte', 'law'))
            if ident in REFERENDUM:
                kind = 'referendum'
            slug = re.sub(r'[^a-z0-9]+', '-', num.lower()).strip('-') if num else (date or 'sans-date')
            key = f'{prefix}-{slug}'
            if key in laws:
                key = f'{key}-{ident[-6:].lower()}'
            lab = f'{label} n° {num} du {fr_date(date)}' if num and date else (
                f'{label} du {fr_date(date)}' if date else ls[0].text.split(' - ')[0])
            title = (rec or {}).get('title') or ''
            title = re.sub(r'\s*\(\d+\)\s*$', '', title)
            publi = (rec or {}).get('publi') or ''
            laws[key] = {'label': lab, 'title': title, 'kind': kind, 'enacted': date or None,
                         'published': publi if publi and publi < OPEN else None,
                         'url': (f'https://www.legifrance.gouv.fr/jorf/id/{ident}' if ident.startswith('JORFTEXT') else
                                 f'https://www.legifrance.gouv.fr/loda/id/{ident}' if ident.startswith('LEGITEXT') else None),
                         'temporary_until': None, 'restores': None}
            ident_key[ident] = key
        return ident_key, laws


# ---------------------------------------------------------------- the crediting rule

def own(v: Version | None, types: set[str], self_ids: set[str]) -> list[Link]:
    if v is None:
        return []
    return [l for l in v.links if l.type in types and l.date and l.cid not in self_ids]


def inherited(prev: Version | None, self_ids: set[str]) -> set:
    """The amendment links the previous version already carried when it took effect."""
    return {l.ident for l in own(prev, CREATE | REMOVE, self_ids) if l.date <= prev.d} if prev else set()


def creators(v: Version, prev: Version | None, self_ids: set[str]) -> list[Link]:
    old = inherited(prev, self_ids)
    cands = [l for l in own(v, CREATE, self_ids) if l.date <= v.d and l.ident not in old]
    if not cands:
        return []
    top = max(l.date for l in cands)
    return [l for l in cands if l.date == top]


def removers(v: Version, prev: Version | None, self_ids: set[str], day: str) -> list[Link]:
    """A transfer link from the provision that created this version says it was moved here, not away, so it is left
    out; an explicit abrogation link from that same provision (a text that inserts an article and abrogates it from a
    later day, like loi n° 2016-1087 art. 4 for Code civil arts. 1386-19 to 1386-25) counts."""
    old = inherited(prev, self_ids)
    made = {l.ident for l in creators(v, prev, self_ids)}
    cands = [l for l in own(v, REMOVE, self_ids) if l.date <= day and l.ident not in old
             and not (l.ident in made and l.type not in ('ABROGATION', 'ABROGE'))]
    if not cands:
        return []
    top = max(l.date for l in cands)
    return [l for l in cands if l.date == top]


def abrogated_state(v: Version, prev: Version | None, self_ids: set[str]) -> list[Link]:
    """A version LEGI keeps after an abrogation, still holding the old words: ETAT abrogated, it follows the previous
    version without a gap and repeats its words, no new link created it, and an abrogation link, not inherited, was
    signed on or before its own first day. The article is absent from that day. (A version with new words, or one
    with a new creating link, that a text signed earlier abrogates later is an ordinary version: a deferred
    abrogation.)"""
    if not v.etat.startswith('ABROGE') or prev is None or prev.f != v.d or prev.text != v.text:
        return []
    if creators(v, prev, self_ids):
        return []
    old = inherited(prev, self_ids)
    cands = [l for l in own(v, {'ABROGATION', 'ABROGE'}, self_ids) if l.date <= v.d and l.ident not in old]
    if not cands:
        return []
    top = max(l.date for l in cands)
    return [l for l in cands if l.date == top]


# ---------------------------------------------------------------- one act

def build_act(act: dict, laws: Laws, log: dict) -> dict:
    vs = read_act(act)
    self_ids = {act['dir'], act['legitext']}
    stats = Counter()
    cases = defaultdict(list)
    by: dict[str, list[Version]] = defaultdict(list)
    for v in vs:
        if v.d >= v.f:  # never in force (MODIFIE_MORT_NE and the like)
            stats['never in force'] += 1
            continue
        by[v.num].append(v)
    width = max(3, max(len(re.match(r'\D*(\d*)', n).group(1)) for n in by))
    keys: dict[str, str] = {}
    for num in sorted(by):
        k = unit_key(num, width)
        if k in keys.values():
            k = k + '-' + hashlib.sha256(num.encode()).hexdigest()[:4]
            cases['key collision'].append(num)
        keys[num] = k

    # Segments per article: (start, end, kind, version, prev) with kind 'text' | 'placeholder'.
    segs: dict[str, list[tuple]] = {}
    removal_credit: dict[tuple[str, str], list[Link]] = {}   # (num, day) -> links
    for num, lst in by.items():
        lst.sort(key=lambda v: (v.d, v.f, v.id))
        clean_list = []
        for v in lst:
            if clean_list and clean_list[-1].d == v.d:
                cases['two versions start the same day (latest file id kept)'].append(f'{num} {v.d}')
                clean_list[-1] = v if v.id > clean_list[-1].id else clean_list[-1]
                continue
            clean_list.append(v)
        out = []
        abrogated = False  # the article was last seen abrogated (an abrogated-state version): a later gap is absence
        for i, v in enumerate(clean_list):
            prev = clean_list[i - 1] if i else None
            end = v.f
            if i + 1 < len(clean_list) and clean_list[i + 1].d < end:
                cases['overlapping versions (the later one wins)'].append(f'{num} {v.d}..{v.f} / {clean_list[i + 1].d}')
                end = clean_list[i + 1].d
            ab = abrogated_state(v, prev, self_ids)
            if ab:
                cases['abrogated-state versions (absent from their first day)'].append(f'{num} {v.d}')
                removal_credit[(num, v.d)] = ab
                abrogated = True
                continue
            if out and out[-1][1] < v.d and not abrogated:
                p = out[-1][3]
                if p.etat not in ENDED and p.f == out[-1][1]:
                    cases['gaps with no text (placeholder)'].append(f'{num} {out[-1][1]}..{v.d}')
                    out.append((out[-1][1], v.d, 'placeholder', p, None))
            out.append((v.d, end, 'text', v, prev))
            abrogated = False
            if not v.text:
                cases['versions with no text (shown as a placeholder)'].append(f'{num} {v.d}')
        segs[num] = out
        # a removal credit for the end of each text segment that no other segment follows on the same day
        for j, (s, e, kind, v, prev) in enumerate(out):
            if kind != 'text' or e >= OPEN:
                continue
            nxt = out[j + 1][0] if j + 1 < len(out) else None
            if nxt == e or (num, e) in removal_credit:
                continue
            removal_credit[(num, e)] = removers(v, prev, self_ids, e)

    # The day-by-day states, from the start date on.
    S = act['start']
    days = sorted({S} | {x for lst in segs.values() for s, e, *_ in lst for x in (s, e) if S < x < OPEN})

    def at(num: str, day: str):
        for seg in segs[num]:
            if seg[0] <= day < seg[1]:
                return seg
        return None

    units_prev: dict[str, dict] = {}
    files_prev: dict[str, str] = {}
    versions = []
    report = []
    for di, day in enumerate(days):
        units, files, which = {}, {}, {}
        for num in by:
            seg = at(num, day)
            if seg is None:
                continue
            k = keys[num]
            text = (seg[3].text if seg[2] == 'text' else '') or PLACEHOLDER
            units[k] = {'label': unit_label(num), 'kind': 'preamble' if k == 'preambule' else 'art', 'text': text}
            files[seg[3].id] = seg[3].sha
            which[k] = (num, seg)
        if di == 0:
            changes = dict(sorted(units.items()))
            credits = {}
        else:
            changed = sorted(k for k in set(units) | set(units_prev)
                             if units.get(k, {}).get('text') != units_prev.get(k, {}).get('text'))
            if not changed:
                units_prev, files_prev = units, files
                continue
            changes, credits = {}, {}
            num_of = {k: n for n, k in keys.items()}
            for k in changed:
                changes[k] = units.get(k)
                num = num_of[k]
                if k in units:
                    seg = which[k][1]
                    if seg[2] == 'placeholder':
                        ls, why = [], 'placeholder'
                    else:
                        ls = creators(seg[3], seg[4], self_ids)
                        why = 'new wording' if k in units_prev else 'inserted'
                else:
                    ls, why = removal_credit.get((num, day), []), 'removed'
                for l in ls:
                    laws.note(l)
                if ls:
                    credits[k] = sorted({l.ident[0] for l in ls})
                stats['changes'] += 1
                stats['credited' if ls else 'unexplained'] += 1
                report.append((day, k, why, ' | '.join(sorted({f'{l.type} {l.date} {l.text}' for l in ls})) or '-'))
        versions.append({'from': day, 'files': files, 'changes': changes, 'credits': credits})
        units_prev, files_prev = units, files

    log[act['slug']] = {'stats': dict(stats), 'cases': {k: v for k, v in sorted(cases.items())}, 'report': report}
    return {'act': act, 'versions': versions, 'keys': keys}


def version_sha(files: dict[str, str]) -> str:
    """sha256 of the manifest of the LEGI article files in force in this version: '<file id>\\t<sha256>\\n', sorted."""
    return hashlib.sha256(''.join(f'{i}\t{s}\n' for i, s in sorted(files.items())).encode()).hexdigest()


# ---------------------------------------------------------------- output

def country(art1: str) -> dict:
    return {
        'code': 'FR', 'name': 'France', 'slug': 'france', 'lang': 'fr', 'tz': 'Europe/Paris', 'future_branch': 'futur',
        'publisher': {'name': 'DILA (Légifrance, base LEGI)', 'email': 'legi@dila.invalid'},
        'default_in_force_rule': {
            'text': 'Code civil, art. 1er, alinéa 1er: "' + art1.split('\n')[0] + '" LEGI already applies this rule, '
                    'or the text\'s own entry-into-force clause, in each article version\'s DATE_DEBUT, which is used '
                    'as the in-force day.',
            'source': 'https://www.legifrance.gouv.fr/codes/article_lc/LEGIARTI000006419280'},
        'licence_note': 'Source : DILA, Légifrance, base LEGI (www.legifrance.gouv.fr), réutilisée sous la Licence '
                        'Ouverte / Open Licence 2.0 (Etalab).',
    }


def sources() -> list[dict]:
    plan = json.loads((CACHE / 'plan.json').read_text('utf-8'))
    reqs = (CACHE / 'requests.jsonl').read_text('utf-8').splitlines() if (CACHE / 'requests.jsonl').exists() else []
    return [{
        'name': 'DILA, base LEGI (Légifrance open data)',
        'url': plan['base'],
        'retrieved': DOCS_DATE,
        'requests': len(reqs),
        'licence': 'Licence Ouverte / Open Licence 2.0 (Etalab), https://www.etalab.gouv.fr/licence-ouverte-open-licence',
        'notes': f'The full dump {plan["files"][0]} and every daily increment after it, {len(plan["files"]) - 1} '
                 f'archives, the last {plan["files"][-1]}, replayed in order by extract.py (deletions listed in '
                 'liste_suppression_legi.dat first, then the archive\'s files). Every archive passed gzip -t; '
                 'sha256 per archive in .cache/extract.json.',
    }]


DECISIONS_COMMON = [
    'Source: the LEGI database of DILA (Légifrance), one XML file per article version with its in-force dates '
    '(DATE_DEBUT, DATE_FIN), its state (ETAT) and links to the texts that created, modified, abrogated or transferred '
    'it. Each version of an act here is the set of LEGI article versions in force on its day; its sha256 is that of '
    'the sorted manifest "<article version id> TAB <sha256 of the file>" of those files, and its source_url is '
    'Légifrance\'s reader for the act on that day.',
    'In-force dates: each change takes effect on the LEGI DATE_DEBUT of the new article version (or the DATE_FIN of '
    'the last one, for a removal). LEGI sets these from the amending text\'s own entry-into-force clause or, failing '
    'one, from Code civil art. 1er (the day after publication in the Journal officiel).',
    'Article versions whose DATE_DEBUT is on or after their DATE_FIN were never in force (ETAT MODIFIE_MORT_NE and '
    'the like) and are skipped.',
    'Credits come only from LEGI\'s own amendment links. A new wording is credited to the texts its article version '
    'links to as creating, modifying, transferring or moving it (CREATION/CREE, MODIFICATION/MODIFIE, '
    'TRANSFERT/TRANSFERE, DEPLACEMENT/DEPLACE, either direction of the link), signed on or before the day it took '
    'effect, leaving out every link the article\'s previous version already carried when it took effect (LEGI repeats '
    'an article\'s older links on its later versions); of those, only the latest signing date counts.',
    'A removal is credited to the removed version\'s own abrogation or transfer links (ABROGATION/ABROGE, '
    'TRANSFERT/TRANSFERE, DEPLACEMENT/DEPLACE) signed on or before the day it ended, leaving out inherited links and '
    'transfer links from the provision that created that version (they record the move in, not out); latest signing '
    'date only. An explicit abrogation link from the creating provision counts: loi n° 2016-1087 art. 4 inserted Code '
    'civil arts. 1386-19 to 1386-25 from 2016-08-10 and abrogated them from 2016-10-01.',
    'Anything those rules leave unexplained is committed as unexplained, by the publisher; no credit is guessed. '
    'Example of why inherited links are left out: Code civil art. 515-11 took a new wording on 2020-01-01; its links '
    'name loi n° 2019-1480 (signed 2019-12-28, already on the version of 2019-12-30) and ordonnance n° 2019-964 '
    'art. 35; only the ordonnance is credited, as LEGI\'s own note on that version says.',
    'An article version whose ETAT is abrogated, that follows the previous version without a gap and repeats its '
    'words, that no new link created, and whose abrogation link was signed on or before its own first day, is the '
    'record LEGI keeps after an abrogation, still holding the old words (for example Code civil art. 9 from '
    '1927-08-14 to 1970-07-19, abrogated by the loi du 10 août 1927): the article is absent from that day, the removal '
    'credited to that abrogation link.',
    'Where an article\'s version ends as modified (not abrogated or transferred) and its next version starts later, '
    'LEGI does not give the text in force in between: the article reads "' + PLACEHOLDER.strip() + '" for that '
    'period, unexplained, rather than keeping the old words or dropping the article.',
    'Two versions of one article overlapping in time: the later one wins from its first day. Two versions of one '
    'article starting the same day: the one with the later LEGI id is kept.',
    'Text: <p>, <div> and <br/> end a line; other markup is dropped; non-breaking spaces become spaces, soft hyphens '
    'are dropped, curly quotes become straight quotes, every dash and minus sign becomes "-", and runs of spaces '
    'collapse. NOTA (editorial notes) are not part of the text.',
    'Unit keys: art-<number> with the first number padded to the act\'s widest (at least 3 digits) and each further '
    'number to 3 (Code civil art. 515-11 is art-0515-011); a letter prefix (R, D, L) is the key prefix instead of '
    '"art" (Code pénal art. R610-1 is r-610-001); the preamble is preambule.',
    'Laws: each amending text is keyed by its nature and number (loi-2016-1547, ordonnance-2016-131, '
    'loi-constitutionnelle-2008-724, decision-2012-240-qpc), labelled from its own LEGI record (nature, number, '
    'signing date) and titled with its TITREFULL from the same dumps (extract.py --titles). Kinds: lois, lois '
    'organiques, lois constitutionnelles and ordonnances are laws; décrets, décrets-lois and arrêtés are decrees; '
    'Conseil constitutionnel decisions are court; the Constitution itself, loi n° 62-1292 (1962) and loi '
    'constitutionnelle n° 2000-964 (2000) were adopted by referendum. A text whose LEGI nature is LOI but whose own '
    'title (or link text) reads "loi constitutionnelle" is labelled a loi constitutionnelle (loi n° 2003-276, '
    'n° 2024-200).',
]


def write_json(path: Path, obj: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=1) + '\n', 'utf-8', newline='\n')
    os.replace(tmp, path)


def summarise(slug: str, info: dict) -> list[str]:
    out = []
    st = info['stats']
    out.append(f'{slug}: {st.get("changes", 0)} changed provisions after the first version, {st.get("credited", 0)} '
               f'credited to a text, {st.get("unexplained", 0)} unexplained (committed by the publisher).')
    for what, items in info['cases'].items():
        shown = ', '.join(items[:60]) + (f', and {len(items) - 60} more' if len(items) > 60 else '')
        out.append(f'{slug}: {len(items)} {what}: {shown}.')
    return out


def main(argv: list[str]) -> None:
    want = [a for a in argv if not a.startswith('--')]
    acts = [a for a in ACTS if not want or a['slug'] in want]
    laws = Laws()
    log: dict = {}
    built = [build_act(a, laws, log) for a in acts]
    for a in acts:  # the start laws and earlier laws need records too
        for cid in ([a['first_law_cid']] if a['first_law_cid'] else []) + a['earlier']:
            rec = laws.title_record(cid)
            if rec is None:
                sys.exit(f'{a["slug"]}: no LEGI title record for {cid} (run extract.py --titles)')
            fake = ET.Element('LIEN', {'typelien': 'CREATION', 'cidtexte': cid, 'datesignatexte': rec['date'],
                                       'naturetexte': rec['nature'], 'numtexte': rec['num']})
            laws.note(Link(fake))
    ident_key, all_laws = laws.build()
    art1 = next(v.text for v in read_act(next(a for a in ACTS if a['slug'] == 'code-civil'))
                if v.num == '1' and v.d <= DOCS_DATE < v.f)

    outputs: dict[str, dict] = {}
    for b in built:
        act = b['act']
        used = set()
        versions = []
        for i, v in enumerate(b['versions']):
            credits = {k: sorted(ident_key[c] for c in cs) for k, cs in v['credits'].items()}
            used.update(x for cs in credits.values() for x in cs)
            out = {'from': v['from'],
                   'source_url': f'https://www.legifrance.gouv.fr/{"codes/texte_lc" if act["part"] else "loda/id"}/'
                                 f'{act["legitext"]}/{v["from"]}',
                   'sha256': version_sha(v['files'])}
            if i == 0:
                out['units'] = v['changes']
            else:
                out['changes'] = v['changes']
                out['credits'] = credits
            if i == 0 and not act['first_law_cid']:
                out['note'] = START_REASONS[act['slug']]
            versions.append(out)
        first = ident_key[act['first_law_cid']] if act['first_law_cid'] else None
        earlier = [ident_key[c] for c in act['earlier']]
        used.update(x for x in [first, *earlier] if x)
        rec = {'slug': act['slug'], 'short': act['short'], 'title': act['title'], 'url': act['url'],
               'first_law': first, 'earlier_laws': earlier, 'versions': versions}
        info = log[act['slug']]
        decisions = [START_REASONS[act['slug']]] + summarise(act['slug'], info)
        part = act['part'] or 'corpus'
        o = outputs.setdefault(part, {'acts': [], 'laws': {}, 'decisions': []})
        o['acts'].append(rec)
        o['laws'].update({k: all_laws[k] for k in sorted(used)})
        o['decisions'] += decisions
        print(decisions[1], flush=True)
        if '--report' in argv:
            rp = HERE / '.tmp-build' / f'credits-{act["slug"]}.tsv'
            rp.parent.mkdir(exist_ok=True)
            rp.write_text(''.join('\t'.join(r) + '\n' for r in info['report']), 'utf-8', newline='\n')

    ai = ['none: no model wrote, chose or checked any legal text or credit. parse.py was written with Claude Code '
          '(Claude Opus 5.5, claude-opus-5-5); it runs no model.']
    if 'corpus' in outputs:
        o = outputs['corpus']
        o['laws'] = dict(sorted(o['laws'].items()))
        write_json(HERE / 'corpus.json', {'country': country(art1), 'sources': sources(), 'laws': o['laws'],
                                          'acts': o['acts'], 'applies': [],
                                          'decisions': DECISIONS_COMMON + o['decisions'], 'ai_use': ai})
    for part, o in outputs.items():
        if part == 'corpus':
            continue
        write_json(HERE / 'corpus.d' / f'{part}.json', {'laws': dict(sorted(o['laws'].items())), 'acts': o['acts'],
                                                        'decisions': o['decisions']})
    write_json(HERE / '.tmp-build' / 'parse-log.json', {k: {'stats': v['stats'], 'cases': v['cases']} for k, v in log.items()})


if __name__ == '__main__':
    main(sys.argv[1:])
