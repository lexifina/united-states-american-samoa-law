"""The law PDF (and the other kit PDFs) linked from an Assemblée nationale loip/<id> page."""
import re, sys, fetch
BASE = 'https://www.assembleenationale.bf'
def kit(n):
    t = fetch.get(f'{BASE}/loip/{n}').decode('utf8', 'replace')
    return [BASE + h for h in re.findall(r'href="(/storage/[^"]+\.pdf)"', t)]
def law_pdf(n):
    k = [u for u in kit(n) if '/storage/Loi/' in u]
    return k[0] if k else None
if __name__ == '__main__':
    for n in sys.argv[1:]:
        u = law_pdf(n); b = fetch.get(u) if u else None
        print(n, u, None if b is None else len(b), fetch.path(u).name if u else '')
