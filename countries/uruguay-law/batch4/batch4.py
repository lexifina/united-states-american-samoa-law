"""Batch 4 of Uruguayan acts: writes scripts/uruguay-law/corpus.d/70-batch4.json (gitlaw_common/SCHEMA.md).

    python -X utf8 scripts/uruguay-law/batch4/batch4.py [slugs] [--dry]
    python -X utf8 scripts/uruguay-law/batch4/batch4.py --vigencia <slug>...   # amending laws' days + candidates
    python -X utf8 scripts/uruguay-law/batch4/batch4.py --count [slugs]        # IMPO paths needed / still missing

Reads only the shared .cache (fetched by batch4/fetch4.py). Each act is rebuilt exactly as batches 2 and 3 rebuilt
theirs: batch2.build_one (imported, not copied) over the main agent's impo_history.build_act, with batch 2's readings
of IMPO's notes, its post-pass and its check that today's text equals IMPO's consolidated text, plus batch 3's
readings (original links for amended articles IMPO gives none for, trailing section headings, dotted articles,
suspensions). batch 3 installs its readings for its own acts' original-text prefixes when imported; they are
re-installed here once with this batch's prefixes added (batch3._install, unchanged). This module holds only the
acts' table, the vigencia articles read by hand, and the part writer.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
UY = HERE.parent
sys.path.insert(0, str(UY))
sys.path.insert(0, str(UY / 'batch2'))
sys.path.insert(0, str(UY / 'batch3'))
import fetch  # noqa: E402
import impo_history as ih  # noqa: E402

_ORIG = {n: getattr(ih, n) for n in ('articles', 'drop_headings', 'unit_label', 'quoted_article')}
import batch2  # noqa: E402
import batch3  # noqa: E402

# slug -> as batch3.ACTS (IMPO path, the act's own law, vigencia articles read by hand, whether the base law enacted
# the text, the prefix of IMPO's original texts, the act's own in-force day).
ACTS: dict[str, dict] = {
    'ley-18381': {
        'short': 'Ley 18.381', 'title': 'Ley sobre el Derecho de Acceso a la Información Pública (Ley Nº 18.381)',
        'path': 'leyes/18381-2008', 'base': '18381', 'enacted': True,
        'original_prefix': 'leyes-originales/18381-2008',
        'vigencia': {},
    },
    'ley-17514': {
        'short': 'Ley 17.514', 'title': 'Ley de Erradicación de la Violencia Doméstica (Ley Nº 17.514)',
        'path': 'leyes/17514-2002', 'base': '17514', 'enacted': True,
        'original_prefix': 'leyes-originales/17514-2002',
        'vigencia': {},
    },
    'ley-19580': {
        'short': 'Ley 19.580', 'title': 'Ley de Violencia hacia las Mujeres Basada en Género (Ley Nº 19.580)',
        'path': 'leyes/19580-2017', 'base': '19580', 'enacted': True,
        'original_prefix': 'leyes-originales/19580-2017',
        'vigencia': {},
    },
    'ley-19574': {
        'short': 'Ley 19.574', 'title': 'Ley Integral contra el Lavado de Activos (Ley Nº 19.574)',
        'path': 'leyes/19574-2017', 'base': '19574', 'enacted': True,
        'original_prefix': 'leyes-originales/19574-2017',
        'vigencia': {},
    },
    'codigo-mineria': {
        'short': 'Código de Minería', 'title': 'Código de Minería (Decreto-Ley Nº 15.242)',
        'path': 'codigo-mineria/15242-1982', 'base': '15242', 'enacted': True,
        'original_prefix': 'decretos-leyes-originales/15242-1982',
        'vigencia': {},
        'base_in_force': ('codigo-mineria/15242-1982/135', '1982-04-01',
                          'El presente Código de Minería entrará en vigencia el 1'),
    },
    'codigo-rural': {
        'short': 'Código Rural', 'title': 'Código Rural (Ley Nº 10.024)',
        'path': 'codigo-rural/10024-1941', 'base': '10024', 'enacted': True,
        'original_prefix': 'textos-originales-ley/10024-1941',
        'vigencia': {},
        'base_in_force': ('codigo-rural/10024-1941/291', '1942-06-14',
                          'El presente Código empezará a regir al año de su promulgación'),
    },
}

# Vigencia articles of amending laws whose IMPO notes give none, read by hand (`--vigencia`); batch 3's table first,
# so a law shared with an earlier batch has the same day.
VIGENCIA: dict[str, str] = {'15903': '2', '16170': '2', '16226': '2',   # as corpus.json (CP) and batch 2 (CGP) read them
                             '16389': '3'}
for _cfg in ACTS.values():
    _cfg['vigencia'] = {**batch3.VIGENCIA, **VIGENCIA, **_cfg['vigencia']}


def _reinstall() -> None:
    """batch 3's readings again, with this batch's original-text prefixes added to batch 3's (batch3._install reads
    the prefixes from batch3.ACTS once, when it runs)."""
    for n, f in _ORIG.items():
        setattr(ih, n, f)
    ih._batch3 = False
    for slug, cfg in ACTS.items():
        assert slug not in batch3.ACTS
    batch3.ACTS.update(ACTS)
    try:
        batch3._install()
    finally:
        for slug in ACTS:
            del batch3.ACTS[slug]


_reinstall()

# One more reading, in this process only: impo_history inserts incisos an earlier law added ("Agrégase ... el
# siguiente inciso") only for a single "Inciso 3º)"; IMPO also notes a run, "Incisos 2º), 3º) y 4º) anteriormente
# agregado/s por: Ley Nº 19.889 ... artículo 225", whose article quotes the incisos together. A run of consecutive
# numbers is read as starting at its first inciso, so the quoted paragraphs go in at that place; check_runs() then
# asserts that the text grew by exactly as many paragraphs as the run names.
INCISO_RUN = re.compile(r'Incisos (\d+)[º°]?\)?((?:\s*,\s*\d+[º°]?\)?)*)\s+y\s+(\d+)[º°]?\)?')
RUNS: dict[str, list[int]] = {}
_inciso_no = ih.inciso_no


def inciso_no(scope: str) -> int | None:
    n = _inciso_no(scope)
    if n is not None:
        return n
    m = INCISO_RUN.fullmatch(scope.strip())
    if not m:
        return None
    nums = [int(m.group(1))] + [int(x) for x in re.findall(r'\d+', m.group(2))] + [int(m.group(3))]
    if nums != list(range(nums[0], nums[0] + len(nums))):
        return None
    RUNS[scope.strip()] = nums
    return nums[0]


ih.inciso_no = inciso_no


# Errata published before an act's first day, which IMPO's original text of an amended article does not carry (its
# consolidated text of unamended articles does): (slug, unit) -> [(the misprint, the correction, the errata)]. Each
# replacement is made in that article's first text only, and must occur exactly once.
ERRATA: dict[tuple[str, str], list[tuple[str, str, str]]] = {
    ('codigo-mineria', 'art-116'): [
        ('sin perjuicio de la vigencia de las autoridades', 'sin perjuicio de la vigilancia de las autoridades',
         'fe-erratas/SN19820317001-1982/1 (Diario Oficial 17/03/1982): "En el artículo 116, quinta línea del literal '
         'a), donde dice: "vigencia", debe decir: "vigilancia""'),
    ],
}


def apply_errata(act: dict) -> list[str]:
    out = []
    for (slug, key), fixes in ERRATA.items():
        if slug != act['slug']:
            continue
        first = act['versions'][0]['units'][key]
        new = dict(first)
        for old, fix, src in fixes:
            assert new['text'].count(old) == 1, (slug, key, old)
            new['text'] = new['text'].replace(old, fix)
            out.append(f'{first["label"]}: "{old}" -> "{fix}" in its first text, by the errata {src}')
        for v in act['versions']:
            if v['units'].get(key) == first:
                v['units'][key] = new
    return out


def check_runs(act: dict, main: dict, base: str) -> list[str]:
    """Every intermediate text built from a run of incisos has exactly len(run) more top-level paragraphs than the
    text before it, and the step is credited to the law that added them."""
    arts, _ = ih.articles(main)
    tl, _ = batch2.timelines(act)
    out = []
    for a in arts:
        for e in a.events:
            run = RUNS.get(e.scope.strip())
            if not run or e.kind not in ('added', 'added-earlier') or e.law == base:
                continue
            chain = tl.get(a.key, [])
            i = next((i for i, c in enumerate(chain) if c[2] == [ih.law_key(e.law)]), None)
            if i is None:
                continue        # the run was not used (the text before it is not known)
            tops = [len([p for p in c[1]['text'].splitlines()[1:] if not ih.ITEM.match(p)]) for c in chain[i - 1:i + 1]]
            assert tops[1] - tops[0] == len(run), (a.key, e.scope, tops)
            out.append(f'{a.label}: {e.scope} as {ih.law_label(e.law)} art. {e.art} adds them (quoted together), '
                       f'from {chain[i][0]}')
    return out

PART = UY / 'corpus.d' / '70-batch4.json'
VERIFICATION = HERE / 'verification.json'
RETRIEVED = '2026-10-29'
batch2.RETRIEVED = RETRIEVED

# Amending laws whose in-force day needs a reading impo_history and batches 2-3 cannot make (law -> (day, how)).
LAW_DAY: dict[str, tuple[str, str]] = {
    '16389': ('1993-07-06', 'its art. 3: "La presente ley entrará en vigencia a partir de su promulgación" '
                            '(promulgated 06/07/1993)'),
}
batch2.LAW_DAY.update(LAW_DAY)

OTHER_PARTS = [UY / 'corpus.json', UY / 'corpus.d' / '50-batch2.json', UY / 'corpus.d' / '60-batch3.json']


def published_laws() -> dict[str, dict]:
    out: dict[str, dict] = {}
    for p in OTHER_PARTS:
        for k, x in json.loads(p.read_text(encoding='utf-8')).get('laws', {}).items():
            out.setdefault(k, x)
    return out


def all_paths(cfg: dict) -> list[str]:
    main = ih.load(cfg['path'])
    extra = [cfg['base_in_force'][0]] if cfg.get('base_in_force') else []
    extra += cfg.get('extra', []) + batch2.sample_paths(cfg)
    return [cfg['path']] + extra + ih.needed_paths(main, cfg['base'], cfg['vigencia'])


def count(only: list[str]) -> None:
    for slug, cfg in ACTS.items():
        if only and slug not in only:
            continue
        try:
            paths = all_paths(cfg)
        except FileNotFoundError:
            print(slug, 'main JSON not cached')
            continue
        todo = [p for p in paths if not fetch.cache_path(fetch.impo(p)).exists()]
        print(slug, len(paths), 'paths,', len(todo), 'missing', f'(~{len(todo) * 10.5 / 60:.0f} min)')


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
        v['suspensions'] = batch3.suspensions(act, cfg, l2)
        v['post_pass']['inciso_runs'] = check_runs(act, ih.load(cfg['path']), cfg['base'])
        v['post_pass']['errata_in_first_text'] = apply_errata(act)
        v['impo_check'] = batch2.check_against_impo(act, ih.load(cfg['path']))
        laws.update(l2)
        acts.append(act)
        unresolved = [k for k, r in v['articles'].items() if 'unresolved' in r]
        print(slug, len(act['versions']), 'versions,', sum(len(x['credits']) for x in act['versions']),
              'credited unit changes; unresolved start', len(unresolved), '; post-pass',
              {k: len(x) for k, x in v['post_pass'].items()}, '; impo',
              {k: x['equal'] for k, x in v['impo_check'].items()}, flush=True)
    pub = published_laws()
    shared = {}
    for k in sorted(set(laws) & set(pub)):
        diff = {f: [pub[k].get(f), laws[k].get(f)] for f in set(pub[k]) | set(laws[k]) if pub[k].get(f) != laws[k].get(f)}
        if diff:
            shared[k] = diff
        laws[k] = pub[k]
    verification['_shared_law_entries_differing'] = shared
    verification['_headings_dropped'] = sorted(set(batch3.HEADINGS_DROPPED))
    if '--dry' in argv or not acts:
        VERIFICATION.with_suffix('.dry.json').write_text(json.dumps(verification, ensure_ascii=False, indent=1),
                                                         encoding='utf-8', newline='\n')
        return
    for a in acts:
        batch2.as_changes(a)
    paths = set()
    for a in acts:
        paths |= set(all_paths(ACTS[a['slug']]))
    part = {
        'sources': [{'name': 'IMPO, Base de datos de normativa (acts of corpus.d/70-batch4)',
                     'url': 'https://www.impo.com.uy/bases', 'retrieved': RETRIEVED, 'requests': len(paths),
                     'licence': 'Texts from IMPO, Base de datos de normativa (www.impo.com.uy/bases).',
                     'notes': 'JSON (?json=true) of each act\'s consolidated text with IMPO\'s notes per article, '
                              'the original texts and amending articles they link, and each amending law. '
                              'robots.txt Crawl-Delay: 10 is kept.'}],
        'laws': dict(sorted(laws.items())),
        'acts': acts,
        'applies': [],
        'decisions': decisions([a['slug'] for a in acts], verification),
        'ai_use': ['A model (Claude) wrote batch4/fetch4.py and batch4/batch4.py (which reuse batches 2 and 3\'s '
                   'code) and read the vigencia articles listed in decisions. It wrote no legal text: every unit is '
                   'parsed from IMPO bytes in the cache, apart from the fixed placeholder sentence of the '
                   'anachronism rule.'],
    }
    tmp = PART.with_name(PART.name + '.tmp')
    tmp.write_text(json.dumps(part, ensure_ascii=False, indent=1) + '\n', encoding='utf-8', newline='\n')
    tmp.replace(PART)
    VERIFICATION.write_text(json.dumps(verification, ensure_ascii=False, indent=1) + '\n', encoding='utf-8',
                            newline='\n')
    print('wrote', PART, PART.stat().st_size, 'bytes')


DECISIONS_COMMON = [
    'Batch 4 acts (corpus.d/70-batch4.json) are rebuilt by the code of batches 2 and 3 unchanged (batch2.build_one '
    'over impo_history.py, with batch 3\'s readings): each amended article starts from IMPO\'s original text, '
    'today\'s text is IMPO\'s consolidated text, intermediate texts are only those an amending law quotes or IMPO\'s '
    'notes determine, and each amending law is in force on the day its own vigencia article gives, else ten days '
    'after publication (Código Civil art. 1); a law shared with an earlier part has the same day there.',
    'Batch 4: legalize-dev/legalize-uy was checked as a faster source and not used for text: its 10,155 law commits '
    'are each a single "[bootstrap]" snapshot of IMPO\'s consolidated text taken in 2026, dated by the base law\'s '
    'publication, with IMPO\'s notes dropped, so it holds no earlier wording and names no amending law; its words '
    'equal IMPO\'s for the laws compared (Leyes 18.331, 16.060, 17.250: 620 of the 623 articles matched by label '
    'word for word, the other 3 only adding the signatories), and it has no file for the codes. Common Crawl (six '
    '2026 crawls) holds some of IMPO\'s HTML pages (e.g. 206 URLs under codigo-rural/, many of them reference pages) '
    'but none of the JSON with notes that the rebuild reads. Every text here is IMPO\'s JSON, fetched live with its '
    'crawl delay.',
]


def decisions(slugs: list[str], verification: dict) -> list[str]:
    out = list(DECISIONS_COMMON)
    for s in slugs:
        cfg = ACTS[s]
        out += ACT_DECISIONS.get(s, [])
        syn = sorted((lab for b, lab, _ in batch3.SYNTHETIC_ORIGINAL if b == cfg['base']), key=batch3._natural)
        if syn:
            out.append(f'{cfg["short"]}: amended articles IMPO gives no TEXTO ORIGINAL link for start from IMPO\'s '
                       f'original text at {cfg["original_prefix"]}/<n>: ' + ', '.join(syn) + '.')
        added = sorted(x for (b, _), x in batch3.ADDED_BY_EARLIER.items() if b == cfg['base'])
        if added:
            out.append(f'{cfg["short"]}, dotted articles: ' + '; '.join(added) + '.')
        for x in verification[s].get('suspensions', []):
            out.append(f'{cfg["short"]}, suspension of vigencia: {x}.')
        for k, items in verification[s]['post_pass'].items():
            if items:
                out.append(f'{cfg["short"]}, {k.replace("_", " ")}: ' + '; '.join(items) + '.')
    return out


ACT_DECISIONS: dict[str, list[str]] = {
    'ley-18381': [
        'Ley 18.381: in force 17 November 2008, ten days after its publication on 07/11/2008 (no vigencia clause); '
        'amended by Leyes 18.719 (1 January 2011, its art. 3), 19.178 (no vigencia clause: ten days after '
        'publication, 18 January 2014) and 19.996 (1 January 2022, its art. 2). Every article of the fixed sample of '
        'unamended articles has the original\'s words.',
    ],
    'ley-17514': [
        'Ley 17.514: in force 19 July 2002, ten days after its publication on 09/07/2002 (no vigencia clause); amended '
        'by Ley 19.580 (which also repealed arts. 24 to 29; ten days after publication, 19 January 2018) and Ley '
        '19.670 (1 January 2019, its art. 2). Every article of the fixed sample of unamended articles has the '
        'original\'s words.',
    ],
    'ley-19580': [
        'Ley 19.580: in force 19 January 2018, ten days after its publication on 09/01/2018 (no vigencia clause; its '
        'law entry is the one corpus.json published, as it amends the Código Civil and Código Penal the same day). '
        'Ley 19.791 has no vigencia clause and is dated ten days after publication (4 October 2019).',
        'Ley 19.580: in the fixed sample of 12 unamended articles, 11 have the original\'s paragraphs exactly; art. '
        '24 has the same words, with IMPO\'s consolidated text breaking its first line one word later.',
    ],
    'ley-19574': [
        'Ley 19.574: in force 20 January 2018, ten days after its publication on 10/01/2018 (no vigencia clause). '
        'Leyes 19.749, 19.889, 20.327 and 20.469 have no vigencia clause and are dated ten days after publication; '
        'Ley 20.130 by its art. 6 numeral 1 (1 August 2023), as batch 2 dates it.',
        'Ley 19.574, art. 34: Ley 20.327 art. 4 added a numeral 34) and Ley 20.469 then reworded the article whole; '
        'the text in between is not determined (the quote does not say whether the numeral goes before or after the '
        'closing paragraph), so the change is shown on Ley 20.469\'s day, credited to both laws. Art. 17: Ley 19.889 '
        'art. 225 added incisos 2 to 4 to a one-inciso article, quoted together; that text is the version from 24 July '
        '2020 (batch4/verification.json, inciso_runs).',
        'Ley 19.574: in the fixed sample of 12 unamended articles, 11 have the original\'s words; art. 56 reads '
        '"escuchará" for the original\'s "escuchara", an accent no amending law explains, not committed as a change.',
    ],
}


if __name__ == '__main__':
    if sys.argv[1:2] == ['--vigencia']:
        batch2.ACTS.update(ACTS)
        for s in sys.argv[2:]:
            batch2.vigencia_report(s)
    elif sys.argv[1:2] == ['--count']:
        count(sys.argv[2:])
    else:
        main(sys.argv[1:])
