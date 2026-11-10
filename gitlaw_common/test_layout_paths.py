"""Tests for layout_paths.py on a tiny repository: python -X utf8 -m unittest test_layout_paths.py"""
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

import layout_paths as LP

ENV = {**os.environ, 'GIT_AUTHOR_NAME': 'Lexifina', 'GIT_AUTHOR_EMAIL': 'x-law@lexifina.com',
       'GIT_COMMITTER_NAME': 'Lexifina', 'GIT_COMMITTER_EMAIL': 'x-law@lexifina.com',
       'GIT_AUTHOR_DATE': '1700000000 +0000', 'GIT_COMMITTER_DATE': '1700000000 +0000'}


def git(repo, *a, env=None):
    return subprocess.run(['git', *a], cwd=repo, capture_output=True, text=True, check=True,
                          env=env or ENV).stdout.strip()


def commit(repo, files, msg, author='Lexifina', remove=()):
    for p, t in files.items():
        f = repo / p
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(t, encoding='utf-8', newline='\n')
    for p in remove:
        git(repo, 'rm', '-r', '-q', p)
    git(repo, 'add', '-A')
    env = {**ENV, 'GIT_AUTHOR_NAME': author, 'GIT_AUTHOR_EMAIL': 'a@x.invalid'} if author != 'Lexifina' else ENV
    git(repo, 'commit', '-q', '-m', msg, env=env)
    return git(repo, 'rev-parse', 'HEAD')


class LayoutTest(unittest.TestCase):
    def test_translate_and_place(self):
        lay = LP.Layout({'paths': {'lr-2006-004': 'lr/2006/004', 'konst': 'konst', 'acts/x-act-1999': 'act/1999/x'}})
        self.assertEqual(lay.to_new('lr-2006-004/art-1.md'), 'lr/2006/004/art-1.md')
        self.assertEqual(lay.to_old('lr/2006/004/art-1.md'), 'lr-2006-004/art-1.md')
        self.assertEqual(lay.to_new('acts/x-act-1999/a.md'), 'act/1999/x/a.md')
        self.assertEqual(lay.to_new('data/repo.json'), 'data/repo.json')
        self.assertEqual(lay.to_new('lr-2006-0040/a.md'), 'lr-2006-0040/a.md')
        ext = lay.extended(['lr-2007-001', 'lr', 'lr-2006-004'])
        self.assertEqual(ext.paths['lr-2007-001'], 'lr/2007/001')
        self.assertNotIn(ext.paths['lr'], ('lr',))  # 'lr' holds other acts' folders: never given to an act
        self.assertEqual(ext.added, ['lr', 'lr-2007-001'])
        self.assertIs(lay.extended(['lr-2006-004']), lay)

    def test_flatten_lift_round_trip(self):
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td)
            git(repo, 'init', '-q', '-b', 'main')
            commit(repo, {'lr-2006-004/art-1.md': 'one\n'}, 'Law one\n\nIn-force: 2006-01-01\n', author='Parl')
            commit(repo, {'lr-2007-002/art-1.md': 'two\n'}, 'Law two\n\nIn-force: 2007-01-01\n', author='Parl')
            base = commit(repo, {'README.md': 'docs\n', 'data/repo.json': '{}\n'}, 'Documentation\n')
            paths = {'lr-2006-004': 'lr/2006/004', 'lr-2007-002': 'lr/2007/002'}
            for k, v in paths.items():
                (repo / v).parent.mkdir(parents=True, exist_ok=True)
                git(repo, 'mv', k, v)
            layout = commit(repo, {'data/paths.json': json.dumps({'paths': paths}, indent=0) + '\n'},
                            'Layout\n\nKind: documentation\n')
            lay = LP.Layout.at(repo, layout)
            flat, r2f = LP.flatten(repo, layout, lay)
            self.assertEqual(git(repo, 'rev-parse', f'{flat}^{{tree}}'), git(repo, 'rev-parse', f'{base}^{{tree}}'))
            self.assertEqual(git(repo, 'rev-parse', f'{flat}^'), base)
            # A flat append: a newer version of act one, a new act, a correction, a docs commit.
            git(repo, 'checkout', '-q', '-B', 'flat', flat)
            commit(repo, {'lr-2006-004/art-1.md': 'one, amended\n'}, 'Law three\n\nIn-force: 2008-01-01\n', author='Parl')
            commit(repo, {'lr-2009-007/art-1.md': 'new\n'}, 'Law four\n\nIn-force: 2009-01-01\n', author='Parl')
            commit(repo, {'lr-2007-002/art-1.md': 'two, fixed\n'}, 'Correction: lr-2007-002\n\nKind: correction\n'
                   'In-force: 2007-01-01\nCorrects: lr-2007-002 2007-01-01..\nAct-path: lr-2007-002\n'
                   'Files: lr-2007-002/art-1.md\n')
            new_flat = commit(repo, {'README.md': 'docs 2\n'}, 'Documentation\n')
            real, f2r, lay2 = LP.lift(repo, layout, flat, new_flat, lay)
            self.assertEqual(LP.verify(repo, real, new_flat, lay2), [])
            self.assertEqual(lay2.added, ['lr-2009-007'])
            files = git(repo, 'ls-tree', '-r', '--name-only', real).split('\n')
            self.assertIn('lr/2009/007/art-1.md', files)
            self.assertFalse([f for f in files if f.startswith('lr-')])
            self.assertEqual(json.loads(git(repo, 'show', f'{real}:data/paths.json'))['paths']['lr-2009-007'],
                             'lr/2009/007')
            fix = f2r[git(repo, 'rev-parse', f'{new_flat}^')]
            msg = git(repo, 'log', '-1', '--format=%B', fix)
            self.assertIn('Act-path: lr/2007/002', msg)
            self.assertIn('Files: lr/2007/002/art-1.md', msg)
            self.assertIn('Corrects: lr-2007-002 2007-01-01..', msg)
            # A law commit carries the published paths.json; the docs commit the extended one.
            law4 = f2r[git(repo, 'rev-parse', f'{new_flat}~2')]
            self.assertEqual(git(repo, 'rev-parse', f'{law4}:data/paths.json'), lay.blob)
            # Flattening the lifted tip gives the flat commits back (the docs commit's paths.json aside).
            flat2, _ = LP.flatten(repo, real, lay2)
            self.assertEqual(LP.law_files(repo, flat2), LP.law_files(repo, new_flat))
            # The docs commit ships the layout reader as tools/on.py.
            self.assertEqual(git(repo, 'show', f'{real}:tools/on.py'),
                             LP.ON_LAYOUT.read_text(encoding='utf-8').rstrip('\n'))
            self.assertEqual(git(repo, 'rev-parse', f'{flat2}~1'), git(repo, 'rev-parse', f'{new_flat}~1'))
            # Nothing new: lifting the flat tip onto itself adds nothing; a docs commit equal to the tip is dropped.
            self.assertEqual(LP.lift(repo, real, flat2, flat2, lay2)[0], real)
            git(repo, 'checkout', '-q', '-f', '-B', 'again', flat2)
            git(repo, 'commit', '-q', '--allow-empty', '-m', 'Documentation again')
            again = git(repo, 'rev-parse', 'HEAD')
            self.assertEqual(LP.lift(repo, real, flat2, again, lay2)[0], real)


if __name__ == '__main__':
    unittest.main()
