"""gitlaw-scraper-dell (2026-10-31): write corpus.d/20-statutes-NN.json and repo/ docs for a Sri Lanka Provincial
Council from the cached Gazette PDFs (lk_prov_fetch.py). Private.

    python -X utf8 lk_prov_make.py uva|northern|central                      # the first part, 20-statutes-01
    python -X utf8 lk_prov_make.py uva --part 20-statutes-02 [--only URL...]  # statutes no earlier part holds

A later part never repeats a statute an earlier part holds (same Gazette PDF and the same slug, or the same Gazette PDF
and the same section 1 text): published parts are never rewritten.

Each statute the parser reads is checked at once by lk_prov_check (a second reader, pdftotext -raw); only statutes
that pass go into a part. The rest are listed in .cache/skipped.json with the reason.
"""
import hashlib
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import lk_prov_parse as P  # noqa: E402
import lk_prov_check as C  # noqa: E402

RETRIEVED = '2026-10-31'
PROV = {
    'uva': {'name': 'Uva Province', 'council': 'Uva Provincial Council', 'code': 'LK-8',
            'listing': 'https://www.up.gov.lk/publications/statutes/', 'site': 'https://www.up.gov.lk'},
    'northern': {'name': 'Northern Province', 'council': 'Northern Provincial Council', 'code': 'LK-4',
                 'listing': 'https://np.gov.lk/statutes/', 'site': 'https://np.gov.lk'},
    'central': {'name': 'Central Province', 'council': 'Central Provincial Council', 'code': 'LK-2',
                'listing': 'https://www.cp.gov.lk/web/statutes/?lang=en', 'site': 'https://www.cp.gov.lk'},
}
COPYRIGHT = ('Intellectual Property Act, No. 36 of 2003 (Sri Lanka), section 8: copyright protection does not extend '
             'to any official text of a legislative, administrative or legal nature, or to any official translation '
             'of such a text')


def slugify(s):
    s = re.sub(r'^the\s+', '', s.lower())
    s = re.sub(r'[^a-z0-9]+', '-', s).strip('-')
    return s[:80].rstrip('-')


def short_title(units, fallback):
    t = ' '.join(l for u in units.values() for l in u['text'].split('\n') if l and not l.startswith('# '))
    m = re.search(r'(?:cited|known|called|introduced|identified|termed|defin\w*)\s+as\s+(?:the\s+)?[“"]?(.{5,200}?'
                  r'\bNo\s*\.?\s*:?\s*0?\d{1,2}\s*(?:of|,|/)\s*(?:the\s+year\s+)?\d{4})', t, re.I)
    if m:
        return re.sub(r'\s+', ' ', m.group(1)).strip(' “”"')
    return fallback


def sec1(units):
    """The letters and digits of a statute's section 1 sentence ("This Statute may be cited as ..."), to know a statute
    again however a later parser splits it into files."""
    t = ' '.join(l for u in units.values() for l in u['text'].split('\n') if l and not l.startswith('# '))
    m = re.search(r'\b0?1\s*\.\s*(?:\(1\)\s*)?(?:Short\s+title\s*[:.\-–—]\s*)?(?:This|These|The)\b.{0,200}', t, re.I)
    return C.ld(m.group(0))[:120] if m else ''


def main(p, part_name=None, only=()):
    cfg = PROV[p]
    folder = HERE.parent / f'sri-lanka-{p}-law'
    cat = json.loads((folder / '.cache' / 'catalogue.json').read_text(encoding='utf-8'))
    acts, skipped = [], []
    have, have_s1, slugs = set(), set(), set()
    for prev in sorted((folder / 'corpus.d').glob('*.json')):
        if part_name and prev.stem >= part_name:
            continue
        for a in json.loads(prev.read_text(encoding='utf-8'))['acts']:
            have.add((a['url'], a['slug']))
            have_s1.add((a['url'], sec1(a['versions'][0]['units'])))
            slugs.add(a['slug'])
    for pdf in sorted({x['pdf'] for x in cat}, key=lambda f: [x['pdf'] for x in cat].index(f)):
        ents = [x for x in cat if x['pdf'] == pdf]
        url = ents[0]['url']
        try:
            parsed, meta = P.parse(Path(pdf))
        except Exception as e:
            skipped.append({'url': url, 'titles': [e2['title'] for e2 in ents], 'reason': f'parse: {e}'[:200]})
            continue
        if not meta['gazette'].get('date'):
            skipped.append({'url': url, 'titles': [e2['title'] for e2 in ents], 'reason': 'no Gazette date on page 1'})
            continue
        S = {m: C.source(Path(pdf), m) for m in C.MODES}
        aside = meta['aside'] + meta['notes'] + [l for n in meta['notice'] for l in n.split('\n')]
        sha = hashlib.sha256(Path(pdf).read_bytes()).hexdigest()
        for k, a in enumerate(parsed):
            nxt = None
            if k + 1 < len(parsed):
                nxt = parsed[k + 1]['units'][next(iter(parsed[k + 1]['units']))]['text'].split('\n')[1][:60]
            ok, msg, reader = False, '', None
            for m in C.MODES:  # the second reader's two reading orders; each check is complete on its own
                ok, got = C.check_act(a['units'], a['used_notes'], S[m], aside, nxt)
                if ok:
                    reader = m or 'physical'
                    break
                msg = msg or got
            fallback = ents[0]['title'] if len(parsed) == 1 and len(ents) == 1 and ents[0]['title'] != 'English' else None
            name = short_title(a['units'], fallback)
            first = next(l for u in a['units'].values() for l in u['text'].split('\n') if l and not l.startswith('# '))
            if ok and re.match(r'[a-z]', first):
                ok, msg = False, f'the record would begin mid-sentence ("{first[:40]}"): the start of the statute was not found'
            if not ok:
                skipped.append({'url': url, 'statute': k + 1, 'of': len(parsed), 'title': name,
                                'reason': f'letters check: {msg}'[:300]})
                continue
            if not name:
                skipped.append({'url': url, 'statute': k + 1, 'of': len(parsed), 'reason': 'no short title found'})
                continue
            if (url, slugify(name)) in have or (url, sec1(a['units'])) in have_s1:
                continue  # an earlier part holds this statute
            if only and url not in only:
                continue
            slug = base = slugify(name)
            n = 2
            while slug in slugs:
                slug = f'{base}-{n}'
                n += 1
            slugs.add(slug)
            g = meta['gazette']
            note = (f'The text as published in the Gazette of the Democratic Socialist Republic of Sri Lanka '
                    f'(Extraordinary) No. {g["no"]} of {g["date"]}, Part IV (A), Provincial Councils, on the '
                    f'{cfg["council"]}\'s website; dated the day of that Gazette.')
            if part_name:
                note += (' Checked against the second reader in its '
                         + ('content-stream' if reader == '-raw' else 'physical') + ' reading order.')
            acts.append({'slug': slug, 'short': name, 'title': fallback or name, 'url': url, 'first_law': None,
                         'earlier_laws': [],
                         'versions': [{'from': g['date'], 'source_url': url, 'sha256': sha, 'units': a['units'],
                                       'credits': {}, 'note': note}]})
    acts.sort(key=lambda a: (a['versions'][0]['from'], a['slug']))
    (folder / '.cache' / (f'skipped-{part_name}.json' if part_name else 'skipped.json')).write_text(json.dumps(skipped, ensure_ascii=False, indent=1), encoding='utf-8')
    country = {
        'code': cfg['code'], 'name': cfg['name'], 'slug': f'sri-lanka-{p}', 'lang': 'en', 'tz': 'Asia/Colombo',
        'future_branch': 'future',
        'publisher': {'name': cfg['council'], 'email': f'council@sri-lanka-{p}-law.invalid'},
        'default_in_force_rule': {
            'text': 'Each statute is dated by the day the Gazette Extraordinary published it; its own section 1 says '
                    'when it comes into operation (usually on the Governor\'s assent), which this record does not '
                    'derive.', 'source': cfg['listing']},
        'licence_note': (f'Statutes of the {cfg["council"]} as published in the Gazette of the Democratic Socialist '
                         f'Republic of Sri Lanka (Extraordinary), Part IV (A), and posted on {cfg["site"]}. '
                         + COPYRIGHT + '.'),
    }
    part = {
        'country': country,
        'sources': [{'name': f'{cfg["council"]}: statutes page, English text of each statute as published in the '
                             f'Gazette Extraordinary (PDF with a text layer)', 'url': cfg['listing'],
                     'retrieved': RETRIEVED, 'licence': country['licence_note'],
                     'notes': f'{len(acts)} statutes in this part; no OCR.'}],
        'laws': {f'{p}-council': {
            'label': cfg['council'], 'title': f'Statutes of the {cfg["council"]} as published in the Gazette',
            'kind': 'publisher', 'enacted': None, 'published': None, 'url': cfg['listing'], 'temporary_until': None,
            'restores': None, 'note': 'The publisher of the texts; no change in this record is credited to it.'}},
        'acts': acts,
        'applies': [],
        'decisions': [
            'Oldest version available: each statute is one version, its English text as published in the Gazette '
            'Extraordinary (Part IV (A), Provincial Councils), dated the day of that Gazette (first_law null), credited '
            'to the Council, not to an amending law. Amending statutes are recorded as statutes of their own; their '
            'changes are not replayed into the statutes they amend.',
            'English text only. Statutes are enacted in Sinhala and Tamil as well; where a statute says which text '
            'prevails, it says so in its own words in this record.',
            'One file per section where each section starts with its number beside a marginal note (the note is the '
            'line after the section label); otherwise one file, 000-text, holding the whole statute from its heading.',
            'Left out: the Gazette masthead, running heads and the Sinhala/Tamil lines in legacy fonts, page labels, '
            'printing footers, the Council Secretary\'s publication notice, and marginal notes where sections are not '
            'split.',
            'A statute is left out when a second reading of its PDF (pdftotext) does not find every paragraph of the '
            'record whole, or finds text in the statute\'s stretch that the record lacks (tables, forms, layout the '
            'parser misreads).'],
        'ai_use': ["Claude Code (claude-opus-5-5) wrote Lexifina's code and chose the sources. No model output is used "
                   'as legal text or dates: every word comes from the Gazette PDFs on the Council\'s website.'],
    }
    out = folder / 'corpus.d' / f'{part_name or "20-statutes-01"}.json'
    out.parent.mkdir(exist_ok=True)
    if out.with_suffix('.PUBLISH').exists():
        raise SystemExit(f'{out.stem} is verified already')
    if part_name:
        # a later part adds statutes only: the country, publisher and decisions come from 20-statutes-01
        part = {'sources': [{**part['sources'][0], 'notes': f'{len(acts)} statutes in {part_name}; no OCR.'}],
                'acts': acts,
                'decisions': [
                    f'{part_name}: statutes an earlier parser could not read (marginal notes set beside short body '
                    'lines, section numbers printed apart from their text, several statutes in one Gazette issue). '
                    'The second reader (pdftotext) checks each statute in its content-stream order and, where that '
                    'order interleaves statutes or marginal notes on a shared page, in its physical reading order; '
                    'every check is complete in the order that passes (each paragraph whole, nothing else in the '
                    'statute\'s stretch but page furniture). The note on each version names the order used.']}
    tmp = out.with_suffix('.json.tmp')
    tmp.write_text(json.dumps(part, ensure_ascii=False, indent=1) + '\n', encoding='utf-8', newline='\n')
    tmp.replace(out)
    print(p, len(acts), 'statutes,', len(skipped), 'skipped')
    for a in acts:
        print('  ', a['versions'][0]['from'], a['slug'], len(a['versions'][0]['units']))


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('prov')
    ap.add_argument('--part')
    ap.add_argument('--only', nargs='*', default=())
    a = ap.parse_args()
    main(a.prov, a.part, set(a.only))
