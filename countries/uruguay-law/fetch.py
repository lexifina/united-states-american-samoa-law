"""Downloads Uruguayan law into scripts/uruguay-law/.cache/.

    python -X utf8 scripts/uruguay-law/fetch.py [acts...]     # default: every act in ACTS
    python -X utf8 scripts/uruguay-law/fetch.py --url URL     # one URL into the cache

Sources:
  IMPO (Dirección Nacional de Impresiones y Publicaciones Oficiales), https://www.impo.com.uy/bases/...
      ?json=true on a norm gives the consolidated text in force with IMPO's own notes per article
      ("redacción dada por", "agregado por", "TEXTO ORIGINAL"). robots.txt asks for Crawl-Delay: 10, which we keep.
      Responses are ISO-8859-1.
  Parlamento del Uruguay, dated texts of the Constitution, read through Wayback Machine `id_` raw captures because
      parlamento.gub.uy answers 403 to this machine. The capture timestamps are pinned in the URLs below.

Every response is cached under .cache/<sha256 of the URL> through curl (Python's TLS fails on this machine), with
the User-Agent below, at most one request per PAUSE seconds per host, and logged to .cache/requests.jsonl.
Re-running only fetches what is missing.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import urlsplit

HERE = Path(__file__).resolve().parent
CACHE = HERE / '.cache'
UA = 'lexifina-watch/1.0 (+https://lexifina.com/watch; corpus@lexifina.com)'
PAUSE = {'www.impo.com.uy': 10.5}   # IMPO robots.txt: Crawl-Delay: 10
DEFAULT_PAUSE = 1.0
_last: dict[str, float] = {}

IMPO = 'https://www.impo.com.uy/bases'
WB = 'https://web.archive.org/web'
PARL_TMP = 'https://infolegislativa.parlamento.gub.uy/temporales'

# Pinned Wayback captures of the Parlamento's dated Constitution texts.
CONST_PARLAMENTO = {
    '1967': f'{WB}/20250820033544id_/{PARL_TMP}/1aea133e-14fa-43c1-ba4a-26cedb0d8c31.HTML',
    '1997': f'{WB}/20240528053904id_/{PARL_TMP}/44c614eb-203a-407e-b0cd-89780505e3cf.HTML',
}

# The Parlamento's pre-2016 site, one page per dated text (Wayback captures, pinned).
OLD_PARL = 'http://www.parlamento.gub.uy:80/constituciones'
CONST_PARLAMENTO_OLD = {
    'index': f'{WB}/20160328225637id_/{OLD_PARL}/',
    '1989': f'{WB}/20141126013720id_/{OLD_PARL}/Const989.htm',
    '1994': f'{WB}/20141126035426id_/{OLD_PARL}/Const994.htm',
    '1997': f'{WB}/20160402141915id_/http://www.parlamento.gub.uy/constituciones/const997.htm',
    '2004': f'{WB}/20160402133447id_/{OLD_PARL}/const004.htm',
}

def impo(path: str) -> str:
    return f'{IMPO}/{path}?json=true'


# Laws and codes rebuilt from IMPO's notes (impo_history.py): slug -> (IMPO path, the norm's own law, and the
# vigencia article of amending laws whose IMPO notes do not point to one, read by hand from the law).
IMPO_ACTS: dict[str, tuple[str, str, dict[str, str]]] = {
    'ley-18331': ('leyes/18331-2008', '18331', {'18719': '3'}),
    'codigo-penal': ('codigo-penal/9155-1933', '9155', {'15903': '2', '17897': '23'}),
    'codigo-civil': ('codigo-civil/16603-1994', '16603',
                     {'17703': '46', '18387': '255', '19075': '29', '19920': '63', '19670': '2'}),
}


def fetch_impo_act(slug: str) -> int:
    """The norm, then everything its notes point to: original texts, amending articles, vigencia articles."""
    import impo_history
    path, base, vig = IMPO_ACTS[slug]
    main = impo_json(impo(path))
    paths = impo_history.needed_paths(main, base, vig)
    for p in paths:
        fetch(impo(p))
    return len(paths) + 1


ACTS: dict[str, list[str]] = {
    'constitucion': [
        f'{IMPO}/constitucion/1967-1967?json=true',
        f'{IMPO}/disposiciones-transitorias-especiales-constitucion/1967-1967?json=true',
        *CONST_PARLAMENTO.values(),
        *CONST_PARLAMENTO_OLD.values(),
    ],
}


def cache_path(url: str) -> Path:
    return CACHE / hashlib.sha256(url.encode()).hexdigest()


def fetch(url: str, offline: bool = False) -> bytes:
    path = cache_path(url)
    if path.exists():
        return path.read_bytes()
    if offline:
        raise FileNotFoundError(f'not cached: {url}')
    CACHE.mkdir(exist_ok=True)
    gi = CACHE / '.gitignore'
    if not gi.exists():
        gi.write_text('*\n')
    host = urlsplit(url).netloc
    pause = PAUSE.get(host, DEFAULT_PAUSE)
    code, out = '', None
    for attempt in range(4):
        wait = _last.get(host, 0) + pause - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        _last[host] = time.monotonic()
        out = subprocess.run(['curl', '-sS', '-L', '--max-redirs', '5', '--compressed', '-A', UA, '-m', '300',
                              '-w', '\n%{http_code}', url], capture_output=True)
        body, _, code = out.stdout.rpartition(b'\n')
        code = code.decode().strip()
        with open(CACHE / 'requests.jsonl', 'a', encoding='utf-8') as log:
            log.write(json.dumps({'url': url, 'status': code, 'bytes': len(body),
                                  'at': dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
                                  'sha256': hashlib.sha256(body).hexdigest()}) + '\n')
        if out.returncode == 0 and code == '200' and body.strip():
            tmp = path.with_suffix('.tmp')
            tmp.write_bytes(body)
            tmp.replace(path)
            return body
        if code == '404':
            break
        time.sleep(5 * (attempt + 1))
    raise RuntimeError(f'{url}: curl {out.returncode if out else "?"} http {code} '
                       f'{out.stderr.decode(errors="replace")[:200] if out else ""}')


def impo_json(url: str, offline: bool = False) -> dict:
    return json.loads(fetch(url, offline).decode('latin-1'), strict=False)


def main(argv: list[str]) -> None:
    if argv[:1] == ['--url']:
        for u in argv[1:]:
            print(len(fetch(u)), u, flush=True)
        return
    for slug in (argv or [*ACTS, *IMPO_ACTS]):
        if slug in IMPO_ACTS:
            print(slug, fetch_impo_act(slug), 'IMPO responses', flush=True)
            continue
        for u in ACTS[slug]:
            print(slug, len(fetch(u)), u, flush=True)


if __name__ == '__main__':
    main(sys.argv[1:])
