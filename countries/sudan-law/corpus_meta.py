"""Country metadata and corpus assembly for Sudan (used by parse.py)."""
import hashlib

ONLY = {'criminal-act-1991'}   # acts whose parse has no open problems; the Civil Transactions Act is still WIP


def build(acts, report, cached):
    out_acts = []
    for a, url, units in acts:
        if a['slug'] not in ONLY or report[a['slug']]['problems']:
            continue
        notes = report[a['slug']]['notes']
        fn = '; '.join(f"{k}: {' / '.join(v)}" for k, v in sorted(notes.items()))
        out_acts.append({
            'slug': a['slug'], 'short': a['short'], 'title': a['title'], 'url': url,
            'first_law': None, 'earlier_laws': [],
            'versions': [{
                'from': '2015-03-30', 'source_url': url,
                'sha256': hashlib.sha256(cached(url)).hexdigest(),
                'units': units, 'credits': {},
                'note': ('Text of the 9th Revised Edition of the Laws of Sudan (Ministry of Justice), which states it '
                         'holds the laws in force to 30 March 2015. Oldest version available; not the act as enacted. '
                         'The edition\'s footnotes name these amending laws: ' + fn)}],
        })
    return {
        'country': {
            'code': 'SD', 'name': 'Sudan', 'slug': 'sudan', 'lang': 'ar', 'tz': 'Africa/Khartoum',
            'future_branch': 'future',
            'publisher': {'name': 'Ministry of Justice of Sudan (وزارة العدل)', 'email': 'moj@moj-gov-sd.invalid'},
            'default_in_force_rule': {'text': 'Not applied: the only version is dated by the revised edition\'s own '
                                              'stated date (laws in force to 30 March 2015).',
                                      'source': 'https://www.moj.gov.sd/sudanlaws/epub/EPUB/xhtml/sibyrw.html'},
            'licence_note': 'Text: وزارة العدل - جمهورية السودان (Ministry of Justice, Republic of Sudan), '
                            'قوانين السودان, 9th Revised Edition, https://www.moj.gov.sd/sudanlaws/',
        },
        'sources': [{'name': 'Ministry of Justice, Laws of Sudan ebook (9th Revised Edition)',
                     'url': 'https://www.moj.gov.sd/sudanlaws/', 'retrieved': '2026-10-28',
                     'licence': 'Rights: وزارة العدل - جمهورية السودان (no open licence stated)',
                     'notes': 'Kotobee EPUB served unpacked at /sudanlaws/epub/EPUB/; package modified 2017-05-01.'}],
        'laws': {},
        'acts': out_acts,
        'applies': [],
        'decisions': [
            'One version per act, from the 9th Revised Edition, dated 2015-03-30 (the edition\'s own stated cut-off), credited to the publisher as oldest version available.',
            'Each source paragraph is one line; the marginal note (section heading) is taken out of the run-in text and put in the heading line.',
            'Footnote markers are dropped from the text; the amending laws they name are listed in the version note, not credited, because the edition gives no dates per change.',
            'The 2019 Constitutional Charter and its 2020 and 2025 amendments are left out: the official gazette PDFs (moj.gov.sd files 144, 226, 425) are scans with no usable text layer, and OCR is not used. The WIPO Lex English text is an International IDEA translation, not official.',
        ],
        'ai_use': ['Claude Code (claude-opus-5-5) wrote fetch.py and parse.py; no model wrote or edited legal text.'],
    }
