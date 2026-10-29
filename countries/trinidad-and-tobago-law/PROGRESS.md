# gitlaw-TT: Trinidad and Tobago law history (HANDOFF, wound down 2026-10-29 00:40 UTC)

Slug `trinidad-and-tobago`, repo `lexifina/trinidad-and-tobago-law` (PRIVATE), clone `C:/Users/alany/Documents/trinidad-and-tobago-law`
(scaffold verified: only `main`, one commit 56be976 "Trinidad and Tobago: sources, before any law"). tz America/Port_of_Spain,
lang en, future branch `future`. Rules: scripts/world-law/FORK.md. Never push; autopush owns the clone.

## Done
- corpus.json: Constitution, 1 version (from 2016-12-31, "oldest version available", first_law null, publisher credit),
  154 units (preamble, sec-001..sec-143 incl. 141-a..d etc., schedule-1..3). NOT verified -> no PUBLISH yet.
- fetch.py (curl, sha256(url) cache in .cache/, requests.jsonl), sources.py (laws.gov.tt act page -> versions/amendments),
  layout.py (PDF -> paragraphs + margin notes; 312pt column, 120-432 even / 180-492 odd pages), parse.py (cache -> corpus.json).

## Sources (all cached in .cache/, archive.org copies in .cache/wb/)
- Constitution itself: https://rgd.legalaffairs.gov.tt/Laws2/Constitution.pdf (live, "UPDATED TO 31ST DECEMBER 2016", 118 pp, text layer).
  Archived same URL (wayback.get, cached): 20121013 (updated to 31 Dec 2009, LRO 1/2009), 20130512 (31 Dec 2011),
  20140124 (31 Dec 2012), 20150319 (31 Dec 2013), 20170329 (31 Dec 2015), 20200528 (= live, 2016), 20120511 (LRO 1/2009).
  Front page "Amended by" list ends at 12 of 2007, so these editions should differ only editorially.
- laws.gov.tt Digital Legislative Library: per act (currentid) versions "as at 31 Dec" 2004/2007/2009/2012/2014/2015/2016 + amending
  Act PDFs. ids: Chap 1:01 Act=530 (NOT the Constitution text; Act + subsidiary only), Data Protection 22:04=80855,
  Criminal Offences 11:01=472, Companies 81:01=608. All their version PDFs are cached (fetch.py). Pre-2004 editions are scans (skip).
- Live current texts also at https://rgd.legalaffairs.gov.tt/laws2/alphabetical_list/lawspdfs/<chap>.pdf (22.04, 11.01, 1.01, 3.01 cached).
- Post-2016 Constitution amendments (Act 14 of 2024, Act 6 of 2025) exist only as amending-Act PDFs on laws.gov.tt (not fetched).
- Commencement rule: not yet found in Interpretation Act Chap 3:01 (cached); search its text for the Gazette/assent rule.

## Resume (exact next steps)
1. `python -X utf8 parse.py` (cache only). Verify the 2016 Constitution units against the PDF (word counts both ways, as
   scripts/guyana-law/verify.py does); spot-check section split (bold section number = new unit). Then write PUBLISH.
2. Add the archived Constitution editions (2009, 2011, 2012, 2013, 2015) as earlier versions dated by their "updated to" date;
   diffs uncredited unless a margin citation names an Act.
3. Data Protection (versions 2012-2016 share one 2013 PDF build; partially proclaimed: LN 2/2012, LN 220/2021) and
   Criminal Offences (2004-2016 editions; Act 13 of 2014) with the same layout.py; Companies is Phase 2.
