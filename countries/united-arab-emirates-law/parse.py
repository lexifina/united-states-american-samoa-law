"""Read the cached archive.org capture of the UAE Constitution (Arabic) and write corpus.json.

Interim (wind-down, 2026-10-29): one "oldest version available" version of the Constitution, the consolidated
Arabic text as the site states it ("last update 29 Mar 2023"), credited to the publisher. No network.
Next step (see PROGRESS.md): add the earlier wordings from the archived "previous texts" popups and credit them to
the constitutional amendments once their own pages (dates, articles changed) are cached.
"""
from __future__ import annotations

import hashlib
import html as H
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, r'C:/Users/alany/Documents/lexifina/scripts/gitlaw_common')
import wayback  # noqa: E402

HERE = Path(__file__).resolve().parent
CACHE = HERE / '.cache'
CONST_URL, CONST_TS = 'https://uaelegislation.gov.ae/ar/legislations/1000/', '20250529114023'


def cached(url: str, ts: str) -> bytes:
    key = f'https://web.archive.org/web/{ts}id_/{url}'
    return (CACHE / hashlib.sha256(key.encode()).hexdigest()).read_bytes()


def clean(fragment: str) -> str:
    s = re.sub(r'<br\s*/?>|</p>|</li>|</div>', '\n', fragment)
    s = H.unescape(re.sub(r'<[^>]+>', '', s))
    s = re.sub(r'[\u200b-\u200f\u202a-\u202e\ufeff]', '', s).replace('\xa0', ' ')
    s = s.replace('–', '-').replace('—', '-')
    lines = [re.sub(r'[ \t]+', ' ', l).strip() for l in s.split('\n')]
    return ''.join(l + '\n' for l in lines if l)


def articles(page: str) -> dict:
    units = {}
    for m in re.finditer(r'<div class="content_"\s+id="item\d+">(.*?)<div class="text_area mm_cnt">(.*?)</div>', page, re.S):
        head = re.sub(r'<div class="tooltip_holder.*', '', m.group(1), flags=re.S)
        num = re.search(r'المادة\s*\((\d+)\)', H.unescape(re.sub(r'<[^>]+>', ' ', head)))
        if not num:
            continue
        n = int(num.group(1))
        label = f'المادة ({n})'
        units[f'art-{n:03d}'] = {'label': label, 'kind': 'art', 'text': f'# {label}\n' + clean(m.group(2))}
    return units


def main() -> None:
    raw = cached(CONST_URL, CONST_TS)
    units = articles(raw.decode('utf-8'))
    corpus = {
        'country': {
            'code': 'AE', 'name': 'United Arab Emirates', 'slug': 'united-arab-emirates', 'lang': 'ar',
            'tz': 'Asia/Dubai', 'future_branch': 'future',
            'publisher': {'name': 'UAE Legislation (uaelegislation.gov.ae), UAE Cabinet', 'email': 'publisher@uaelegislation.invalid'},
            'default_in_force_rule': {'text': 'Constitution art. 111: federal laws are published in the Official Gazette within two weeks of signature and come into force one month after publication unless the law provides otherwise. Each act\'s own in-force clause overrides this.',
                                      'source': 'https://uaelegislation.gov.ae/ar/legislations/1000'},
            'licence_note': 'Text: UAE Legislation platform (uaelegislation.gov.ae), UAE Cabinet; read from Internet Archive captures. In case of conflict the Arabic text prevails.'},
        'sources': [{'name': 'UAE Legislation, Arabic act page for the Constitution (id 1000), Internet Archive capture ' + CONST_TS,
                     'url': f'https://web.archive.org/web/{CONST_TS}id_/{CONST_URL}', 'retrieved': '2026-10-28', 'requests': 1,
                     'licence': 'Official text of the UAE federal government; no reuse licence stated on the site.',
                     'notes': 'The live site answers this machine with a Cloudflare challenge (403), so only archive.org id_ captures are read.'}],
        'laws': {},
        'acts': [{
            'slug': 'constitution', 'short': 'الدستور',
            'title': 'دستور دولة الإمارات العربية المتحدة',
            'url': 'https://uaelegislation.gov.ae/ar/legislations/1000',
            'first_law': None, 'earlier_laws': [],
            'versions': [{
                'from': '2023-03-29', 'source_url': f'https://web.archive.org/web/{CONST_TS}id_/{CONST_URL}',
                'sha256': hashlib.sha256(raw).hexdigest(), 'units': units, 'credits': {},
                'note': 'Consolidated Arabic text as published by uaelegislation.gov.ae, which states it is current to its last update of 29 March 2023. Earlier wordings are not yet added.'}]}],
        'applies': [],
        'decisions': [
            'Interim build: the Constitution is one "oldest version available" version (first_law null), dated 2023-03-29, the date the publisher gives for its last update, and credited to the publisher.',
            'Arabic is the authoritative text and is what is built; the English version on the same site is a reference only.',
            'Part and chapter headings are not yet kept as units; the preamble (loaded by the site via ajax) is not yet included.'],
        'ai_use': ['none: no model wrote, summarised or corrected any legal text; parsing is rule-based (parse.py).'],
    }
    out = HERE / 'corpus.json'
    tmp = out.with_suffix('.json.tmp')
    tmp.write_text(json.dumps(corpus, ensure_ascii=False, indent=1), 'utf-8', newline='\n')
    os.replace(tmp, out)
    print(len(units), 'articles')


if __name__ == '__main__':
    main()
