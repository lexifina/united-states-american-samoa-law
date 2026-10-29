# Discovery helper (not part of the build): lists Congreso ADLP norms by number range and type.
# Usage: python -X utf8 codes/discover.py TYPE FROM-TO      TYPE: 0 = ley, 3 = decreto legislativo
# Results come 20 per query, so it walks the range in chunks of 20.
import html
import re
import sys
from pathlib import Path
from urllib.parse import urlencode

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cfetch  # noqa: E402

fetch = cfetch.fetch
J = str(fetch.CACHE / 'cookies-codes.txt')
CK = ['-b', J, '-c', J]
U = 'https://www.leyes.congreso.gob.pe/LeyNumePP.aspx?xNorma=' + (sys.argv[1] if len(sys.argv) > 1 else '0')


def fields(t):
    def val(name):
        m = (re.search(r'name="%s"[^>]*value="([^"]*)"' % re.escape(name), t)
             or re.search(r'value="([^"]*)"[^>]*name="%s"' % re.escape(name), t))
        return html.unescape(m.group(1)) if m else ''
    return {k: val(k) for k in ['__VIEWSTATE', '__VIEWSTATEGENERATOR', '__EVENTVALIDATION']}


def rows(s):
    return [(m.group(1), m.group(2), html.unescape(m.group(3))) for m in re.finditer(
        r'LinkNumero"[^>]*>(\d+)</a>.*?<font[^>]*>(\d\d/\d\d/\d{4})</font>.*?<font[^>]*>([^<]*)</font>', s, re.S)]


def query(tipo, a, b):
    t = cfetch.get(U + '&s=1', force=True, extra=CK).read_text('utf8', 'replace')
    data = fields(t)
    data.update({'ctl00$ContentPlaceHolder1$DdlEstado': '2', 'ctl00$ContentPlaceHolder1$DdlTipoNorma': str(tipo),
                 'ctl00$ContentPlaceHolder1$DdlTipoBusqueda': '4', 'ctl00$ContentPlaceHolder1$TxtBuscar': '',
                 'ctl00$ContentPlaceHolder1$DdlOrdenar': '0', 'ctl00$ContentPlaceHolder1$BtnConsultar': 'Consultar',
                 'ctl00$ContentPlaceHolder1$TxtFechaIni': '', 'ctl00$ContentPlaceHolder1$TxtFechaFin': '',
                 'ctl00$ContentPlaceHolder1$TxtNroNormaI': str(a), 'ctl00$ContentPlaceHolder1$TxtNroNormaF': str(b)})
    s = cfetch.get(U + '&s=1', cache_as=fetch.post_key(U, data), extra=['--data-binary', '@-'] + CK,
                   stdin=urlencode(sorted(data.items())), force=True).read_text('utf8', 'replace')
    return rows(s)


def main():
    tipo = sys.argv[1]
    a, b = map(int, sys.argv[2].split('-'))
    for s in range(a, b + 1, 20):
        got = query(tipo, s, min(s + 19, b))
        for r in got:
            print(*r, flush=True)
        if not got:
            break


if __name__ == '__main__':
    main()
