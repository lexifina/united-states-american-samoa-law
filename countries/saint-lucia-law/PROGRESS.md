# gitlaw-LC: Saint Lucia law history (handoff, 2026-10-29 00:40 UTC, wind-down)

Slug `saint-lucia`, repo `lexifina/saint-lucia-law` (PRIVATE), clone `C:/Users/alany/Documents/saint-lucia-law`
(scaffold verified 2026-10-28: only `main`, single commit 492a150 "Saint Lucia: sources, before any law").
tz America/St_Lucia, lang en, future branch `future`. Rules: scripts/world-law/FORK.md. Never push; autopush does it.
WebSearch used: 3 of 4.

## Done
- [x] Scaffold check + clone
- [x] fetch.py (curl, sha256(url) cache in .cache/, 3 req/s/host, requests.jsonl); crawl.py (TOC-ordered page crawl);
      sec.py / txt.py (debug viewers); probe_cc.py (archive probe)
- [x] corpus.json (first cut): Constitution, 1 version "oldest version available" from 2023-03-27, 129 units
      (preamble, ss. 1-124 + 108A, Schedules 1-3) from the Revised Laws (2023) HTML. NOT verified; no PUBLISH.
- [ ] Data Protection Act, Criminal Code: not in corpus yet (pages partly cached, see below)

## Sources (probed 2026-10-28)
- Revised Laws of Saint Lucia (2023), https://attorneygeneralchambers.com/laws-of-saint-lucia/<act>/<page>:
  section-level HTML, `<section id="document">`; each provision carries notes "(Amended|Substituted|Inserted|Repealed by
  Act N of YYYY)"; each act's `/act` page lists every amending act with its in-force date. robots allows all. No licence stated.
  Current text only (no dated versions).
- Common Crawl: 0 captures for these act prefixes. archive.org: only 2023+ captures of the same 2023 edition (no older edition).
- NPC (National Printing Corporation, the government printer) https://npc.govt.lc/laws/acts/<year> (2022-2026 acts, PDFs with text layer)
  and `http://npc.govt.lc/files/documents/Constitution of Saint Lucia.pdf` (CACHED: 87 pp, PageMaker print of 9 May 2005,
  text layer; the Constitution AS MADE: s.25(a) still says "thirty years", i.e. before Act 17/1980; has typos vs the Order).
- Act 2 of 2023 and Act 7 of 2023 PDFs CACHED (URLs in .cache/npc_2023.json). 2/2023: assent 8 Mar, in force 9 Mar 2023
  (ss.16(4),18(1),73(5),106 "Her Majesty in Council"->"Caribbean Court of Justice"; 41(7)(a) substituted; s.108 substituted;
  s.108A inserted; s.124 two definitions). 7/2023: assent 22 Mar, in force 27 Mar 2023 (s.36 substituted).
- Revised Edition of the Laws of Saint Lucia 2001 (revision date 31 Dec 2001) came into force 1 May 2006 (S.I. 30/2006,
  CACHED via npc download URL). Supplements: 2013 (S.I. 48/2015, 26 May 2015), 2014 (S.I. 56/2018, 4 Jul 2018),
  2015 (S.I. 130/2019, 23 Sep 2019), 2017 (S.I. 201/2020, 4 Dec 2020), 2019 (S.I. 198/2021, 6 Dec 2021), 2020 (S.I. 156/2022, 7 Nov 2022).

## Plan for the Constitution history (next step)
1. v1 1979-02-22 = NPC 2005 print (first_law si-1978-1901; normalise "a)"->"(a)", "N.-" headings; paragraphs = PDF blocks,
   join blocks starting lowercase non-label across pages; drop CHAPTER/Part heading blocks; stop at "SCHEDULE 2 TO THE ORDER").
2. v2 1980-09-26: s.25(a) "thirty" -> "21" credited to act-17-1980 (act text not online; wording from the revised edition).
3. v3 2006-05-01: revised-edition formal changes (gender-neutral "his or her", numerals) uncredited (publisher), dated by
   S.I. 30/2006; disclose that a later supplement may have made some of them.
4. v4 2023-03-09 (act-2-2023), v5 2023-03-27 (act-7-2023) = current revised text for those sections.
## Other acts
- Data Protection Act (Act 11/2011, amended 2/2015 in force 13 Apr 2015): only Part 1, ss.32-43, Part 6, Sch 2 (a)-(g) in
  force from 31 Jan 2023 (S.I. 4/2023). Build v1 2023-01-31 with only the commenced units (first_law null). Pages cached (86).
- Criminal Code (Act 9/2004, in force 1 Jan 2005; amended 38/2006, 11/2008, 2/2010, 9/2018 + others named in notes):
  ss.1-1264 + Sch 1-8. Crawl stopped at about page 400 of 1309; rerun `python -X utf8 crawl.py criminal-code` (resumes).
  No older text online -> current text as oldest version available, dated by latest in-force date among its notes.

## Commands
    python -X utf8 crawl.py constitution-of-saint-lucia data-protection-act criminal-code   # resumes from cache
    python -X utf8 parse.py                                                                  # writes corpus.json atomically
    python -X utf8 ../gitlaw_common/build.py . --repo .tmp-build --docs-date 2026-10-28 ; check.py as in SCHEMA.md
Still to do: verify Interpretation Act commencement rule (Cap. 1.06) for default_in_force_rule; repo/README.md; PUBLISH.
