"""Phase 2 of Chile (gitlaw-CL-codes): fetches the Código Penal, the Código de Comercio and the Código del Trabajo
from LeyChile through the main fetch.py (same cache, same User-Agent, same request log), 1 s between requests.

    python -X utf8 scripts/chile-law/codes/fetch_codes.py [slug...]

The idNorma chains below were verified on 2026-10-28 against LeyChile's own get_cadena_refundidos and get_versiones
(see codes/PROGRESS.md). Besides every dated version, it fetches the unversioned current text (idVersion empty),
which codes/verify_codes.py compares with the corpus.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import fetch  # noqa: E402

fetch.PAUSE = 1.0   # one request per second per host (the main agent has finished fetching)

CHAINS = {
    'codigo-penal': [1984],              # Código Penal (1874), one norm, versions from 1875-03-01
    'codigo-comercio': [1974],           # Código de Comercio (1865), one norm
    'codigo-trabajo': [3471, 207436],    # DFL 1 1994, then DFL 1 2003 (textos refundidos of the Código del Trabajo)
    'codigo-procedimiento-civil': [22740],   # Ley 1.552 (1902), one norm
    'codigo-procesal-penal': [176595],       # Ley 19.696 (2000), one norm
    # Part 60-more (verified 2026-10-28 the same way):
    'codigo-tributario': [6374],             # DL 830 (1974), Código Tributario
    'codigo-sanitario': [5595],              # DFL 725 (1968), Código Sanitario
    'codigo-aguas': [5605],                  # DFL 1.122 (1981), Código de Aguas
    'ley-18046': [29473],                    # Ley 18.046 sobre sociedades anónimas (1981)
    'ley-19496': [61438, 1160403],           # Ley 19.496 (1997), then DFL 3 (2021, texto refundido)
    # Part 70-batch3 (verified 2026-10-28 the same way):
    'codigo-organico-tribunales': [25563],   # Ley 7.421 (1943), Código Orgánico de Tribunales
    'codigo-mineria': [29668],               # Ley 18.248 (1983), Código de Minería
    'codigo-aeronautico': [30287],           # Ley 18.916 (1990), Código Aeronáutico
    'codigo-justicia-militar': [18914],      # Decreto 2.226 (1944); DL 806 of 1925 (6363) has one version only
    'ley-20393': [1008668],                  # Ley 20.393 (2009), responsabilidad penal de las personas jurídicas
    'ley-19880': [210676],                   # Ley 19.880 (2003), procedimiento administrativo
    'ley-18010': [29438],                    # Ley 18.010 (1981), operaciones de crédito
    # Part 80-batch4 (verified 2026-10-28 the same way; chains from get_cadena_refundidos):
    'ley-18695': [30077, 14962, 150973, 197482, 251693],  # Ley 18.695 (1988); textos refundidos Decreto 662 (1992),
                                                          # DFL 2 (2000), DFL 1 (2002), DFL 1 (2006)
    'ley-18575': [29967, 191865],            # Ley 18.575 (1986); DFL 1/19.653 (2001, texto refundido)
    'ley-20000': [235507],                   # Ley 20.000 (2005), drogas
    'ley-17336': [28933],                    # Ley 17.336 (1970), propiedad intelectual
    'ley-19039': [30406, 250708, 1179684],   # Ley 19.039 (1991); DFL 3 (2006) and DFL 4 (2022) textos refundidos
    'ley-18045': [29472],                    # Ley 18.045 (1981), mercado de valores
    'ley-20720': [1058072],                  # Ley 20.720 (2014), insolvencia
    'dfl-1-2005-salud': [249177],            # DFL 1 de 2005 (Salud), texto refundido of DL 2.763, Leyes 18.469, 18.933
    'ley-16744': [28650],                    # Ley 16.744 (1968), accidentes del trabajo
    # Part 90-batch5 (verified 2026-10-28 the same way; 19.947 and 14.908 located with get_norma_json?idLey=):
    'ley-19300': [30667],                    # Ley 19.300 (1994), bases generales del medio ambiente
    'ley-18834': [30210, 236392],            # Ley 18.834 (1989); DFL 29 (2005, texto refundido), Estatuto Administrativo
    'dl-3500': [7147],                       # DL 3.500 (1980), sistema de pensiones
    'ley-21595': [1195119],                  # Ley 21.595 (2023), delitos económicos
    'ley-19913': [219119],                   # Ley 19.913 (2003), Unidad de Análisis Financiero
    'ley-18290': [29708, 1007469],           # Ley 18.290 (1984); DFL 1 (2009, texto refundido), Ley de Tránsito
    'ley-19968': [229557],                   # Ley 19.968 (2004), Tribunales de Familia
    'ley-20084': [244803],                   # Ley 20.084 (2005), responsabilidad penal adolescente
    'ley-19947': [225128],                   # Ley 19.947 (2004), Matrimonio Civil
    'ley-14908': [27977, 172986],            # Ley 14.908 (1962); then DFL 1 (2000) art. 7, which fixes its text
    # Part 95-batch6 (ids from get_norma_json?idLey=<number> -> metadatos.id_norma, then verified the same way):
    'ley-19537': [81505],                    # Ley 19.537 (1997), copropiedad inmobiliaria
    'ley-18101': [29526],                    # Ley 18.101 (1982), arrendamiento de predios urbanos
    'ley-20285': [276363],                   # Ley 20.285 (2008), acceso a la información pública
    'ley-18700': [30082, 1108229],           # Ley 18.700 (1988); DFL 2 (2017, texto refundido), votaciones populares
    'ley-20584': [1039348],                  # Ley 20.584 (2012), derechos y deberes de los pacientes
    'ley-19733': [186049],                   # Ley 19.733 (2001), libertades de opinión e información y periodismo
    'ley-20529': [1028635],                  # Ley 20.529 (2011), aseguramiento de la calidad de la educación
    'ley-21091': [1118991],                  # Ley 21.091 (2018), educación superior
    # Part 97-batch7 (gitlaw-CL-2, 2026-10-29; ids from get_norma_json?idLey=<number> -> metadatos.id_norma, DL ids
    # from get_cadena_refundidos; chains from get_cadena_refundidos, versions from get_versiones):
    'dl-824': [6368],                        # DL 824 (1974), Ley sobre Impuesto a la Renta
    'dl-825': [6369],                        # DL 825 (1974), Ley sobre Impuesto a las Ventas y Servicios
    'ley-21325': [1158549],                  # Ley 21.325 (2021), migración y extranjería
    'ley-19886': [213004],                   # Ley 19.886 (2003), compras públicas
    'ley-18840': [30216],                    # Ley 18.840 (1989), orgánica constitucional del Banco Central
    'ley-20066': [242648],                   # Ley 20.066 (2005), violencia intrafamiliar
    'ley-18314': [29731],                    # Ley 18.314 (1984), conductas terroristas
    'ley-17798': [29291, 13031],             # Ley 17.798 (1972), then Decreto 400 (1978, texto refundido), armas
    'ley-20609': [1042092],                  # Ley 20.609 (2012), medidas contra la discriminación
    'ley-19799': [196640],                   # Ley 19.799 (2002), documentos y firma electrónica
    # Part 98-batch8 (gitlaw-CL-2, 2026-10-29, found and verified the same way):
    'ley-20370': [1006043, 1014974],         # Ley 20.370 (2009), then DFL 2 (2010, texto refundido), Ley General de
                                             # Educación; LeyChile's chain starts with Ley 18.962 (LOCE), not used
    'ley-20730': [1060115],                  # Ley 20.730 (2014), lobby
    'ley-21430': [1173643],                  # Ley 21.430 (2022), garantías de la niñez
    'ley-19253': [30620],                    # Ley 19.253 (1993), indígenas
    'ley-20422': [1010903],                  # Ley 20.422 (2010), discapacidad
    'ley-10336': [26356, 18995],             # Ley 10.336 (1952), then Decreto 2.421 (1964, texto refundido), Contraloría
    'ley-17997': [29427, 1016103],           # Ley 17.997 (1981), then DFL 5 (2010, texto refundido), Tribunal
                                             # Constitucional
    'ley-19640': [145437],                   # Ley 19.640 (1999), Ministerio Público
    'ley-18918': [30289],                    # Ley 18.918 (1990), Congreso Nacional
    'ley-21442': [1174663],                  # Ley 21.442 (2022), copropiedad inmobiliaria
    'ley-19418': [30785, 70040],             # Ley 19.418 (1995), then Decreto 58 (1997, texto refundido), juntas de
                                             # vecinos
    'ley-3918': [24349],                     # Ley 3.918 (1923), sociedades de responsabilidad limitada
    'ley-19857': [207588],                   # Ley 19.857 (2003), empresas individuales de responsabilidad limitada
    'ley-21521': [1187323],                  # Ley 21.521 (2023), Fintec
    'ley-20500': [1023143],                  # Ley 20.500 (2011), asociaciones y participación ciudadana
    # Part 99-batch9 (gitlaw-CL-2, 2026-10-29): laws whose text DFL 1 of 2000 (172986) fixes in one of its articles,
    # read as that article only (parse_codes.ACT_NORM_PART), like Ley 14.908 above:
    'ley-4808': [24928, 172986],             # Ley 4.808 (1930), Registro Civil; DFL 1 of 2000 art. 3
    'ley-17344': [28940, 172986],            # Ley 17.344 (1970), cambio de nombres y apellidos; art. 4
    'ley-16618': [28581, 172986],            # Ley 16.618 (1967), Ley de Menores; art. 6
    'ley-16271': [28367, 172986],            # Ley 16.271 (1965), impuesto a las herencias; art. 8
    # Part 96-batch10 (gitlaw-CL-3, 2026-10-29; Ley ids from get_norma_json?idLey=<number> -> metadatos.id_norma, the
    # others from get_cadena_refundidos; chains from get_cadena_refundidos, versions from get_versiones):
    'dfl-458': [13560],                      # DFL 458 (1976), Ley General de Urbanismo y Construcciones
    'ley-general-bancos': [5205, 83135],     # DFL 252 (1960), then DFL 3 (1997, texto refundido), Ley General de
                                             # Bancos; DL 1.097 (6484, also in LeyChile's chain) is a different law
    'dl-211': [5872, 74808, 236106],         # DL 211 (1973), then Decreto 511 (1980) and DFL 1 (2005) textos
                                             # refundidos, libre competencia
    'ley-18892': [30265, 13315],             # Ley 18.892 (1989), then Decreto 430 (1992, texto refundido), pesca
    'ley-18168': [29591],                    # Ley 18.168 (1982), telecomunicaciones
    'ley-19175': [30542, 243771],            # Ley 19.175 (1992), then DFL 1 (2005, texto refundido), gobierno regional
    'ley-19070': [30437, 60439],             # Ley 19.070 (1991), then DFL 1 (1997, texto refundido), Estatuto Docente
    'ley-20600': [1041361],                  # Ley 20.600 (2012), tribunales ambientales
    'ley-18287': [29705],                    # Ley 18.287 (1984), procedimiento ante los juzgados de policía local
    'ley-15231': [28104, 12193],             # Ley 15.231 (1963), then Decreto 307 (1978, texto refundido), juzgados
                                             # de policía local; Leyes 6.827 and 15.123 (one version each) not used
    'ley-19728': [184979],                   # Ley 19.728 (2001), seguro de desempleo
    'ley-20880': [1086062],                  # Ley 20.880 (2016), probidad
    'ley-19983': [233421],                   # Ley 19.983 (2004), factura
    'ley-18603': [29994, 1107684],           # Ley 18.603 (1987), then DFL 4 (2017, texto refundido), partidos políticos
    'ley-17322': [28919],                    # Ley 17.322 (1970), cobranza judicial de cotizaciones
    'ley-18097': [29522],                    # Ley 18.097 (1982), orgánica constitucional sobre concesiones mineras
    'ley-19378': [30745],                    # Ley 19.378 (1995), atención primaria de salud municipal
    'ley-21040': [1111237],                  # Ley 21.040 (2017), sistema de educación pública
    'ley-20712': [1057895],                  # Ley 20.712 (2014), administración de fondos de terceros
    'ley-20659': [1048718],                  # Ley 20.659 (2013), régimen simplificado de sociedades
    # Part 99b-batch11 (gitlaw-CL-4, 2026-10-29; Ley ids from get_norma_json?idLey=<number> -> metadatos.id_norma,
    # DFL/DL ids from get_cadena_refundidos; chains from get_cadena_refundidos, versions from get_versiones):
    'ley-20830': [1075210],                  # Ley 20.830 (2015), acuerdo de unión civil
    'ley-21120': [1126480],                  # Ley 21.120 (2018), identidad de género
    'ley-19620': [140084],                   # Ley 19.620 (1999), adopción de menores
    'ley-18216': [29636],                    # Ley 18.216 (1983), penas sustitutivas
    'ley-12927': [27292, 16080],             # Ley 12.927 (1958), then Decreto 890 (1975, texto refundido), seguridad
                                             # del Estado
    'ley-21000': [1100517],                  # Ley 21.000 (2017), Comisión para el Mercado Financiero
    'ley-20920': [1090894],                  # Ley 20.920 (2016), residuos y responsabilidad extendida del productor
    'ley-21455': [1177286],                  # Ley 21.455 (2022), marco de cambio climático
    'ley-17288': [28892],                    # Ley 17.288 (1970), monumentos nacionales
    'ley-18883': [30256],                    # Ley 18.883 (1989), estatuto administrativo de funcionarios municipales
    'ley-18415': [29824],                    # Ley 18.415 (1985), estados de excepción
    'ley-21459': [1177743],                  # Ley 21.459 (2022), delitos informáticos
    'ley-20416': [1010668],                  # Ley 20.416 (2010), empresas de menor tamaño
    'ley-19966': [229834],                   # Ley 19.966 (2004), garantías en salud
    'ley-18838': [30214],                    # Ley 18.838 (1989), Consejo Nacional de Televisión
    'ley-20255': [269892],                   # Ley 20.255 (2008), reforma previsional
    'ley-19995': [234426],                   # Ley 19.995 (2005), casinos de juego
    'ley-20283': [274894],                   # Ley 20.283 (2008), bosque nativo
    'ley-19884': [213283, 1107658],          # Ley 19.884 (2003), then DFL 3 (2017, texto refundido), gasto electoral
    'ley-18460': [29864],                    # Ley 18.460 (1985), Tribunal Calificador de Elecciones
    'ley-20551': [1032158],                  # Ley 20.551 (2011), cierre de faenas mineras
    'ley-18961': [30329],                    # Ley 18.961 (1990), orgánica constitucional de Carabineros
    'ley-21389': [1168463],                  # Ley 21.389 (2021), registro nacional de deudores de pensiones de alimentos
    'ley-21057': [1113932],                  # Ley 21.057 (2018), entrevistas grabadas en video
    'ley-19970': [231105],                   # Ley 19.970 (2004), registros de ADN
    'ley-20357': [1004297],                  # Ley 20.357 (2009), lesa humanidad, genocidio y crímenes de guerra
    'ley-21600': [1195666],                  # Ley 21.600 (2023), Servicio de Biodiversidad y Áreas Protegidas
    'ley-general-servicios-electricos': [3410, 258171],  # DFL 1 (1982), then DFL 4 (2007, texto refundido)
    'dl-1263': [6536],                       # DL 1.263 (1975), administración financiera del Estado
    'dl-2186': [6848],                       # DL 2.186 (1978), procedimiento de expropiaciones
}
EXTRA = [30011]                          # Ley 18.620 (Código del Trabajo of 1987): metadata only, single version


def current_url(id_norma: int) -> str:
    return (f'{fetch.SERVICE}/Navegar/get_norma_json?idNorma={id_norma}&idVersion=&idLey=&tipoVersion=&cve='
            '&agrupa_partes=1&r=')


def ley_url(number: int) -> str:
    """LeyChile's reader for a Ley by its number; metadatos.id_norma names the norm."""
    return (f'{fetch.SERVICE}/Navegar/get_norma_json?idNorma=&idVersion=&idLey={number}&tipoVersion=&cve='
            '&agrupa_partes=1&r=')


# Coordinator SPEED RULE (2026-10-28 21:55Z): direct official sources up to 3 requests a second, 3 in parallel; on
# 429 or 503, halve the rate and wait 60 s. fetch.fetch is single-threaded, so the parallel path below keeps fetch.py's
# cache (sha256 of the URL), User-Agent, curl call and request log, and adds one shared limiter.
_lock = threading.Lock()
_interval = [1 / 3]
_next = [0.0]


def _slot() -> None:
    with _lock:
        now = time.monotonic()
        at = max(now, _next[0])
        _next[0] = at + _interval[0]
    if at > now:
        time.sleep(at - now)


def fast_fetch(url: str) -> bytes:
    path = fetch.cache_path(url)
    if path.exists():
        return path.read_bytes()
    fetch.CACHE.mkdir(exist_ok=True)
    for attempt in range(5):
        _slot()
        out = subprocess.run(['curl', '-sS', '-L', '--max-redirs', '4', '--compressed', '-A', fetch.UA, '-m', '300',
                              '-w', '\n%{http_code}', url], capture_output=True)
        body, _, code = out.stdout.rpartition(b'\n')
        code = code.decode().strip()
        with _lock, open(fetch.CACHE / 'requests.jsonl', 'a', encoding='utf-8') as log:
            log.write(json.dumps({'url': url, 'status': code, 'bytes': len(body),
                                  'at': dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
                                  'sha256': hashlib.sha256(body).hexdigest()}) + '\n')
        if out.returncode == 0 and code == '200' and body.strip():
            tmp = path.with_name(path.name + f'.{threading.get_ident()}.tmp')
            tmp.write_bytes(body)
            tmp.replace(path)
            return body
        if code in ('429', '503'):
            with _lock:
                _interval[0] *= 2
                _next[0] = time.monotonic() + 60
            print(f'http {code}: rate halved to {1 / _interval[0]:.2f}/s, waiting 60 s', flush=True)
        else:
            time.sleep(5 * (attempt + 1))
    raise RuntimeError(f'{url}: curl {out.returncode} http {code} {out.stderr.decode(errors="replace")[:200]}')


def fetch_parallel(slugs: list[str], workers: int = 3) -> None:
    """Every version of every norm of the acts, plus the current page, 3 at a time at up to 3 requests a second."""
    urls = []
    for s in slugs:
        for idn in CHAINS[s]:
            fast_fetch(fetch.chain_url(idn))
            fast_fetch(fetch.versions_url(idn))
            urls += [fetch.version_url(idn, v['@vigenteDesde']) for v in fetch.versions(idn, offline=True)]
        urls.append(current_url(CHAINS[s][-1]))
    todo = [u for u in dict.fromkeys(urls) if not fetch.cache_path(u).exists()]
    print(f'{len(urls)} urls, {len(todo)} to fetch', flush=True)
    with ThreadPoolExecutor(workers) as ex:
        for i, _ in enumerate(ex.map(fast_fetch, todo), 1):
            if i % 50 == 0:
                print(f'{i}/{len(todo)}', flush=True)


def host_fetch(url: str) -> bytes:
    """SPEED RULE 2 (user, 2026-10-29): gitlaw_common/wayback.host_get, one adaptive rate per host shared by every
    process on the machine (backs off on 429/503/timeouts). Same cache file (sha256 of the URL) as fetch.py."""
    sys.path.insert(0, str(HERE.parent.parent / 'gitlaw_common'))
    import wayback
    body = wayback.host_get(url, fetch.CACHE)
    if not body or not body.strip():
        raise RuntimeError(f'{url}: no body')
    return body


def main(argv: list[str]) -> None:
    global fast_fetch
    fetch.ACTS.update(CHAINS)
    workers = 3
    if argv and argv[0] == '--host':
        # `--host --fast slug...`, `--host --ley N...`, `--host --norma id...`: host_get from a pool of 12 threads.
        fast_fetch, workers, argv = host_fetch, 12, argv[1:]
    if argv and argv[0] == '--fast':
        fetch_parallel(argv[1:] or list(CHAINS), workers)
        return
    if argv and argv[0] == '--norma':
        # What LeyChile says each idNorma is (current page metadatos), for norms without a Ley number (DFL, DL).
        def one(n):
            d = json.loads(fast_fetch(current_url(int(n))))
            m = d.get('metadatos') or {}
            return f'{n} {m.get("tipo_norma") or m.get("tipo")} {m.get("numero_norma") or m.get("numero")} ' \
                   f'{(m.get("titulo_norma") or m.get("titulo") or "")[:110]}'
        with ThreadPoolExecutor(workers) as ex:
            for line in ex.map(one, argv[1:]):
                print(line, flush=True)
        return
    if argv and argv[0] == '--ley':
        def ley(n):
            try:
                d = json.loads(fast_fetch(ley_url(int(n))))
            except (RuntimeError, ValueError) as e:
                return f'{n} - {e}'[:200]
            m = d.get('metadatos') or {}
            return f'{n} {m.get("id_norma")} {(m.get("titulo_norma") or m.get("titulo") or "")[:120]}'
        with ThreadPoolExecutor(workers) as ex:
            for line in ex.map(ley, argv[1:]):
                print(line, flush=True)
        return
    if argv and argv[0] == '--probe':
        def probe(n):
            try:
                fast_fetch(fetch.chain_url(int(n)))
                vs = json.loads(fast_fetch(fetch.versions_url(int(n))))['Versiones'].get('Version')
            except (RuntimeError, ValueError) as e:
                return f'{n} - {e}'[:200]
            vs = fetch.as_list(vs)
            return f'{n} {len(vs)} ' + fast_fetch(fetch.chain_url(int(n)))[:400].decode('utf-8', 'replace')
        with ThreadPoolExecutor(workers) as ex:
            for line in ex.map(probe, argv[1:]):
                print(line, flush=True)
        return
    for slug in (argv or list(CHAINS)):
        fetch.fetch_act(slug)
        fetch.fetch(current_url(CHAINS[slug][-1]))
    for idn in EXTRA:
        fetch.fetch(fetch.version_url(idn, fetch.versions(idn)[0]['@vigenteDesde']))


if __name__ == '__main__':
    main(sys.argv[1:])
