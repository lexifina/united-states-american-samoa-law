"""Checks the last version of each act in corpus.json against the text wetten.overheid.nl shows as in force today.

    python -X utf8 scripts/netherlands-law/verify.py            # writes verify.json beside corpus.json

For each act it reads https://wetten.overheid.nl/<BWB id> (which serves the version in force on the day it is read)
through fetch.py (curl, cached by the sha256 of the URL, logged to .cache/requests.jsonl; delete the cached page to
re-check on a later day), and:
1. compares the page's "Geldend van DD-MM-YYYY t/m heden" with the day of the act's last version in corpus.json;
2. compares every article word for word: the page's article text (site chrome removed: action menus, structural
   headings, the "Wijziging(en) zonder datum inwerkingtreding" and "nog niet in werking getreden" banners, the "Red:"
   label of editorial notes) against each article file of the last version, as sequences of words (letters and
   digits; punctuation and spacing ignored).
Page articles that are only a "Vervallen per ..." placeholder are expected (repealed articles are absent here), and so
are articles the page marks as not yet in force ("nogniet" in the BWB; absent here until they take effect).
Standard library only; fetch.py does the network.
"""
from __future__ import annotations

import difflib
import html
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import fetch  # noqa: E402
import parse  # noqa: E402


def toks(s: str) -> list[str]:
    return re.findall(r'[0-9A-Za-zÀ-ÿ€§]+', html.unescape(s).replace('\xad', '').lower())


def page_articles(t: str) -> list[list[str]]:
    t = re.sub(r'<ul role="list".*?</ul>', ' ', t, flags=re.S)
    t = re.sub(r'<(script|style)\b.*?</\1>', ' ', t, flags=re.S)
    t = re.sub(r'<h[1-3]\b.*?</h[1-3]>', ' ', t, flags=re.S)
    t = re.sub(r'<div class="article__header--law (?!artikel)[^"]*">\s*<h4\b.*?</h4>', ' ', t, flags=re.S)
    t = re.sub(r'<p class="regeling-toestand-meldingen">.*?</p>', ' ', t, flags=re.S)
    t = re.sub(r'<a [^>]*>(wijzigingenoverzicht)</a>', r'\1', t)
    t = re.sub(r'<p>\[(?:Vervallen|Toekomstige wijziging|Tekst zonder datum|Wijziging)[^\]]*?'
               r'(?:wijzigingenoverzicht|werking getreden)[^\]]*?\]\s*</p>', ' ', t, flags=re.S)
    t = re.sub(r'<p>\s*\[Vervallen per \d\d-\d\d-\d{4}\]\s*</p>', ' ', t)
    t = re.sub(r'<p>\s*Dit onderdeel is \(nog\) niet in werking getreden; zie het wijzigingenoverzicht\.\s*</p>', ' ', t)
    t = re.sub(r'<a [^>]*>\s*Origineel slotformulier en ondertekening\s*</a>', ' ', t)
    t = re.split(r'<div id="popup', t)[0]  # the dialogs and footer after the act
    t = t.replace('[Red: ', '[')
    out = []
    for p in re.split(r'<div class="artikel"', t)[1:]:
        p = re.split(r'<div class="(?:wetsluiting|slotformulering|ondertekening|bijlage|nota-toelichting)', p)[0]
        p = re.sub(r'</?(?:a|span|i|b|em|strong|small|sub|sup|abbr)\b[^>]*>', '', p)
        out.append(toks(re.sub(r'<[^>]+>', ' ', '<x' + p)))
    return out


def last_state(act: dict) -> dict:
    u: dict = {}
    for v in act['versions']:
        if 'units' in v:
            u = dict(v['units'])
        for k, x in (v.get('changes') or {}).items():
            if x is None:
                u.pop(k, None)
            else:
                u[k] = x
    return u


def main() -> dict:
    corpus = json.loads((HERE / 'corpus.json').read_text(encoding='utf-8'))
    report = {}
    for act in corpus['acts']:
        bwb = fetch.ACTS[act['slug']]['bwb']
        url = f'https://wetten.overheid.nl/{bwb}'
        raw = fetch.fetch(url)
        t = raw.decode('utf-8', 'replace')
        m = re.search(r'Geldend van (\d\d)-(\d\d)-(\d{4}) t/m heden', t)
        consulted = re.search(r'Geraadpleegd op (\d\d-\d\d-\d{4})', t)
        page_day = f'{m.group(3)}-{m.group(2)}-{m.group(1)}' if m else None
        page = page_articles(t)
        ours = {k: toks(v['text'].lstrip('# ')) for k, v in last_state(act).items() if k != 'inhoud'}
        pool: dict[str, int] = {}
        for p in page:
            pool[' '.join(p)] = pool.get(' '.join(p), 0) + 1
        unmatched = {}
        for k, w in sorted(ours.items()):
            key = ' '.join(w)
            if pool.get(key):
                pool[key] -= 1
                continue
            same = [s for s, n in pool.items() if n and s.split()[:2] == w[:2]]
            other = same[0].split() if same else []
            sm = difflib.SequenceMatcher(None, w, other, autojunk=False)
            unmatched[k] = [[op, ' '.join(w[a:b]), ' '.join(other[c:e])]
                            for op, a, b, c, e in sm.get_opcodes() if op != 'equal'][:5]
        # Articles the last toestand itself marks vervallen or nogniet (absent from the corpus by design).
        last_raw = fetch.fetch(act['versions'][-1]['source_url'], offline=True)
        gone = {k: a.get('status') for k, a in parse.read_version(last_raw)['gone'].items()}
        rest = [s for s, n in pool.items() for _ in range(n)
                if not re.fullmatch(r'artikel \S+( vervallen( per \d\d \d\d \d{4})*)?', s)]
        not_yet, page_only = [], []
        for s in rest:
            w = s.split()
            key = parse.article_key(w[1], '') if w[0] == 'artikel' and len(w) > 1 else None
            if key in gone or 'nog niet in werking getreden' in s:
                not_yet.append(f'{key or s[:30]} ({gone.get(key, "banner")})')
            else:
                page_only.append(s[:100])
        report[act['slug']] = {
            'url': url, 'consulted': consulted.group(1) if consulted else None, 'page_in_force_from': page_day,
            'ours_last': act['versions'][-1]['from'], 'date_ok': page_day == act['versions'][-1]['from'],
            'articles_ours': len(ours), 'articles_page': len(page), 'unmatched': unmatched, 'page_only': page_only,
            'page_not_yet_in_force': not_yet}
        print(act['slug'], 'page in force from', page_day, 'ours', act['versions'][-1]['from'],
              'articles', len(ours), 'unmatched', len(unmatched), 'page-only', len(page_only),
              'not yet in force (expected)', not_yet)
        for k, d in unmatched.items():
            print('  ', k, d)
        for s in page_only:
            print('   page only:', s)
    tmp = HERE / 'verify.json.tmp'
    tmp.write_text(json.dumps(report, ensure_ascii=False, indent=1) + '\n', encoding='utf-8', newline='\n')
    tmp.replace(HERE / 'verify.json')
    return report


if __name__ == '__main__':
    main()
