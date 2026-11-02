"""Rebuilds the history of a law or code from IMPO's consolidated text and IMPO's own notes.

IMPO (www.impo.com.uy/bases) gives, for each norm, the text in force today and, per article, notes such as

    Inciso 2º) redacción dada por: Ley Nº 18.719 de 27/12/2010 artículo 152.
    Literal Ñ) agregado/s por: Ley Nº 19.924 de 18/12/2020 artículo 86.
    Derogado/s por: Ley Nº 19.075 de 03/05/2013 artículo 26.
    TEXTO ORIGINAL: Ley Nº 18.331 de 11/08/2008 artículo 35.

with a link to the article as originally published (/bases/leyes-originales/...). Each article's history is the
original text, then one text per amending law in the order the laws took effect, ending with today's text.
Intermediate texts (an article amended by two or more laws on different days) are rebuilt only when IMPO's notes say
exactly what the later law did:

  * a later law *added* a lettered or numbered item: the earlier text is the later one without that item;
  * a later law gave a new wording to an item of an article an earlier law had rewritten whole, and IMPO links the
    earlier law's article as a TEXTO ORIGINAL: the earlier text is the one that law quotes.

Anything else is reported in the verification output and the article's intermediate text is not invented: the
article then changes once, on the last law's day, credited to all the laws IMPO names.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import re
from dataclasses import dataclass, field

import fetch
from parse_text import impo_paragraphs, key_of, norm, strip_tags, wrap_width

KIND = {'redacción dada por': 'wording', 'redacción dada anteriormente por': 'wording-earlier',
        'agregado/s por': 'added', 'anteriormente agregado/s por': 'added-earlier',
        'derogado/s por': 'repealed', 'ver vigencia': 'vigencia'}
NOTE = re.compile(r'(?P<kind>redacción dada anteriormente por|redacción dada por|anteriormente agregado/s por|'
                  r'agregado/s por|derogado/s por|ver vigencia):\s*'
                  r'(?P<refs>(?:,?\s*(?:y\s+)?Ley Nº [\d.]+ de \d\d/\d\d/\d{4}\s+artículos?\s+[\d\s,y]+)+)', re.I)
REF = re.compile(r'Ley Nº (?P<n>[\d.]+) de (?P<d>\d\d)/(?P<m>\d\d)/(?P<y>\d{4})\s+artículos?\s+(?P<a>\d+)')


@dataclass
class Event:
    kind: str
    scope: str            # '' for the whole article, else e.g. 'Literal Ñ)', 'Inciso 2º)'
    law: str              # '18719'
    year: str
    art: str


@dataclass
class Article:
    key: str
    label: str
    current: list[str]
    events: list[Event] = field(default_factory=list)
    originals: list[tuple[str, str, str]] = field(default_factory=list)   # (law, year, art) under TEXTO ORIGINAL


def note_text(html: str) -> str:
    t = strip_tags(html.replace('<br>', '\n'))
    t = t.replace('\r\n', '\n')
    return re.sub(r'[ \t]+', ' ', t)


def parse_notes(html: str) -> tuple[list[Event], list[tuple[str, str, str]]]:
    t = note_text(html)
    events: list[Event] = []
    head, _, orig = t.partition('TEXTO ORIGINAL:')
    flat = re.sub(r'\s+', ' ', head)
    for m in NOTE.finditer(flat):
        before = flat[:m.start()]
        scope = re.split(r'(?<=\.)\s|\n', before)[-1].strip()
        scope = scope if re.match(r'(Inciso|Literal|Literales|Numeral|Numerales|Apartado|Párrafo)', scope) else ''
        kind = KIND[m.group('kind').lower()]
        # "Ver vigencia: Ley Nº 19.920 … artículo 62 (La Ley Nº 19.920 … artículo 62, derogó la Ley … que agregaba
        # … los artículos 2393 a 2405)": the article was repealed by that law, though IMPO keeps its text.
        if kind == 'vigencia' and re.match(r'\s*\([^)]*derog[óo]', flat[m.end():]):
            kind = 'repealed'
        for r in REF.finditer(m.group('refs')):
            events.append(Event(kind, scope, r.group('n').replace('.', ''), r.group('y'), r.group('a')))
    originals = [(r.group('n').replace('.', ''), r.group('y'), r.group('a')) for r in REF.finditer(orig)]
    return events, originals


def unit_key(nro: str, sec: str, pad: int = 3) -> str:
    sec = sec.strip().lower()
    return f'art-{int(nro):0{pad}d}' + (f'-{sec}' if sec else '')


def unit_label(nro: str, sec: str) -> str:
    return f'Artículo {int(nro)}' + (f' {sec.strip().upper()}' if sec.strip() else '')


def load(path: str, offline: bool = True) -> dict:
    return fetch.impo_json(fetch.impo(path), offline)


def load_cached(path: str) -> dict | None:
    try:
        return load(path)
    except FileNotFoundError:
        return None


def articles(main: dict) -> tuple[list[Article], int]:
    width = wrap_width([a['textoArticulo'] for a in main['articulos']])
    pad = max(3, len(str(max(int(a['nroArticulo']) for a in main['articulos']))))
    out = []
    for a in main['articulos']:
        ev, orig = parse_notes(a.get('notasArticulo') or '')
        hrefs = re.findall(r'href="(/bases/[^"]+)"', (a.get('notasArticulo') or '').partition('TEXTO ORIGINAL')[2])
        art = Article(unit_key(a['nroArticulo'], a['secArticulo'], pad), unit_label(a['nroArticulo'], a['secArticulo']),
                      impo_paragraphs(a['textoArticulo'], width), ev, orig)
        art.original_hrefs = hrefs
        art.nro = a['nroArticulo']
        art.sec = a['secArticulo'].strip().lower()
        out.append(art)
    return out, width


# ---------------------------------------------------------------- dates

def ddmmyyyy(s: str) -> str:
    d, m, y = s.strip().split('/')
    return f'{y}-{m}-{d}'


def plus_days(day: str, n: int) -> str:
    return (dt.date.fromisoformat(day) + dt.timedelta(days=n)).isoformat()


VIGENCIA = re.compile(r'regir[áa] a partir del? (?:d[íi]a )?(\d+)[º°]? de (\w+) de (\d{4})', re.I)
NUMBERS = {'diez': 10, 'quince': 15, 'veinte': 20, 'treinta': 30, 'sesenta': 60, 'noventa': 90,
           'ciento veinte': 120, 'ciento ochenta': 180}
RELATIVE = re.compile(r'entrar[áa] en (?:vigencia|vigor) (?:a los )?(\d+|diez|quince|veinte|treinta|sesenta|noventa|'
                      r'ciento veinte|ciento ochenta)(?: \([a-z ]+\))? días (?:de|después de) su '
                      r'(promulgación|publicación)', re.I)
MONTHS = {'enero': 1, 'febrero': 2, 'marzo': 3, 'abril': 4, 'mayo': 5, 'junio': 6, 'julio': 7, 'agosto': 8,
          'setiembre': 9, 'septiembre': 9, 'octubre': 10, 'noviembre': 11, 'diciembre': 12}


def in_force(header: dict, vigencia_text: str | None) -> tuple[str, str]:
    """(in-force day, how it was found) for a law, from its own vigencia article or the default rule."""
    if vigencia_text:
        t = re.sub(r'\s+', ' ', vigencia_text)
        m = VIGENCIA.search(t)
        if m:
            return (f'{m.group(3)}-{MONTHS[m.group(2).lower()]:02d}-{int(m.group(1)):02d}',
                    f'its vigencia article: "{m.group(0)}"')
        m = re.search(r'entrar[áa] en (?:vigencia|vigor) desde su promulgaci[óo]n', t, re.I)
        if m:
            return ddmmyyyy(header['fechaPromulgacion']), f'its vigencia article: "{m.group(0)}"'
        m = RELATIVE.search(t)
        if m:
            n = int(m.group(1)) if m.group(1).isdigit() else NUMBERS[m.group(1).lower()]
            ref = 'fechaPromulgacion' if m.group(2).lower().startswith('promulga') else 'fechaPublicacion'
            return plus_days(ddmmyyyy(header[ref]), n), f'its vigencia article: "{m.group(0)}"'
    pub = ddmmyyyy(header['fechaPublicacion'])
    return plus_days(pub, 10), f'published {pub}; Código Civil art. 1: ten days after publication'


# ---------------------------------------------------------------- items

ITEM = re.compile(r"^(?:(\d+)\s?[º°o]?[).]|([A-ZÑa-zñ])\))")


def scope_marker(scope: str) -> str | None:
    """'Literal Ñ)' -> 'Ñ', 'Numeral 5)' -> '5'; None for incisos and compound scopes."""
    m = re.fullmatch(r'(?:Literal|Numeral|Apartado) ([0-9]+|[A-ZÑ])[º°]?\)', scope.strip())
    return m.group(1) if m else None


def item_index(paras: list[str], marker: str) -> int | None:
    hits = [i for i, p in enumerate(paras) if (m := ITEM.match(p)) and (m.group(1) or m.group(2)) == marker]
    return hits[0] if len(hits) == 1 else None


def quoted_article(law_text: str, art: str, width: int, sec: str = '') -> list[str] | None:
    """The new wording an amending article gives to article `art`: the quoted block that opens with
    "ARTICULO <art>." (IMPO's original of the amending law)."""
    t = law_text.replace('\r\n', '\n')
    num = art + (r'\s*' + sec if sec else r'(?!\d)(?![º°]?\s*(?:bis|ter|quater)\b)')
    m = re.search(r'"?\s*(?:ART[IÍ]CULO|Art[íi]culo)\s+' + num + r'[º°]?\.?\s*-?\s*', t, re.I if sec else 0)
    if not m or '"' not in t[:m.start() + 1]:
        return None
    rest = t[m.end():]
    end = re.search(r'"\s*(?:\.|\n\s*\n|$)|\n\s*"?\s*(?:ART[IÍ]CULO|Art[íi]culo)\s+\d+', rest)   # the quote closes, or the next article
    body = rest[:end.start()] if end else rest
    if re.match(r'Inciso', body.strip()):
        return None                 # only one inciso is quoted
    return impo_paragraphs(body, width)


def inciso_no(scope: str) -> int | None:
    m = re.fullmatch(r'Inciso (\d+)[º°]?\)?', scope.strip())
    return int(m.group(1)) if m else None


def top_level_index(paras: list[str], n: int) -> int | None:
    """Where inciso n goes: the index of the n-th paragraph that is not an item, or the end."""
    tops = [i for i, p in enumerate(paras) if not ITEM.match(p)]
    if n - 1 < len(tops):
        return tops[n - 1]
    return len(paras) if n - 1 == len(tops) else None


def quoted_paragraphs(law_text: str, width: int) -> list[str] | None:
    """The one quoted passage of an amending article ("… el siguiente inciso: "…"")."""
    quotes = re.findall(r'"\s*(.*?)"', law_text.replace('\r\n', '\n'), re.S)
    return impo_paragraphs(quotes[0], width) if len(quotes) == 1 else None


def quoted_item(law_text: str, marker: str, width: int) -> str | None:
    """The new wording of one item ("Sustitúyese el numeral 3º) ... por el siguiente: "3º) ...""): the quoted
    paragraph that opens with that item's marker."""
    t = law_text.replace('\r\n', '\n')
    for m in re.finditer(r'"\s*(.*?)"', t, re.S):
        ps = impo_paragraphs(m.group(1), width)
        if len(ps) == 1 and (im := ITEM.match(ps[0])) and (im.group(1) or im.group(2)) == marker:
            return ps[0]
    return None


# ---------------------------------------------------------------- what to fetch

def law_path(law: str, year: str, art: str | None = None, original: bool = False) -> str:
    base = f'{"leyes-originales" if original else "leyes"}/{law}-{year}'
    return f'{base}/{art}' if art else base


def amending_laws(arts: list[Article], base: str) -> dict[str, dict]:
    """law -> {'year', 'arts': set of amending article numbers, 'vigencia': article number or None}."""
    laws: dict[str, dict] = {}
    for a in arts:
        for e in a.events:
            if e.law == base:
                continue
            d = laws.setdefault(e.law, {'year': e.year, 'arts': set(), 'vigencia': None})
            if e.kind == 'vigencia':
                d['vigencia'] = e.art
            else:
                d['arts'].add(e.art)
    return laws


def needed_paths(main: dict, base: str, vigencia_arts: dict[str, str]) -> list[str]:
    arts, _ = articles(main)
    paths: list[str] = []
    for a in arts:
        if any(e.law != base and e.kind != 'vigencia' for e in a.events):
            paths += [h.removeprefix('/bases/') for h in a.original_hrefs]
        # an article amended by two or more laws: each amending article as published, for the wording it gives
        evs = [e for e in a.events if e.law != base and e.kind != 'vigencia']
        if len({e.law for e in evs}) > 1:
            paths += [law_path(e.law, e.year, e.art, original=True) for e in evs if e.kind != 'repealed']
        # incisos or paragraphs a law added: its article as published, to take them out again
        paths += [law_path(e.law, e.year, e.art, original=True) for e in evs
                  if e.kind in ('added', 'added-earlier') and e.scope and not scope_marker(e.scope)]
    for law, d in sorted(amending_laws(arts, base).items()):
        if not d['arts'] and not d['vigencia']:
            continue
        paths.append(law_path(law, d['year'], min(d['arts'], key=int) if d['arts'] else d['vigencia']))
        vig = d['vigencia'] or vigencia_arts.get(law)
        if vig:
            paths.append(law_path(law, d['year'], vig))
    # each amending law whole, to find its vigencia article by hand (vigencia_candidates)
    paths += [law_path(law, d['year']) for law, d in sorted(amending_laws(arts, base).items()) if d['arts']]
    seen, out = set(), []
    for p in paths:
        if p not in seen:
            seen.add(p)
            out.append(p)
    return out


# ---------------------------------------------------------------- the history of one act

def law_key(law: str) -> str:
    return f'ley-{law}'


def law_label(law: str) -> str:
    return f'Ley Nº {int(law):,}'.replace(',', '.')


def render(label: str, paras: list[str]) -> str:
    return f'# {label}\n' + ''.join(p + '\n' for p in paras)


HEADING = re.compile(r'(CAP[IÍ]TULO|SECCI[OÓ]N|T[IÍ]TULO|LIBRO|PARTE)\b')


INDEX = re.compile(r'(?:\* )?(?:Libro|Título|Capítulo|Sección) [IVXLC]+\b')


def drop_headings(paras: list[str]) -> list[str]:
    """IMPO's original texts carry the next chapter's heading at the end of an article (and, for the Código Penal's
    art. 1, the code's table of books and titles at its start)."""
    return [x for x in paras if not (HEADING.match(x) and x.upper() == x) and not (INDEX.match(x) and len(x) < 200)]


def without_items(paras: list[str], markers: list[str]) -> list[str] | None:
    out = list(paras)
    for mk in markers:
        i = item_index(out, mk)
        if i is None:
            return None
        del out[i]
    return out


def title_case(s: str) -> str:
    return re.sub(r'\s+', ' ', norm(s)).strip()


UNKNOWN = object()


def build_act(*, slug: str, short: str, title: str, path: str, base: str,
              vigencia_arts: dict[str, str], verification: dict,
              base_is_enactment: bool = True, base_in_force: tuple[str, str] | None = None) -> tuple[dict, dict]:
    """The laws and the act (SCHEMA.md) for the norm at IMPO `path`, whose own law is `base` (e.g. '18331')."""
    raw_main = fetch.fetch(fetch.impo(path), True)
    main = fetch.impo_json(fetch.impo(path), True)
    arts, width = articles(main)
    amend = amending_laws(arts, base)

    laws: dict[str, dict] = {}
    day_of: dict[str, str] = {}
    how: dict[str, str] = {}
    base_day, base_how = base_in_force or in_force(main, None)
    for law, d in sorted(amend.items()):
        if not d['arts']:
            continue
        hdr = load(law_path(law, d['year'], min(d['arts'], key=int)))
        vig = d['vigencia'] or vigencia_arts.get(law)
        vtext = load(law_path(law, d['year'], vig)).get('textoArticulo') if vig else None
        day_of[law], how[law] = in_force(hdr, vtext)
        if vig:
            how[law] += f' (artículo {vig})'
        laws[law_key(law)] = {
            'label': law_label(law), 'title': title_case(hdr.get('nombreNorma') or law_label(law)),
            'kind': 'law', 'enacted': ddmmyyyy(hdr['fechaPromulgacion']) if hdr.get('fechaPromulgacion') else None,
            'published': ddmmyyyy(hdr['fechaPublicacion']), 'url': f'{fetch.IMPO}/{law_path(law, d["year"])}',
            'temporary_until': None, 'restores': None, 'note': None}
    laws[law_key(base)] = {
        'label': law_label(base), 'title': title, 'kind': 'law',
        'enacted': ddmmyyyy(main['fechaPromulgacion']) if main.get('fechaPromulgacion') else None,
        'published': ddmmyyyy(main['fechaPublicacion']) if re.match(r'\d\d/\d\d/\d{4}$', main.get(
            'fechaPublicacion', '')) else None, 'url': f'{fetch.IMPO}/{path}',
        'temporary_until': None, 'restores': None, 'note': None}

    report: dict[str, dict] = {}
    chains: dict[str, list[tuple[str, list[str] | None, list[str]]]] = {}   # key -> [(day, paras or None, laws)]
    labels = {a.key: a.label for a in arts}
    for a in arts:
        # laws in force before the norm's own day are already in its text
        evs = [e for e in a.events if e.law != base and e.kind != 'vigencia' and e.law in day_of
               and day_of[e.law] > base_day]
        if not evs:
            chains[a.key] = [(base_day, a.current or None, [])]   # empty: repealed before the norm's first day
            continue
        order = sorted({e.law for e in evs}, key=lambda l: (day_of[l], int(l)))
        repealed = any(e.kind == 'repealed' and not e.scope for e in evs)
        # texts[j] is the text before order[j] took effect; texts[-1] is today's (None once repealed).
        texts: list = [UNKNOWN] * len(order) + [None if repealed or not a.current else a.current]
        how_built: list[str] = [''] * len(order)
        for j in range(len(order) - 1, -1, -1):
            law = order[j]
            lev = [e for e in evs if e.law == law]
            later = texts[j + 1]
            if j == 0 and any(e.kind in ('added', 'added-earlier') and not e.scope for e in lev):
                texts[0], how_built[0] = None, 'added by this law'
                continue
            if j == 0 and a.key.rsplit('-', 1)[-1] in ('bis', 'ter', 'quater') and not any(
                    f'/{base}-' in h for h in a.original_hrefs):
                texts[0], how_built[0] = None, 'a BIS article, not in the original text: added by this law'
                continue
            if later not in (None, UNKNOWN) and lev and all(
                    e.kind in ('added', 'added-earlier') and e.scope and not scope_marker(e.scope) for e in lev):
                t = list(later)
                for e in lev:
                    o = load_cached(law_path(e.law, e.year, e.art, original=True))
                    q = quoted_paragraphs(o['textoArticulo'], width) if o else None
                    keys = [key_of(x) for x in q] if q else None
                    hit = next((i for i in range(len(t) - len(keys) + 1)
                                if [key_of(x) for x in t[i:i + len(keys)]] == keys), None) if keys else None
                    if hit is None:
                        t = None
                        break
                    del t[hit:hit + len(keys)]
                if t is not None:
                    texts[j] = t
                    how_built[j] = 'the later text without what this law added: ' + ', '.join(
                        f'{e.scope} ({law_label(e.law)} art. {e.art})' for e in lev)
                    continue
            if all(e.kind == 'repealed' and not e.scope for e in lev) and a.current and j == len(order) - 1:
                texts[j], how_built[j] = a.current, 'the text IMPO still prints for the repealed article'
                continue
            if j == 0:
                href = next((h for h in a.original_hrefs if f'/{base}-' in h), None)
                if href:
                    texts[0] = drop_headings(impo_paragraphs(load(href.removeprefix('/bases/'))['textoArticulo'], width))
                    how_built[0] = f'IMPO original text ({href})'
                    continue
            if later not in (None, UNKNOWN) and all(
                    e.kind in ('added', 'added-earlier') and scope_marker(e.scope) for e in lev):
                t = without_items(later, [scope_marker(e.scope) for e in lev])
                if t is not None:
                    texts[j] = t
                    how_built[j] = 'the later text without the items this law added: ' + ', '.join(
                        e.scope for e in lev)
                    continue
            if j:
                srcs = [(l, y, n) for l, y, n in a.originals if l == order[j - 1]]
                srcs += [(e.law, e.year, e.art) for e in evs if e.law == order[j - 1] and not e.scope
                         and e.kind in ('wording', 'wording-earlier')]
                for src in srcs:
                    o = load_cached(law_path(*src, original=True))
                    t = quoted_article(o['textoArticulo'], a.nro, width, a.sec) if o else None
                    if t:
                        texts[j] = drop_headings(t)
                        how_built[j] = f'the wording {law_label(src[0])} art. {src[2]} gives it (IMPO original)'
                        break
        # Forward: an earlier law that gave new wording to single items of a known text.
        for j in range(1, len(order)):
            if texts[j] is not UNKNOWN or texts[j - 1] in (None, UNKNOWN):
                continue
            lev = [e for e in evs if e.law == order[j - 1]]
            if lev and all(e.kind in ('added', 'added-earlier') and inciso_no(e.scope) for e in lev):
                # an earlier law that added incisos ("Agrégase … el siguiente inciso: "…""): insert the quoted
                # inciso at the place IMPO's note gives
                t = list(texts[j - 1])
                for e in sorted(lev, key=lambda e: inciso_no(e.scope)):
                    o = load_cached(law_path(e.law, e.year, e.art, original=True))
                    q = quoted_paragraphs(o['textoArticulo'], width) if o else None
                    pos = top_level_index(t, inciso_no(e.scope))
                    if not q or pos is None:
                        t = None
                        break
                    t[pos:pos] = q
                if t is not None:
                    texts[j] = t
                    how_built[j] = 'the earlier text with ' + ', '.join(
                        f'{e.scope} as {law_label(e.law)} art. {e.art} adds it' for e in lev)
                continue
            if not lev or not all(e.kind in ('wording', 'wording-earlier') and scope_marker(e.scope) for e in lev):
                continue
            t = list(texts[j - 1])
            for e in lev:
                o = load_cached(law_path(e.law, e.year, e.art, original=True))
                item = quoted_item(o['textoArticulo'], scope_marker(e.scope), width) if o else None
                i = item_index(t, scope_marker(e.scope))
                if item is None or i is None:
                    t = None
                    break
                t[i] = item
            if t is not None:
                texts[j] = t
                how_built[j] = 'the earlier text with the items ' + ', '.join(
                    f'{e.scope} as {law_label(e.law)} art. {e.art} words them' for e in lev)
        # A text that no source gives is not invented: the change is shown on the next day whose text is known,
        # credited to every law in between; with no known start, the article keeps today's text throughout.
        if texts[0] is UNKNOWN:
            chains[a.key] = [(base_day, a.current, [])]
            report[a.key] = {'laws': [law_label(l) for l in order],
                             'unresolved': 'no original text; today\'s text is used from the start'}
            continue
        chain = [(base_day, texts[0], [])]
        pending: list[str] = []
        for j, law in enumerate(order):
            pending.append(law_key(law))
            if texts[j + 1] is UNKNOWN:
                continue
            chain.append((day_of[law], texts[j + 1], pending))
            pending = []
        chains[a.key] = chain
        report[a.key] = {'laws': [law_label(l) for l in order],
                         'earliest_text': how_built[0] or 'today\'s text',
                         'intermediate': {law_label(order[j]): (how_built[j] or 'unknown: change shown later')
                                          for j in range(1, len(order))},
                         'steps': [{'day': d, 'laws': ls,
                                    'diff': _diff(chain[i][1], c) if chain[i][1] is not None and c is not None
                                    else ('added' if c is not None else 'removed')}
                                   for i, (d, c, ls) in enumerate(chain[1:])]}

    days = sorted({d for c in chains.values() for d, _, _ in c})
    digest = hashlib.sha256(raw_main).hexdigest()
    versions, prev_units = [], {}
    for day in days:
        units, credits = {}, {}
        for key, chain in chains.items():
            cur = [c for c in chain if c[0] <= day]
            if not cur:
                continue
            d, paras, ls = cur[-1]
            if paras is not None:
                units[key] = {'label': labels[key], 'kind': 'art', 'text': render(labels[key], paras)}
            if d == day and ls:
                credits[key] = list(ls)
        changed = {k for k in set(units) | set(prev_units)
                   if units.get(k, {}).get('text') != prev_units.get(k, {}).get('text')}
        versions.append({'from': day, 'source_url': f'{fetch.IMPO}/{path}', 'sha256': digest,
                         'units': dict(sorted(units.items())),
                         'credits': {k: v for k, v in sorted(credits.items()) if k in changed}, 'note': None})
        prev_units = units
    versions[0]['note'] = ('Rebuilt from IMPO: the original text of every article IMPO marks as amended, and '
                           'today\'s text of every other article.')
    if len(versions) > 1:
        versions[-1]['note'] = 'Today\'s text: IMPO\'s consolidated text.'
    verification[slug] = {
        'in_force': {law_label(l): {'day': day_of[l], 'how': how[l]} for l in sorted(day_of)},
        'base_in_force': {'day': base_day, 'how': base_how},
        'articles': report,
        'last_version_equals_impo': all(
            versions[-1]['units'].get(a.key, {}).get('text') == render(a.label, a.current)
            for a in arts if a.current and not any(e.kind == 'repealed' and not e.scope for e in a.events))}
    act = {'slug': slug, 'short': short, 'title': title, 'url': f'{fetch.IMPO}/{path}',
           'first_law': law_key(base) if base_is_enactment else None,
           'earlier_laws': [] if base_is_enactment else [law_key(base)], 'versions': versions}
    used = {l for v in versions for ls in v['credits'].values() for l in ls} | {law_key(base)}
    return {k: v for k, v in laws.items() if k in used}, act


def _diff(a: list[str], b: list[str]) -> list[str]:
    import difflib
    wa, wb = ' '.join(a).split(), ' '.join(b).split()
    out = []
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(None, wa, wb, autojunk=False).get_opcodes():
        if op != 'equal':
            out.append(f'{op}: {" ".join(wa[i1:i2])[:200]!r} -> {" ".join(wb[j1:j2])[:200]!r}')
    return out


def vigencia_candidates(law_json: dict) -> list[tuple[str, str]]:
    """Articles of a law that speak of its entry into force, for choosing a vigencia article by hand."""
    out = []
    for a in law_json.get('articulos', []):
        t = ' '.join(a['textoArticulo'].split())
        if re.search(r'(?i)(presente ley|esta ley)[^.]{0,80}(regir|entrar|vigencia|vigor)|'
                     r'(regir|entrar)[^.]{0,40}(vigencia|vigor)', t):
            out.append((a['nroArticulo'], t[:300]))
    return out
