# Archive-first fetching for crawl-delayed Australian hosts (2026-10-29 to 30)

Question (Alan, via global-law-main-composer): how far can archive-first fetching (Common Crawl, then archive.org,
then the live host) go for three slow hosts? This was measurement only: no live host was contacted, and every live
figure comes from the running fetchers' logs.

## Headline

| Host | Needed files | Common Crawl, usable | archive.org | Live-only | Best archive-first | Saving |
|---|---|---|---|---|---|---|
| ACT (Word republications) | 6,694 | **0.1%** as Word (1 of 16 tried passed); **81%** as untruncated PDF | **89.6%** (6,000), 99.7% pass | 19.5 h | 11.9 h (live and IA pull from one list) / about 2 h if the CC PDFs are used | **39%** / ~90% with a PDF reader |
| WA subsidiary (version HTML) | 12,011 | **45.6%** indexed, 95.5% pass, so about **43.6%** usable | 44.8% indexed (mostly the same files), 65% pass | 7.3 h | **4.1 h** | **44%** |
| Federal (compilation EPUB) | 21,805 | **0%** as EPUB; **20.7%** as unpacked EPUB HTML parts | **0.4%** as EPUB; about **35%** as unpacked parts (25-title sample) | 5.5 days (60.6 h at 11 quiet hours a day) | 5.5 days EPUB-only; **about 3.7 days** with CC and IA parts | 0.4% / **about 33%** with a parts reader |

The archives already pay on WA. On ACT and Federal, most of the gain needs a change of format: PDFs from Common Crawl
for ACT, and the unpacked EPUB HTML for Federal. The fetchers don't take those yet.

## Method

- **Needed files**, from each corpus's own list (read offline):
  - ACT (`australia-australian-capital-territory-law`): every republication file (DOCX, else RTF) of the 291 In Force
    Acts whose page is in `cache/manifest.json`, leaving out "as notified" rows: **6,694 files**. The fetch is still
    finding Acts, so the final total will be higher. `/current/` files count only for a capture taken after their
    publication day, as in `archive_fetch.py`.
  - WA (`australia-western-australia-law`): every version text (`mrdoc_<n>`) on the versions pages of all 1,542
    instruments: **12,011 files**.
  - Federal (`australia-law`): `fetchlib.wanted()`, the 21,805 compilation EPUBs in tiers 0 to 3 (5.05 GB).
- **Coverage over the full lists**, plus a random 300-file sample per host (seed 20261029) as a check. Only index and
  CDX queries were used:
  - Common Crawl: the fetchers' per-crawl index dumps. ACT used 78 crawls (2018-34 to 2026-43) and WA all 128. For
    Federal I re-read the same 37 crawls (2023-06 to 2026-43) for every text form (EPUB, OEBPS parts, Word, PDF), not
    only EPUB. That took 297 index requests in 149 s at 3 a second or less, on top of wayback.py's pacer.
  - archive.org: WA used the fetcher's one prefix CDX dump (90,012 captures). Federal used the fetcher's 134 EPUB CDX
    pages, plus 25 per-title CDX queries with no mimetype filter, for the other forms. ACT used a full read of the
    `legislation.act.gov.au/DownloadFile/a/` prefix: 19 CDX pages, one at a time, 35,245 captures, 42 to 383 s per page
    (median 112 s). Everything went through `wayback.py`'s shared limiter.
- **Usable** means passing the fetcher's own check, using its pass and reject counts where it has tried:
  - ACT: real DOCX or RTF, within 3% of the listed size.
  - WA: right instrument and version in the title, complete page.
  - Federal: size, the cover's number and date, and the parser reads it.
- **Timing:** 30 downloads per host and archive (27 for ACT CC), one at a time. Common Crawl used `wayback.cc_get`, at 3
  requests a second or less from here and inside the machine pacer. archive.org went only through `wayback.get` (the
  shared limiter), with the limiter wait and the transfer time recorded separately. In all: 87 CC body requests, 90
  archive.org downloads (107 attempts), 47 archive.org CDX requests and 297 CC index requests. Live times come from the
  fetchers' logs.

## Coverage detail

**ACT.**
- Common Crawl's index holds 30,755 captures of `/DownloadFile/a/.../PDF/`, against 242 RTF and 12 DOCX. Only 187
  needed Word files have a capture at all, and the fetcher passed 1 of 16 tried: 15 were "bad rtf", 2019 captures cut
  short.
- CC has a PDF of the same republication for 5,846 needed files (87%); 5,446 are untruncated (81%).
- archive.org holds 6,000 of 6,694 (89.6%; sample 266 of 300). The fetcher's checks passed 700 of 702.

**WA.**
- CC indexes 5,480 (45.6%; sample 151 of 300). archive.org has 5,377 (44.8%; sample 149), and either has 5,714
  (47.6%; sample 158). The two archives mostly hold the same files: archive.org adds only 234.
- The fetcher verified 2,998 of the 3,139 CC captures it tried (95.5%) and 197 of 302 archive.org captures (65%; the
  failures were mostly cut-off pages).
- Current versions are much better covered: CC has 1,255 of 1,542 (81%).
- Capture years run from 2019 to 2026, densest in 2021 and 2025.

**Federal.**
- EPUB files: CC has 256 captures and none usable (wrong rectification or version: 219 needed compilations have a
  capture of another rectification). archive.org has 83 (0.4%), all 2024 to 2026, and 30 of 30 sampled matched the
  register's size.
- **Unpacked EPUB HTML** (`/<id>/<d>/<d>/text/<rect>/epub/OEBPS/document_N/document_N.html`):
  - CC has parts for **4,516 needed compilations (20.7%**; sample 50 of 300).
  - I checked 373 of them against EPUBs already in the cache. CC has every document of the EPUB for 354 (95%), and every
    one untruncated for 337 (90%). Of 30 downloaded `document_1.html` files, **26 are byte-identical** to the file inside
    the register's EPUB. The other 4 are a later re-render by the register (an added Aspose.Words generator tag, and nbsp
    and letter-split spacing such as "A n Act"), so they fail a strict text check.
  - In 25 sample titles (790 needed files), archive.org holds parts for 277 (35%), CC for 171, and either for 289
    (36.6%). archive.org also has Word for 137 and PDF for 135 there.
  - So about 36% of files exist in an archive as parts. Allowing about 10% for missing or cut-off parts gives roughly
    **33% usable**.

## Time per file

| Host | Live, at its crawl delay (logged) | Common Crawl (sample, one at a time) | archive.org, this sample (sequential) | archive.org, fetchers' logs (4 workers) |
|---|---|---|---|---|
| ACT | **10.5 s** (Crawl-delay 10, one at a time) | 1.38 s median (17.4 MB) | 24.1 s median: 19.8 s limiter wait + 3.2 s transfer (53.2 MB, 30 of 30 real RTF/DOCX) | **16.5 s** (700 files, 20:16 to 23:28 UTC) |
| WA | **2.2 s** effective (no Crawl-delay, 4 parallel; 3,190 files in 7,026 s) | 0.90 s median (14.6 MB); fetcher 0.19 s at 12 threads | 46.6 s median: 45.0 s wait + 2.3 s transfer | **11.8 s** (302 files in 3,571 s) |
| Federal | **10 s** (Crawl-delay 10), quiet hours only, 11 h a day | 1.26 s median per `document_1.html` (23.7 MB) | 47.2 s median: 43.5 s wait + 2.9 s transfer (30 of 30 EPUBs size-exact) | **26 s** (80 files, 22:15 to 22:50 UTC) |

- **Common Crawl is 8 to 12 times faster than any live host, even one file at a time.** It runs in parallel up to the
  machine cap of 20 a second, so a whole corpus's archived share takes minutes.
- **archive.org is slower than the live crawl delay on every host tonight.** The transfer takes only 2 to 3 s; the
  rest is queueing in the shared limiter. The limiter sat at 0.3 to 0.8 requests a second with about 990 throttled
  answers machine-wide, shared by three fetchers and this experiment. It still adds capacity, because it is another
  host with another limit. So it should run **alongside** the live queue, both drawing on one list of files, never as
  a stage that must finish first.

## Projected total fetch time

Assumptions: one live process at the logged rate; archive.org at the fetchers' logged 4-worker rate; CC at a few
files a second (minutes for any of these corpora). "Shared list" means live and archive.org take the next file from
one list, so the total is N / (live rate + IA rate) for the files both could serve.

| Host | Live-only | Archive-first as the fetchers run it now | Best within the rules |
|---|---|---|---|
| ACT | 6,694 x 10.5 s = **19.5 h** | Archives first, then live: about 5,980 from IA x 16.5 s = **27 h** (slower than live-only) | **Shared list: 11.9 h (-39%).** With the CC PDFs as a source: about 5,450 from CC in about 30 min, then about 1,250 by live and IA, **about 2 h (-90%)** |
| WA | 12,011 x 2.2 s = **7.3 h** | CC about 5,230 (minutes) + IA about 150 + live about 6,630 x 2.2 s = **4.1 h (-44%)** | The same. IA adds little (234 files beyond CC) |
| Federal | 21,805 x 10 s = 60.6 h = **5.5 days** | EPUB-only: 83 files from IA, so **5.5 days (-0.4%)** | Read unpacked parts. CC about 4,070 (minutes) + IA parts about 3,000 (about 14 to 40 h, round the clock, inside the live window), then live about 14,700 x 10 s = 40.8 h = **about 3.7 days (-33%)**. CC parts alone: 49 h = 4.5 days (-19%) |

## Verdict

1. **WA: archive-first works now.** Common Crawl gives 44% of the files verified, at well over 10 times the live rate.
   It cuts 7.3 h to 4.1 h. Keep it.
2. **ACT: archive.org holds 90% of the Word files, but its shared limiter is slower than the register's 10 s crawl delay.**
   Running archives strictly first makes the fetch slower (27 h against 19.5 h). Change it to one shared list (live and
   IA both taking the next file): 11.9 h. The big prize is Common Crawl's PDFs (81% of files, untruncated, at about
   1.4 s each): about 2 h in all. That needs a PDF reader whose text matches the Word text, which is not yet built or
   checked.
3. **Federal: the EPUB-file route through the archives is a dead end (0.4%).** The archives hold the *unpacked* EPUB
   HTML instead: CC for 21%, and with archive.org about 36%. That is byte-identical to the register's file in 26 of 30
   samples. An "EPUB from parts" reader (with a strict check against the register's size or cover data, and every
   document present) would cut 5.5 days to about 3.7. The live host stays the bottleneck either way.
4. **General lesson.** On crawl-delayed hosts, ask the archives for every *form* the publisher serves (PDF, Word,
   unpacked HTML), not only the form the parser reads. The forms the fetchers skipped are where the coverage was:
   81% for ACT and 21 to 36% for Federal, against 0.1% and 0.4%. archive.org's shared limiter tonight (about 45 s
   queueing per request) makes it useful only in parallel with live fetching, never in front of it.

## Caveats

- The ACT needed list is partial: 291 In Force Acts known so far, with Acts after 2019 still being found.
- Federal's IA parts share comes from 25 titles (790 files), clustered by title: CC's share on the same titles (21.6%)
  matches its overall 20.7%, which suggests the sample is representative.
- CC crawls before 2023 were not read for Federal: the register's current URL scheme starts in 2023.
- archive.org timings depend heavily on how busy the shared limiter is. The transfer itself is 2 to 3 s, so on a quiet
  machine archive.org would beat both crawl delays.
