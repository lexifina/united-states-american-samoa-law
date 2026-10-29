# gitlaw-LR: Liberia law history (progress / handoff, 2026-10-29 00:43Z)

Slug `liberia`, repo `lexifina/liberia-law` (PRIVATE), clone `C:/Users/alany/Documents/liberia-law` (autopush owns it).
tz Africa/Monrovia, lang en, future branch `future`, on-date tool = builder's `tools/on.py`.

## Status: Phase 1 built, verified, PUBLISH written (00:42Z)
- Constitution 1986: 1 version (1986-01-06, WIPO Lex), 112 units, credited to constitution-1986. No amendment applied.
- Penal Law Title 26: 4 versions 1978-04-03 / 1985-07-09 / 1994-12-06 / 2006-01-17, 214-215 units, rebuilt only
  from LiberLII's own dated notes (see decisions in parse.py).
- Freedom of Information Act 2010: 1 version (2010-10-06), 59 units, credited to foi-act-2010.
- Local build: 6 history commits + docs, 9 tags; check.py 0 mismatches; --compare main_identical; autopush preview
  earlier pushed 48f2d7a (same as local build then). verify.py: 0 words added in all 3 acts.

## Files
fetch.py (Cache from peachjam.py read-only for direct hosts; archive.org via gitlaw_common/wayback.py), parse.py,
verify.py, sources.json (pinned captures), wb_index.json (CDX listing of liberlii.org/lr/legis/, 186 rows),
repo/README.md, repo/LICENSE, repo/jurisdiction.json, PUBLISH.

## Cache (.cache/)
Pinned Wayback captures: constitution col1986235 (20240524225821), penal plt26lcolr367 (2017-04-20 and 2026-07-03,
byte-identical), foia222 (20240630082656), cplt2lcolr491 Criminal Procedure (20170809005959), cplt1lcolr470 Civil
Procedure (20220424112734), gclt15lcolr538 General Construction Law. Direct: WIPO Lex 8556, emansion/moj PDFs
(scans), ACE NEC Referendum Regulations 2011 PDF, liberlii robots.txt.

## Findings
- No government source with a text layer: emansion.gov.lr (Data Protection Act 2026, Cybercrime Act 2025) and
  moj.gov.lr (FOI, Police Act) PDFs are scans; legislature.gov.lr does not resolve; necliberia.org 403.
- LiberLII = AustLII-style single pages, no dated versions; Penal Law prints dated annotations; Criminal Procedure Law
  footnotes quote repealed §§ 31.3, 32.1 (repealed by the Penal Law Act, 1978-04-03), but no CPL effective date.
- 2011 referendum Prop. 4 (Art. 83(b)) outcome disputed (NEC: failed; LoC blog: Supreme Court overturned NEC). No
  text-layer wording found; not applied, stated in README.
- Common Crawl index (index.commoncrawl.org) refused connections at 22:00Z; archive.org was throttled.

## Next steps
1. Criminal Procedure Law (cached): find a sourced effective date for Title 2 (e.g. its enacting act), then build
   v1 with §§ 31.3/32.1 from the footnotes and v2 1978-04-03 credited to penal-law-1976.
2. Civil Procedure Law (cached): footnote [17] gives INA Decree No. 20 of 24 Dec 1985; needs a Title 1 effective date.
3. Other LiberLII acts/codes in wb_index.json (each one page, one version).
4. Search for a primary text of the 2011 Art. 83(b) amendment / Supreme Court ruling (LiberLII /lr/cases/ via Wayback).

## WebSearch used: 2 of 4
## Open issues: none in the shared builder or adapter (no ISSUES file).
## Background processes: none running.
