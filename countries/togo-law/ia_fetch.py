"""Fetch archive.org `id_` captures of named PDFs (earliest 200 capture of each), via the shared wayback client.

    python -X utf8 ia_fetch.py <host-prefix> <substring> [<substring> ...]
Prints: timestamp, original URL, bytes, pages, text-layer characters.
"""
import sys, urllib.parse
sys.path.insert(0, r'C:/Users/alany/Documents/lexifina/scripts/gitlaw_common')
import wayback, fitz

CACHE = 'C:/Users/alany/Documents/lexifina/scripts/togo-law/.cache'


def pick(host, subs):
    caps = wayback.captures(host, match='prefix', cache=CACHE)
    out = {}
    for c in sorted(caps, key=lambda c: c['timestamp']):
        u = urllib.parse.unquote(c['original'])
        if any(s.lower() in u.lower() for s in subs):
            key = u.split('://', 1)[1].replace(':80/', '/').replace('www.', '')
            out.setdefault(key, c)
    return list(out.values())


if __name__ == '__main__':
    for c in pick(sys.argv[1], sys.argv[2:]):
        b = wayback.get(c['original'], ts=c['timestamp'], cache=CACHE)
        if not b:
            print('MISS', c['timestamp'], c['original']); continue
        try:
            d = fitz.open(stream=b, filetype='pdf'); n = d.page_count; t = sum(len(p.get_text()) for p in d)
        except Exception as e:
            n, t = 0, repr(e)[:60]
        print(c['timestamp'], c['original'], len(b), n, t, flush=True)
