"""Write corpus.d parts for one Kenyan county from the cached county Acts (Kenya Gazette Supplements posted on the
county assembly's website): 20-acts-NN, about 50 Acts each.

    python -X utf8 make_part.py <county-slug> [--flush]

Private (gitlaw-scraper-dell, 2026-10-31). Reads only the cache (scripts/world-law/.lk-ke-ph/ke/<county>.catalogue.json
and the PDFs). An Act is left out (.lk-ke-ph/ke/<county>.skipped.json, with the reason) when it is not a Kenya Gazette
Supplement with a text layer, the parser cannot read it, its sections do not match its arrangement of sections, or the
letters-and-digits check fails. Verified parts (with .PUBLISH) are never rewritten; new parts are numbered after them.
"""
import hashlib
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE))
import pkmy_fetch as F  # noqa: E402
import parse as P  # noqa: E402
import check_letters as C  # noqa: E402

import pymupdf  # noqa: E402

PART = 50
RETRIEVED = '2026-10-31'
COUNTIES = {
    'garissa': ('KE-07', 'Garissa', 'https://garissaassembly.go.ke/acts/', 'garissaassembly.go.ke'),
    'tana-river': ('KE-40', 'Tana River', 'https://tanariverassembly.go.ke/house-business/acts/', 'tanariverassembly.go.ke'),
    'taita-taveta': ('KE-39', 'Taita-Taveta', 'https://taitatavetaassembly.go.ke/document-category/acts/',
                     'taitatavetaassembly.go.ke'),
}
COPYRIGHT = ('Copyright Act, 2001 (Cap. 130, Laws of Kenya), section 2, definition of "literary work", which ends: '
             '"but does not include a written law or a judicial decision"')


def slugify(s):
    s = re.sub(r'^the\s+', '', s.lower())
    s = re.sub(r'[^a-z0-9]+', '-', s).strip('-')
    return s[:80].rstrip('-')


def version_date(meta, units):
    """Commencement when the Act states a date; otherwise the day the Gazette Supplement was published, but never
    before assent. Returns (date, how)."""
    if meta['commencement']:
        return meta['commencement'], f'its Date of Commencement ({meta["commencement"]})'
    g, a = meta['gazette_date'], meta['assent']
    if g and (not a or g >= a):
        return g, (f'the date of the Kenya Gazette Supplement that published it ({g}); the Act gives its commencement '
                   f'as "{meta["commencement_text"]}"' if meta['commencement_text'] else
                   f'the date of the Kenya Gazette Supplement that published it ({g})')
    if a:
        return a, f'its Date of Assent ({a}), the Gazette Supplement date being missing or earlier'
    return None, None


def main(county: str):
    code, name, list_url, host = COUNTIES[county]
    out_dir = HERE.parent.parent / f'kenya-{county}-law'
    cat = json.loads((HERE.parent / '.lk-ke-ph' / 'ke' / f'{county}.catalogue.json').read_text(encoding='utf-8'))
    taken = set()
    for kp in (out_dir / 'corpus.d').glob('*.keys.txt'):
        if kp.with_name(kp.name.replace('.keys.txt', '.PUBLISH')).exists():
            taken |= set(json.loads(kp.read_text(encoding='utf-8')))
    skipped, acts, slugs, seen_sha = [], [], set(), set()
    publisher = f'County Assembly of {name}'
    for it in cat:
        pdf = F.path_for(it['url'])
        if not pdf.exists():
            skipped.append({'url': it['url'], 'reason': 'not fetched'})
            continue
        sha = hashlib.sha256(pdf.read_bytes()).hexdigest()
        if sha in seen_sha:
            skipped.append({'url': it['url'], 'reason': 'same file as another entry'})
            continue
        seen_sha.add(sha)
        try:
            units, meta = P.parse(pdf)
        except Exception as e:
            skipped.append({'url': it['url'], 'reason': f'parse: {e}'[:200]})
            continue
        doc = pymupdf.open(pdf)
        front = '\n'.join(doc[i].get_text() for i in range(meta['start_page'] + 1))
        arr = [int(x) for x in re.findall(r'(?m)^\s*(\d{1,3})\s*[—–-]', front)]
        if not arr or max(arr) != meta['sections']:
            skipped.append({'url': it['url'], 'reason': f'sections parsed {meta["sections"]} != arrangement '
                                                        f'{max(arr) if arr else None}'})
            continue
        ok, msg = C.check_act(units, C.source(pdf, meta['start_page'], meta['end_page']), meta['aside'], meta['headings'])
        if not ok:
            skipped.append({'url': it['url'], 'reason': f'letters check: {msg}'[:300]})
            continue
        day, how = version_date(meta, units)
        if not day:
            skipped.append({'url': it['url'], 'reason': 'no date'})
            continue
        if it['url'] in taken:
            continue
        title = meta['short_title'] or meta['title'] or it.get('title')
        title = re.sub(r'\s+', ' ', title).strip(' .')
        slug = slugify(title)
        base, n = slug, 2
        while slug in slugs:
            slug = f'{base}-{n}'
            n += 1
        slugs.add(slug)
        note = (f'{title}, {meta["number"] or "number not printed"}, as published in {meta["supplement"] or "a Kenya Gazette Supplement"}'
                f'{" of " + meta["gazette_date"] if meta["gazette_date"] else ""} (Government Printer) and posted on the '
                f'website of the {publisher}. Date of Assent: {meta["assent"] or "not printed"}. The text is the Act as '
                f'enacted; dated by {how}.')
        acts.append(({'slug': slug, 'short': title, 'title': title, 'url': it.get('page') or list_url,
                      'first_law': None, 'earlier_laws': [],
                      'versions': [{'from': day, 'source_url': it['url'], 'sha256': sha, 'units': units,
                                    'credits': {}, 'note': note}]}, it['url']))
    acts.sort(key=lambda a: (a[0]['versions'][0]['from'], a[0]['slug']))
    (HERE.parent / '.lk-ke-ph' / 'ke' / f'{county}.skipped.json').write_text(
        json.dumps(skipped, ensure_ascii=False, indent=1), encoding='utf-8')
    country = {
        'code': code, 'name': f'{name} County', 'slug': f'kenya-{county}', 'lang': 'en', 'tz': 'Africa/Nairobi',
        'future_branch': 'future',
        'publisher': {'name': f'{publisher} (Kenya Gazette Supplement, Government Printer)',
                      'email': f'acts@{host.replace(".", "-")}.invalid'},
        'default_in_force_rule': {
            'text': 'Each Act is dated by the "Date of Commencement" its Gazette Supplement prints; where that is not a '
                    'date (for example "See Section 1"), by the date of the Gazette Supplement, and never before the '
                    'Date of Assent.',
            'source': list_url},
        'licence_note': (f'Text of the {name} County Acts as published in the Kenya Gazette Supplement (Government '
                         f'Printer, Nairobi) and posted on the website of the {publisher} ({host}). Written law is not a '
                         f'literary work under the {COPYRIGHT}.'),
    }
    out_dir.joinpath('corpus.d').mkdir(parents=True, exist_ok=True)
    n = len(list((out_dir / 'corpus.d').glob('20-acts-*.PUBLISH')))
    for k in range(0, len(acts), PART):
        chunk = acts[k:k + PART]
        if len(chunk) < PART and '--flush' not in sys.argv:
            break
        n += 1
        path = out_dir / 'corpus.d' / f'20-acts-{n:02d}.json'
        if path.with_suffix('.PUBLISH').exists():
            raise SystemExit(f'{path.name} is verified already')
        part = {
            'country': country,
            'sources': [{'name': f'{publisher}: "Acts", Kenya Gazette Supplements (Government Printer) as PDF with a text layer',
                         'url': list_url, 'retrieved': RETRIEVED, 'licence': country['licence_note'],
                         'notes': f'{len(chunk)} County Acts in this part, each one Gazette Supplement PDF; no OCR.'}],
            'laws': {'gazette-supplement': {
                'label': 'Kenya Gazette Supplement', 'title': f'{name} County Acts as published in the Kenya Gazette Supplement',
                'kind': 'publisher', 'enacted': None, 'published': None, 'url': list_url, 'temporary_until': None,
                'restores': None, 'note': 'The publisher of the texts; no change in this record is credited to it.'}},
            'acts': [a for a, _ in chunk],
            'applies': [],
            'decisions': [
                'Text as enacted only: the county assembly posts each Act as its Kenya Gazette Supplement, with no '
                'consolidated text, so each Act is one version ("oldest version available", first_law null), credited '
                'to the publisher, not to an amending law. Amending Acts in this record are separate Acts; their '
                'amendments are not applied to the Acts they amend.',
                'Each version is dated by the Date of Commencement the Supplement prints; where that is not a date '
                '("See Section 1"), by the date of the Supplement, and never before the Date of Assent.',
                'One file per section; the long title and enacting words are "000-title", and each Schedule its own '
                'file. Part headings and section headings (bold rows or margin notes) stand above the section they '
                'head.',
                'Left out: the Supplement cover, the title block (number, Dates of Assent and Commencement, which go '
                'into the version note) and the arrangement of sections, running heads and page numbers.',
                'An Act is left out when its PDF is a scan with no text layer, is not a Gazette Supplement, cannot be '
                'read reliably (tables or forms that the independent check does not find in the same order), or its '
                'parsed sections differ from its arrangement of sections.'],
            'ai_use': ["Claude Code (claude-opus-5-5) wrote Lexifina's code and chose the sources. No model output is "
                       'used as legal text or dates: every word comes from the Gazette Supplement PDFs.'],
        }
        tmp = path.with_suffix('.json.tmp')
        tmp.write_text(json.dumps(part, ensure_ascii=False, indent=1) + '\n', encoding='utf-8', newline='\n')
        tmp.replace(path)
        path.with_name(path.stem + '.keys.txt').write_text(json.dumps([u for _, u in chunk]), encoding='utf-8')
        print(path.name, len(chunk))
    print(county, len(acts), 'ready,', len(skipped), 'skipped')


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    main(sys.argv[1])
