"""Downloads the official Surinamese sources into .cache/ (gitlaw-SR).

    python -X utf8 scripts/suriname-law/fetch.py

Every request goes through curl (Python TLS fails on this machine), at most one per second per host, with the
Lexifina User-Agent. Files are cached under .cache/<sha256(url)>, so a rerun only fetches what is missing, and every
network request is logged to .cache/requests.jsonl. DNA act pages (dna.sr/wetgeving/...) each hold one PDF under
/media/; the PDF link is read from the cached page and fetched too.
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import urljoin, urlparse

HERE = Path(__file__).resolve().parent
CACHE = HERE / '.cache'
UA = 'lexifina-watch/1.0 (+https://lexifina.com/watch; corpus@lexifina.com)'
DNA = 'https://www.dna.sr/wetgeving/surinaamse-wetten/'

# Index pages of the DNA collection.
INDEXES = [
    DNA + 'geldende-teksten-t-m-2005/',
    DNA + 'wetten-na-2005/',
    DNA + 'wijzigingen-na-2005/',
]

# DNA act pages whose PDF we read (each page links exactly one PDF).
ACT_PAGES = [
    # Grondwet
    DNA + 'geldende-teksten-t-m-2005/grondwet-van-de-republiek-suriname/',
    DNA + 'wijzigingen-na-2005/wet-wijz-grondwet/',
    DNA + 'geldende-teksten-t-m-2005/wet-algemene-bepalingen/',
    # Wetboek van Strafrecht
    DNA + 'geldende-teksten-t-m-2005/wetboek-van-strafrecht-1910-1/',
    DNA + 'wijzigingen-na-2005/wetboek-van-strafrecht/',
    DNA + 'wijzigingen-na-2005/wetboek-van-strafrecht-17-april-2009/',
    DNA + 'wijzigingen-na-2005/wetboek-van-strafrecht-ivm-herziening-zedenmisdrijven/',
    DNA + 'wijzigingen-na-2005/wetboek-strafrecht-vuurwapenwet-en-wet-mot/',
    DNA + 'wijzigingen-na-2005/wijz-wetboek-van-strafrecht-16-september-2014/',
    DNA + 'wijzigingen-na-2005/wet-wijz-wetboek-van-strafrecht-30-maart-2015/',
    DNA + 'wijzigingen-na-2005/wet-wijz-wetboek-van-strafrecht-18-februari-2020/',
    DNA + 'wijzigingen-na-2005/wet-wijz-wetboek-v-strafrecht-wet-ter-voorkoming-en-bestrijding-money-laundering-en-terrorismefin-wet-strafbaarstelling-money-laundering/',
    DNA + 'wijzigingen-na-2005/wet-strafbaarstelling-belaging/',
    # Burgerlijk Wetboek
    DNA + 'geldende-teksten-t-m-2005/burgerlijk-wetboek/',
    DNA + 'geldende-teksten-t-m-2005/burgerlijk-wetboek-1859/',
    DNA + 'wetten-na-2005/nieuw-burgerlijk-wetboek/',
    DNA + 'wijzigingen-na-2005/wet-wijz-surinaams-burgerlijk-wetboek/',
    DNA + 'wijzigingen-na-2005/wijz-surinaams-burgerlijk-wetboek-zoals-laatstelijk-gewijz-bij-s-b-2016-no-67-wet-van-16-maart-2022/',
    # Kiesregeling amendments listed by DNA (to see whether any came after S.B. 2025 no. 16)
    DNA + 'wijzigingen-na-2005/wet-wijz-kiesregeling-2025/',
    DNA + 'wijzigingen-na-2005/wet-wijz-kiesregeling-2024/',
    DNA + 'wijzigingen-na-2005/wijz-kiesregeling-s-b-1987-no-62-zoals-laatstelijk-gewijzigd-bij-s-b-2024-no-59/',
]

# Direct files.
FILES = [
    # S.B. 2025 no. 15: Resolutie of 6 Feb 2025 placing the current Grondwet text (after S.B. 2023 no. 157).
    'https://sris.sr/wp-content/uploads/2025/04/RESOLUTIE-van-6-februari-2025-no.14.22724-houdende-plaatsing-staatsblad-republiek-suriname-thans-geldende-tekst-grondwet-rep-sur-S.B.-2025-no.-15.pdf',
    # gov.sr copy of the 1992 consolidation (cross-check only).
    'https://gov.sr/wp-content/uploads/2023/09/grondwet_suriname.pdf',
    # sris.sr copy of the 1992 consolidation with the 1992 Memorie van Toelichting.
    'https://www.sris.sr/wp-content/uploads/2020/06/Grondwet-met-Mvt.pdf',
]

# Second round (2026-10-29), found through the sris.sr WordPress media listing
# (https://sris.sr/wp-json/wp/v2/media?per_page=100&page=1..18).
SRIS = 'https://www.sris.sr/wp-content/uploads/'
FILES += [SRIS + p for p in [
    # Nieuw Burgerlijk Wetboek and its companion acts (2024), in force by Resolutie S.B. 2025 no. 14.
    '2025/01/S.B-2024-no.-164-Burgerlijk-Wetboek.pdf',
    '2025/02/Resolutie-houdende-vaststelling-van-de-inwerkingtreding-van-het-Burgerlijk-Wetboek-S.B.-2025-no.-14.pdf',
    '2025/01/S.B.-2024-no.-165-Overgangswet-aanpassingswetgeving-nieuw-Burgerlijk-Wetboek.pdf',
    '2025/01/S.B.-2024-no.-166-Overgangswet-nieuw-Burgerlijk-Wetboek.pdf',
    '2025/01/S.B.-2024-no.-168-Aanpassingswet-nieuw-Burgerlijk-Wetboek.pdf',
    '2025/01/S.B.-2024-no.-170-Wetboek-van-Burgerlijke-Rechtsvordering.pdf',
    # Kiesregeling: current text (S.B. 2025 no. 16) and the amending acts before it.
    '2025/04/RESOLUTIE-van-6-februari-2025-no.-14.228-24-houdende-plaatsing-staatsblad-republiek-suriname-thans-geldende-tekst-kiesregeling-S.B.-2025-no.-16.pdf',
    '2025/04/S.B.-2025-no.-8-Wet-Kiesregeling-wijziging.pdf',
    '2024/06/S.B.-2024-no.-59-wijziging-van-de-Kiesregeling.pdf',
    '2023/10/SB-2023-158-nadere-wijziging-van-de-Kiesregeling.pdf',
    '2019/08/S.B.-2019-no.-55-Wijziging-Kiesregeling.pdf',
    '2020/06/Kiesregeling-bijgewerkt-tm-S.B.-2019-no.-55.pdf',
    # Wetboek van Strafrecht amending acts (sris.sr copies).
    '2017/10/23.S.B._2015_no._44_wet_van_30_mrt_15_wijz._wetboek_van_strafrecht.pdf',
    '2020/03/wet-wijz.-wetboek-van-strafrecht.pdf',
    '2023/09/Wijziging-wetboek-van-strafrecht-en-intrekking-van-de-wet-Strafbaarstelling-money-laundering-S.B.-2023-no.-133.pdf',
    '2023/09/Wet-Hazardspelen-wijz-wetboek-van-strafrecht-wetboek-van-strafvordering-en-wet-casinobelasting-2002-S.B.-2023-no.-135.pdf',
    '2023/09/S.B.-2014-no.-118-nadere-wijziging-Wetboek-van-Strafrecht.pdf',
]]

_last: dict[str, float] = {}


def path_for(url: str) -> Path:
    return CACHE / hashlib.sha256(url.encode('utf-8')).hexdigest()


def get(url: str, offline: bool = False) -> Path | None:
    """The cached file for url, fetching it if missing (unless offline)."""
    p = path_for(url)
    if p.exists():
        return p
    if offline:
        return None
    CACHE.mkdir(exist_ok=True)
    gi = CACHE / '.gitignore'
    if not gi.exists():
        gi.write_text('*\n', encoding='utf-8')
    host = urlparse(url).netloc
    wait = 1.0 - (time.time() - _last.get(host, 0))
    if wait > 0:
        time.sleep(wait)
    tmp = p.with_suffix('.part')
    r = subprocess.run(['curl', '-sS', '-L', '--compressed', '--max-time', '180', '-A', UA, '-o', str(tmp),
                        '-w', '%{http_code}\t%{content_type}\t%{size_download}', url],
                       capture_output=True, text=True)
    _last[host] = time.time()
    code, ctype, size = (r.stdout.split('\t') + ['', '', ''])[:3]
    rec = {'t': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), 'url': url, 'status': code, 'type': ctype,
           'bytes': size, 'sha256_url': p.name}
    with open(CACHE / 'requests.jsonl', 'a', encoding='utf-8') as f:
        f.write(json.dumps(rec) + '\n')
    if r.returncode != 0 or code != '200':
        tmp.unlink(missing_ok=True)
        print(f'FAIL {code} {url} {r.stderr.strip()}', file=sys.stderr)
        return None
    tmp.replace(p)
    print(f'{code} {size:>9} {url}')
    return p


def page_pdfs(page: Path, base: str) -> list[str]:
    s = page.read_text(encoding='utf-8', errors='replace')
    out = []
    for h in re.findall(r'(?:href|src)="(/media/[^"#?]+\.pdf)', s, re.I):
        u = urljoin(base, h)
        if u not in out:
            out.append(u)
    return out


def main():
    for u in INDEXES + FILES:
        get(u)
    for u in ACT_PAGES:
        p = get(u)
        if p:
            for pdf in page_pdfs(p, u):
                get(pdf)


if __name__ == '__main__':
    main()
