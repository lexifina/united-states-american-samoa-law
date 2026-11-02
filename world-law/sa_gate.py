"""Gate one host: robots.txt alone, then (only if robots allows /) the home page; list links about ordinances,
gazettes, laws and terms. Private."""
import re
import sys
import time
import urllib.robotparser

import sa_probe

KEY = re.compile(r'ordenanz|gaceta|normativ|normograma|leyes|ley-|constituci|t[eé]rminos|condiciones|derechos-de-autor|'
                 r'politica|aviso-legal|transparencia|decretos|acuerdos', re.I)


def gate(base: str, show_links: bool = True) -> str:
    rb = sa_probe.fetch(base.rstrip('/') + '/robots.txt')
    st = rb['status']
    body = sa_probe.text(rb['body'])
    print(f'== {base} robots: HTTP {st} {rb.get("final", "")} {rb.get("error", "")[:120]} {rb.get("challenge_markers") or ""}')
    if st == 0:
        return 'FAIL timeout/error on robots.txt'
    if st in (403, 429) or rb.get('challenge_markers') and st != 404 and st != 200:
        return f'FAIL challenge/{st} on robots.txt'
    if st >= 500:
        return 'FAIL robots 5xx (disallow all)'
    rp = urllib.robotparser.RobotFileParser()
    if st == 200 and 'html' not in rb.get('ctype', '').lower():
        lines = [l for l in body.splitlines() if l.strip() and not l.startswith('#')]
        print('   ' + ' | '.join(lines[:25]))
        rp.parse(body.splitlines())
        if re.search(r'claudebot|claude-web|anthropic-ai|gptbot', body, re.I):
            print('   NOTE: names an AI crawler')
        if not rp.can_fetch('*', base.rstrip('/') + '/'):
            return 'FAIL robots disallows /'
    else:
        print('   (no robots.txt file)')
    time.sleep(0.1)
    h = sa_probe.fetch(base)
    s = sa_probe.text(h['body'])
    print(f'   home: HTTP {h["status"]} {h.get("final", "")} {len(h["body"])} bytes {h.get("challenge_markers") or ""} {h.get("error", "")[:100]}')
    if h['status'] in (0, -1):
        return 'FAIL timeout/error on home'
    if h['status'] in (403, 429):
        return f'FAIL {h["status"]} on home'
    if h.get('challenge_markers') and any(m in h['challenge_markers'] for m in ('just a moment', 'cf-chl', 'incapsula incident', 'challenge-platform', 'captcha')):
        return 'FAIL challenge on home'
    if show_links:
        links = []
        for m in re.finditer(r'href=["\']([^"\']+)["\'][^>]*>(.{0,120}?)</a', s, re.S | re.I):
            t = re.sub(r'<[^>]+>|\s+', ' ', m.group(2)).strip()
            if KEY.search(m.group(1)) or KEY.search(t):
                links.append(f'{m.group(1)}  [{t[:60]}]')
        print('   ' + '\n   '.join(dict.fromkeys(links).keys().__iter__().__class__ and list(dict.fromkeys(links))[:40]))
    return 'PASS robots+home'


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    for b in sys.argv[1:]:
        print('  ->', gate(b))
