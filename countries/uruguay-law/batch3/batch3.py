"""Batch 3 of Uruguayan acts: writes scripts/uruguay-law/corpus.d/60-batch3.json (gitlaw_common/SCHEMA.md).

    python -X utf8 scripts/uruguay-law/batch3/batch3.py [slugs] [--dry]
    python -X utf8 scripts/uruguay-law/batch3/batch3.py --vigencia <slug>...   # amending laws' days + candidates

Reads only the shared .cache (fetched by batch3/fetch3.py). Each act is rebuilt exactly as batch 2 rebuilt its codes:
batch2.build_one (imported, not copied) runs the main agent's impo_history.build_act with batch 2's readings of
IMPO's notes, its post-pass (article vigencia, absent between repeal and revival, the anachronism rule) and its check
that today's text equals IMPO's consolidated text. This module holds only the acts' table, the vigencia articles read
by hand, and the part writer.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
UY = HERE.parent
sys.path.insert(0, str(UY))
sys.path.insert(0, str(UY / 'batch2'))
import fetch  # noqa: E402
import impo_history as ih  # noqa: E402
import batch2  # noqa: E402

# slug -> as batch2.ACTS: IMPO path, the act's own law, vigencia articles of amending laws read by hand (law ->
# article), whether the base law enacted the text, and the act's own in-force day (IMPO path of the article that
# gives it, day, the words that must be in that article).
ACTS: dict[str, dict] = {
    'ley-17250': {
        'short': 'Ley 17.250', 'title': 'Ley de Relaciones de Consumo (Ley Nº 17.250)',
        'path': 'leyes/17250-2000', 'base': '17250', 'enacted': True,
        'original_prefix': 'leyes-originales/17250-2000',
        'vigencia': {},
    },
    'codigo-aduanero': {
        'short': 'CAROU', 'title': 'Código Aduanero de la República Oriental del Uruguay (Ley Nº 19.276)',
        'path': 'codigo-aduanero/19276-2014', 'base': '19276', 'enacted': True,
        'original_prefix': 'leyes-originales/19276-2014',
        'vigencia': {},
        'extra': ['leyes/19322-2015', 'leyes/19394-2016'],      # the suspending laws whole, for a vigencia clause
        'base_in_force': ('codigo-aduanero/19276-2014/276', '2015-03-18',
                          'Este Código entrará en vigencia a los ciento ochenta días de su promulgación'),
        # Laws that suspended the vigencia of some articles and changed no words: (law, year, article, the words
        # that must open that article, the note its commit prints).
        'suspensions': [
            ('19322', '2015', '1', 'Suspéndese la vigencia de los artículos 224, 225, 227 a 257 y 269',
             'Suspended the vigencia of arts. 224, 225, 227 to 257 and 269 of the code, and of art. 275 as to its '
             'repeal of procedural articles of Ley Nº 13.318, until 1 March 2016 (art. 1); the wording is unchanged.'),
            ('19394', '2016', '1', 'Suspéndese la vigencia de los artículos 224, 225, 227 a 257 y 269',
             'Extended the suspension of the vigencia of arts. 224, 225, 227 to 257 and 269 of the code, and of art. '
             '275 as to its repeal of procedural articles of Ley Nº 13.318, until 16 July 2017 (art. 1); the wording '
             'is unchanged.'),
        ],
    },
    'codigo-tributario': {
        'short': 'Código Tributario', 'title': 'Código Tributario (Decreto-Ley Nº 14.306)',
        'path': 'codigo-tributario/14306-1974', 'base': '14306', 'enacted': True,
        # IMPO's links use both textos-originales-decreto-ley/ and decretos-leyes-originales/; the first answers an
        # empty text for most articles, the second has them all.
        'original_prefix': 'decretos-leyes-originales/14306-1974',
        'vigencia': {},
    },
    'ley-16060': {
        'short': 'Ley de Sociedades Comerciales', 'title': 'Ley de Sociedades Comerciales (Ley Nº 16.060)',
        'path': 'leyes/16060-1989', 'base': '16060', 'enacted': True,
        'original_prefix': 'leyes-originales/16060-1989',
        'vigencia': {},
        'base_in_force': ('leyes/16060-1989/511', '1989-12-31',
                          'Esta ley entrará en vigencia a los sesenta días de su publicación'),
    },
    'codigo-ninez-adolescencia': {
        'short': 'CNA', 'title': 'Código de la Niñez y la Adolescencia (Ley Nº 17.823)',
        'path': 'codigo-ninez-adolescencia/17823-2004', 'base': '17823', 'enacted': True,
        'original_prefix': 'leyes-originales/17823-2004',
        'vigencia': {},
    },
}

# Vigencia articles of amending laws whose IMPO notes give none, read by hand from each law's text (cached) with
# `--vigencia`; one table for all batch-3 acts (a law has one vigencia article whatever it amends).
VIGENCIA: dict[str, str] = {
    '18046': '2', '18362': '2', '16736': '2', '16871': '101', '19075': '29', '18083': '113', '19288': '21',
    '19551': '21', '19747': '9',
    # as the published acts and batch 2 read them (same days everywhere)
    '16462': '2', '17930': '2', '18172': '2', '18387': '255', '18719': '3', '19149': '2', '19355': '3',
    '19438': '2', '19535': '2', '19670': '2', '19924': '3', '20075': '5', '20212': '2', '20446': '3',
}
for _cfg in ACTS.values():
    _cfg['vigencia'] = {**VIGENCIA, **_cfg['vigencia']}

# ---------------------------------------------------------------- two more readings (this process only)

FETCHING = False          # fetch3.py sets it: then every possible original text is asked for


def _install() -> None:
    """1. An amended article IMPO gives no TEXTO ORIGINAL link for (typically one a later law only added an item to)
    still has its text as enacted at IMPO, under the act's originals (e.g. leyes-originales/19276-2014/49). That
    path is added as the article's original link, so impo_history starts the article from it instead of leaving it
    unresolved. Only for articles without a BIS/TER suffix (those were added later), and, when building, only if
    IMPO served a JSON text for it (cached).
    2. IMPO's original texts end with the next section's heading, as a paragraph of its own or run on after the last
    sentence ("... la misma. PROCESO INFRACCIONAL ADUANERO JURISDICCIÓN Y COMPETENCIA"); a trailing run of capitals
    is a heading, not article text, and is dropped (impo_history drops only headings that start CAPÍTULO, TÍTULO...).
    """
    if getattr(ih, '_batch3', False):
        return
    ih._batch3 = True
    prefixes = {cfg['base']: cfg['original_prefix'] for cfg in ACTS.values() if cfg.get('original_prefix')}
    orig_articles = ih.articles

    def articles(main: dict):
        arts, width = orig_articles(main)
        base = str(main.get('nroNorma') or '').replace('.', '')
        prefix = prefixes.get(base)
        if prefix:
            # 3. Dotted articles (CNA "Artículo 133.1") are absent from the act as enacted: a later law added them
            #    while rewording a whole chapter, and IMPO notes that law as "Redacción dada anteriormente por". If
            #    IMPO's original of the parent article does not contain the dotted number, the earliest such law
            #    added the article (its first text is the one that law quotes, read by quoted_article below).
            for a in arts:
                if not a.sec.isdigit() or int(a.sec) >= int(a.nro) or any(f'/{base}-' in h for h in a.original_hrefs):
                    continue
                if any(e.kind in ('added', 'added-earlier') and not e.scope for e in a.events):
                    continue
                earlier = [e for e in a.events if e.kind == 'wording-earlier' and not e.scope and e.law != base]
                if not earlier:
                    continue
                first = min(earlier, key=lambda e: int(e.law))
                parent = _load_text(f'{prefix}/{int(a.nro)}')
                if parent is None or re.search(rf'{a.nro}\s*\.\s*{a.sec}(?!\d)', parent):
                    continue
                a.events.append(ih.Event('added', '', first.law, first.year, first.art))
                ADDED_BY_EARLIER[(base, a.key)] = (f'{a.label}: not in IMPO\'s original of art. {int(a.nro)} '
                                                   f'({prefix}/{int(a.nro)}); first worded by '
                                                   f'{ih.law_label(first.law)} art. {first.art}, read as added by it')
            for a in arts:
                if a.sec or any(f'/{base}-' in h for h in a.original_hrefs):
                    continue
                if not any(e.law != base and e.kind != 'vigencia' for e in a.events):
                    continue
                path = f'{prefix}/{int(a.nro)}'
                if FETCHING or _has_text(path):
                    a.original_hrefs = a.original_hrefs + [f'/bases/{path}']
                    SYNTHETIC_ORIGINAL.add((base, a.label, path))
        return arts, width

    ih.articles = articles
    orig_drop = ih.drop_headings

    def drop_headings(paras: list[str]) -> list[str]:
        out = list(orig_drop(paras))
        while out and (_caps(out[-1]) or _heading_like(out[-1])):
            HEADINGS_DROPPED.append(out.pop())
        if out:
            m = TRAILING_CAPS.search(out[-1])
            if m and _caps(m.group(1)):
                out[-1] = out[-1][:m.start()]
        return out

    ih.drop_headings = drop_headings

    # 4. Dotted article numbers: label "Artículo 133.1" (IMPO keeps 133 / 1; batch 2's range relabelling, meant for
    #    "Artículos 114 a 123", then leaves it alone), and an amending law's quote "ARTÍCULO 133.1." is found.
    orig_label = ih.unit_label

    def unit_label(nro: str, sec: str) -> str:
        s = sec.strip()
        return f'Artículo {int(nro)}.{int(s)}' if s.isdigit() and int(s) < int(nro) else orig_label(nro, sec)

    ih.unit_label = unit_label
    orig_quoted = ih.quoted_article

    def quoted_article(law_text: str, art: str, width: int, sec: str = '') -> list[str] | None:
        if sec.isdigit() and int(sec) < int(art):
            return orig_quoted(law_text, art, width, r'\.' + sec + r'(?!\d)')
        return orig_quoted(law_text, art, width, sec)

    ih.quoted_article = quoted_article


TRAILING_CAPS = re.compile(r'(?<=[.;:])\s+([A-ZÁÉÍÓÚÑÜ][A-ZÁÉÍÓÚÑÜ ,]{5,})$')


def _caps(s: str) -> bool:
    letters = [c for c in s if c.isalpha()]
    return len(letters) >= 4 and all(c.isupper() for c in letters)


def _load_text(path: str) -> str | None:
    try:
        t = ih.load(path).get('textoArticulo')
    except (FileNotFoundError, ValueError):
        return None
    return t if t and t.strip() else None      # IMPO answers some missing originals with an empty text


def _heading_like(p: str) -> bool:
    """A short trailing line with no closing punctuation that is not a list item, e.g. "De los consorcios": the
    next section's title in IMPO's original texts (Ley 16.060)."""
    p = p.strip()
    return (0 < len(p) <= 80 and p[0].isupper() and not ih.ITEM.match(p)
            and not p.endswith(('.', ';', ':', ',', ')', '"', '»', '”', '-')))


HEADINGS_DROPPED: list[str] = []


def _has_text(path: str) -> bool:
    return _load_text(path) is not None


ADDED_BY_EARLIER: dict[tuple[str, str], str] = {}
SYNTHETIC_ORIGINAL: set[tuple[str, str, str]] = set()


_install()

PART = UY / 'corpus.d' / '60-batch3.json'
VERIFICATION = HERE / 'verification.json'
RETRIEVED = '2026-10-29'
batch2.RETRIEVED = RETRIEVED          # batch2.check_against_impo compares the state on this day with IMPO

# Amending laws whose in-force day needs a reading impo_history and batch 2 cannot make (law -> (day, how)), each from
# the law's own vigencia article (IMPO text, cached), worked out by hand.
LAW_DAY: dict[str, tuple[str, str]] = {
    '18083': ('2007-07-01', 'its art. 113: "Las disposiciones de esta ley para las que no se haya establecido una '
                            'vigencia específica, regirán desde el 1º de julio de 2007"'),
    '19288': ('2014-11-01', 'its art. 21: "entrará en vigencia a partir del primer día del segundo mes siguiente al de '
                            'su promulgación" (promulgated 26/09/2014)'),
    '19551': ('2017-11-01', 'its art. 21: "entrará en vigencia en forma conjunta con la Ley N° 19.293" (the CPP, in '
                            'force 1 November 2017 by its art. 403; Ley 19.551 was promulgated 25/10/2017)'),
    '19747': ('2019-10-16', 'its art. 9: "entrará en vigencia a partir de los ciento ochenta días de su promulgación" '
                            '(promulgated 19/04/2019)'),
}
batch2.LAW_DAY.update(LAW_DAY)

OTHER_PARTS = [UY / 'corpus.json', UY / 'corpus.d' / '50-batch2.json']


def suspensions(act: dict, cfg: dict, laws: dict) -> list[str]:
    """A law that only suspended the vigencia of articles (SCHEMA.md: an event that changed no words): a version of
    its own on its in-force day, with no change of words, crediting it to exactly the articles whose IMPO notes say
    "Ver vigencia: <that law> artículo <n>"; the law carries a note saying what it did."""
    done = []
    main = ih.load(cfg['path'])
    arts, _ = ih.articles(main)
    for law, year, art, words, note in cfg.get('suspensions', []):
        path = ih.law_path(law, year, art)
        hdr = ih.load(path)
        text = ' '.join(hdr['textoArticulo'].split())
        assert text.startswith(words), (path, text[:200])
        day, how = ih.in_force(hdr, None)
        keys = sorted(a.key for a in arts if any(e.kind == 'vigencia' and e.law == law and e.art == art and not e.scope
                                                 for e in a.events))
        assert keys, (law, 'no article names it')
        vs = act['versions']
        assert all(v['from'] != day for v in vs), (law, day, 'a version already has that day')
        i = next((j for j, v in enumerate(vs) if v['from'] > day), len(vs))
        assert i > 0
        prev = vs[i - 1]['units']
        assert all(k in prev for k in keys), (law, [k for k in keys if k not in prev])
        vs.insert(i, {'from': day, 'source_url': f'{fetch.IMPO}/{path}',
                      'sha256': hashlib.sha256(fetch.fetch(fetch.impo(path), True)).hexdigest(),
                      'units': prev, 'credits': {k: [ih.law_key(law)] for k in keys}, 'note': None})
        laws[ih.law_key(law)] = {
            'label': ih.law_label(law), 'title': ih.title_case(hdr.get('nombreNorma') or ih.law_label(law)),
            'kind': 'law', 'enacted': ih.ddmmyyyy(hdr.get('fechaPromulgacion')),
            'published': ih.ddmmyyyy(hdr.get('fechaPublicacion')), 'url': f'{fetch.IMPO}/{ih.law_path(law, year)}',
            'temporary_until': None, 'restores': None, 'note': note}
        done.append(f'{ih.law_label(law)} art. {art} ("{words} ..."), in force {day} ({how}): wording unchanged, '
                    f'credited to {len(keys)} articles IMPO notes name it on: ' + ', '.join(keys))
    return done


def published_laws() -> dict[str, dict]:
    """Law entries of the published corpus (corpus.json and batch 2), which the build reads first and keeps."""
    out: dict[str, dict] = {}
    for p in OTHER_PARTS:
        for k, x in json.loads(p.read_text(encoding='utf-8')).get('laws', {}).items():
            out.setdefault(k, x)
    return out


def main(argv: list[str]) -> None:
    verification: dict = {}
    laws: dict = {}
    acts: list = []
    only = [a for a in argv if not a.startswith('--')]
    for slug, cfg in ACTS.items():
        if only and slug not in only:
            continue
        if not batch2.ready(cfg):
            print(slug, 'not fully cached: skipped', flush=True)
            continue
        l2, act, v = batch2.build_one(slug, cfg, verification)
        v['suspensions'] = suspensions(act, cfg, l2)
        laws.update(l2)
        acts.append(act)
        unresolved = [k for k, r in v['articles'].items() if 'unresolved' in r]
        print(slug, len(act['versions']), 'versions,', sum(len(x['credits']) for x in act['versions']),
              'credited unit changes; unresolved start', len(unresolved), '; post-pass',
              {k: len(x) for k, x in v['post_pass'].items()}, '; impo',
              {k: x['equal'] for k, x in v['impo_check'].items()}, flush=True)
    # A law the published corpus already has keeps that entry (the build keeps the first one it reads); any field
    # that differs is reported, never silently changed.
    pub = published_laws()
    shared = {}
    for k in sorted(set(laws) & set(pub)):
        diff = {f: [pub[k].get(f), laws[k].get(f)] for f in set(pub[k]) | set(laws[k]) if pub[k].get(f) != laws[k].get(f)}
        if diff:
            shared[k] = diff
        laws[k] = pub[k]
    verification['_shared_law_entries_differing'] = shared
    verification['_headings_dropped'] = sorted(set(HEADINGS_DROPPED))
    if '--dry' in argv or not acts:
        VERIFICATION.with_suffix('.dry.json').write_text(json.dumps(verification, ensure_ascii=False, indent=1),
                                                         encoding='utf-8', newline='\n')
        return
    for a in acts:
        batch2.as_changes(a)
    paths = set()
    for a in acts:
        cfg = ACTS[a['slug']]
        paths |= {cfg['path']} | set(ih.needed_paths(ih.load(cfg['path']), cfg['base'], cfg['vigencia']))
        paths |= set(batch2.sample_paths(cfg)) | set(cfg.get('extra', []))
    part = {
        'sources': [{'name': 'IMPO, Base de datos de normativa (acts of corpus.d/60-batch3)',
                     'url': 'https://www.impo.com.uy/bases', 'retrieved': RETRIEVED, 'requests': len(paths),
                     'licence': 'Texts from IMPO, Base de datos de normativa (www.impo.com.uy/bases).',
                     'notes': 'JSON (?json=true) of each act\'s consolidated text with IMPO\'s notes per article, '
                              'the original texts and amending articles they link, and each amending law. '
                              'robots.txt Crawl-Delay: 10 is kept.'}],
        'laws': dict(sorted(laws.items())),
        'acts': acts,
        'applies': [],
        'decisions': decisions([a['slug'] for a in acts], verification),
        'ai_use': ['A model (Claude) wrote batch3/fetch3.py and batch3/batch3.py (which reuse batch 2\'s code) and '
                   'read the vigencia articles listed in decisions. It wrote no legal text: every unit is parsed '
                   'from IMPO bytes in the cache, apart from the fixed placeholder sentence of the anachronism rule.'],
    }
    PART.parent.mkdir(exist_ok=True)
    tmp = PART.with_name(PART.name + '.tmp')
    tmp.write_text(json.dumps(part, ensure_ascii=False, indent=1) + '\n', encoding='utf-8', newline='\n')
    tmp.replace(PART)
    VERIFICATION.write_text(json.dumps(verification, ensure_ascii=False, indent=1) + '\n', encoding='utf-8',
                            newline='\n')
    print('wrote', PART, PART.stat().st_size, 'bytes')


DECISIONS_COMMON = [
    'Batch 3 acts (corpus.d/60-batch3.json) are rebuilt by batch 2\'s code unchanged (batch2.build_one over '
    'impo_history.py): each amended article starts from IMPO\'s original text, today\'s text is IMPO\'s consolidated '
    'text, intermediate texts are only those an amending law quotes or IMPO\'s notes determine, and each amending law '
    'is in force on the day its own vigencia article gives, else ten days after publication (Código Civil art. 1). '
    'Batch 2\'s readings of IMPO\'s notes and its anachronism rule (placeholder "' + batch2.PLACEHOLDER + '") apply.',
    'Batch 3: IMPO\'s original texts end with the next section\'s heading, in capitals ("PROCESO INFRACCIONAL '
    'ADUANERO") or as a short line with no closing punctuation ("De los consorcios"); such trailing lines are '
    'dropped from first texts and quoted wordings (the list is in batch3/verification.json, headings_dropped).',
    'Batch 3: articles are dated by each amending law\'s general in-force day as batch 2 does; where a law also '
    'amends an act of corpus.json or batch 2, it has the same day there.',
    'Batch 3: Ley Nº 19.889 (Ley de Urgente Consideración) was a candidate but is left out: IMPO\'s consolidated '
    'text of it gives 253 of its 476 articles only as "(*)" pointers to the laws they amended, so it has no '
    'self-standing consolidated text to rebuild; its changes are in those laws\' histories.',
]


def decisions(slugs: list[str], verification: dict) -> list[str]:
    out = list(DECISIONS_COMMON)
    for s in slugs:
        cfg = ACTS[s]
        out += ACT_DECISIONS.get(s, [])
        syn = sorted((lab for b, lab, _ in SYNTHETIC_ORIGINAL if b == cfg['base']), key=_natural)
        if syn:
            out.append(f'{cfg["short"]}: amended articles IMPO gives no TEXTO ORIGINAL link for start from IMPO\'s '
                       f'original text at {cfg["original_prefix"]}/<n>: ' + ', '.join(syn) + '.')
        added = sorted(x for (b, _), x in ADDED_BY_EARLIER.items() if b == cfg['base'])
        if added:
            out.append(f'{cfg["short"]}, dotted articles: ' + '; '.join(added) + '.')
        for x in verification[s].get('suspensions', []):
            out.append(f'{cfg["short"]}, suspension of vigencia: {x}.')
        for k, items in verification[s]['post_pass'].items():
            if items:
                out.append(f'{ACTS[s]["short"]}, {k.replace("_", " ")}: ' + '; '.join(items) + '.')
    return out


def _natural(label: str) -> list:
    return [int(x) if x.isdigit() else x for x in re.split(r'(\d+)', label)]


ACT_DECISIONS: dict[str, list[str]] = {
    'ley-17250': [
        'Ley 17.250: in force 27 August 2000, ten days after its publication on 17/08/2000 (it has no vigencia '
        'clause). Vigencia articles read by hand: Ley 18.046 art. 2 and Ley 18.362 art. 2 (1 January 2007 and 2009).',
        'Ley 17.250: Ley Nº 20.531 (promulgated 01/10/2026, in force 1 January 2027 by its art. 2) substitutes art. 16 '
        '(art. 108) and the acápite and literales C) and F) of art. 42 (art. 117); IMPO\'s consolidated text does not '
        'include it yet (IMPO notes only "Ver vigencia"), so it is not in this history.',
        'Ley 17.250, art. 31: Literal I) was added by Ley 19.149 and reworded by Ley 20.212; the 2014 wording is not '
        'determined by IMPO\'s notes, so the change is shown on 1 January 2024, credited to both laws.',
    ],
    'codigo-aduanero': [
        'CAROU: in force 18 March 2015, 180 days after its promulgation on 19/09/2014 (its art. 276).',
        'CAROU: Leyes 19.322 and 19.394 changed no words: each suspended the vigencia of arts. 224, 225, 227 to 257 '
        'and 269 (and of art. 275 as to its repeal of procedural articles of Ley 13.318), until 1 March 2016 and then '
        'until 16 July 2017, retroactively (each validates proceedings under the old law from the earlier date). They '
        'are recorded as wording-unchanged commits on their in-force days (ten days after publication; neither has a '
        'vigencia clause), crediting the 35 articles whose IMPO notes name them, with a note on each law; the '
        'articles\' text stays in the tree throughout. The day the suspension ended (16 July 2017) is not a commit.',
        'CAROU: Leyes 19.651 and 20.419 have no vigencia clause and are dated ten days after publication.',
        'CAROU: interpretative laws IMPO names on art. 240 (Leyes 19.924 art. 230, 19.996 art. 123, 20.446 art. 198) '
        'change no words and are not recorded.',
    ],
    'codigo-tributario': [
        'Código Tributario (Decreto-Ley Nº 14.306, kind "decree"): in force 16 December 1974, ten days after its '
        'publication on 06/12/1974 (no vigencia clause); the errata IMPO notes (published 13/12/1974) came before that '
        'day and are part of the first text. Decree-laws 14.416, 14.948, 15.294, 15.322 and 15.524 have no vigencia '
        'clause and are dated ten days after publication; Ley 18.083 by its art. 113 (1 July 2007).',
        'Código Tributario: in a fixed sample of 12 articles IMPO records no change to, 7 have the original\'s words '
        'exactly; arts. 5 ("las"/"los"), 13 ("Con"/"Son") and 105 ("representantes"/"representados", '
        '"dependencias"/"dependientes") differ by a word, art. 75 by a heading run into its text, and art. 40 by the '
        'words "ficta; se notifique la resolución definitiva" that no amending law IMPO names explains. Unamended '
        'articles carry IMPO\'s consolidated text throughout, so these are not committed as changes '
        '(batch3/verification.json, unamended_sample).',
    ],
    'ley-16060': [
        'Ley 16.060: in force 31 December 1989, sixty days after its publication on 01/11/1989 (its art. 511), the '
        'day batch 2 uses for it in the Código de Comercio. Its law entry is the one batch 2 published (title "LEY DE '
        'SOCIEDADES COMERCIALES").',
        'Ley 16.060: vigencia articles read by hand: Ley 16.736 art. 2 (1 January 1996), Ley 16.871 art. 101 (1 '
        'January 1998), Ley 18.083 art. 113 (1 July 2007), Ley 19.288 art. 21 ("primer día del segundo mes siguiente '
        'al de su promulgación", promulgated 26/09/2014: 1 November 2014); laws without a vigencia clause are dated '
        'ten days after publication.',
        'Ley 16.060: in a fixed sample of 12 unamended articles, 11 have the original\'s words (after dropping the '
        'next section\'s heading); art. 345 differs only in where a paragraph breaks.',
    ],
    'codigo-ninez-adolescencia': [
        'CNA: in force 24 September 2004, ten days after its publication on 14/09/2004 (no vigencia clause). Vigencia '
        'read by hand: Ley 19.075 art. 29 (90 days after promulgation, as the Código Civil uses it), Ley 19.551 art. 21 '
        '(with the CPP, 1 November 2017), Ley 19.747 art. 9 (180 days after promulgation on 19/04/2019: 16 October '
        '2019); the others by their own vigencia article or ten days after publication.',
        'CNA: IMPO numbers articles added inside a chapter 120.1, 132.1, 133.1 ... (IMPO "120 / 1"); they are labelled '
        '"Artículo 120.1" with keys art-120-1.',
        'CNA: in a fixed sample of 12 unamended articles, 10 have the original\'s words; art. 28 as enacted also '
        'reworded inciso 4 of Código Civil art. 227, a paragraph IMPO\'s consolidated text leaves out, and art. 199 '
        'reads "Instituto del Niño y Adolescente del Uruguay (INAU)" for the original "Instituto Nacional del Menor", '
        'the renaming art. 223 orders in the text; neither is committed as a change. Where an amended article\'s '
        'original says INAME, the INAU wording appears in its first recorded change.',
    ],
}


if __name__ == '__main__':
    if sys.argv[1:2] == ['--vigencia']:
        batch2.ACTS.update(ACTS)
        for s in sys.argv[2:]:
            batch2.vigencia_report(s)
    else:
        main(sys.argv[1:])
