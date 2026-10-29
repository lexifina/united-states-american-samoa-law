import sys, re, html
sys.path.insert(0, '.')
import fetch

q = sys.argv[1]
pages = int(sys.argv[2]) if len(sys.argv) > 2 else 1
pat = sys.argv[3] if len(sys.argv) > 3 else 'enmienda'
for pg in range(1, pages + 1):
    u = f'https://www.registroficial.gob.ec/page/{pg}/?s={q}' if pg > 1 else f'https://www.registroficial.gob.ec/?s={q}'
    p = fetch.get(u)
    if not p:
        print('FAIL', u)
        break
    raw = p.read_bytes()
    try:
        t = raw.decode('utf-8')
    except UnicodeDecodeError:
        t = raw.decode('cp1252', 'replace')
    t = re.sub(r'<(script|style)[^>]*>.*?</\1>', '', t, flags=re.S)
    i = t.find('Resultados de b')
    body = t[i:]
    cards = re.split(r"(?=<h4 class='card__title_post_imagen'>)|(?=<div class='card__item)", body)
    for c in cards:
        s = re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]+>', ' ', c))).strip()
        pdf = re.findall(r"href=['\"]([^'\"]*storage/api[^'\"]*)", c)
        if not s or 'Descargar' not in s:
            continue
        m = re.search(r'(.{0,60}A.o [IVX]+ - N. \d+ \w+, \d+ \w+ \d{4})', s)
        hits = [h.start() for h in re.finditer(pat, s, re.I)]
        snip = ' ... '.join(s[max(0, h - 150):h + 250] for h in hits[:1])
        print('*', m.group(1) if m else s[:80], '|', pdf[0] if pdf else '-')
        print('    ', snip[:420])
