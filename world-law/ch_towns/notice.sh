# usage: notice.sh <url>   fetch one legal-notice page (3 s gap) and print its copyright/reproduction sentences
h(){ python -c "import hashlib,sys;print('probe-cache/'+hashlib.sha256(sys.argv[1].encode()).hexdigest()[:16]+'.body')" "$1"; }
python -I -X utf8 probe.py 3 "$1"
python -I -X utf8 - "$(h "$1")" <<'PY'
import re, sys, html
b = open(sys.argv[1], 'rb').read()
try: t = b.decode('utf-8')
except UnicodeDecodeError: t = b.decode('cp1252')
t = re.sub(r'(?s)<(script|style).*?</\1>', '', t); t = html.unescape(re.sub(r'<[^>]+>', ' ', t)); t = re.sub(r'\s+', ' ', t)
sents = re.split(r'(?<=[.!?])\s+', t)
hits = [s for s in sents if re.search(r'urheber|copyright|reprodu|vervielfält|zustimmung|einwilligung|bewilligung|genehmigung|gesetzestext|erlass|autorisation|droit d.auteur|weiterverwend|nutzung der inhalte|kopier', s, re.I)]
print('\n'.join(dict.fromkeys(x[:600] for x in hits)) or '(no copyright/reproduction sentence)')
PY
