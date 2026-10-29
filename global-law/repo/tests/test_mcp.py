"""The MCP server, spoken to the way a client does: newline-delimited JSON-RPC over stdio.

  python -m unittest tests.test_mcp -v
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
USC = 'us/federal/usc/title-11/1182.md'
GG = 'de/bund/grundgesetz/artikel/{}.md'
SEND = 'gb/uk/send/uksi/2014/1530/regulation/13.md'


class Server:
    def __init__(self):
        self.proc = subprocess.Popen([sys.executable, str(ROOT / 'tools/mcp_server.py')], stdin=subprocess.PIPE,
                                     stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=ROOT,
                                     env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'})
        self.next_id = 0

    def send(self, method: str, params: dict | None = None, notify: bool = False):
        msg = {'jsonrpc': '2.0', 'method': method, **({'params': params} if params is not None else {})}
        if not notify:
            self.next_id += 1
            msg['id'] = self.next_id
        self.proc.stdin.write((json.dumps(msg) + '\n').encode('utf-8'))
        self.proc.stdin.flush()
        if notify:
            return None
        return json.loads(self.proc.stdout.readline().decode('utf-8'))

    def call(self, name: str, **arguments):
        reply = self.send('tools/call', {'name': name, 'arguments': arguments})
        return reply['result']

    def close(self):
        self.proc.stdin.close()
        self.proc.wait(timeout=30)


class McpServer(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.s = Server()
        cls.init = cls.s.send('initialize', {'protocolVersion': '2025-06-18', 'capabilities': {}, 'clientInfo': {'name': 'test', 'version': '0'}})
        cls.s.send('notifications/initialized', notify=True)

    @classmethod
    def tearDownClass(cls):
        cls.s.close()

    def text(self, result):
        return result['content'][0]['text']

    # protocol

    def test_handshake_and_tool_list(self):
        r = self.init['result']
        self.assertEqual(r['protocolVersion'], '2025-06-18')
        self.assertIn('tools', r['capabilities'])
        self.assertIn('list_jurisdictions', r['instructions'])
        tools = {t['name']: t for t in self.s.send('tools/list')['result']['tools']}
        self.assertGreaterEqual(len(tools), 11)
        for t in tools.values():
            self.assertEqual(t['inputSchema']['type'], 'object')
            self.assertTrue(t['annotations']['readOnlyHint'])

    def test_unknown_method_and_tool(self):
        self.assertEqual(self.s.send('no/such')['error']['code'], -32601)
        self.assertEqual(self.s.send('tools/call', {'name': 'nope', 'arguments': {}})['error']['code'], -32602)
        self.assertEqual(self.s.send('ping')['result'], {})

    def test_bad_input_never_kills_the_server(self):
        p = self.s.proc
        p.stdin.write(b'this is not json\n')
        p.stdin.flush()
        self.assertEqual(json.loads(p.stdout.readline())['error']['code'], -32700)
        # a batch of two requests and a notification gets two answers, in one array
        batch = [{'jsonrpc': '2.0', 'id': 901, 'method': 'ping'}, {'jsonrpc': '2.0', 'method': 'notifications/x'},
                 {'jsonrpc': '2.0', 'id': 902, 'method': 'tools/list'}]
        p.stdin.write((json.dumps(batch) + '\n').encode())
        p.stdin.flush()
        replies = json.loads(p.stdout.readline())
        self.assertEqual([r['id'] for r in replies], [901, 902])
        # wrong argument types come back as tool errors, and the server keeps answering
        r = self.s.call('find_provision', query='1182', max_results='abc')
        self.assertTrue(r['isError'])
        self.assertIn('whole number', r['content'][0]['text'])
        self.assertFalse(self.s.call('laws_between', start=20220101, end='2022-12-31')['isError'])  # 8-digit dates are read
        self.assertEqual(self.s.send('ping')['result'], {})

    def test_resources(self):
        names = [r['uri'] for r in self.s.send('resources/list')['result']['resources']]
        self.assertIn('global-law://README.md', names)
        body = self.s.send('resources/read', {'uri': 'global-law://manifest.json'})['result']['contents'][0]['text']
        self.assertIn('us/federal/usc', body)

    # the questions

    def test_list_jurisdictions(self):
        r = self.s.call('list_jurisdictions')
        paths = {c['path'] for c in r['structuredContent']['corpora']}
        self.assertEqual(paths, {'de/bund/grundgesetz', 'gb/uk/send', 'us/federal/usc'})
        for c in r['structuredContent']['corpora']:
            self.assertTrue(c['example_path'].endswith('.md'), c)

    def test_find_provision_by_number_and_words(self):
        hits = self.s.call('find_provision', query='1182')['structuredContent']['results']
        self.assertEqual(hits[0]['path'], USC)
        art = self.s.call('find_provision', query='Art. 16a')['structuredContent']['results']
        self.assertEqual(art[0]['path'], GG.format('016a'))
        reg = self.s.call('find_provision', query='reg 13', jurisdiction='gb')['structuredContent']['results']
        self.assertEqual(reg[0]['path'], SEND)
        words = self.s.call('find_provision', query='Timescales EHC plans')['structuredContent']['results']
        self.assertEqual(words[0]['path'], SEND)
        # Grundgesetz headings are only numbers, so a topic is found in the text.
        asyl = self.s.call('find_provision', query='Asylrecht', jurisdiction='de')['structuredContent']['results']
        self.assertIn(GG.format('016a'), [h['path'] for h in asyl][:3])
        self.assertTrue(self.s.call('find_provision', query='')['isError'])

    def test_read_law_across_the_2022_gap(self):
        may = self.s.call('read_law', path=USC, date='2022-05-01')
        july = self.s.call('read_law', path=USC, date='2022-07-01')
        self.assertNotIn('7,500,000', may['structuredContent']['text'])
        self.assertIn('7,500,000', july['structuredContent']['text'])
        self.assertIn('117-151', july['structuredContent']['last_change']['law'])
        self.assertIn('117-151', may['structuredContent']['next_change']['law'])

    def test_read_law_flags_a_later_law_that_reaches_back(self):
        # In the 2022 gap the words read "small business debtor", but Pub. L. 117-151 later reached back to
        # cases commenced on or after 2020-03-27.
        gap = self.s.call('read_law', path=USC, date='2022-05-01')
        self.assertTrue(any('117-151' in b and 'reaches back' in b for b in gap['structuredContent']['beyond_the_words']))
        self.assertIn('Not the whole answer', self.text(gap))
        settled = self.s.call('read_law', path=GG.format('001'), date='2000-01-01')['structuredContent']
        self.assertEqual(settled['beyond_the_words'], [])

    def test_applies_to_case_looks_ahead(self):
        # Read on the day the case was filed, in the gap: Pub. L. 117-151 is later, but reaches back to it.
        r = self.s.call('applies_to_case', path=USC, commenced='2022-05-01', date='2022-05-01')
        ahead = r['structuredContent']['later_changes_reaching_back']
        self.assertEqual([a['in_force'] for a in ahead][:1], ['2022-06-21'])
        self.assertIn('7,500,000', ahead[0]['changes_to_the_text'])  # what the reach-back changes, in the answer itself
        self.assertIn('{+', self.text(r))
        early = self.s.call('applies_to_case', path=USC, commenced='2020-01-15', date='2020-01-15')['structuredContent']
        self.assertFalse(any('117-151' in a['law'] for a in early['later_changes_reaching_back']))

    def test_search_knows_popular_names(self):
        r = self.s.call('search_law', query='Ewigkeitsklausel')['structuredContent']
        self.assertEqual(r['popular_name_for'], [GG.format('079')])

    def test_popular_names(self):
        debt = self.s.call('find_provision', query='Schuldenbremse')['structuredContent']['results']
        self.assertEqual({h['path'] for h in debt[:3]}, {GG.format('109'), GG.format('115'), GG.format('143d')})
        ehc = self.s.call('find_provision', query='EHC plan')['structuredContent']['results']
        self.assertIn(SEND, [h['path'] for h in ehc[:3]])
        stay = self.s.call('find_provision', query='automatic stay', jurisdiction='us')['structuredContent']['results']
        self.assertEqual(stay[0]['path'], 'us/federal/usc/title-11/362.md')

    def test_read_law_says_why_there_is_no_text(self):
        before = self.s.call('read_law', path=GG.format('091e'), date='2010-07-26')
        self.assertFalse(before['structuredContent']['in_force'])
        self.assertIn('first appears on 2010-07-27', self.text(before))
        typo = self.s.call('read_law', path='us/federal/usc/title-11/1183x.md', date='2022-07-01')
        self.assertIn('not in this record at any date', self.text(typo))
        bad = self.s.call('read_law', path=USC, date='2022-5-1')
        self.assertTrue(bad['isError'])
        self.assertIn('Not a date', self.text(bad))
        outside = self.s.call('read_law', path='fr/code-civil/1.md')
        self.assertTrue(outside['isError'])

    def test_read_law_warns_past_the_end_of_a_record(self):
        # Pick a corpus whose record ends before the date, whichever it is when the test runs.
        corpora = self.s.call('list_jurisdictions')['structuredContent']['corpora']
        ending = min((c for c in corpora if c['record_to']), key=lambda c: c['record_to'])
        late = f"{int(ending['record_to'][:4]) + 1}-06-01"
        r = self.s.call('read_law', path=ending['example_path'], date=late)
        self.assertTrue(any('runs to' in c for c in r['structuredContent']['caveats']), r)
        self.assertIn('Note:', self.text(r))

    def test_world_on_date(self):
        r = self.s.call('world_on_date', date='2016-01-01')['structuredContent']
        by = {c['corpus']: c for c in r['corpora']}
        self.assertIn('60.', by['de/bund/grundgesetz']['last_change'])  # in force 1 January 2015
        self.assertIsNone(by['us/federal/usc']['last_change'])  # the US record starts in 2018
        mid = {c['corpus']: c for c in self.s.call('world_on_date', date='2022-05-01')['structuredContent']['corpora']}
        self.assertIn('117-151', mid['us/federal/usc']['next_change'])
        early = self.s.call('world_on_date', date='1990-10-03')['structuredContent']
        self.assertIsNone({c['corpus']: c for c in early['corpora']}['us/federal/usc']['last_change'])

    def test_who_wrote_by_word_and_line(self):
        words = self.s.call('who_wrote', path=USC, date='2022-07-01')['structuredContent']
        restored = ''.join(r['text'] for r in words['runs'] if '117-151' in r['law'])
        self.assertIn('7,500,000', restored)
        self.assertTrue(any('116-54' in l['law'] for l in words['laws']))
        lines = self.s.call('who_wrote', path=GG.format('091e'), date='2017-07-20', granularity='line')['structuredContent']
        self.assertTrue(all('58.' in l['law'] for l in lines['lines']))

    def test_compare_dates(self):
        r = self.s.call('compare_dates', path=USC, date_a='2022-07-01', date_b='2022-05-01')['structuredContent']
        self.assertEqual((r['date_a'], r['date_b']), ('2022-05-01', '2022-07-01'))
        self.assertIn('{+', r['word_diff'])
        self.assertEqual([c['in_force'] for c in r['changes']], ['2022-06-21'])

    def test_provision_history(self):
        r = self.s.call('provision_history', path=USC)['structuredContent']['changes']
        self.assertEqual([c['in_force'] for c in r], sorted(c['in_force'] for c in r))
        self.assertTrue(any(c['in_force'] == '2020-03-27' and '116-136' in c['law'] for c in r))

    def test_laws_between(self):
        r = self.s.call('laws_between', start='2014-12-31', end='2012-01-01')['structuredContent']['changes']
        self.assertEqual({c['corpus'] for c in r}, {'de/bund/grundgesetz', 'gb/uk/send'})
        de = self.s.call('laws_between', start='1990-01-01', end='1990-12-31', jurisdiction='de')['structuredContent']['changes']
        self.assertTrue(any('36.' in c['law'] for c in de))
        us = self.s.call('laws_between', start='2018-01-01', end='2026-12-31', jurisdiction='us')['structuredContent']
        self.assertGreater(us['provisions_per_law']['Pub. L. 116-54 (Small Business Reorganization Act of 2019)'], 20)

    def test_search_law_on_a_date(self):
        r = self.s.call('search_law', query='coronavirus', date='2022-05-01')['structuredContent']
        self.assertTrue(any(p.startswith('us/federal/usc/') for p in r['provisions']))
        self.assertFalse(any(p.endswith(('README.md', 'REPRODUCE.md')) for p in r['provisions']))
        before = self.s.call('search_law', query='coronavirus', date='2019-01-01')['structuredContent']
        self.assertEqual(before['provisions'], [])
        # Not in the text, but in the change notes: the search says so and names the changes.
        notes = self.s.call('search_law', query='Bankruptcy Threshold Adjustment', date='2023-01-01')
        self.assertEqual(notes['structuredContent']['provisions'], [])
        self.assertTrue(notes['structuredContent']['related_changes'])
        self.assertIn('change note', self.text(notes))
        de = self.s.call('search_law', query='Asylrecht', jurisdiction='de', date='2000-01-01')['structuredContent']
        self.assertIn(GG.format('016a'), de['provisions'])
        # The Code writes "COVID–19" with an en dash; a plain hyphen must still find it, and regex characters are literal.
        dash = self.s.call('search_law', query='COVID-19', date='2022-05-01')['structuredContent']
        self.assertTrue(dash['provisions'])
        self.assertEqual(self.s.call('search_law', query='(B)', jurisdiction='us', date='2022-05-01', max_results=1)['isError'], False)

    def test_phrase_history(self):
        r = self.s.call('phrase_history', query='7,500,000', jurisdiction='us')['structuredContent']['changes']
        seen = [(c['in_force'], c['effect']) for c in r if c['path'] == USC]
        self.assertEqual(seen, [('2020-03-27', 'added'), ('2022-03-27', 'removed'), ('2022-06-21', 'added'), ('2024-06-21', 'removed')])
        covid = self.s.call('phrase_history', query='COVID', jurisdiction='de')['structuredContent']['changes']
        self.assertEqual([(c['path'], c['effect']) for c in covid][:1], [(GG.format('143h'), 'added')])

    def test_changes_between(self):
        r = self.s.call('changes_between', date_a='2022-05-01', date_b='2022-07-01')['structuredContent']
        us = next(c for c in r['corpora'] if c['corpus'] == 'us/federal/usc')
        self.assertIn(USC, [p['path'] for p in us['provisions']])
        self.assertTrue(any('117-151' in l for l in us['laws']))

    def test_law_details(self):
        short = self.s.call('law_details', law='Pub. L. 116-54', max_message_chars=500)
        self.assertIn('more characters', self.text(short))
        r = self.s.call('law_details', law='Pub. L. 117-151')['structuredContent']['changes']
        self.assertTrue(r)
        first = r[-1]
        self.assertEqual(first['corpus'], 'us/federal/usc')
        self.assertIn('In-force', first['trailers'])
        self.assertTrue(any(p.endswith('1182.md') for c in r for p in c['provisions']))
        gg = self.s.call('law_details', law='36. Änderung', corpus='de')['structuredContent']['changes']
        self.assertTrue(gg and gg[0]['trailers'].get('In-Kraft') == '1990-09-29')
        self.assertTrue(self.s.call('law_details', law='Pub. L. 1-1')['isError'])

    def test_list_provisions(self):
        r = self.s.call('list_provisions', path='us/federal/usc/title-11', date='2022-07-01')['structuredContent']
        self.assertIn(USC, [p['path'] for p in r['provisions']])
        gg = self.s.call('list_provisions', path='de/bund/grundgesetz', date='1960-01-01')['structuredContent']
        paths = [p['path'] for p in gg['provisions']]
        self.assertIn(GG.format('001'), paths)
        self.assertNotIn(GG.format('012a'), paths)  # not until 1968
        self.assertTrue(self.s.call('list_provisions', path='fr')['isError'])

    def test_search_changes(self):
        r = self.s.call('search_changes', query='temporary')['structuredContent']['changes']
        self.assertTrue(r)
        self.assertEqual([c['in_force'] for c in r], sorted(c['in_force'] for c in r))
        de = self.s.call('search_changes', query='Abstimmung', jurisdiction='de', start='1990-01-01', end='1990-12-31')['structuredContent']['changes']
        self.assertTrue(all(c['corpus'] == 'de/bund/grundgesetz' and c['in_force'].startswith('1990') for c in de))

    def test_missing_after_the_record_ends_says_so(self):
        corpora = self.s.call('list_jurisdictions')['structuredContent']['corpora']
        ending = min((c for c in corpora if c['record_to']), key=lambda c: c['record_to'])
        missing = ending['example_path'].rsplit('/', 1)[0] + '/no-such-provision.md'
        r = self.s.call('read_law', path=missing, date=f"{int(ending['record_to'][:4]) + 1}-06-01")
        self.assertIn('may exist in the law after that date', self.text(r))

    def test_read_law_gives_sources_to_cite(self):
        r = self.s.call('read_law', path=USC, date='2022-07-01')['structuredContent']
        self.assertTrue(any('govinfo.gov' in s for s in r['sources']), r['sources'])
        h = self.s.call('provision_history', path=SEND)['structuredContent']['changes']
        self.assertTrue(any('legislation.gov.uk' in s for c in h for s in c['sources']))

    def test_applies_to_case(self):
        r = self.s.call('applies_to_case', path=USC, commenced='2022-05-01', date='2022-07-01')['structuredContent']
        later = [c for c in r['changes'] if c['in_force'] > '2022-05-01']
        self.assertEqual([c['in_force'] for c in later], ['2022-06-21'])
        self.assertIn('7,500,000', r['text'])  # no recorded scope excludes it, so the July text applies
        self.assertTrue(any('March 27, 2020' in s for s in later[0]['scope']), later[0]['scope'])  # the scope in words
        self.assertFalse(any('http' in s for s in later[0]['scope']))
        self.assertTrue(later[0]['verdict'].startswith('applies'))
        # Filed before 27 March 2020: neither the CARES text nor Pub. L. 117-151's reaches the case.
        old = self.s.call('applies_to_case', path=USC, commenced='2020-01-15', date='2022-07-01')['structuredContent']
        verdicts = {c['law'][:15]: c['verdict'] for c in old['changes'] if c['in_force'] > '2020-01-15'}
        self.assertTrue(verdicts['Pub. L. 117-151'].startswith('does not apply'), verdicts)
        self.assertNotIn('7,500,000', old['text'])
        self.assertEqual(old['text_date'], '2020-02-19')
        early = self.s.call('applies_to_case', path=USC, commenced='2023-01-01', date='2023-01-01')
        self.assertIn('No change took effect after the case was commenced', self.text(early))
        self.assertTrue(self.s.call('applies_to_case', path=USC, commenced='2024-01-01', date='2023-01-01')['isError'])

    def test_many_requests_in_one_session_stay_fast(self):
        import time
        start = time.time()
        for date in ('2018-06-01', '2019-06-01', '2020-06-01', '2021-06-01', '2022-06-01', '2023-06-01'):
            self.s.call('read_law', path=USC, date=date)
        self.assertLess(time.time() - start, 10)


class ScopeRules(unittest.TestCase):
    """The applicability rules on their own, with the record's own trailer format (no corpus has it yet)."""

    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, str(ROOT / 'tools'))
        sys.dont_write_bytecode = True
        import mcp_server
        cls.m = mcp_server

    BODY = ('Pub. L. 117-151\n\n'
            'Applies: 11 U.S.C. §1182(1) | commenced-on-or-after 2022-06-21 | set-by Pub. L. 117-151, §2(h)(1)\n'
            'Applies: 11 U.S.C. §1182(1) | commenced-on-or-after 2020-03-27; commenced-before 2022-06-21; pending-on 2022-06-21 | set-by Pub. L. 117-151, §2(h)(2)\n')

    def test_parse(self):
        groups = self.m.applies_groups(self.BODY)
        self.assertEqual(len(groups), 2)
        self.assertEqual(groups[1]['conditions'][2], ('pending-on', '2022-06-21'))
        self.assertEqual(groups[0]['set_by'], 'Pub. L. 117-151, §2(h)(1)')

    def test_cases_on_each_side_of_the_gap(self):
        groups = self.m.applies_groups(self.BODY)
        def reaches(day):
            return [ok for ok, _ in (self.m.group_holds(g['conditions'], day) for g in groups)]
        self.assertEqual(reaches('2022-07-01'), [True, False])   # filed after the Act
        self.assertEqual(reaches('2022-05-01'), [False, True])   # filed in the gap, if still pending
        self.assertEqual(reaches('2020-01-01'), [False, False])  # filed before 27 March 2020
        _, assumed = self.m.group_holds(groups[1]['conditions'], '2022-05-01')
        self.assertIn('still pending on 2022-06-21', assumed[0])

    def test_scope_sentences_in_words(self):
        f = self.m.conditions_from_words
        self.assertEqual(f('Applies to any case that is commenced under title 11 on or after March 27, 2020.'),
                         [('commenced-on-or-after', '2020-03-27')])
        self.assertEqual(f('Applies to any case commenced before, on, or after March 27, 2020.'), [('any-commencement', '')])
        self.assertEqual(f('Applies to any case under title 11 commenced on or after October 1, 2026.'),
                         [('commenced-on-or-after', '2026-10-01')])
        self.assertIsNone(f('Applies only to small business debtors that elect subchapter V.'))

    def test_modifies_effects_are_read(self):
        # The proposed trailer for "same words, different law", parsed from a commit body the way modifies_in does.
        line = 'Modifies: title-11/101.md#(51D) | amount-adjusted | 2025-04-01.. | "$3,024,725" becomes "$3,424,000" | set-by 90 F.R. 8941'
        parts = [p.strip() for p in line[len('Modifies: '):].split('|')]
        self.assertEqual(parts[1], 'amount-adjusted')
        self.assertEqual(parts[2].partition('..')[0], '2025-04-01')

    def test_any_commencement_and_unknown_conditions(self):
        self.assertEqual(self.m.group_holds([('any-commencement', '')], '1999-01-01'), (True, []))
        ok, assumed = self.m.group_holds([('subset', 'small business')], '2022-01-01')
        self.assertTrue(ok)
        self.assertIn('cannot check', assumed[0])


if __name__ == '__main__':
    unittest.main()
