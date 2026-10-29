"""Index of the Assemblée nationale 'Répertoire des lois votées' pages in the cache."""
import re, html, fetch
def rows():
    out = []
    for i in range(1, 15):
        b = fetch.get('https://www.assembleenationale.bf/loip' + ('' if i == 1 else f'?page={i}'))
        t = b.decode('utf8', 'replace')
        for m in re.finditer(r'<a [^>]*href="(https://www.assembleenationale.bf/loip/\d+)"[^>]*>(.*?)</a>(.*?)</tr>', t, re.S):
            txt = html.unescape(re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', m.group(2) + ' | ' + m.group(3)))).strip()
            out.append((m.group(1), txt))
    return out
if __name__ == '__main__':
    for u, t in rows(): print(u, t)
