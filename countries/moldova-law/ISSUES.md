# gitlaw-MD: issues for the coordinator

1. `scripts/gitlaw_common/wayback.py` `_locked()`: on Windows, `os.open(LOCK, O_CREAT | O_EXCL | O_WRONLY)` can raise
   `PermissionError: [Errno 13] Permission denied: '...\Temp\gitlaw-wayback-rate.lock'` (the lock file is being deleted
   by another process at that moment) instead of `FileExistsError`. It killed one of my archive.org probes
   (2026-10-29 ~12:50 UTC). Catching `PermissionError` like `FileExistsError` (retry) would fix it. Worked around: not needed
   for the build (all pinned captures were already cached).
2. Common Crawl holds no legis.md pages: `www.legis.md/cautare/{showdetails,downloadpdf,getResults}` prefixes returned 0
   records in 16 crawls (CC-MAIN-2025-30 to 2026-43), presumably because Cloudflare blocks CCBot. archive.org has only
   108 `showdetails/` captures. Useful for any other country behind Cloudflare.

- 2026-10-29 coordinator: fixed. Both lock loops in gitlaw_common/wayback.py now retry on PermissionError as on FileExistsError.
