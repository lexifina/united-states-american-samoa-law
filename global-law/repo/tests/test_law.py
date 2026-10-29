"""Checks on the global law tree. Run from the repo root after `git submodule update --init`:

  python -m unittest discover -s tests -v
"""
from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.dont_write_bytecode = True  # never leave cache files inside a corpus checkout (it blocks git checkout)
sys.path.insert(0, str(ROOT / 'tools'))
import law  # noqa: E402

USC = 'us/federal/usc/title-11/1182.md'
GG = 'de/bund/grundgesetz/artikel/{}.md'
SEND = 'gb/uk/send/uksi/2014/1530/regulation/13.md'


class Structure(unittest.TestCase):
    def test_every_level_describes_itself_and_its_children(self):
        tree = json.loads((ROOT / 'jurisdiction.json').read_text(encoding='utf-8'))
        stack = [('', tree)]
        seen = set()
        while stack:
            path, node = stack.pop()
            seen.add(path)
            for child in node['jurisdictions']:
                self.assertEqual(child.rsplit('/', 1)[0] if '/' in child else '', path)
                stack.append((child, json.loads((ROOT / child / 'jurisdiction.json').read_text(encoding='utf-8'))))
            for corpus in node['corpora']:
                self.assertTrue((ROOT / corpus / '.git').exists(), f'{corpus} is not checked out')
        corpora = {c['path'] for c in law.manifest()['corpora']}
        self.assertTrue(all(c.rsplit('/', 1)[0] in seen for c in corpora))

    def test_head_pins_each_corpus_at_its_latest_commit(self):
        for corpus in law.manifest()['corpora']:
            pin = law.pinned('HEAD', corpus['path'])
            last = [e for e in law.timeline() if e.corpus == corpus['path']][-1]
            self.assertEqual(pin, last.corpus_commit)


class Timeline(unittest.TestCase):
    events = law.timeline()

    def test_in_force_order(self):
        dates = [e.in_force for e in self.events]
        self.assertEqual(dates, sorted(dates))

    def test_one_root_commit_per_corpus_commit(self):
        for corpus in law.manifest()['corpora']:
            path = ROOT / corpus['path']
            leaf = law.git('rev-list', '--first-parent', '--reverse', 'HEAD', cwd=path).split()
            ours = [e.corpus_commit for e in self.events if e.corpus == corpus['path']]
            self.assertEqual(ours, leaf, corpus['path'])

    def test_each_root_commit_moves_exactly_one_pin(self):
        corpora = [c['path'] for c in law.manifest()['corpora']]
        previous = {c: None for c in corpora}
        for event in self.events:
            now = {c: law.pinned(event.commit, c) for c in corpora}
            moved = [c for c in corpora if now[c] != previous[c]]
            self.assertEqual(moved, [event.corpus], event.subject)
            self.assertEqual(now[event.corpus], event.corpus_commit)
            previous = now

    def test_commit_dates_never_go_backwards(self):
        stamps = [int(s) for s in law.git('log', '--first-parent', '--reverse', '--format=%at').split()]
        self.assertEqual(stamps, sorted(stamps))


class OnADate(unittest.TestCase):
    def test_before_the_record_nothing_is_in_force(self):
        self.assertIsNone(law.root_on('1949-05-23'))
        self.assertIsNone(law.text_on('2017-12-31', USC))

    def test_us_small_business_debtor_limit_across_the_gap(self):
        # CARES Act raised the limit to $7.5 million; it lapsed on 27 March 2022 and Pub. L. 117-151 restored it
        # from 21 June 2022 until 21 June 2024.
        self.assertIn('7,500,000', law.text_on('2021-06-01', USC))
        self.assertNotIn('7,500,000', law.text_on('2022-05-01', USC))
        self.assertIn('7,500,000', law.text_on('2022-07-01', USC))
        self.assertNotIn('7,500,000', law.text_on('2024-07-01', USC))

    def test_grundgesetz_before_1970(self):
        # Art. 12a came with the 17th amendment, in force 28 June 1968; git cannot date that commit, the trailer can.
        self.assertIsNone(law.text_on('1968-06-27', GG.format('012a')))
        self.assertIsNotNone(law.text_on('1968-06-28', GG.format('012a')))
        self.assertIsNotNone(law.text_on('1949-05-24', GG.format('001')))

    def test_grundgesetz_art_91e_from_2010(self):
        self.assertIsNone(law.text_on('2010-07-26', GG.format('091e')))
        self.assertIsNotNone(law.text_on('2010-07-27', GG.format('091e')))

    def test_one_date_reads_every_jurisdiction(self):
        commit = law.root_on('2022-05-01')
        for corpus in law.manifest()['corpora']:
            self.assertIsNotNone(law.pinned(commit, corpus['path']), corpus['path'])
        self.assertIsNotNone(law.text_on('2022-05-01', SEND))

    def test_matches_each_corpus_read_on_its_own(self):
        events = law.timeline()
        for date in ('1956-03-19', '1990-09-29', '2015-09-01', '2020-03-27', '2022-05-01', '2024-06-21'):
            commit = law.root_on(date, events)
            for corpus in law.manifest()['corpora']:
                own = [e.corpus_commit for e in events if e.corpus == corpus['path'] and e.in_force <= date]
                self.assertEqual(law.pinned(commit, corpus['path']), own[-1] if own else None, (date, corpus['path']))


class WhoWroteIt(unittest.TestCase):
    def test_blame_names_the_law(self):
        lines = law.blame_on('2022-07-01', USC)
        authors = {author for author, line in lines if '7,500,000' in line}
        self.assertTrue(authors and all('117-151' in a for a in authors), authors)

    def test_diff_between_dates(self):
        diff = law.diff_between('2022-05-01', '2022-07-01', USC)
        self.assertIn('{+', diff)
        self.assertIn('7,500,000', diff)
        self.assertEqual(law.diff_between('2022-07-01', '2022-07-02', USC), '')


class AgainstEachCorpusOwnTools(unittest.TestCase):
    """The tree must give the same answers as each corpus read with its own tools."""

    def test_grundgesetz_matches_its_own_reader(self):
        gg = ROOT / 'de/bund/grundgesetz'
        # Force: after a corpus force-push, an older clone keeps its old tags, and stand_am.py reads tags.
        law.git('fetch', '-q', '--force', '--tags', law.corpus_info('de/bund/grundgesetz')['url'], cwd=gg)
        for date in ('1949-05-24', '1956-03-22', '1968-06-28', '1990-10-03', '1994-11-15', '2010-07-27', '2017-07-20'):
            for art in ('1', '12a', '16', '23', '91e', '143d'):
                own = subprocess.run([sys.executable, 'tools/stand_am.py', date, art], cwd=gg, capture_output=True,
                                     encoding='utf-8')
                ours = law.text_on(date, GG.format(art.zfill(3) if art.isdigit() else art.zfill(4)))
                if ours is None:
                    self.assertNotEqual(own.returncode == 0 and f'# Artikel {art}' in own.stdout, True, (date, art))
                else:
                    self.assertIn(ours.strip(), own.stdout, (date, art))

    def test_uk_matches_every_version_in_its_data(self):
        send = ROOT / 'gb/uk/send'
        sys.path.insert(0, str(send / 'tools'))
        import ukhistory  # the corpus's own builder
        history = json.loads((send / 'data/history.json').read_text(encoding='utf-8'))
        checked = 0
        for p in history['provisions']:
            last_per_day = {v['date']: v for v in p['versions']}
            for day, v in last_per_day.items():
                expected = ukhistory.render(p, v, history['instruments'][p['instrument']])
                self.assertEqual(law.text_on(day, f"gb/uk/send/{ukhistory.provision_path(p['id'])}"), expected, (p['id'], day))
                checked += 1
        self.assertGreaterEqual(checked, 20)


    def test_shared_builder_corpora_match_their_own_on_tool(self):
        # Every corpus built by scripts/gitlaw_common ships tools/on.py, which picks a version by its In-force trailer
        # independently of this tree. On every in-force day (sampled) and for files in every act, the two must agree.
        checked = 0
        for corpus in law.manifest()['corpora']:
            home = ROOT / corpus['path']
            if not (home / 'tools/on.py').exists():
                continue
            days = sorted({d for d in law.git('log', '--format=%(trailers:key=In-force,valueonly,separator=)', 'HEAD',
                                              cwd=home).split() if d})
            days = days[::max(1, len(days) // 25)] + days[-1:]
            files = [f for f in law.git('ls-tree', '-r', '--name-only', 'HEAD', cwd=home).splitlines()
                     if f.endswith('.md') and '/' in f and f.split('/')[0] not in ('data', 'tools')
                     and not f.endswith('/README.md')]
            acts: dict[str, list[str]] = {}
            for f in files:
                acts.setdefault(f.split('/')[0], []).append(f)
            sample = [f for fs in acts.values() for f in fs[:3] + fs[-2:]]
            for day in days:
                for f in sample:
                    act, unit = f.split('/', 1)
                    own = subprocess.run([sys.executable, 'tools/on.py', day, act, unit[:-3]], cwd=home,
                                         capture_output=True, encoding='utf-8')
                    ours = law.text_on(day, f'{corpus["path"]}/{f}')
                    if ours is None:
                        self.assertNotEqual(own.returncode, 0, (corpus['path'], day, f))
                    else:
                        self.assertEqual(ours, own.stdout, (corpus['path'], day, f))
                    checked += 1
        if any((ROOT / c['path'] / 'tools/on.py').exists() for c in law.manifest()['corpora']):
            self.assertGreater(checked, 0)


class Semantics(unittest.TestCase):
    """The reader's questions, answered from the tree."""

    def test_follow_a_section_lists_each_law_with_its_dates(self):
        h = law.history(USC)
        laws = [x['law'] for x in h]
        self.assertTrue(any('116-136' in l for l in laws) and any('117-151' in l for l in laws))
        cares = next(x for x in h if '116-136' in x['law'])
        self.assertEqual(cares['in_force'], '2020-03-27')
        self.assertEqual(cares['enacted'], '2020-03-27')
        self.assertEqual([x['in_force'] for x in h], sorted(x['in_force'] for x in h))

    def test_dates_differ_where_the_law_says_so(self):
        # Germany: the 58th amendment was promulgated before it took effect; the UK regulations were made before.
        art = law.history(GG.format('091e'))[0]
        self.assertEqual(art['in_force'], '2010-07-27')
        self.assertTrue(art['published'] and art['published'][:10] < art['in_force'])
        made, in_force = law.history(SEND)[:2]  # the SEND Regulations: made 4 June, in force 1 September 2014
        self.assertEqual((made['in_force'], in_force['in_force'], in_force['enacted']), ('2014-06-04', '2014-09-01', '2014-06-04'))

    def test_blame_names_the_law_in_every_jurisdiction(self):
        gg = {a for a, _ in law.blame_on('2017-07-20', GG.format('091e'))}
        self.assertTrue(any('58.' in a for a in gg), gg)
        uk = {a for a, line in law.blame_on('2021-12-31', SEND) if line.startswith('(')}
        self.assertTrue(all(a.startswith(('S.I.', '20')) for a in uk), uk)

    def test_words_are_credited_to_the_law_that_wrote_them(self):
        runs = law.words_on('2022-07-01', USC)
        by_law: dict[str, str] = {}
        for author, text in runs:
            by_law[author] = by_law.get(author, '') + text
        restored = next(a for a in by_law if '117-151' in a)
        self.assertIn('7,500,000', by_law[restored])
        self.assertIn('person engaged in commercial or business activities', by_law[restored])
        self.assertIn('Definitions', next(t for a, t in by_law.items() if '116-54' in a))
        self.assertEqual(''.join(t for _, t in runs), law.text_on('2022-07-01', USC))
        # Germany: Art. 79 keeps the 1949 words beside those of the 4th amendment (1954).
        authors = {a for a, _ in law.words_on('2017-07-20', GG.format('079'))}
        self.assertTrue({'Grundgesetz (1949)', '4. Änderung (1954)'} <= authors, authors)
        # UK: one word of reg. 13(3) is the coronavirus regulations' (S.I. 2020/471), the rest the 2014 regulations'.
        uk = [(a, t) for a, t in law.words_on('2021-12-31', SEND) if '2020/471' in a]
        self.assertTrue(uk and all(len(t.split()) <= 3 for _, t in uk), uk)

    def test_copied_tags_point_at_the_matching_world_state(self):
        for corpus in law.manifest()['corpora']:
            path = ROOT / corpus['path']
            own = {}
            for line in law.git('tag', '--format=%(refname:short) %(*objectname) %(objectname)', cwd=path).splitlines():
                name, *shas = line.split()
                own[name] = shas[0]
            ours = [t for t in law.git('tag', '--list', f"{corpus['path']}/*").split()]
            self.assertEqual(len(ours), len(own), corpus['path'])
            for tag in ours[:40]:
                name = tag[len(corpus['path']) + 1:]
                self.assertEqual(law.pinned(tag, corpus['path']), own[name], tag)

    def test_plain_git_checkout_gives_the_same_text(self):
        # What a reader without the tools would do: take the root commit for a date and read the pinned file.
        commit = law.root_on('2022-05-01')
        pin = law.git('ls-tree', commit, '--', 'us/federal/usc').split()[2]
        text = law.git('show', f'{pin}:title-11/1182.md', cwd=ROOT / 'us/federal/usc')
        self.assertEqual(text, law.text_on('2022-05-01', USC))

    def test_laws_in_a_window_across_jurisdictions(self):
        window = [e for e in law.timeline() if '2012-01-01' <= e.in_force <= '2014-12-31' and e.kind == 'law']
        self.assertEqual({e.corpus for e in window}, {'de/bund/grundgesetz', 'gb/uk/send'})
        self.assertEqual([e.in_force for e in window], sorted(e.in_force for e in window))


class GitReadsTheDates(unittest.TestCase):
    """git's own trailer parser must find each law commit's in-force date, so plain git (interpret-trailers,
    %(trailers)) works without our parser. Trailer keys must be ASCII: a key like `Verkündet:` makes git reject the
    whole block. List a corpus in KNOWN_OPEN while a fix is pending."""

    KNOWN_OPEN: set[str] = set()  # the Grundgesetz was fixed in its 2026-10-28 rebuild (Verkuendet)

    def test_in_force_date_is_a_git_trailer(self):
        for corpus in law.manifest()['corpora']:
            key = corpus['in_force_trailer']
            raw = law.git('log', '--format=%H%x1f%(trailers:key=' + key + ',valueonly)%x1f%B%x1e', cwd=ROOT / corpus['path'])
            missing = []
            for record in raw.split('\x1e'):
                if not record.strip():
                    continue
                sha, parsed, body = record.strip('\n').split('\x1f', 2)
                if law.trailers(body).get(key) and not parsed.strip():
                    missing.append(sha[:7])
            if corpus['path'] in self.KNOWN_OPEN:
                if not missing:
                    self.fail(f"{corpus['path']} is fixed: remove it from KNOWN_OPEN")
                continue
            self.assertEqual(missing, [], f"{corpus['path']}: git cannot read {key} in {len(missing)} commits")


class Pins(unittest.TestCase):
    def test_every_pin_is_on_its_corpus_published_main(self):
        # A force-pushed corpus orphans the pin; once GitHub collects it, a fresh clone cannot fetch it.
        for corpus in law.manifest()['corpora']:
            path = ROOT / corpus['path']
            law.git('fetch', '-q', corpus['url'], '+HEAD:refs/remotes/published/HEAD', cwd=path)
            pin = law.pinned('HEAD', corpus['path'])
            done = subprocess.run(['git', 'merge-base', '--is-ancestor', pin, 'refs/remotes/published/HEAD'], cwd=path)
            self.assertEqual(done.returncode, 0, f"{corpus['path']}: pin {pin[:7]} is not on the published main; rebuild global-law")


class CommandLine(unittest.TestCase):
    """The mistakes a reader makes, and the limits of each record, must give a clear answer, never a wrong one."""

    def cli(self, *args):
        done = subprocess.run([sys.executable, str(ROOT / 'tools/law.py'), *args], capture_output=True, encoding='utf-8',
                              env={**__import__('os').environ, 'PYTHONIOENCODING': 'utf-8', 'PYTHONDONTWRITEBYTECODE': '1'})
        return done.returncode, done.stdout, done.stderr

    def test_bad_dates_are_refused(self):
        for bad in ('2022-5-1', '2022-13-45', 'yesterday', '05/01/2022'):
            code, out, err = self.cli('world', bad)
            self.assertNotEqual(code, 0, bad)
            self.assertIn('Not a date', err, bad)

    def test_paths_written_differently_still_work(self):
        for path in (f'./{USC}', USC.replace('/', '\\')):
            code, out, _ = self.cli('show', '2022-07-01', path)
            self.assertEqual(code, 0, path)
            self.assertIn('7,500,000', out)

    def test_a_mistyped_path_is_not_reported_as_not_in_force(self):
        code, _, err = self.cli('show', '2022-07-01', 'us/federal/usc/title-11/1183x.md')
        self.assertNotEqual(code, 0)
        self.assertIn('not in this record at any date', err)

    def test_missing_text_says_why(self):
        _, _, before = self.cli('show', '2010-07-26', GG.format('091e'))
        self.assertIn('first appears on 2010-07-27', before)
        _, _, start = self.cli('show', '2015-01-01', USC)
        self.assertIn('record starts on 2018-01-12', start)

    def test_dates_past_a_record_carry_a_warning(self):
        code, out, err = self.cli('show', '2027-06-01', GG.format('016a'))
        self.assertEqual(code, 0)
        self.assertIn('record runs to 2026-10-28', err)
        self.assertNotIn('Note:', out)
        _, _, quiet = self.cli('show', '2016-01-01', GG.format('016a'))
        self.assertNotIn('Note:', quiet)

    def test_diff_from_before_a_record_shows_the_text_arriving(self):
        _, out, err = self.cli('diff', '1990-01-01', '2022-07-01', USC)
        self.assertIn('7,500,000', out)
        self.assertIn('record starts', err)

    def test_reversed_window_and_missing_arguments(self):
        _, out, _ = self.cli('laws', '2022-12-31', '2022-01-01', 'us')
        self.assertIn('117-151', out)
        code, _, err = self.cli('world')
        self.assertNotEqual(code, 0)
        self.assertNotIn('Traceback', err)

    def test_words_is_fast_on_a_long_section(self):
        import time
        start = time.time()
        code, out, _ = self.cli('words', '2026-04-01', 'us/federal/usc/title-17/115.md')
        self.assertEqual(code, 0)
        self.assertLess(time.time() - start, 8, 'law.py words took too long on 17 U.S.C. §115 (124 KB)')


if __name__ == '__main__':
    unittest.main()
