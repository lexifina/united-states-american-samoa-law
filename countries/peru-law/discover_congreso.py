# Discovery helper (not part of the build): searches the Congreso ADLP law index by title text, with paging.
# Usage: python -X utf8 discover_congreso.py "REFORMA CONSTITUCIONAL"
import sys, re, html
sys.path.insert(0, '.')
import fetch
J = str(fetch.CACHE / 'cookies.txt')
CK = ['-b', J, '-c', J]
u = 'https://www.leyes.congreso.gob.pe/LeyNumePP.aspx?xNorma=0'
def fields(t):
    def val(name):
        m = re.search(r'name="%s"[^>]*value="([^"]*)"' % re.escape(name), t) or re.search(r'value="([^"]*)"[^>]*name="%s"' % re.escape(name), t)
        return html.unescape(m.group(1)) if m else ''
    return {k: val(k) for k in ['__VIEWSTATE', '__VIEWSTATEGENERATOR', '__EVENTVALIDATION']}
def rows(s):
    return [(m.group(1), m.group(2), html.unescape(m.group(3))) for m in re.finditer(r'LinkNumero"[^>]*>(\d+)</a>.*?<font[^>]*>(\d\d/\d\d/\d{4})</font>.*?<font[^>]*>([^<]*)</font>', s, re.S)]
t = fetch.get(u + '&s=1', force=True, extra=CK).read_text('utf8', 'replace')
q = sys.argv[1]
data = fields(t)
num = re.fullmatch(r'(\d+)-(\d+)', q)
data.update({'ctl00$ContentPlaceHolder1$DdlEstado': '2', 'ctl00$ContentPlaceHolder1$DdlTipoNorma': '0',
             'ctl00$ContentPlaceHolder1$DdlTipoBusqueda': '3', 'ctl00$ContentPlaceHolder1$TxtBuscar': q,
             'ctl00$ContentPlaceHolder1$DdlOrdenar': '0', 'ctl00$ContentPlaceHolder1$BtnConsultar': 'Consultar',
             'ctl00$ContentPlaceHolder1$TxtFechaIni': '', 'ctl00$ContentPlaceHolder1$TxtFechaFin': '',
             'ctl00$ContentPlaceHolder1$TxtNroNormaI': '', 'ctl00$ContentPlaceHolder1$TxtNroNormaF': ''})
if num:  # number range search: discover_congreso.py 32146-32600
    data.update({'ctl00$ContentPlaceHolder1$DdlTipoBusqueda': '4', 'ctl00$ContentPlaceHolder1$TxtBuscar': '',
                 'ctl00$ContentPlaceHolder1$TxtNroNormaI': num.group(1), 'ctl00$ContentPlaceHolder1$TxtNroNormaF': num.group(2)})
s = fetch.post(u + '&s=1', data, force=True, extra_ck=CK) if False else None
from urllib.parse import urlencode
s = fetch.get(u + '&s=1', cache_as=fetch.post_key(u, data), extra=['--data-binary', '@-'] + CK, stdin=urlencode(sorted(data.items())), force=True).read_text('utf8','replace')
allr = rows(s)
for page in range(2, 40):
    m = re.search(r'\[(\d+) de (\d+)\]', s)
    if not m or int(m.group(1)) >= int(m.group(2)): break
    d = fields(s)
    pager = re.search(r'name="([^"]*ImgBtnSiguiente)"', s).group(1)
    d.update({pager + '.x': '5', pager + '.y': '5'})
    s = fetch.get(u + '&s=1', cache_as=fetch.post_key(u, d), extra=['--data-binary', '@-'] + CK, stdin=urlencode(sorted(d.items())), force=True).read_text('utf8','replace')
    allr += rows(s)
for r in allr: print(*r)
