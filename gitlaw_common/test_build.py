"""End-to-end test of the shared builder on a small invented corpus that exercises every rule in SCHEMA.md.

    python -X utf8 scripts/gitlaw_common/test_build.py
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent


def corpus() -> dict:
    u = lambda label, text: {'label': label, 'kind': 'art', 'text': text}
    v1 = {'art-001': u('Art. 1', '# Art. 1\nLa República es democrática.\n'),
          'art-002': u('Art. 2', '# Art. 2\nEl límite es 100.\n')}
    v2 = {**v1, 'art-002': u('Art. 2', '# Art. 2\nEl límite es 200.\n'), 'art-002-bis': u('Art. 2 bis', '# Art. 2 bis\nNuevo.\n')}
    v3 = {**v2, 'art-001': u('Art. 1', '# Art. 1\nLa República es democrática y social.\n')}
    v4 = {k: x for k, x in v3.items() if k != 'art-002-bis'}
    v5 = {**v4, 'art-002': u('Art. 2', '# Art. 2\nEl límite es 100.\n')}
    v6 = {**v5, 'art-001': u('Art. 1', '# Art. 1\nLa República es democrática, social y federal.\n')}
    cc1 = {'art-001': u('Art. 1', '# Art. 1\nLas leyes obligan.\n')}
    cc2 = {'art-001': u('Art. 1', '# Art. 1\nLas leyes obligan a todos.\n')}
    data = {
        'country': {'code': 'XX', 'name': 'Testland', 'slug': 'testland', 'lang': 'es', 'tz': 'America/Santiago',
                    'future_branch': 'futuro', 'publisher': {'name': 'Boletín (test)', 'email': 'boletin@test.invalid'},
                    'default_in_force_rule': {'text': 'from publication', 'source': 'https://example.invalid/rule'}},
        'sources': [{'name': 'Test', 'url': 'https://example.invalid', 'retrieved': '2026-10-28', 'requests': 3, 'licence': 'CC0'}],
        'laws': {
            'const-1925': {'label': 'Constitución de 1925', 'kind': 'law', 'enacted': '1925-09-18', 'published': '1925-09-18'},
            'ley-100': {'label': 'Ley 100', 'kind': 'law', 'title': 'Sube el límite', 'enacted': '1965-01-01', 'published': '1965-01-02',
                        'temporary_until': '1999-12-31'},
            'ley-101': {'label': 'Ley 101', 'kind': 'law', 'title': 'Añade el 2 bis', 'enacted': '1964-12-30', 'published': '1964-12-31'},
            'ley-200': {'label': 'Ley 200', 'kind': 'law', 'title': 'Social', 'enacted': '2001-03-01', 'published': '2001-03-02'},
            'ley-201': {'label': 'Ley 201', 'kind': 'law', 'title': 'Sin cambios de texto', 'enacted': '2001-03-01', 'published': '2001-03-02'},
            'c-55-05': {'label': 'Sentencia C-55/05', 'kind': 'court', 'title': 'Inexequible el 2 bis', 'enacted': '2005-05-05'},
            'ley-300': {'label': 'Ley 300', 'kind': 'law', 'title': 'Fin del límite temporal', 'enacted': '2009-12-01',
                        'restores': 'ley-100'},
            'ley-400': {'label': 'Ley 400', 'kind': 'referendum', 'title': 'Federal', 'enacted': '2099-01-01'},
            'cc-1': {'label': 'Código Civil', 'kind': 'law', 'enacted': '2000-01-01'},
            'ley-500': {'label': 'Ley 500', 'kind': 'law', 'enacted': '2016-01-01', 'published': '2016-01-02'},
            'ref-2016': {'label': 'Referéndum 2016', 'kind': 'referendum', 'enacted': '2016-02-21', 'note': 'Rejected by the voters; the text was not changed.'},
        },
        'acts': [
            {'slug': 'constitucion', 'short': 'CPT', 'title': 'Constitución de Testland', 'url': 'https://example.invalid/c',
             'first_law': 'const-1925', 'versions': [
                {'from': '1925-10-18', 'units': v1, 'credits': {}},
                {'from': '1965-01-12', 'units': v2, 'credits': {'art-002': ['ley-101', 'ley-100'], 'art-002-bis': ['ley-101']}},
                {'from': '2001-03-12', 'units': v3, 'credits': {'art-001': ['ley-200'], 'art-099': ['ley-201']}},
                {'from': '2005-06-01', 'units': v4, 'credits': {'art-002-bis': ['c-55-05']}},
                {'from': '2010-01-01', 'units': v5, 'credits': {}, 'note': 'The temporary limit ended.'},
                {'from': '2016-02-21', 'credits': {'art-002': ['ref-2016']}},
                {'from': '2016-02-21', 'same_day': True, 'changes': {'art-003': {'label': 'Art. 3', 'kind': 'art', 'text': '# Art. 3\nMismo día.\n'}}, 'credits': {'art-003': ['ley-500']}},
                {'from': '2099-02-01', 'units': v6, 'credits': {'art-001': ['ley-400']}},
            ]},
            {'slug': 'codigo-civil', 'short': 'CC', 'title': 'Código Civil', 'first_law': None, 'earlier_laws': ['cc-1'],
             'versions': [{'from': '2000-06-01', 'units': cc1}, {'from': '2001-03-12', 'changes': {'art-001': cc2['art-001']}, 'credits': {'art-001': ['ley-200']}}]},
        ],
        'applies': [{'law': 'ley-200', 'provision': 'art-001',
                     'groups': [{'conditions': [{'kind': 'commenced_on_or_after', 'date': '2001-03-12'}], 'set_by': 'Ley 200, art. 2 transitorio'}]}],
        'decisions': ['Test decision.'], 'ai_use': ['none'],
    }
    # These invented test texts have no source images.
    for act in data['acts']:
        for version in act['versions']:
            version['source_images'] = 0
    return data


def run(*args, cwd=None):
    out = subprocess.run([sys.executable, '-X', 'utf8', *args], capture_output=True, text=True, encoding='utf-8', cwd=cwd)
    return out.returncode, out.stdout + out.stderr


def main():
    tmp = Path(tempfile.mkdtemp())
    try:
        folder = tmp / 'testland-law'
        (folder / 'repo').mkdir(parents=True)
        (folder / 'repo' / 'README.md').write_text('# Testland law\n', encoding='utf-8')
        # The Civil Code goes in a corpus.d part, as a second agent working on the same country would write it.
        c = corpus()
        cc = c['acts'].pop(1)
        (folder / 'corpus.json').write_text(json.dumps(c, ensure_ascii=False, indent=1), encoding='utf-8')
        (folder / 'corpus.d').mkdir()
        (folder / 'corpus.d' / '20-codigo-civil.json').write_text(json.dumps(
            {'acts': [cc], 'laws': {'cc-1': c['laws']['cc-1']}, 'decisions': ['Part decision.']}, ensure_ascii=False),
            encoding='utf-8')
        repo, again = tmp / 'repo', tmp / 'again'
        code, out = run(str(HERE / 'build.py'), str(folder), '--repo', str(repo), '--docs-date', '2026-10-28')
        assert code == 0, out
        code, out = run(str(HERE / 'check.py'), str(repo), '--corpus', str(folder / 'corpus.json'), '--write')
        assert code == 0, out
        res = json.loads(out)
        assert res['mismatches'] == 0 and res['versions'] == 10, res
        code, out = run(str(HERE / 'build.py'), str(folder), '--repo', str(again), '--docs-date', '2026-10-28', '--compare', str(repo))
        assert code == 0, out
        g = lambda *a: subprocess.run(['git', *a], cwd=repo, capture_output=True, text=True, encoding='utf-8').stdout
        log = g('log', '--format=%an|%s|%ad', '--date=iso-strict', 'main')
        print(log)
        assert 'Ley 101|' in log and 'Ley 100|' in log and 'Sentencia C-55/05|' in log and 'Boletín (test)|' in log
        assert 'Ley 400' not in log and 'Ley 400' in g('log', '--format=%an', 'futuro')
        assert '1970-01-01' in log and '-03:00' in log
        msg = g('log', '-1', '--format=%B', 'law/ley-100')
        assert 'Also-amended-by: Ley 101' in msg and 'Temporary-until: 1999-12-31' in msg, msg
        msg = g('log', '-1', '--format=%B', 'law/ley-101')
        assert 'Also-amended-by' not in msg and 'Art. 2 bis' in msg, msg
        msg = g('log', '-1', '--format=%B', 'law/ley-201')
        assert 'Words-changed: no' in msg, msg
        msg = g('log', '-1', '--format=%B', 'law/ley-200')
        assert 'Applies: art-001 | commenced-on-or-after 2001-03-12 | set-by Ley 200' in msg and 'CPT Art. 1; CC Art. 1 (Ley 200)' in msg, msg
        assert 'unexplained' in g('log', '--format=%s', 'main')
        msg = g('log', '-1', '--format=%B', 'law/ref-2016')
        assert 'Rejected by the voters' in msg and 'The source lists' not in msg and 'Affecting: CPT Art. 2' in msg and 'wording unchanged' in msg, msg
        for day, want in (('1964-12-31', 'El límite es 100.'), ('1965-01-12', 'El límite es 200.'), ('2026-01-01', 'El límite es 100.')):
            code, out = run('tools/on.py', day, 'constitucion', '2', cwd=repo)
            assert code == 0 and want in out, (day, out)
        code, out = run('tools/on.py', '2100-01-01', 'constitucion', '1', cwd=repo)
        assert 'federal' in out, out
        code, out = run('tools/on.py', '1920-01-01', 'constitucion', cwd=repo)
        assert code != 0, out
        rep = (repo / 'REPRODUCE.md').read_text(encoding='utf-8')
        assert '{{' not in rep and 'Test decision.' in rep, rep
        print('OK', res)
    finally:
        def force(fn, path, _exc):
            os.chmod(path, 0o700)
            fn(path)
        shutil.rmtree(tmp, onexc=force)


if __name__ == '__main__':
    main()
