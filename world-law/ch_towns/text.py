import re, sys, html
b = open(sys.argv[1], 'rb').read()
try:
    t = b.decode('utf-8')
except UnicodeDecodeError:
    t = b.decode('cp1252')
t = re.sub(r'(?s)<(script|style|nav).*?</\1>', '', t)
t = html.unescape(re.sub(r'<[^>]+>', ' ', t)); t = re.sub(r'\s+', ' ', t)
for kw in sys.argv[2:]:
    for m in re.finditer(kw, t, re.I):
        print('...', t[max(0, m.start()-300):m.start()+900], '\n')
