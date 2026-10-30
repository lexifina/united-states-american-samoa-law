"""The last step before a builder writes files into a published record (user's rule, 2026-10-29).

Scrubs this machine's home path from every published text file and refuses the build if any file the rule keeps
private would be published: a private file by name, code using the fast-fetch tooling, or a published doc that
describes how the source was scraped. Lives here, not in a published repo, because it names what it looks for.
"""
from private import HOME, PRIVATE_NAME, SPEED_MARK

SCRAPE_WORDS = ('crawl-delay', 'robots.txt', 'user-agent', 'requests a second', 'requests at a time', '.cache/',
                'fetch.py', 'fetch-log', 'bot challenge', 'cloudflare')
TEXT_NOT_SCANNED = ('.csv', '.tsv')        # data tables: law text and notes, never scraping prose
TEMPLATE_PREFIX = 'tools/build/repo/'      # templates are scanned as the docs they render into


def publish_gate(files: dict[str, bytes]) -> dict[str, bytes]:
    out, bad = {}, []
    for path, data in files.items():
        name = path.rsplit('/', 1)[-1]
        if PRIVATE_NAME.match(name):
            bad.append(f'{path}: private by name')
            continue
        if name.endswith(('.py', '.sh')) and SPEED_MARK.search(data):
            bad.append(f'{path}: uses fast-fetch tooling')
            continue
        if not name.endswith(TEXT_NOT_SCANNED):
            text = data.decode('utf-8')
            data = HOME.sub('~', text).encode('utf-8')
            if name.endswith('.md'):
                low = text.lower()
                bad += [f'{path}: describes scraping ({w!r})' for w in SCRAPE_WORDS if w in low]
        out[path] = data
    if bad:
        raise SystemExit('publish gate refused:\n  ' + '\n  '.join(bad))
    return out
