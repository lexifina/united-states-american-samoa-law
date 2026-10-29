"""Tests for parse.py's crediting rule and text handling, on real LEGI files from the cache.

    python -X utf8 -m unittest test_parse -v      (from scripts/france-law/)

Expected credits are the constitutional revisions as published in the Journal officiel, and Code civil cases where
LEGI's links are known to mislead (inherited links, abrogated-state versions).
"""
import unittest

import parse

CONST = next(a for a in parse.ACTS if a['slug'] == 'constitution')
CIVIL = next(a for a in parse.ACTS if a['slug'] == 'code-civil')
_cache: dict = {}


def versions(act: dict) -> dict[str, list]:
    if act['slug'] not in _cache:
        by: dict[str, list] = {}
        for v in parse.read_act(act):
            if v.d < v.f:
                by.setdefault(v.num, []).append(v)
        for lst in by.values():
            lst.sort(key=lambda v: (v.d, v.f, v.id))
        _cache[act['slug']] = by
    return _cache[act['slug']]


def credit(act: dict, num: str, day: str) -> set[str]:
    """numtexte (or cid) of the texts credited for the version of `num` starting on `day`."""
    lst = versions(act)[num]
    i = next(i for i, v in enumerate(lst) if v.d == day)
    ls = parse.creators(lst[i], lst[i - 1] if i else None, {act['dir'], act['legitext']})
    return {l.numtexte or l.cid for l in ls}


class ConstitutionCredits(unittest.TestCase):
    def test_revisions(self):
        cases = [
            ('1', '1995-08-05', {'95-880'}), ('1', '2003-03-29', {'2003-276'}), ('1', '2008-07-25', {'2008-724'}),
            ('6', '1962-11-09', {'62-1292'}), ('6', '2000-10-03', {'2000-964'}), ('6', '2008-07-25', {'2008-724'}),
            # LEGI's 1976-06-19 version of art. 7 carries no amendment link at all (the change is loi constitutionnelle
            # n° 76-527, but the source does not say so on this version): it stays unexplained, never guessed.
            ('7', '1976-06-19', set()), ('7', '2003-03-29', {'2003-276'}),
            ('61', '1974-10-30', {'74-904'}), ('89', '2008-07-25', {'2008-724'}),
            ('34', '1996-02-23', {'96-138'}), ('34', '2024-03-10', {'2024-200'}), ('PREAMBULE', '2005-03-02', {'2005-205'}),
            ('88-5', '2005-03-02', {'2005-204'}), ('88-5', '2008-07-25', {'2008-724'}), ('88-5', '2009-12-01', {'2008-724'}),
            ('66-1', '2007-02-24', {'2007-239'}),
        ]
        for num, day, want in cases:
            with self.subTest(num=num, day=day):
                self.assertEqual(credit(CONST, num, day), want)

    def test_as_enacted(self):
        """Every version in force on 1958-10-05 has no amendment link: the first commit is the Constitution itself."""
        self_ids = {CONST['dir'], CONST['legitext']}
        for num, lst in versions(CONST).items():
            for v in lst:
                if v.d <= '1958-10-05' < v.f:
                    self.assertEqual(parse.own(v, parse.CREATE, self_ids), [], num)


class CodeCivilCredits(unittest.TestCase):
    def test_inherited_link_is_not_a_credit(self):
        # 2020-01-01: links name loi 2019-1480 (already on the 2019-12-30 version) and ordonnance 2019-964 art. 35;
        # LEGI's NOTA on that version: "Conformément à l'article 36 de l'ordonnance n° 2019-964 [...] 1er janvier 2020"
        self.assertEqual(credit(CIVIL, '515-11', '2019-12-30'), {'2019-1480'})
        self.assertEqual(credit(CIVIL, '515-11', '2020-01-01'), {'2019-964'})

    def test_modifie_link_in_cible_direction(self):
        self.assertEqual(credit(CIVIL, '1240', '2016-10-01'), {'2016-131'})

    def test_staged_change_by_same_provision_is_unexplained(self):
        # loi 2019-222 art. 9 is the only link on both the 2019-03-25 and the 2020-01-01 versions of art. 427:
        # it cannot be told apart from an inherited link, so the second change stays unexplained.
        self.assertEqual(credit(CIVIL, '427', '2020-01-01'), set())

    def test_removal_by_the_creating_provision(self):
        v = versions(CIVIL)['1386-19'][0]
        ls = parse.removers(v, None, {CIVIL['dir'], CIVIL['legitext']}, v.f)
        self.assertEqual({(l.numtexte, l.type) for l in ls}, {('2016-1087', 'ABROGE')})
        # and a version with new words that a text signed earlier abrogates later is not an abrogated-state version
        lst = versions(CIVIL)['1386-6']
        self.assertEqual(parse.abrogated_state(lst[1], lst[0], {CIVIL['dir'], CIVIL['legitext']}), [])

    def test_abrogated_state_version(self):
        lst = versions(CIVIL)['9']
        i = next(i for i, v in enumerate(lst) if v.d == '1927-08-14')
        ab = parse.abrogated_state(lst[i], lst[i - 1], {CIVIL['dir'], CIVIL['legitext']})
        self.assertEqual({l.date for l in ab}, {'1927-08-10'})
        self.assertEqual(credit(CIVIL, '9', '1970-07-19'), {'70-643'})


class Text(unittest.TestCase):
    def test_lines(self):
        self.assertEqual(parse.text_of('<p>A  b</p><p>C <sup>er</sup>’x – y</p><br/>'), "A b\nC er'x - y\n")
        self.assertEqual(parse.text_of(''), '')

    def test_keys(self):
        self.assertEqual(parse.unit_key('515-11', 4), 'art-0515-011')
        self.assertEqual(parse.unit_key('89', 3), 'art-089')
        self.assertEqual(parse.unit_key('PREAMBULE', 3), 'preambule')
        self.assertEqual(parse.unit_key('R610-1', 3), 'r-610-001')
        self.assertEqual(parse.unit_key('R*131-1', 3), 'r-131-001')
        self.assertEqual(parse.unit_key('222-14 A', 3), 'art-222-014-a')
        self.assertEqual(parse.unit_key('434-35-1-A', 3), 'art-434-035-001-a')

    def test_dates(self):
        self.assertEqual(parse.fr_date('2005-03-01'), '1er mars 2005')
        self.assertEqual(parse.fr_date('2008-07-23'), '23 juillet 2008')


if __name__ == '__main__':
    unittest.main()
