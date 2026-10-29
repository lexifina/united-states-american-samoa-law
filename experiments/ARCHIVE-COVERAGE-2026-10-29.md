# Archive-first fetching for crawl-delayed Australian hosts (2026-10-29)

**Status: PARTIAL.** The archive.org numbers for ACT and the archive.org timing samples are still running.
This file will be updated.

Question (Alan, via global-law-main-composer): how far can archive-first fetching (Common Crawl, then archive.org,
then the live host) go for three slow hosts? This was measurement only: no live host was contacted.

## Method

- **Needed files** are each corpus's own list, read offline from its scripts folder:
  - ACT (`australia-australian-capital-territory-law`): every republication file (DOCX, else RTF) of the 291 In Force
    Acts whose page is in `cache/manifest.json`, leaving out "as notified" rows. That gives **6,694 files**. The fetch
    is still finding Acts, so the final total will be higher.
  - WA subsidiary legislation (`australia-western-australia-law`): every version text (`mrdoc_<n>`) on the
    versions pages of all 1,542 instruments. That gives **12,011 files**.
  - Federal (`australia-law`): `fetchlib.wanted()`, the 21,805 compilation EPUBs in tiers 0 to 3 (5.05 GB).
- **Coverage** was measured over the full lists, not only a sample, because the fetchers' own index dumps cover every
  file. A random 300-file sample per host (seed 20261029) is reported alongside as a check.
  - Common Crawl: the fetchers' per-crawl index dumps. ACT used 78 crawls (2018-34 to 2026-43). WA used all 128. Federal
    used 37 (2023-06 to 2026-43), and for this experiment I re-read those 37 crawls' index for every text form of the
    host, not only EPUB (297 index requests at 3 a second or less, on top of wayback.py's pacer).
  - archive.org: WA has one complete prefix CDX dump (90,012 captures, collapsed by digest). Federal has 134 CDX pages
    (EPUB mimetype). ACT has 26 per-Act answers cached; the full 19-page prefix read is running (one request at a time,
    through wayback.py's shared limiter).
- **Usable** means the capture passes the fetcher's own check. For ACT that is a real DOCX or RTF within 3% of the
  listed size. For WA it is the right instrument and version in the title, and the page is complete. For Federal it is
  the size, the cover's compilation number and date, and the parser reading it. Where the fetchers have already tried
  captures, their pass and reject counts are used.
- **Timing:** I downloaded 30 samples (27 for ACT CC) one at a time per host and archive. Common Crawl used `wayback.cc_get`,
  at 3 requests a second or less from this script and inside the machine-wide pacer. archive.org went only through
  `wayback.get`, under the shared limiter. Live per-file times come from the fetchers' logs (SCRAPING-LOG.md and
  their own logs). No live requests were made.

## Numbers so far

### Coverage of the needed files

| Host | Needed | Common Crawl, usable form | archive.org | Either | Notes |
|---|---|---|---|---|---|
| ACT | 6,694 | **187 (2.8%)** DOCX/RTF captures; most are 2019 RTFs that fail the check ("bad rtf") | 26 Acts asked so far: 753 of 801 files (94%); full read running | – | CC has **PDFs** of 5,846 needed republications (87%), 5,446 of them untruncated (81%). The corpus parses Word, not PDF |
| WA subsidiary | 12,011 | **5,480 (45.6%)**; 95.5% of those tried passed the check (2,998 of 3,139) | **5,377 (44.8%)**; 65% of those tried passed (197 of 302) | **5,714 (47.6%)** | Sample of 300: CC 151, IA 149, either 158. Current versions do better: CC 1,255 of 1,542 (81%) |
| Federal | 21,805 | **0** EPUB files (256 EPUB captures, all of the wrong rectification or version) | **83 (0.4%)** EPUB files (665 captures, 2024 to 2026) | 83 | CC holds the **unpacked EPUB HTML** (`.../epub/OEBPS/document_N/document_N.html`) for **4,516 needed compilations (20.7%)**. Every part is present and untruncated for about 90% of them (337 of 373 checked against cached EPUBs), so about 4,070 (18.7%) |

### Time per file

| Host | Live, at its crawl delay (logged) | Common Crawl (this sample, one at a time) | archive.org (fetchers' logs, shared limiter) |
|---|---|---|---|
| ACT | **10.5 s** (Crawl-delay 10, one at a time) | 1.38 s median (27 files, 17.4 MB: 20 PDF, 5 RTF, 2 DOCX) | **16.5 s** (700 files, 20:16 to 23:28 UTC, 4 workers) |
| WA subsidiary | **2.2 s** effective (no Crawl-delay, 4 parallel: 3,190 files in 7,026 s) | 0.90 s median (30 files, 14.6 MB). Fetcher: 0.19 s at 12 threads | **11.8 s** (302 files in 3,571 s, 4 threads) |
| Federal | **10 s** (Crawl-delay 10), quiet hours only (11 h a day) | 1.26 s median (30 `document_1.html`, 23.7 MB) | **26 s** (80 files, 22:15 to 22:50 UTC) |

Common Crawl one at a time is about 1 to 1.4 s per file. It runs in parallel up to the machine cap, so the effective
time is 0.05 to 0.3 s per file. archive.org was slower than the live crawl delay on every host tonight: its shared
limiter sat at its 0.3 to 0.4 a second floor, with 917 throttled answers machine-wide. It only helps because it runs
**alongside** the live queue (another host, another limit), never instead of it.

Federal CC part check: 26 of 30 downloaded `document_1.html` captures are **byte-identical** to the same file in the
register's EPUB. The 4 that differ are being examined.

### Projected total fetch time (whole needed list, one live process at the crawl delay)

| Host | Live-only | Archive-first (archives in parallel with live) | Saving |
|---|---|---|---|
| ACT, Word only | 6,694 x 10.5 s = **19.5 h** | IA-covered share pending (94% in the Acts asked so far). At 94%, live is about 400 files, 1.2 h, and the IA queue is about 6,290 x 16.5 s = 28.8 h. So **archive.org's limiter, not the register, sets the time** | depends on IA rate |
| WA subsidiary | 12,011 x 2.2 s = **7.3 h** | CC about 5,230 usable (minutes) + IA about 150 + live about 6,630 x 2.2 s = **4.1 h** | **44%** |
| Federal, EPUB only | 21,805 x 10 s = 60.6 h = **5.5 days** at 11 quiet hours a day | 83 from IA: **5.5 days** | **0.4%** |
| Federal, plus CC unpacked parts | 5.5 days | about 4,150 from archives, then 17,650 x 10 s = 49 h = **4.5 days** | **19%**, if the build reads unpacked parts |

## Verdict (provisional)

- **WA:** archive-first pays. Common Crawl alone covers 46% of the files with 95% verified, at well over 10 times
  the live rate. Do it first, every time.
- **Federal:** archive-first as built (EPUB files only) is worth almost nothing (0.4%). The real archive supply is CC's
  unpacked EPUB parts: about 19% of files, byte-identical in 26 of 30 samples. That needs an "EPUB from parts"
  reader, and the live host stays the bottleneck.
- **ACT:** CC has almost no Word files. archive.org has most of them, but tonight it is slower per file (16.5 s) than
  the register's crawl delay (10.5 s), so it shortens the total only by running alongside the live queue. CC's PDFs
  (81% untruncated) are the big untapped source, if a PDF parser can match the Word text.
