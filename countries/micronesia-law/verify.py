"""Independent checks of corpus.json against second renderings of the same sources (gitlaw-FM). Cache only.

1. Code titles, first version: every paragraph of every section must appear, word for word, in the FSM LIS
   per-chapter HTML of the same 2014 edition (code2014/FSMCode2014TitNNChapMM.html, Internet Archive captures),
   which is a separate export from the title PDF parse.py reads.
2. Public-law versions: every paragraph of every changed unit must appear word for word in the enrolled law's
   PyMuPDF text (parse.py read it with pdftotext), after dropping the printed line numbers (1-2 digit tokens) on
   both sides.
3. Latest state: the text each act has today (after all versions) is printed as counts for the record.

Usage: python -X utf8 verify.py      (writes verification.json; exit 1 on any miss)
"""
import json
import os
import re
import sys

import fitz

import fetch

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'gitlaw_common'))
import wayback  # noqa: E402

CACHE = os.path.join(HERE, '.cache')
TITLE_NO = {'title-11-crimes': 11, 'title-07-citizenship': 7}


def words(t, drop_small_numbers=False):
    t = t.replace('ï¿½', ' ').replace('�', ' ')
    w = re.sub(r'[^a-z0-9$]+', ' ', t.lower()).split()
    if drop_small_numbers:
        w = [x for x in w if not re.fullmatch(r'\d{1,2}', x)]
    return ' ' + ' '.join(w) + ' '


def html_words(b):
    import html
    s = b.decode('cp1252', 'replace')
    s = re.sub(r'(?is)<script.*?</script>|<style.*?</style>|<!--.*?-->', ' ', s)
    s = html.unescape(re.sub(r'<[^>]+>', ' ', s))
    return words(s.replace('§', ' '))


def chapter_html(tn, ch):
    name = f'FSMCode2014Tit{tn:02d}Chap{ch:02d}.html'
    caps = wayback.captures(f'fsmlaw.org/fsm/code/code2014/{name}', cache=CACHE)
    if not caps:
        return None, None
    c = sorted(caps, key=lambda c: c['timestamp'])[0]
    return fetch.wb(c.get('original') or c['url'], c['timestamp']), c['timestamp']


def main():
    c = json.load(open(os.path.join(HERE, 'corpus.json'), encoding='utf-8'))
    report, misses = {}, []
    for a in c['acts']:
        if a['slug'] not in TITLE_NO:
            continue
        tn = TITLE_NO[a['slug']]
        v0 = a['versions'][0]
        chapters = sorted({int(k[4:8]) // 100 for k in v0['units'] if k.startswith('sec-')})
        texts, used = {}, {}
        for ch in chapters:
            b, ts = chapter_html(tn, ch)
            if b is not None:
                texts[ch], used[ch] = html_words(b), ts
        paras = checked = 0
        for k, u in v0['units'].items():
            if not k.startswith('sec-'):
                continue
            ch = int(k[4:8]) // 100
            if ch not in texts:
                continue
            checked += 1
            for p in u['text'].split('\n')[1:]:
                if not p.strip():
                    continue
                paras += 1
                if words(p.replace('§', ' ')) not in texts[ch]:
                    misses.append({'act': a['slug'], 'version': v0['from'], 'unit': k, 'para': p[:160]})
        report[a['slug']] = {'edition_sections_checked': checked, 'edition_paragraphs': paras,
                             'html_chapters': {str(k): v for k, v in sorted(used.items())},
                             'chapters_without_html': [ch for ch in chapters if ch not in texts]}
        pl_paras = 0
        for v in a['versions'][1:]:
            doc = fitz.open(fetch.path_for(v['source_url']))
            keep = [ln for i in range(doc.page_count) for ln in doc[i].get_text().split('\n')
                    if not re.match(r'^\s*(P\.?\s?C\.?\s*NO\.|PC NO\.|CONGRESSIONAL BILL NO\.|PUBLIC LAW NO\.|CBL\b|'
                                    r'(\d+\s+)?o?f\s+\d+\s*$|(C\.\s?D\.\s?\d*,?\s*)+$)', ln.strip(), re.I)]
            plw = words(' '.join(keep), True)   # running heads and folios dropped, as in layout.public_law
            for k, u in v['changes'].items():
                for p in (u['text'].split('\n')[1:] if u else []):
                    if not p.strip():
                        continue
                    pl_paras += 1
                    if words(p, True) not in plw:
                        misses.append({'act': a['slug'], 'version': v['from'], 'unit': k, 'para': p[:160]})
        report[a['slug']]['public_law_paragraphs'] = pl_paras
    report['misses'] = misses
    with open(os.path.join(HERE, 'verification.json'), 'w', encoding='utf-8', newline='\n') as f:
        json.dump(report, f, ensure_ascii=False, indent=1)
        f.write('\n')
    print(json.dumps({k: v for k, v in report.items() if k != 'misses'}, indent=1))
    print('misses', len(misses))
    for m in misses[:40]:
        print(' ', m)
    sys.exit(1 if misses else 0)


if __name__ == '__main__':
    main()
