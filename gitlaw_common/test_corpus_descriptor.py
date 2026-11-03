"""The root corpus.json the builder writes (corpus_descriptor): ISO path, history, record dates and citation rule.

    python -X utf8 scripts/gitlaw_common/test_corpus_descriptor.py
"""
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build as B  # noqa: E402

FAIL = []


def ok(name, cond, extra=''):
    print(('PASS ' if cond else 'FAIL ') + name + (f'  [{extra}]' if extra else ''), flush=True)
    if not cond:
        FAIL.append(name)


def corpus(code='XX', slug='testland', lang='de', units=('par-001', 'par-002', 'par-008a', 'art-001'), versions=2,
           law_dates=True, **country):
    laws = {'g1': {'label': 'G 1', 'enacted': '2001-01-10' if law_dates else None,
                   'published': '2001-01-20' if law_dates else None}}
    vs = [{'from': f'200{i + 1}-02-01', 'units': {k: {'label': k, 'text': f'{k} v{i}\n'} for k in units}}
          for i in range(versions)]
    vs.append({'from': '2099-01-01', 'units': {k: {'label': k, 'text': 'later\n'} for k in units}})  # future branch
    return {'country': {'code': code, 'name': 'Testland', 'slug': slug, 'lang': lang, 'tz': 'UTC',
                        'publisher': {'name': 'Gazette', 'email': 'g@test.invalid'}, **country},
            'laws': laws, 'sources': [{'name': 's', 'url': 'https://test.invalid', 'retrieved': '2026-10-30'},
                                      {'name': 's', 'url': 'https://test.invalid', 'retrieved': '2026-10-28'}],
            'acts': [{'slug': 'gesetz', 'short': 'G', 'title': 'Gesetz', 'first_law': 'g1', 'versions': vs}]}


d = lambda c, day='2026-11-01': B.corpus_descriptor(c, [], day)  # noqa: E731
PATH = re.compile(r'[a-z]{2}(/[a-z0-9-]+){2,3}')
for code, slug, want in (('XX', 'testland', 'xx/national/acts'), ('DE-HB', 'germany-bremen', 'de/bremen/acts'),
                         ('BR-MG-MURIAE', 'brazil-muriae-city', 'br/minas-gerais/muriae/acts'),
                         ('US-AZ', 'united-states-arizona', 'us/arizona/acts'),
                         ('ID-BE', 'indonesia-bengkulu', 'id/bengkulu/acts')):
    got = d(corpus(code, slug))['corpus']
    ok(f'path {slug} -> {want}', got == want and PATH.fullmatch(got), got)
ok('country.corpus wins', d(corpus(corpus='de/bremen/verordnungen'))['corpus'] == 'de/bremen/verordnungen')

x = d(corpus())
ok('history in-force with several versions', x['history'] == 'in-force')
ok('history_from: the first version on main', x['history_from'] == '2001-02-01', x['history_from'])
ok('record_to: newest retrieval, capped at the docs date', x['record_to'] == '2026-10-30' and
   d(corpus(), '2026-10-29')['record_to'] == '2026-10-29')
ok('checked_on: the docs date', x['checked_on'] == '2026-11-01')
ok('the future branch is not counted', '2099' not in json.dumps(x), x['coverage'])
ok('in_force_trailer and no correction_trailer', x['in_force_trailer'] == 'In-force' and 'correction_trailer' not in x)
ok('record_note names the publisher', x['record_note'] == 'Texts from Gazette.')
ok('as-enacted: one version, dated from its law', d(corpus(versions=1))['history'] == 'as-enacted')
ok('current-only when one version and its law is undated', d(corpus(versions=1, law_dates=False))['history'] == 'current-only')
ok('country.history wins', d(corpus(versions=1, law_dates=False, history='current-only'))['history'] == 'current-only')

cit = x['citation']
rx = re.compile(cit['file'])
ok('citation: German par -> §', cit['cites'].startswith('§'), cit)
ok('citation.file: (folder, number), letters kept', rx.fullmatch('gesetz/par-008a.md').groups() == ('gesetz', '8a')
   and rx.fullmatch('gesetz/par-001.md').group(2) == '1' and not rx.fullmatch('gesetz/art-001.md')
   and not rx.fullmatch('README.md') and not rx.fullmatch('gesetz/README.md'))
pt = d(corpus(lang='pt', units=('art-0001', 'art-0002', 'art-0005-a', '000-titulo')))['citation']
ok('citation: Portuguese art, plain numbers only', re.fullmatch(pt['file'], 'lei-1/art-0005.md')
   and not re.fullmatch(pt['file'], 'lei-1/art-0005-a.md'), pt)
ok('no citation for a prefix with no known rule', 'citation' not in d(corpus(lang='fr', units=('sec-1', 'sec-2'))))
ok('no citation when the prefix is under half the files',
   'citation' not in d(corpus(units=('par-001', 'z-anlage-01', 'z-anlage-02', 'y-inhalt', '000-titel'))))
ok('a small corpus: the only numbered prefix counts though boilerplate outnumbers it',
   'citation' in d(corpus(lang='id', units=('pasal-001', 'pasal-002', 'a-pembukaan', 'z1-penutup', 'z2-penjelasan'))))
with tempfile.TemporaryDirectory() as tmp:
    (Path(tmp) / 's.txt').write_text('nach § 8a Abs. 1 und Art. 3 sowie art. 5º, Pasal 7 dan section 12\n',
                                     encoding='utf-8')
    for (prefix, lang), (cites, _) in B.CITATION.items():
        n = {'par': '8a', 'art': '3' if lang in ('de', 'nl') else '5', 'pasal': '7', 's': '12', 'sec': '12'}[prefix]
        r = subprocess.run(['git', 'grep', '-E', '-q', '--no-index', cites.replace('{n}', n), '--', 's.txt'], cwd=tmp)
        ok(f'cites {prefix}/{lang} runs in git grep -E and finds {n}', r.returncode == 0, cites)

# docs_files writes it at the root, valid JSON, and never over a hand-made one in repo/.
with tempfile.TemporaryDirectory() as tmp:
    f = Path(tmp)
    c = corpus()
    c['_docs_date'] = '2026-11-01'
    files = B.docs_files(c, f, b'{}', [], {}, '2026-11-01')
    ok('docs_files writes corpus.json at the root', json.loads(files['corpus.json'])['corpus'] == 'xx/national/acts')
    (f / 'repo').mkdir()
    (f / 'repo' / 'corpus.json').write_text('{"corpus": "xx/hand/made"}\n', encoding='utf-8')
    files = B.docs_files(c, f, b'{}', [], {}, '2026-11-01')
    ok('a hand-made repo/corpus.json is kept', json.loads(files['corpus.json'])['corpus'] == 'xx/hand/made')

print('all passed' if not FAIL else 'FAILED: ' + ', '.join(FAIL))
sys.exit(1 if FAIL else 0)
