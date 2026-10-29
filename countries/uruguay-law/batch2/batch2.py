"""Batch 2 of the Uruguayan codes: writes scripts/uruguay-law/corpus.d/50-batch2.json (gitlaw_common/SCHEMA.md).

    python -X utf8 scripts/uruguay-law/batch2/batch2.py

Reads only the shared .cache (fetched by batch2/fetch2.py). Each code is rebuilt by the main agent's
impo_history.build_act (imported, not copied) from IMPO's consolidated text and IMPO's per-article notes, with each
in-force day taken from the amending law's own vigencia article. This module adds only:

  * two readings of IMPO's notes that impo_history does not know (NOTE_KINDS, scope words such as "Ordinal"),
  * a post-pass over the rebuilt versions: an article IMPO says was repealed and later given new wording is absent in
    between, and the anachronism rule (BRIEF.md, 2026-10-28) is applied to every unit,
  * the verification that today's text equals IMPO's consolidated text, unit for unit.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
UY = HERE.parent
sys.path.insert(0, str(UY))
import fetch  # noqa: E402
import impo_history as ih  # noqa: E402

# ---------------------------------------------------------------- readings of IMPO's notes

# Kinds of note impo_history does not parse; added to its tables so that the laws they name enter the history.
DECREE_LAWS: set[str] = set()
NOTE_KINDS = {'derogado anteriormente por': 'repealed-earlier', 'derogado/s anteriormente por': 'repealed-earlier',
              'redacción derogada por': 'wording-repealed',
              'reincorporado por': 'wording'}     # an article repealed earlier and put back: today's words


def _install_note_readings() -> None:
    if getattr(ih, '_batch2', False):
        return
    ih._batch2 = True
    ih.KIND.update(NOTE_KINDS)
    kinds = sorted(ih.KIND, key=len, reverse=True)
    ih.NOTE = re.compile('(?P<kind>' + '|'.join(re.escape(k) for k in kinds) + r'):\s*'
                         r'(?P<refs>(?:,?\s*(?:y\s+)?(?:Decreto[ -])?Ley Nº [\d.]+ de \d\d/\d\d/\d{4}\s+'
                         r'artículos?\s+[\d\s,y]+)+)', re.I)

    # Decree-laws (1973-1985) are numbered in the laws' own series; IMPO keeps them under decretos-ley/. A number a
    # note calls "Decreto Ley Nº" gets its own key, label and IMPO path.
    orig_parse_notes, orig_key, orig_label, orig_path = ih.parse_notes, ih.law_key, ih.law_label, ih.law_path

    def parse_notes(html: str):
        DECREE_LAWS.update(n.replace('.', '') for n in re.findall(r'Decreto[ -]Ley\s+Nº\s*([\d.]+)', html or ''))
        return orig_parse_notes(html)

    def law_key(law: str) -> str:
        return f'decreto-ley-{law}' if law in DECREE_LAWS else orig_key(law)

    def law_label(law: str) -> str:
        return orig_label(law).replace('Ley Nº', 'Decreto-Ley Nº') if law in DECREE_LAWS else orig_label(law)

    def law_path(law: str, year: str, art: str | None = None, original: bool = False) -> str:
        if law not in DECREE_LAWS:
            return orig_path(law, year, art, original)
        base = f'{"decretos-leyes-originales" if original else "decretos-ley"}/{law}-{year}'
        return f'{base}/{art}' if art else base

    ih.parse_notes, ih.law_key, ih.law_label, ih.law_path = parse_notes, law_key, law_label, law_path
    orig_note_text = ih.note_text

    def note_text(html: str) -> str:
        # The CGP and the CPP number their paragraphs "ordinales" (547.1, 547.2); IMPO's notes scope changes to
        # them ("Ordinal 1º) inciso 2º) agregado/s por"). impo_history knows only Inciso/Literal/Numeral/Apartado
        # scopes and would read an unknown scope as the whole article, so "Ordinal" is read as an Apartado scope
        # that names no single item (no item marker is derived from it).
        return re.sub(r'\b[Oo]rdinal(es)?\b', lambda m: 'Apartado ordinal' + (m.group(1) or ''), orig_note_text(html))

    ih.note_text = note_text

    # Vigencia wordings impo_history.in_force does not read; tried first, else impo_history's own reading.
    orig_in_force = ih.in_force

    def in_force(header: dict, vigencia_text: str | None) -> tuple[str, str]:
        law = str(header.get('nroNorma') or '').replace('.', '')
        if law in LAW_DAY:
            return LAW_DAY[law]
        if vigencia_text:
            t = ' '.join(vigencia_text.split())
            m = EXTRA_DATE.search(t)
            if m and m.group(2).lower() in ih.MONTHS:
                return (f'{m.group(3)}-{ih.MONTHS[m.group(2).lower()]:02d}-{int(m.group(1)):02d}',
                        f'its vigencia article: "{m.group(0)}"')
            m = EXTRA_PROMULGATION.search(t)
            if m and header.get('fechaPromulgacion'):
                return ih.ddmmyyyy(header['fechaPromulgacion']), f'its vigencia article: "{m.group(0)}"'
        if not re.fullmatch(r'\s*\d\d/\d\d/\d{4}\s*', header.get('fechaPublicacion') or '') and re.fullmatch(
                r'\s*\d\d/\d\d/\d{4}\s*', header.get('fechaPromulgacion') or ''):
            # old laws IMPO gives no publication day for: Código Civil art. 1 counts the ten days from promulgation
            r = orig_in_force(dict(header, fechaPublicacion=header['fechaPromulgacion']), vigencia_text)
            if r[1].startswith('published'):
                prom = ih.ddmmyyyy(header['fechaPromulgacion'])
                r = (r[0], f'promulgated {prom}, no publication day in IMPO; Código Civil art. 1: ten days after '
                           f'promulgation')
            return r
        return orig_in_force(header, vigencia_text)

    ih.in_force = in_force

    # Old laws (before ~1900) have no publication day in IMPO ("No fue publicado", or no field): their law entry
    # gets published: null instead of a crash.
    orig_ddmmyyyy, orig_load = ih.ddmmyyyy, ih.load

    def ddmmyyyy(s: str | None) -> str | None:
        return orig_ddmmyyyy(s) if re.fullmatch(r'\s*\d\d/\d\d/\d{4}\s*', s or '') else None

    def load(path: str, offline: bool = True) -> dict:
        try:
            d = orig_load(path, offline)
        except json.JSONDecodeError:
            # IMPO answers 200 with an HTML page where it has no such text (e.g. originals of 19th-century laws)
            raise FileNotFoundError(f'IMPO has no JSON text for {path}') from None
        if 'fechaPromulgacion' in d and 'fechaPublicacion' not in d:
            d = dict(d, fechaPublicacion='')
        return d

    ih.ddmmyyyy, ih.load = ddmmyyyy, load

    # The CGP's amending laws quote single ordinales ("ARTICULO 349.3.- ..."); impo_history.quoted_article would take
    # such a quote for the whole article. Refuse it: that intermediate text is then unknown (shown later).
    orig_quoted_article = ih.quoted_article

    def quoted_article(law_text: str, art: str, width: int, sec: str = '') -> list[str] | None:
        t = law_text.replace('\r\n', '\n')
        m = re.search(r'(?:ART[IÍ]CULO|Art[íi]culo)\s+' + art + (r'\s*' + sec if sec else r'(?!\d)'), t,
                      re.I if sec else 0)
        if m and re.match(r'\.\d', t[m.end():]):
            return None
        # "Sustitúyese el artículo 29.1 del Código ... por el siguiente: "ARTÍCULO 29. ... 29.1 ..."": the words
        # before the first quote name an ordinal of this article, so the quote is not the whole article
        intro = t.split('"', 1)[0]
        if not sec and re.search(r'(?<![\d.])' + art + r'\.\d', intro):
            return None
        return orig_quoted_article(law_text, art, width, sec)

    ih.quoted_article = quoted_article

    # IMPO's texts carry a few layout tags the main parser does not strip: an empty anchor after the "(*)" marker
    # (CGP art. 451) and <center> around the chapter headings inside the Código de Comercio's 1865 texts of whole
    # titles. The anchor goes; a centred heading keeps its words on a line of its own.
    orig_paragraphs = ih.impo_paragraphs

    def impo_paragraphs(raw: str, width: int = 72) -> list[str]:
        raw = re.sub(r'<a\b[^>]*>\s*</a>', '', raw or '', flags=re.I)
        # IMPO's "(*)" amendment marker also stands inside a paragraph or after an ordinal that ends a line ("...
        # anterior. (*)" then "400.8"), where the main parser keeps it and joins the next ordinal on: drop it.
        raw = re.sub(r'[ \t]*\(\*\)', '', raw)
        raw = re.sub(r'<center>(.*?)</center>', lambda m: '\n\n' + ' '.join(m.group(1).split()) + '\n\n', raw,
                     flags=re.I | re.S)
        return orig_paragraphs(raw, width)

    ih.impo_paragraphs = impo_paragraphs


EXTRA_DATE = re.compile(r'(?:regir[áa]n?|entrar[áa]n? en (?:vigencia|vigor)|comenzar[áa]n? a regir)\s+(?:a partir\s+)?'
                        r'(?:del?|el)\s+(?:d[íi]a\s+)?(\d+)[º°]?\s+de\s+(\w+)\s+de\s+(\d{4})', re.I)
EXTRA_PROMULGATION = re.compile(r'entrar[áa] en (?:vigencia|vigor) a partir de (?:su|la) promulgaci[óo]n', re.I)

# Amending laws whose in-force day needs a reading impo_history and the patterns above cannot make; each from the
# law's own vigencia article (IMPO text, cached), worked out by hand.
LAW_DAY: dict[str, tuple[str, str]] = {
    '19090': ('2013-08-14', 'its art. 2: "Esta ley entrará en vigencia el día hábil siguiente a los sesenta días de su '
                            'promulgación" (promulgated 14/06/2013; the sixtieth day is Tuesday 13/08/2013, the next '
                            'working day Wednesday 14/08/2013)'),
    '19544': ('2017-11-01', 'its art. 11: "regirá simultáneamente con la entrada en vigencia de la Ley N° 19.293" '
                            '(the CPP, in force 1 November 2017 by its art. 403)'),
    '20130': ('2023-08-01', 'its art. 6 numeral 1: "el primer día del tercer mes siguiente al de su publicación en el '
                            'Diario Oficial" (published 10/05/2023)'),
}

_install_note_readings()

# ---------------------------------------------------------------- the acts

# slug -> IMPO path, the code's own law, vigencia articles of amending laws read by hand (law -> article), whether the
# base law enacted the text, and the code's own in-force day (IMPO path of the article that gives it, day, the words
# that must be in that article).
ACTS: dict[str, dict] = {
    'codigo-general-proceso': {
        'short': 'CGP', 'title': 'Código General del Proceso (Ley Nº 15.982)',
        'path': 'codigo-general-proceso/15982-1988', 'base': '15982', 'enacted': True,
        'original_prefix': 'textos-originales-ley/15982-1988',
        'vigencia': {'16053': '3', '16170': '2', '16226': '2', '16462': '2', '16871': '101', '17296': '2',
                     '17453': '51', '17707': '28', '17930': '2', '18172': '2', '18387': '255', '19090': '2',
                     '19535': '2', '19670': '2'},
        'base_in_force': ('codigo-general-proceso/15982-1988/547', '1989-11-20', 'el 20 de noviembre de 1989'),
    },
    'codigo-comercio': {
        'short': 'Código de Comercio', 'title': 'Código de Comercio',
        'path': 'codigo-comercio/817-1865', 'base': '817', 'enacted': False,
        'original_prefix': 'textos-originales-ley/817-1865',
        'extra': ['leyes/841-1866'],
        'extra_laws': {'ley-841': {'label': 'Ley Nº 841', 'title': 'Código de Comercio. Vigencia', 'kind': 'law',
                                   'enacted': '1866-01-24', 'published': None,
                                   'url': 'https://www.impo.com.uy/bases/leyes/841-1866', 'temporary_until': None,
                                   'restores': None, 'note': None}},
        'first_note': ('Dated 24 January 1866, the day Ley Nº 841 was promulgated to fix the day the code began to '
                       'apply: IMPO gives that day only in a scan of the law, which is not read (no OCR).'),
        'vigencia': {'14701': '127', '16060': '511', '17930': '2', '18387': '255'},
        'base_in_force': ('leyes/841-1866', '1866-01-24', 'Fíjase la fecha en que comenzará a regir el Código de Comercio'),
        # Libro IV (quiebras) was replaced whole in 1878 and again in 1900; IMPO's notes name those laws with no
        # article and give no text of either. Units -> (law, IMPO path, in-force day, words of IMPO's summary).
        'whole_rewrites': {
            'art-1523-1781': ('1422', 'leyes/1422-1878', '1879-02-01', 'empiece a regir desde el 1º de Febrero de 1879'),
            'art-1764-1785': ('1422', 'leyes/1422-1878', '1879-02-01', 'empiece a regir desde el 1º de Febrero de 1879'),
        },
    },
    'codigo-proceso-penal': {
        'short': 'CPP', 'title': 'Código del Proceso Penal (Ley Nº 19.293)',
        'path': 'codigo-proceso-penal-2017/19293-2014', 'base': '19293', 'enacted': True,
        'vigencia': {'19510': '2', '19670': '2', '20446': '3'},
        'base_in_force': ('codigo-proceso-penal-2017/19293-2014/403', '2017-11-01',
                          'entrará en vigencia el 1° de noviembre de 2017'),
    },
}

PART = UY / 'corpus.d' / '50-batch2.json'
VERIFICATION = HERE / 'verification.json'
RETRIEVED = '2026-10-28'
PLACEHOLDER = '[La fuente no da el texto vigente en esta fecha.]'
WORDING_NOW = ('wording', 'added')        # IMPO notes whose words are in today's text


def base_in_force(cfg: dict, main: dict) -> tuple[str, str] | None:
    """The code's own in-force day, from the article that gives it (asserted to contain the words in ACTS)."""
    if not cfg.get('base_in_force'):
        return None
    vpath, day, words = cfg['base_in_force']
    nro = vpath.rsplit('/', 1)[1]
    if vpath.startswith(cfg['path'] + '/'):
        art = next(a for a in main['articulos'] if a['nroArticulo'] == nro and not a['secArticulo'].strip())
    else:
        art = ih.load(vpath)
    if 'textoArticulo' not in art:      # a law IMPO gives only as a scan: its summary ("vistos") and header
        text = ' '.join(art.get('vistos', '').split())
        assert words in text and ih.ddmmyyyy(art['fechaPromulgacion']) == day, (vpath, text)
        return day, (f'{vpath}: promulgated {day}, "{text}"; the day it fixes is only in IMPO\'s scan, which is not '
                     f'read (no OCR), so the code is dated on that law\'s promulgation')
    text = ' '.join(art['textoArticulo'].split())
    assert words in text, (vpath, text)
    return day, f'{vpath}: "{text}"'


# ---------------------------------------------------------------- per-unit timelines

def timelines(act: dict) -> tuple[dict[str, list], dict[str, str]]:
    """key -> [(day, unit or None, credits)] at every change, from versions that all carry full `units`."""
    tl: dict[str, list] = {}
    prev: dict = {}
    for v in act['versions']:
        units = v['units']
        for k in sorted(set(units) | set(prev)):
            if units.get(k) != prev.get(k) or k not in tl:
                tl.setdefault(k, []).append([v['from'], units.get(k), list(v['credits'].get(k, []))])
        prev = units
    labels = {k: next(u['label'] for _, u, _ in c if u) for k, c in tl.items() if any(u for _, u, _ in c)}
    return tl, labels


def versions_from(tl: dict[str, list], template: list[dict]) -> list[dict]:
    days = sorted({d for c in tl.values() for d, _, _ in c})
    src, sha = template[0]['source_url'], template[0]['sha256']
    notes = {v['from']: v.get('note') for v in template}
    out, prev = [], {}
    for day in days:
        units, credits = {}, {}
        for k, chain in tl.items():
            cur = [c for c in chain if c[0] <= day]
            if not cur:
                continue
            d, u, ls = cur[-1]
            if u is not None:
                units[k] = u
            if d == day and ls and units.get(k) != prev.get(k):
                credits[k] = list(ls)
        out.append({'from': day, 'source_url': src, 'sha256': sha, 'units': dict(sorted(units.items())),
                    'credits': dict(sorted(credits.items())), 'note': notes.get(day)})
        prev = units
    out[0]['note'] = template[0].get('note')
    out[-1]['note'] = template[-1].get('note') if len(out) > 1 else out[-1]['note']
    return out


def unit(label: str, paras: list[str]) -> dict:
    return {'label': label, 'kind': 'art', 'text': ih.render(label, paras)}


ART_SUBJECT = (r'(?:el presente art[íi]culo|este art[íi]culo|la presente disposici[óo]n|esta disposici[óo]n|'
               r'lo dispuesto en (?:el presente|este) art[íi]culo)')
ART_PROMULGATION = re.compile(ART_SUBJECT + r'[^.]{0,40}?(?:entrar[áa] en vigencia|regir[áa]|tendr[áa] vigencia)\s+'
                              r'(?:a partir de|desde)\s+(?:la|su)\s+promulgaci[óo]n', re.I)
ART_DATE = re.compile(ART_SUBJECT + r'[^.]{0,40}?(?:entrar[áa] en vigencia|regir[áa]|tendr[áa] vigencia)\s+'
                      r'a partir del?\s+(?:d[íi]a\s+)?(\d+)[º°]?\s+de\s+(\w+)\s+de\s+(\d{4})', re.I)
_law_cache: dict[tuple[str, str], dict | None] = {}


def article_in_force(law: str, year: str, art: str) -> tuple[str, str] | None:
    """An amending article's own vigencia sentence ("El presente artículo entrará en vigencia a partir de la
    promulgación de la presente ley"), which overrides its law's general day. Read from IMPO's text of the whole
    amending law, outside any quoted passage."""
    if (law, year) not in _law_cache:
        _law_cache[(law, year)] = ih.load_cached(ih.law_path(law, year))
    whole = _law_cache[(law, year)]
    if not whole:
        return None
    a = next((x for x in whole.get('articulos', []) if x['nroArticulo'] == art and not x['secArticulo'].strip()), None)
    if not a:
        return None
    t = ' '.join(re.sub(r'"[^"]*"', ' ', (a.get('textoArticulo') or '').replace('“', '"').replace('”', '"')).split())
    if m := ART_PROMULGATION.search(t):
        return ih.ddmmyyyy(whole['fechaPromulgacion']), f'{ih.law_label(law)} art. {art}: "{m.group(0)}"'
    if (m := ART_DATE.search(t)) and m.group(2).lower() in ih.MONTHS:
        return (f'{m.group(3)}-{ih.MONTHS[m.group(2).lower()]:02d}-{int(m.group(1)):02d}',
                f'{ih.law_label(law)} art. {art}: "{m.group(0)}"')
    return None


def loose_key(text: str) -> str:
    """impo_history's comparison key, ignoring accents as well."""
    import unicodedata
    k = ih.key_of(text)
    return ''.join(c for c in unicodedata.normalize('NFD', k) if unicodedata.category(c) != 'Mn')


def post_pass(act: dict, main: dict, base: str, ver: dict) -> dict:
    """Article-level vigencia, repealed-then-revived articles, and the anachronism rule. Returns what it changed."""
    arts, wrap = ih.articles(main)
    day_of = {label: d['day'] for label, d in ver['in_force'].items()}     # keyed by law label
    base_day = ver['base_in_force']['day']
    tl, labels = timelines(act)
    done = {'first_text_from_earlier_law': [], 'article_vigencia': [], 'article_vigencia_not_applied': [], 'absent_between': [],
            'added_part_removed': [], 'placeholder': [], 'absent_before': []}

    for a in arts:
        chain = tl.get(a.key)
        if chain is None:
            continue
        own: dict[str, tuple[str, str]] = {}       # law -> (day, how) from the amending article's own clause
        for e in a.events:
            if e.law != base and e.kind != 'vigencia' and (r := article_in_force(e.law, e.year, e.art)):
                if r[0] != day_of.get(ih.law_label(e.law)) and (e.law not in own or r[0] > own[e.law][0]):
                    own[e.law] = r

        def day(law: str, own=own) -> str | None:
            return own[law][0] if law in own else day_of.get(ih.law_label(law))

        # -1. A law in force before the code's first day gave this article its words, and a later law changed it:
        #     impo_history starts such an article from the code's original (or, with no original, today's) text.
        #     Its first text is the one that earlier law quotes; with no such quote it is unknown (placeholder).
        pre = [e for e in a.events if e.law != base and e.kind in ('wording', 'wording-earlier', 'added',
               'added-earlier') and not e.scope and day(e.law) and day(e.law) <= base_day]
        post = [e for e in a.events if e.law != base and e.kind != 'vigencia' and day(e.law)
                and day(e.law) > base_day]
        if pre and post:
            last_pre = max(pre, key=lambda e: (day(e.law), int(e.law)))
            o = ih.load_cached(ih.law_path(last_pre.law, last_pre.year, last_pre.art, original=True))
            q = ih.quoted_article(o['textoArticulo'], a.nro, wrap, a.sec) if o else None
            first = unit(a.label, ih.drop_headings(q)) if q else unit(a.label, [PLACEHOLDER])
            how = (f'the wording {ih.law_label(last_pre.law)} art. {last_pre.art} gives it' if q
                   else 'unknown (placeholder)')
            if 'unresolved' in ver['articles'].get(a.key, {}) and len(chain) == 1:
                lks = [ih.law_key(l) for l in sorted({e.law for e in post}, key=lambda l: (day(l), int(l)))]
                last_day = max(day(e.law) for e in post)
                chain[:] = [[chain[0][0], first, []], [last_day, chain[0][1], lks]]
                ver['articles'][a.key]['resolved_by_post_pass'] = how
                done['first_text_from_earlier_law'].append(f'{a.label}: {how}')
            elif chain[0][1] != first:
                chain[0][1] = first
                done['first_text_from_earlier_law'].append(f'{a.label}: {how}')

        # 0. Move each change to the day its laws' own articles put it in force, when that keeps the order.
        for i in range(1, len(chain)):
            ls = [l.removeprefix('ley-') for l in chain[i][2]]
            if not ls or not any(l in own for l in ls) or any(day(l) is None for l in ls):
                continue
            new = max(day(l) for l in ls)
            if new == chain[i][0]:
                continue
            what = '; '.join(own[l][1] for l in ls if l in own)
            if chain[i - 1][0] < new and (i + 1 == len(chain) or new < chain[i + 1][0]) and new > base_day:
                done['article_vigencia'].append(f'{a.label}: {chain[i][0]} -> {new} ({what})')
                chain[i][0] = new
            else:
                done['article_vigencia_not_applied'].append(f'{a.label}: stays {chain[i][0]}, not {new} '
                                                            f'(would cross another change) ({what})')
        evs = [e for e in a.events if e.law != base and e.kind != 'vigencia' and day(e.law) and day(e.law) > base_day]
        # 1. "Derogado anteriormente por" a law R, and the article given new wording later: absent from R's day
        #    until the next law after R changes it.
        for e in evs:
            if e.kind != 'repealed-earlier' or e.scope:
                continue
            r, rk = day(e.law), ih.law_key(e.law)
            later = [c for c in chain if c[0] > r]
            if not later or later[0][1] is None:
                continue
            for c in later:
                if rk in c[2]:
                    c[2].remove(rk)
            chain[:] = [c for c in chain if c[0] < r] + [[r, None, [rk]]] + later
            done['absent_between'].append(f'{a.label}: absent from {r} ({ih.law_label(e.law)}, "derogado '
                                          f'anteriormente") until {later[0][0]}')
        # 2. The anachronism rule: today's wording must not appear before the last law that IMPO says gave it. This
        #    concerns only articles impo_history could give no sourced earlier text for ('unresolved': today's text
        #    from the start); a sourced original that happens to equal today's words is the law's text then.
        if 'unresolved' not in ver['articles'].get(a.key, {}) or 'resolved_by_post_pass' in ver['articles'][a.key]:
            continue
        now = [e for e in evs if e.kind in WORDING_NOW]
        if not now or not a.current:
            continue
        # 2a. Every change was an addition IMPO scopes to part of the article, and the adding law quotes it: the
        #     earlier text is today's without it. impo_history compares exact words; here accents are ignored too
        #     (IMPO's consolidated text accents words the law as published does not, e.g. "facsímil"/"facsimil").
        if all(e.kind == 'added' and e.scope and not ih.scope_marker(e.scope) for e in evs) and len(chain) == 1:
            t = list(a.current)
            for e in sorted(evs, key=lambda e: day(e.law)):
                o = ih.load_cached(ih.law_path(e.law, e.year, e.art, original=True))
                q = ih.quoted_paragraphs(o['textoArticulo'], wrap) if o else None
                keys = [loose_key(x) for x in q] if q else None
                hit = next((i for i in range(len(t) - len(keys) + 1)
                            if [loose_key(x) for x in t[i:i + len(keys)]] == keys), None) if keys else None
                if hit is None:
                    t = None
                    break
                del t[hit:hit + len(keys)]
            if t is not None and len({e.law for e in evs}) == 1:
                e = evs[0]
                chain[:] = [[chain[0][0], unit(a.label, t), []], [day(e.law), unit(a.label, a.current),
                                                                   [ih.law_key(e.law)]]]
                done['added_part_removed'].append(f'{a.label}: before {day(e.law)}, today\'s text without '
                                                  f'{e.scope} ({ih.law_label(e.law)} art. {e.art} quotes it)')
                continue
        last = max(now, key=lambda e: day(e.law))
        d_last = day(last.law)
        today = unit(a.label, a.current)
        early = [c for c in chain if c[0] < d_last and c[1] == today]
        if not early:
            continue
        inserted = (last.kind == 'added' and not last.scope)
        first_early = early[0][0]
        # the change on first_early keeps its credit (that law did change the article; its words are unknown);
        # today's wording arrives on d_last, credited to every law after first_early up to d_last
        lks: list[str] = []
        for c in chain:
            if first_early < c[0] <= d_last:
                lks += [l for l in c[2] if l not in lks]
        for l in sorted({e.law for e in evs if first_early < day(e.law) <= d_last}, key=lambda l: (day(l), int(l))):
            if ih.law_key(l) not in lks:
                lks.append(ih.law_key(l))
        keep = [c for c in chain if c[0] < first_early]
        filler = None if inserted else unit(a.label, [PLACEHOLDER])
        mid = [[first_early, filler, list(early[0][2]) if keep else []]]
        rest = [c for c in chain if c[0] > d_last]
        chain[:] = keep + mid + [[d_last, today, lks or [ih.law_key(last.law)]]] + rest
        done['absent_before' if inserted else 'placeholder'].append(
            f'{a.label}: today\'s wording held back until {d_last} ({ih.law_label(last.law)})')
    act['versions'] = versions_from(tl, act['versions'])
    return done


# ---------------------------------------------------------------- the part

def ready(cfg: dict) -> bool:
    try:
        main = ih.load(cfg['path'])
    except FileNotFoundError:
        return False
    return all(fetch.cache_path(fetch.impo(p)).exists() for p in ih.needed_paths(main, cfg['base'], cfg['vigencia']))


SAMPLE = 12


def sample_paths(cfg: dict) -> list[str]:
    """Original texts of a fixed sample of articles IMPO records no change to (every n-th one), to test that
    IMPO's text of an unamended article is the text as enacted (no unrecorded amendment)."""
    if not cfg.get('original_prefix'):
        return []
    arts, _ = ih.articles(ih.load(cfg['path']))
    plain = [a for a in arts if not a.events and a.current and not a.sec]
    step = max(1, len(plain) // SAMPLE)
    return [f'{cfg["original_prefix"]}/{int(a.nro)}' for a in plain[step // 2::step][:SAMPLE]]


def sample_check(cfg: dict) -> dict:
    arts, width = ih.articles(ih.load(cfg['path']))
    by = {int(a.nro): a for a in arts if not a.sec}
    out = {}
    for p in sample_paths(cfg):
        o = ih.load_cached(p)
        if not o:
            out[p] = 'not cached'
            continue
        a = by[int(p.rsplit('/', 1)[1])]
        orig = ih.drop_headings(ih.impo_paragraphs(o['textoArticulo'], width))
        same = [ih.key_of(x) for x in orig] == [ih.key_of(x) for x in a.current]
        out[p] = ('same words' if same else 'IMPO serves no original text' if not orig
                  else {'original': orig, 'impo_today': a.current})
    return out


def state_on(act: dict, day: str) -> dict:
    units: dict = {}
    for v in act['versions']:
        if v['from'] > day:
            break
        units = v['units']
    return units


def check_against_impo(act: dict, main: dict) -> dict:
    """Today's text (the state on RETRIEVED, and the last version) against IMPO's consolidated text, unit for unit.
    Articles IMPO marks repealed whole, or prints with no text, must be absent."""
    arts, _ = ih.articles(main)
    want = {}
    for a in arts:
        gone = any(e.kind == 'repealed' and not e.scope for e in a.events) or not a.current
        if not gone:
            want[a.key] = ih.render(a.label, a.current)
    out = {}
    for name, units in (('today', state_on(act, RETRIEVED)), ('last_version', act['versions'][-1]['units'])):
        have = {k: u['text'] for k, u in units.items()}
        diff = sorted(k for k in set(want) | set(have) if want.get(k) != have.get(k))
        out[name] = {'equal': not diff, 'differ': diff}
    return out


def relabel_ranges(act: dict) -> None:
    """IMPO gives a run of repealed articles as one entry (nroArticulo 114, secArticulo 123): label it
    "Artículos 114 a 123" rather than "Artículo 114 123"."""
    for v in act['versions']:
        for k, u in v['units'].items():
            m = re.fullmatch(r'art-0*(\d+)-(\d+)', k)
            if m and u['label'] == f'Artículo {m.group(1)} {m.group(2)}':
                new = f'Artículos {m.group(1)} a {m.group(2)}'
                u['text'] = u['text'].replace(f'# {u["label"]}\n', f'# {new}\n', 1)
                u['label'] = new


def whole_rewrites(act: dict, main: dict, cfg: dict, laws: dict) -> list[str]:
    """A unit IMPO says a law replaced whole ("Redacción dada anteriormente por: Ley Nº 1.422", no article), with no
    text of that law's wording: the original text stands until that law's day, then the placeholder, until the next
    change with a known text (here the repeal). Later laws IMPO names inside the unknown text change no known words
    and are not credited (decisions)."""
    rw = cfg.get('whole_rewrites')
    if not rw:
        return []
    arts, _ = ih.articles(main)
    notes = {a.key: ih.note_text(x.get('notasArticulo') or '') for a, x in zip(arts, main['articulos'])}
    tl, _ = timelines(act)
    done = []
    for key, (law, path, day, words) in rw.items():
        label = ih.law_label(law)
        note = ' '.join(notes[key].split())
        assert re.search(r'Redacción dada anteriormente por:.*' + re.escape(label) + r' de \d\d/\d\d/\d{4}[.,]', note), \
            (key, note)
        hdr = ih.load(path)
        assert words in ' '.join(hdr.get('vistos', '').split()), (path, hdr.get('vistos'))
        chain = tl[key]
        assert chain[0][1] is not None and chain[-1][1] is None and day > chain[0][0], (key, chain)
        lk = ih.law_key(law)
        repeal = chain[-1]
        rk = ih.law_key(re.search(r'Derogado/s por: Ley Nº ([\d.]+)', note).group(1).replace('.', ''))
        assert rk in repeal[2], (key, rk, repeal)
        later_laws = sorted({l for c in chain[1:] for l in c[2]} - {rk}, key=lambda l: int(l.rsplit('-', 1)[1]))
        chain[:] = [chain[0], [day, unit(chain[0][1]['label'], [PLACEHOLDER]), [lk]], [repeal[0], None, [rk]]]
        laws[lk] = {'label': label, 'title': ih.title_case(hdr.get('nombreNorma') or label), 'kind': 'law',
                    'enacted': ih.ddmmyyyy(hdr.get('fechaPromulgacion')), 'published': ih.ddmmyyyy(hdr.get('fechaPublicacion')),
                    'url': f'{fetch.IMPO}/{path}', 'temporary_until': None, 'restores': None, 'note': None}
        done.append(f'{key}: the 1865 text until {day}, then "{PLACEHOLDER}" ({label} replaced it whole; IMPO\'s '
                    f'summary: "{words}"), removed on {repeal[0]}; not credited within the unknown text: '
                    + ', '.join(later_laws))
    act['versions'] = versions_from(tl, act['versions'])
    return done


def build_one(slug: str, cfg: dict, verification: dict) -> tuple[dict, dict, dict]:
    main = ih.load(cfg['path'])
    ver: dict = {}
    laws, act = ih.build_act(slug=slug, short=cfg['short'], title=cfg['title'], path=cfg['path'], base=cfg['base'],
                             vigencia_arts=cfg['vigencia'], verification=ver, base_is_enactment=cfg['enacted'],
                             base_in_force=base_in_force(cfg, main))
    v = ver[slug]
    v['post_pass'] = post_pass(act, main, cfg['base'], v)
    v['post_pass']['whole_rewrites'] = whole_rewrites(act, main, cfg, laws)
    relabel_ranges(act)
    v['impo_check'] = check_against_impo(act, main)
    if 'samples' not in v and cfg.get('original_prefix'):
        v['unamended_sample'] = sample_check(cfg)
    used = {l for x in act['versions'] for ls in x['credits'].values() for l in ls} | {ih.law_key(cfg['base'])}
    # Laws that changed the code before its own first day are inside its first text, which is then not the text as
    # enacted: the first version is the "oldest version available", naming them.
    arts, _ = ih.articles(main)
    base_day = v['base_in_force']['day']
    pre = sorted((l for l in ih.amending_laws(arts, cfg['base']) if ih.law_label(l) in v['in_force']
                  and v['in_force'][ih.law_label(l)]['day'] <= base_day), key=int)
    if pre:
        act['first_law'] = None
        act['earlier_laws'] = [ih.law_key(cfg['base'])] + [ih.law_key(l) for l in pre]
        used |= set(act['earlier_laws'])
        amend = ih.amending_laws(arts, cfg['base'])
        for l in pre:
            d = amend[l]
            hdr = ih.load(ih.law_path(l, d['year'], min(d['arts'], key=int)))
            laws[ih.law_key(l)] = {
                'label': ih.law_label(l), 'title': ih.title_case(hdr.get('nombreNorma') or ih.law_label(l)),
                'kind': 'law', 'enacted': ih.ddmmyyyy(hdr.get('fechaPromulgacion')),
                'published': ih.ddmmyyyy(hdr.get('fechaPublicacion')),
                'url': f'{fetch.IMPO}/{ih.law_path(l, d["year"])}', 'temporary_until': None, 'restores': None,
                'note': None}
        act['versions'][0]['note'] = (
            f'The code as in force on {base_day}: the text of {ih.law_label(cfg["base"])} with the changes '
            + ', '.join(ih.law_label(l) for l in pre) + ' made before that day (IMPO notes). ' + act['versions'][0]['note'])
        v['before_first_day'] = {ih.law_label(l): v['in_force'][ih.law_label(l)] for l in pre}
    elif not cfg['enacted']:
        act['earlier_laws'] = [ih.law_key(cfg['base'])] + sorted(cfg.get('extra_laws', {}))
        used |= set(act['earlier_laws'])
    laws.update(cfg.get('extra_laws', {}))
    for k, x in laws.items():
        if k.startswith('decreto-ley-'):
            x['kind'] = 'decree'
    if cfg.get('first_note'):
        act['versions'][0]['note'] = cfg['first_note'] + ' ' + act['versions'][0]['note']
    verification[slug] = v
    return {k: x for k, x in laws.items() if k in used}, act, v


def as_changes(act: dict) -> None:
    import parse   # the main agent's delta writer (SCHEMA.md, Large acts)
    parse.as_changes(act)


def main(argv: list[str]) -> None:
    verification: dict = {}
    laws: dict = {}
    acts: list = []
    only = [a for a in argv if not a.startswith('--')]
    for slug, cfg in ACTS.items():
        if only and slug not in only:
            continue
        if not ready(cfg):
            print(slug, 'not fully cached: skipped', flush=True)
            continue
        l2, act, v = build_one(slug, cfg, verification)
        laws.update(l2)
        acts.append(act)
        unresolved = [k for k, r in v['articles'].items() if 'unresolved' in r]
        print(slug, len(act['versions']), 'versions,', sum(len(x['credits']) for x in act['versions']),
              'credited unit changes; unresolved start', len(unresolved), '; post-pass',
              {k: len(x) for k, x in v['post_pass'].items()}, '; impo',
              {k: x['equal'] for k, x in v['impo_check'].items()}, flush=True)
    if '--dry' in argv or not acts:
        VERIFICATION.with_suffix('.dry.json').write_text(json.dumps(verification, ensure_ascii=False, indent=1),
                                                         encoding='utf-8', newline='\n')
        return
    for a in acts:
        as_changes(a)
    paths = set()
    for a in acts:
        cfg = ACTS[a['slug']]
        paths |= {cfg['path']} | set(ih.needed_paths(ih.load(cfg['path']), cfg['base'], cfg['vigencia']))
    part = {
        'sources': [{'name': 'IMPO, Base de datos de normativa (codes of corpus.d/50-batch2)',
                     'url': 'https://www.impo.com.uy/bases', 'retrieved': RETRIEVED, 'requests': len(paths),
                     'licence': 'Texts from IMPO, Base de datos de normativa (www.impo.com.uy/bases).',
                     'notes': 'JSON (?json=true) of each code\'s consolidated text with IMPO\'s notes per article, '
                              'the original texts and amending articles they link, and each amending law. '
                              'robots.txt Crawl-Delay: 10 is kept.'}],
        'laws': dict(sorted(laws.items())),
        'acts': acts,
        'applies': [],
        'decisions': decisions([a['slug'] for a in acts], verification),
        'ai_use': ['A model (Claude) wrote batch2/fetch2.py and batch2/batch2.py and read the vigencia articles '
                   'listed in decisions. It wrote no legal text: every unit is parsed from IMPO bytes in the cache, '
                   'apart from the fixed placeholder sentence of the anachronism rule.'],
    }
    PART.parent.mkdir(exist_ok=True)
    tmp = PART.with_name(PART.name + '.tmp')
    tmp.write_text(json.dumps(part, ensure_ascii=False, indent=1) + '\n', encoding='utf-8', newline='\n')
    tmp.replace(PART)
    VERIFICATION.write_text(json.dumps(verification, ensure_ascii=False, indent=1) + '\n', encoding='utf-8',
                            newline='\n')
    print('wrote', PART, PART.stat().st_size, 'bytes')


DECISIONS_COMMON = [
    'Batch 2 codes (corpus.d/50-batch2.json) are rebuilt by the same impo_history.py as the Código Civil and Penal: '
    'the original text of each amended article from IMPO\'s TEXTO ORIGINAL link, today\'s text from IMPO, sourced '
    'intermediate texts only, and each amending law in force on the day its own vigencia article gives, else ten '
    'days after publication (Código Civil art. 1).',
    'Batch 2: IMPO notes "Derogado anteriormente por" and "Redacción derogada por" are read as events of that law; '
    'an article repealed and later given new wording is absent in between.',
    'Batch 2: IMPO scopes changes in the CGP and CPP to "ordinales" (e.g. 547.1); such a note is read as a scoped '
    'change to the article, never as a change to the whole article.',
    'Batch 2, anachronism rule: where a unit would show today\'s wording before the last law IMPO says gave it was in '
    'force, it reads "' + PLACEHOLDER + '" until that day (or is absent if that law inserted it); the units are '
    'listed below and in batch2/verification.json (post_pass).',
]


def decisions(slugs: list[str], verification: dict) -> list[str]:
    out = list(DECISIONS_COMMON)
    for s in slugs:
        out += ACT_DECISIONS.get(s, [])
        for k, items in verification[s]['post_pass'].items():
            if items:
                out.append(f'{ACTS[s]["short"]}, {k.replace("_", " ")}: ' + '; '.join(items) + '.')
    return out


ACT_DECISIONS: dict[str, list[str]] = {
    'codigo-comercio': [
        'Código de Comercio: the first version is the code of 1865 (Ley Nº 817) as IMPO gives it, dated 24 January '
        '1866, the promulgation of Ley Nº 841, which fixed the day the code began to apply; that day is only in '
        'IMPO\'s scan of Ley Nº 841, which is not read (no OCR). The version is credited to the publisher as the '
        'oldest version available, naming Leyes 817 and 841.',
        'Código de Comercio: each amended article starts from IMPO\'s original 1865 text (textos-originales-ley/'
        '817-1865); unamended articles carry IMPO\'s consolidated text throughout. In a fixed sample of 12 unamended '
        'articles, 10 have the original\'s words exactly; arts. 66 ("hacerse,", "asiento,", "foja" for "hoja") and '
        '382 ("los" for "lo") differ in punctuation or one word, with no amending law recorded, so no change is '
        'committed for them (batch2/verification.json, unamended_sample).',
        'Código de Comercio: vigencia articles read by hand: Decreto-Ley 14.701 art. 127 (1 November 1977), Ley '
        '16.060 art. 511 (sixty days after publication on 01/11/1989: 31/12/1989), Ley 17.930 art. 2, Ley 18.387 '
        'art. 255; laws of 1878 and 1882 that IMPO gives no publication day for are dated ten days after '
        'promulgation.',
        'Código de Comercio, Libro IV (quiebras): IMPO keeps it as two entries, arts. 1523 a 1781 and 1764 a 1785, '
        'whose original texts are the 1865 arts. 1523-1747 and 1748-1768 (the numbering changed with the 1878 and '
        '1916 texts). Ley Nº 1.422 replaced the whole book, in force 1 February 1879 by IMPO\'s summary of it, and '
        'Ley Nº 2.666 (1900) replaced it again; IMPO gives neither text, so from 1879 both units read the '
        'placeholder until Ley Nº 18.387 repealed them; the later partial changes IMPO lists inside that unknown '
        'text are not committed (listed under "whole rewrites" below).',
        'Batch 2: decree-laws of 1973-1985 (IMPO "Decreto Ley Nº") are kind "decree", with their own keys '
        '(decreto-ley-<n>) and IMPO paths (decretos-ley/).',
    ],
    'codigo-proceso-penal': [
        'CPP: in force 1 November 2017 by its art. 403 (as worded by Ley 19.510). Leyes 19.436, 19.474, 19.510, '
        '19.511 and 19.544 (the last in force with the code, by its art. 11) changed it before that day, so the first '
        'version is the oldest version available; where a later law changed such an article, its first text is the '
        'wording the earlier law quotes (post_pass first_text_from_earlier_law), else the placeholder.',
        'CPP: arts. 383 to 392 (suspensión condicional del proceso) are absent from Ley 19.889\'s day until Ley '
        '20.519 (IMPO note "Reincorporado por", in force ten days after its publication on 14/09/2026) puts them back.',
        'CPP: vigencia articles read by hand: Ley 19.510 art. 2, 19.670 art. 2, 20.446 art. 3; 19.544 art. 11.',
    ],
    'codigo-general-proceso': [
        'CGP: in force 20 November 1989 by its own art. 547 (as worded by Ley 16.053, which took effect before the '
        'code and is therefore part of its first text). The first version is therefore the code as in force on that '
        'day (Ley 15.982 with Ley 16.053\'s changes), credited to the publisher as the oldest version available, '
        'naming both laws.',
        'CGP: vigencia articles read by hand (batch2.ACTS): Ley 16.053 art. 3, 16.170 art. 2, 16.226 art. 2, 16.462 '
        'art. 2, 16.871 art. 101, 17.296 art. 2, 17.453 art. 51, 17.707 art. 28, 17.930 art. 2, 18.172 art. 2, '
        '18.387 art. 255, 19.090 art. 2, 19.535 art. 2, 19.670 art. 2; budget laws that say they rule from 1 January '
        'are dated so even when published later. Ley 19.090 ("el día hábil siguiente a los sesenta días de su '
        'promulgación", promulgated 14/06/2013) is dated 14/08/2013; Ley 20.130 (art. 6.1, first day of the third '
        'month after publication on 10/05/2023) 01/08/2023.',
        'CGP: an amending article\'s own clause ("El presente artículo entrará en vigencia a partir de la '
        'promulgación") overrides its law\'s day when it keeps the article\'s changes in order (post_pass '
        'article_vigencia).',
        'CGP: many amending laws quote a single ordinal ("ARTICULO 349.3", "Sustitúyese el artículo 29.1"); such a '
        'quote is not taken for the whole article, so that intermediate text is unknown and the change is shown on '
        'the next day with a known text, credited to every law in between (batch2/verification.json).',
        'CGP: Ley 20.531 (promulgated 01/10/2026, in force 1 January 2027 by its art. 2) substitutes arts. 64 and 64 '
        'BIS; IMPO\'s consolidated text does not include it yet, so it is not in this history.',
    ],
}


def vigencia_report(slug: str) -> None:
    """For choosing vigencia articles by hand: each amending law's day as found now, and its candidate articles."""
    cfg = ACTS[slug]
    main = ih.load(cfg['path'])
    arts, _ = ih.articles(main)
    for law, d in sorted(ih.amending_laws(arts, cfg['base']).items(), key=lambda x: (x[1]['year'], x[0])):
        if not d['arts']:
            continue
        hdr = ih.load_cached(ih.law_path(law, d['year'], min(d['arts'], key=int)))
        vig = d['vigencia'] or cfg['vigencia'].get(law)
        vt = ih.load_cached(ih.law_path(law, d['year'], vig)) if vig else None
        day, how = ih.in_force(hdr, vt.get('textoArticulo') if vt else None) if hdr else ('?', 'not cached')
        print(f'== {law} ({d["year"]}) vig={vig} -> {day} [{how[:140]}]')
        whole = ih.load_cached(ih.law_path(law, d['year']))
        if whole and not vig:
            whole = dict(whole, articulos=[a for a in whole.get('articulos', []) if 'textoArticulo' in a])
            for n, t in ih.vigencia_candidates(whole):
                print(f'   art {n}: {t[:260]}')


if __name__ == '__main__':
    if sys.argv[1:2] == ['--vigencia']:
        for s in sys.argv[2:]:
            vigencia_report(s)
    else:
        main(sys.argv[1:])
