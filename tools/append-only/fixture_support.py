"""Portable synthetic inputs and the shared builder under test; no country checkout."""
from pathlib import Path

COMMON = Path(__file__).resolve().parents[2] / 'gitlaw_common'


def surveyed(corpus):
    """These literal test fixtures contain no source images."""
    for act in corpus['acts']:
        for version in act['versions']:
            version['source_images'] = 0
    return corpus


def append_fixture(full):
    first = {'from': '2000-01-01', 'units': {'s-1': {'label': 'Section 1', 'text': 'First.\n'}}}
    later = {'from': '2010-01-01', 'units': {'s-1': {'label': 'Section 1', 'text': 'Later.\n'}},
             'credits': {'s-1': ['amendment']}}
    acts = [{'slug': 'first', 'short': 'First', 'title': 'First fixture', 'first_law': 'original',
             'versions': [first] + ([later] if full else [])}]
    if full:
        acts.append({'slug': 'second', 'short': 'Second', 'title': 'Newly found older fixture',
                     'first_law': 'older', 'versions': [{'from': '1995-01-01',
                     'units': {'s-1': {'label': 'Section 1', 'text': 'Newly found.\n'}}}]})
    return surveyed({'country': {'code': 'XT', 'name': 'Testland', 'slug': 'testland', 'lang': 'en', 'tz': 'UTC',
                     'publisher': {'name': 'Fixture publisher', 'email': 'fixture@test.invalid'}},
                     'laws': {'original': {'label': 'Original', 'enacted': '1999-12-01'},
                              'amendment': {'label': 'Amendment', 'enacted': '2009-12-01'},
                              'older': {'label': 'Older', 'enacted': '1994-12-01'}},
                     'acts': acts, 'sources': [{'name': 'Fixture', 'url': 'https://example.invalid',
                                               'retrieved': '2026-10-29'}]})
