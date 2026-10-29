# Issues for the coordinator (gitlaw-UA)

1. `scripts/gitlaw_common/wayback.py` `_curl()` does not pass `-g`/`--globoff`. A URL with `[` `]` `{` `}` (for example a
   CDX regex filter `filter=length:[0-9]{5,}`) is expanded by curl into many requests and the status reads
   `200200200…429`; the concatenated body is cached as one response. Work-around here: percent-encode `[]{}` before
   calling `wayback.fetch` (fetch.py `cdx()`). Fix: add `'-g'` to the curl argument list.
2. `index.commoncrawl.org` refused connections from this machine on 2026-10-28/29 (TCP connect timeout, 21 s), while
   `data.commoncrawl.org` answered. Ukraine is therefore read from archive.org only.
