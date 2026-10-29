"""Reads Portuguese consolidated legislation (Legislação Consolidada) from the Diário da República (diariodarepublica.pt),
through the same JSON calls its web application makes, with a file cache so every rebuild reads the same bytes.

The site is an OutSystems application. Each screen loads its data with a POST to /dr/screenservices/<module>/<screen>/
<action>, sending the screen's variables as JSON plus a version token of the module and of the action. We send the
screen's own default variables (templates/*.json, captured from the site's own requests) with the act and the day
filled in, the anonymous CSRF header the site's script sends for visitors who are not logged in, and nothing else.
Three calls are used:

- DataActionGetDiplomaFragByIdAndApplicationSetting: the act's record (its id in the legislation database, title).
- DataActionGetConsolidacaoByDiplomaFrag: the act's amendment timeline, every amending act with the provisions it
  added, changed or repealed and the day each change took effect.
- DataActionGetData: the whole consolidated text in force on a given day, provision by provision, each with the
  version id and in-force day of its wording.
"""
from __future__ import annotations

import concurrent.futures as cf
import gzip
import hashlib
import json
import re
import subprocess
import threading
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
CACHE = HERE / '.cache'
SITE = 'https://diariodarepublica.pt'
UA = 'lexifina-watch/1.0 (+https://lexifina.com/watch; corpus@lexifina.com)'
CSRF = 'T6C+9iB49TLra4jEsMeSckDMNhQ='   # OutSystems' AnonymousCSRFToken, as the site's own script sends it
PAUSE = 0.34        # seconds between the starts of two requests; at most WORKERS at a time
WORKERS = 3

ACTIONS = {
    'frag': ('LegislacaoConsolidada/LegCons_Detalhe/DataActionGetDiplomaFragByIdAndApplicationSetting',
             'LegislacaoConsolidada.LegCons_Detalhe', 'LegCons_Detalhe'),
    'data': ('LegislacaoConsolidada/LegCons_Detalhe/DataActionGetData', 'LegislacaoConsolidada.LegCons_Detalhe',
             'LegCons_Detalhe'),
    'timeline': ('LegislacaoConsolidada/AlteracoesTimelineByDiplomaLegisId/DataActionGetConsolidacaoByDiplomaFrag',
                 'LegislacaoConsolidada.LegCons_Detalhe', 'AlteracoesTimelineByDiplomaLegisId'),
}
TEMPLATE = {'frag': 'DataActionGetDiplomaFragByIdAndApplicationSetting', 'data': 'DataActionGetData',
            'timeline': 'DataActionGetConsolidacaoByDiplomaFrag'}

REQUESTS: list[dict] = []   # every call the build read, for REPRODUCE.md
_lock = threading.Lock()
_last = [0.0]
_versions: dict[str, str] = {}


def _http(url: str, body: bytes | None = None, headers: dict | None = None) -> bytes:
    """One request through curl (Python's TLS rejects some chains on this machine), at most WORKERS at a time and one
    started every PAUSE seconds; every request is logged to .cache/requests.jsonl."""
    with _lock:
        wait = _last[0] + PAUSE - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        _last[0] = time.monotonic()
    args = ['curl', '-sS', '-f', '--compressed', '--max-time', '180', '-A', UA, url]
    for k, v in (headers or {}).items():
        args += ['-H', f'{k}: {v}']
    if body is not None:
        args += ['--data-binary', '@-']
    out = subprocess.run(args, input=body, capture_output=True)
    CACHE.mkdir(parents=True, exist_ok=True)
    with _lock, open(CACHE / 'requests.jsonl', 'a', encoding='utf-8') as f:
        f.write(json.dumps({'t': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), 'url': url,
                            'body_sha256': hashlib.sha256(body).hexdigest() if body else None,
                            'status': out.returncode, 'bytes': len(out.stdout)}) + '\n')
    if out.returncode:
        raise RuntimeError(f'curl {url}: {out.stderr.decode(errors="replace")}')
    return out.stdout


def versions() -> dict[str, str]:
    """The module's version token and each action's API version, read from the site's own manifest and scripts (they
    change when the site is redeployed; the server answers a stale token with hasModuleVersionChanged)."""
    with _lock:
        if _versions:
            return _versions
    info = json.loads(_http(f'{SITE}/dr/moduleservices/moduleinfo'))
    found = {'module': info['manifest']['versionToken']}
    scripts = info['manifest']['urlVersions']
    osjs = _http(f'{SITE}/dr/scripts/OutSystems.js{scripts.get("/dr/scripts/OutSystems.js", "")}').decode('utf-8', 'replace')
    m = re.search(r'AnonymousCSRFToken="([^"]+)"', osjs)
    if not m or m.group(1) != CSRF:
        raise SystemExit(f'the site\'s anonymous CSRF token changed ({m and m.group(1)}); update CSRF in source.py')
    for screen in sorted({a[2] for a in ACTIONS.values()}):
        path = f'/dr/scripts/dr.LegislacaoConsolidada.{screen}.mvc.js'
        js = _http(f'{SITE}{path}{scripts[path]}').decode('utf-8', 'replace')
        for m in re.finditer(r'"screenservices/dr/([A-Za-z0-9_/]+)", "([^"]+)"', js):
            found[m.group(1)] = m.group(2)
    with _lock:
        _versions.update(found)
    return _versions


def cache_key(kind: str, params: dict) -> str:
    return kind + '-' + hashlib.sha256(json.dumps([kind, params], sort_keys=True).encode()).hexdigest()[:24]


def call(kind: str, params: dict, offline: bool = False) -> dict:
    """One screen-service call, from the cache when it has been made before. params fill the screen variables."""
    key = cache_key(kind, params)
    path = CACHE / f'{key}.json.gz'
    with _lock:
        REQUESTS.append({'kind': kind, 'params': params, 'file': path.name})
    if path.exists():
        return json.loads(gzip.decompress(path.read_bytes()))
    if offline:
        raise SystemExit(f'not cached: {kind} {params}')
    action, view, _ = ACTIONS[kind]
    body = json.loads((HERE / 'templates' / f'{TEMPLATE[kind]}.json').read_text(encoding='utf-8'))
    body['screenData']['variables'].update(params)
    ver = versions()
    body['versionInfo'] = {'moduleVersion': ver['module'], 'apiVersion': ver[action]}
    body['viewName'] = view
    data = json.dumps(body, ensure_ascii=False, sort_keys=True).encode('utf-8')
    for attempt in range(5):
        try:
            raw = _http(f'{SITE}/dr/screenservices/dr/{action}', data,
                        {'Content-Type': 'application/json; charset=UTF-8', 'Accept': 'application/json',
                         'X-CSRFToken': CSRF})
            res = json.loads(raw.decode('utf-8'))
            if 'exception' in res:
                raise RuntimeError(f'{kind} {params}: {res["exception"]}')
            vi = res.get('versionInfo') or {}
            if vi.get('hasModuleVersionChanged') or vi.get('hasApiVersionChanged'):
                raise RuntimeError(f'{kind}: the site was redeployed (stale version token); rerun to refresh')
            CACHE.mkdir(parents=True, exist_ok=True)
            (CACHE / '.gitignore').write_text('*\n')
            # The response bytes as received, compressed with a fixed mtime so the cache file is reproducible.
            path.write_bytes(gzip.compress(raw, mtime=0))
            return res
        except Exception:
            if attempt == 4:
                raise
            time.sleep(5 * (attempt + 1))
    raise AssertionError


def call_all(jobs: list[tuple[str, dict]], offline: bool) -> list[dict]:
    with cf.ThreadPoolExecutor(WORKERS) as ex:
        return list(ex.map(lambda j: call(j[0], j[1], offline), jobs))


# ---------------------------------------------------------------- the three calls for one act

def act_params(act: dict) -> dict:
    y = act['key'].split('-')[0]
    return {'DiplomaFragId': act['frag'], 'Tipo': act['tipo'], 'Key': act['key'], 'Ano': int(y)}


def record(act: dict, offline: bool) -> dict:
    res = call('frag', {**act_params(act), 'DiplomaLegisId': '0', 'DataSelecionada': '1900-01-01',
                        'DataAux': '1900-01-01'}, offline)
    return res['data']['ConsolidadaConteudoDetalhe']


def timeline(act: dict, legis: str, offline: bool) -> list[dict]:
    res = call('timeline', {'DiplomaFragId': act['frag'], 'DiplomaLegisId': legis, 'Data': '1900-01-01',
                            'DataAux': '1900-01-01'}, offline)
    return res['data']['ModificacoesList']['List']


def text_on(act: dict, legis: str, day: str, offline: bool) -> dict:
    return call('data', {**act_params(act), 'DiplomaLegisId': legis, 'DataSelecionada': day, 'DataAux': day}, offline)


def texts_on(act: dict, legis: str, days: list[str], offline: bool) -> dict[str, dict]:
    jobs = [('data', {**act_params(act), 'DiplomaLegisId': legis, 'DataSelecionada': d, 'DataAux': d}) for d in days]
    return dict(zip(days, call_all(jobs, offline)))
