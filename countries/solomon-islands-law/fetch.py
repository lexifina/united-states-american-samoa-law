"""Cached fetcher for Solomon Islands sources (gitlaw-SB).

PacLII sits behind a bot challenge, so it is read only through archive.org `id_` captures
(scripts/gitlaw_common/wayback.py, shared machine-wide rate) or Common Crawl. Every request is
logged to .cache/requests.jsonl by the shared client.

Usage: python -X utf8 fetch.py TIMESTAMP URL [TIMESTAMP URL ...]  (prints cache path and size)
"""
import os
import sys

sys.path.insert(0, r'C:/Users/alany/Documents/lexifina/scripts/gitlaw_common')
import wayback  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, '.cache')


def ia(ts, url):
    """Bytes of the archive.org capture of url at timestamp ts (exact timestamp pins the capture)."""
    return wayback.get(url, ts=ts, cache=CACHE)


def ia_key(ts, url):
    return f'https://web.archive.org/web/{ts}id_/{url}'


if __name__ == '__main__':
    a = sys.argv[1:]
    for ts, url in zip(a[::2], a[1::2]):
        b = ia(ts, url)
        print(ts, url, len(b) if b else None)
