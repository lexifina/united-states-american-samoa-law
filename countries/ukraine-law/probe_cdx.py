"""Probe: list archive.org captures of an act's dated revisions (edYYYYMMDD) on zakon.rada.gov.ua."""
import sys, json, re, urllib.parse
sys.path.insert(0, r'C:/Users/alany/Documents/lexifina/scripts/gitlaw_common')
import wayback

CACHE = r'C:/Users/alany/Documents/lexifina/scripts/ukraine-law/.cache'


def q(s):
    return urllib.parse.quote(s, safe='/')


def main(code, suffix=''):
    base = f'zakon.rada.gov.ua/laws/show/{q(code)}{suffix}'
    caps = wayback.captures(base, match='prefix', cache=CACHE, collapse='urlkey')
    eds = {}
    other = []
    for c in caps:
        u = urllib.parse.unquote(c['original'])
        m = re.search(r'/ed(\d{8})(/print)?', u)
        if m:
            eds.setdefault(m.group(1), []).append((c['timestamp'], c['length'], u))
        else:
            other.append((c['timestamp'], c['length'], u))
    print(code, 'captures', len(caps), 'editions', len(eds))
    for d in sorted(eds):
        print(' ', d, len(eds[d]), eds[d][0])
    return eds


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else '')
