"""Downloads Chilean law from BCN LeyChile into scripts/chile-law/.cache/.

    python -X utf8 scripts/chile-law/fetch.py [acts...]      # default: every act in ACTS

LeyChile (Biblioteca del Congreso Nacional) serves its single-page reader from two JSON services, which we read:

  versions list   https://nuevo.leychile.cl/servicios/Consulta/get_versiones?idNorma=N&formato=json&idParte=&idsParte=
                  every dated version of a norm ("vigenteDesde" / "vigenteHasta") and, on each version, the norms
                  that ended it ("Modificatorias", with their own idNorma, number, publication date and the day the
                  change took effect, "inicioVigencia").
  one version     https://nuevo.leychile.cl/servicios/Navegar/get_norma_json?idNorma=N&idVersion=YYYY-MM-DD&...
                  the text of the norm as in force on that day, as a tree of parts ("html"), each paragraph with
                  the source's own amendment notes ("LEY N° 19.611 Art. único Nº1 D.O. 16.06.1999").
  refunded chain  https://nuevo.leychile.cl/servicios/Navegar/get_cadena_refundidos?idNorma=N

Every response is cached under .cache/<sha256 of the URL>, through curl (Python's TLS fails on this machine), one
request per second per host, with the User-Agent below, and logged to .cache/requests.jsonl. Re-running only
fetches what is missing.
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
SERVICE = 'https://nuevo.leychile.cl/servicios'
PAUSE = 2.0   # LeyChile is shared with the helper agent (corpus.d): together at most 1 request per second
_last: dict[str, float] = {}

# Each act is a chain of LeyChile norms: when a code was re-enacted as a "texto refundido", LeyChile starts a new
# norm (idNorma) and ends the old one. The chain is taken from get_cadena_refundidos.
ACTS = {
    'constitucion': [7129, 242302],          # DL 3.464 (1980), then DS 100 (2005, texto refundido)
    'codigo-civil': [172986],                # DFL 1 (2000, texto refundido del Código Civil)
    'ley-19628': [141599],                   # Ley 19.628 sobre protección de la vida privada
    'codigo-penal': [1984],                  # Código Penal (1874)
    'codigo-comercio': [1974],               # Código de Comercio (1865)
    'codigo-trabajo': [207436],              # DFL 1 (2002, texto refundido del Código del Trabajo)
    'codigo-procedimiento-civil': [22740],   # Ley 1.552, Código de Procedimiento Civil (1902)
    'codigo-procesal-penal': [176595],       # Ley 19.696, Código Procesal Penal (2000)
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
    wait = _last.get(host, 0) + PAUSE - time.monotonic()
    if wait > 0:
        time.sleep(wait)
    for attempt in range(4):
        _last[host] = time.monotonic()
        out = subprocess.run(['curl', '-sS', '-L', '--max-redirs', '4', '--compressed', '-A', UA, '-m', '300',
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
        time.sleep(5 * (attempt + 1))
    raise RuntimeError(f'{url}: curl {out.returncode} http {code} {out.stderr.decode(errors="replace")[:200]}')


def versions_url(id_norma: int) -> str:
    return f'{SERVICE}/Consulta/get_versiones?idNorma={id_norma}&formato=json&idParte=&idsParte='


def version_url(id_norma: int, day: str) -> str:
    return (f'{SERVICE}/Navegar/get_norma_json?idNorma={id_norma}&idVersion={day}'
            f'&idLey=&tipoVersion=&cve=&agrupa_partes=1&r=')


def chain_url(id_norma: int) -> str:
    return f'{SERVICE}/Navegar/get_cadena_refundidos?idNorma={id_norma}'


def as_list(x) -> list:
    if x is None:
        return []
    return x if isinstance(x, list) else [x]


def versions(id_norma: int, offline: bool = False) -> list[dict]:
    """The versions of a norm, oldest first."""
    d = json.loads(fetch(versions_url(id_norma), offline))
    vs = as_list(d['Versiones'].get('Version'))
    return sorted(vs, key=lambda v: v['@vigenteDesde'])


def fetch_act(slug: str, offline: bool = False) -> int:
    n = 0
    for id_norma in ACTS[slug]:
        fetch(chain_url(id_norma), offline)
        vs = versions(id_norma, offline)
        for v in vs:
            fetch(version_url(id_norma, v['@vigenteDesde']), offline)
            n += 1
        print(f'{slug}: norm {id_norma}: {len(vs)} versions', flush=True)
    return n


def main(argv: list[str]) -> None:
    for slug in (argv or list(ACTS)):
        fetch_act(slug)


if __name__ == '__main__':
    main(sys.argv[1:])
