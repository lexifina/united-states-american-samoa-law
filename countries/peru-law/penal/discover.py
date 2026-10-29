"""Discovery only (not part of the build): list norms in the Congreso ADLP index by number range, with the
document links each row carries.

    python -X utf8 penal/discover.py KIND FROM-TO        KIND: ley | dleg

Rows print as: number, publication date (dd/mm/yyyy), title, links. Cached under ../.cache (POST bodies keyed by
fetch.post_key); every request is logged to ../.cache/requests.jsonl.
"""
from __future__ import annotations

import html
import re
import sys
from pathlib import Path
from urllib.parse import urlencode

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import fetch  # noqa: E402

J = str(fetch.CACHE / 'cookies-penal.txt')
CK = ['-b', J, '-c', J]
XN = {'ley': '0', 'dleg': '3'}


def fields(t):
    def val(name):
        m = re.search(r'name="%s"[^>]*value="([^"]*)"' % re.escape(name), t) or \
            re.search(r'value="([^"]*)"[^>]*name="%s"' % re.escape(name), t)
        return html.unescape(m.group(1)) if m else ''
    return {k: val(k) for k in ['__VIEWSTATE', '__VIEWSTATEGENERATOR', '__EVENTVALIDATION']}


def rows(s):
    out = []
    for tr in re.findall(r'<tr[^>]*>(.*?)</tr>', s, re.S):
        m = re.search(r'LinkNumero"[^>]*>(\d+)</a>', tr)
        if not m:
            continue
        d = re.search(r'(\d\d/\d\d/\d{4})', tr)
        fonts = [html.unescape(x).strip() for x in re.findall(r'<font[^>]*>([^<]*)</font>', tr)]
        title = max(fonts, key=len) if fonts else ''
        links = sorted(set(re.findall(r'href="([^"]+\.pdf)"', tr, re.I)))
        out.append((m.group(1), d.group(1) if d else '', ' '.join(title.split()), links))
    return out


def main(kind, rng):
    u = 'https://www.leyes.congreso.gob.pe/LeyNumePP.aspx?xNorma=%s' % XN[kind]
    t = fetch.get(u + '&s=1', force=True, extra=CK).read_text('utf8', 'replace')
    a, b = rng.split('-')
    data = fields(t)
    data.update({'ctl00$ContentPlaceHolder1$DdlEstado': '2', 'ctl00$ContentPlaceHolder1$DdlTipoNorma': XN[kind],
                 'ctl00$ContentPlaceHolder1$DdlTipoBusqueda': '4', 'ctl00$ContentPlaceHolder1$TxtBuscar': '',
                 'ctl00$ContentPlaceHolder1$DdlOrdenar': '0', 'ctl00$ContentPlaceHolder1$BtnConsultar': 'Consultar',
                 'ctl00$ContentPlaceHolder1$TxtFechaIni': '', 'ctl00$ContentPlaceHolder1$TxtFechaFin': '',
                 'ctl00$ContentPlaceHolder1$TxtNroNormaI': a, 'ctl00$ContentPlaceHolder1$TxtNroNormaF': b})
    s = fetch.get(u + '&s=1', cache_as=fetch.post_key(u, data), extra=['--data-binary', '@-'] + CK,
                  stdin=urlencode(sorted(data.items())), force=True).read_text('utf8', 'replace')
    allr = rows(s)
    for _ in range(200):
        m = re.search(r'\[(\d+) de (\d+)\]', s)
        if not m or int(m.group(1)) >= int(m.group(2)):
            break
        d = fields(s)
        pg = re.search(r'name="([^"]*ImgBtnSiguiente)"', s)
        if not pg:
            break
        d.update({pg.group(1) + '.x': '5', pg.group(1) + '.y': '5'})
        s = fetch.get(u + '&s=1', cache_as=fetch.post_key(u, d), extra=['--data-binary', '@-'] + CK,
                      stdin=urlencode(sorted(d.items())), force=True).read_text('utf8', 'replace')
        allr += rows(s)
    for r in allr:
        print(r[0], r[1], r[2], ' '.join(r[3]), flush=True)


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
