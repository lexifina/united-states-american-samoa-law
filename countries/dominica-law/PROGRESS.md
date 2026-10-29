# gitlaw-DM: Dominica law history (progress, HANDOFF at wind-down 2026-10-29 00:42Z)

Slug `dominica`, repo `lexifina/dominica-law` (PRIVATE, never change), clone `C:/Users/alany/Documents/dominica-law`.
Scaffold verified 2026-10-28 23:15Z: only `main`, one commit ff03bfd "Dominica: sources, before any law".
Re-check `git ls-remote` before any PUBLISH. tz America/Dominica, lang en, future branch `future`.
Rules: scripts/world-law/WAVE.md (+ FORK.md, africa-law/FANOUT.md, south-america-law/BRIEF.md). WebSearch used: 0 of 3.

## Status: NOTHING BUILT. No corpus.json, no PUBLISH. No background processes running.

## Checklist
- [x] Scaffold check + clone
- [x] fetch.py (curl, sha256 cache key = URL [+ "\n" + POST body], 1 req/s/host, UA lexifina-watch, requests.jsonl);
      `python -X utf8 fetch.py search <term> [title|year]` lists portal hits; `fetch.py get <url>` caches a file
- [x] Probe of the official portal (below)
- [ ] parse.py / corpus.json  <- NEXT
- [ ] repo/README.md, LICENSE, jurisdiction.json (copy from scaffold, build -> real status)

## Probe findings (2026-10-28)
- https://dominica.gov.dm/laws-of-dominica : Joomla page, search is a POST to `laws-of-dominica?page=1` with
  `searchname=<term>&s=title|year&searchbtn=Search`; results are `<li><a href='<pdf>'>title</a>`. robots.txt allows /laws/.
  Holds "Revised Laws of Dominica 1990, Acts & SROs 1991-2009" plus later Acts (2010-2026). No licence stated.
- **All 1990 Revised Edition chapter PDFs are image scans with NO text layer** (producer MFPImgLib, made 2008-07-28):
  chap1-01.pdf (Constitution Order, 144 pp), chap1-01-sch1.pdf (Constitution, 112 pp), chap12-01.pdf (Criminal Law and
  Procedure Act, 34 pp), chap3-01.pdf (Interpretation and General Clauses Act, 44 pp). No OCR allowed -> no base text
  for the Constitution or Cap 12:01 from the official portal.
- Post-2010 Acts have text layers (Ghostscript): Constitution of Dominica (Amendment) Act 2014, Act 4 of 2014
  (`laws/2014/Constitution of Dominica (Amendment) Act.pdf`, 10 pp, assent + Gazette 8 Jul 2014; CCJ as final court;
  amends ss 16, 17, 42, 72, 104, 106 (replaced), 106A (new), 121, Sch 2 of the Order); Electronic Transactions Act 2013,
  Act 19 of 2013 (`laws/2013/Electronic Transactions Act, 2013 Act 19 of 2013.pdf`, 40 pp, text layer OK).
- Commencement order for Act 4/2014 is listed (SRO 4 of 2015, `laws/2015/Constitution of Dominica (Amendment)
  (Commencement) Order, 2015.pdf`) but GET returned 404; retry with the comma percent-encoded (%2C), or via Wayback.
- Cap 12:01 amending Acts listed: 10/1992, 13/1993 (laws/1992/act10-1992.pdf, laws/1993/act13-1993.pdf), 2/2013,
  11/2013, 3/2014 (URLs via `fetch.py search criminal`). Not fetched yet; 1990s ones may be scans too.
- Wayback CDX for prefix dominica.gov.dm/ cached in .cache/wb (32,093 captures, 11,366 URLs): only the same chapter PDFs
  (scans), no text edition of the Constitution. houseofassembly.gov.dm is a stub; AG chambers page has no laws.
- Cache: 14 MB, 15 portal requests + 1 CDX request.

## Next step (exact)
1. Per FORK.md rule 1, build the Electronic Transactions Act 2013 (Act 19/2013, text layer) as its first version
   (first_law = act-2013-19, in force per its s.1 commencement; check for an SRO/commencement and any amendments
   via `fetch.py search electronic` / year search). Write corpus.json atomically, then verify word-for-word vs the PDF.
2. Find a text-layer official Constitution: try Wayback/Common Crawl of other gov.dm hosts (electoraloffice.gov.dm,
   presidentoffice.gov.dm, opm.gov.dm, news.gov.dm) for a constitution PDF; else spend 1 WebSearch. If none, the
   Constitution cannot be built without OCR: say so in README; Act 4/2014 alone cannot be replayed without a base.
3. Same scan problem for Cap 12:01; consider post-2010 core Acts with text layers instead (e.g. Electronic Evidence
   Act 13/2010, Criminal Justice (Reform) amendments) as Phase 1 substitutes, noted in decisions.
4. Default in-force rule: Interpretation and General Clauses Act Cap 3:01 is a scan; cite the rule from a text source
   (Act 10 of 2024 amends it and has text) or the Act's own commencement section.

## Open issues
- Commencement order SRO 4/2015 URL 404 (likely URL encoding of the comma; not a site outage).
