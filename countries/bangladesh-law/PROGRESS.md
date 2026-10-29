# gitlaw-BD: Bangladesh law history (progress / handoff)

Slug `bangladesh`, repo `lexifina/bangladesh-law` (PRIVATE), clone `C:/Users/alany/Documents/bangladesh-law`.
tz Asia/Dhaka, lang en, future branch `future`. Rules: `scripts/world-law/WAVE.md` -> `scripts/africa-law/FANOUT.md` -> `scripts/south-america-law/BRIEF.md`.

Status at the 00:44 UTC wind-down (2026-10-29): **probe done, nothing parsed, no corpus.json, no PUBLISH.**

## Checklist
- [x] Scaffold confirmed: remote main = b7536f2 "Bangladesh: sources, before any law" (the only commit). Cloned.
- [x] Probe of bdlaws.minlaw.gov.bd (results below)
- [x] fetch.py (curl, sha256(url) cache, 3 req/s per host, UA lexifina-watch, requests.jsonl; `text_of()` decodes the site's UTF-16)
- [x] acts.json (Phase 1 acts and their full-text URLs)
- [x] Full current text cached: act-details-367 (Constitution), -11 (Penal Code), -75 (CrPC); General Clauses Act s.5 page cached
- [x] Wayback CDX listings cached (in .cache) for print_sections_all.php, act-details and pdf_part.php for ids 367, 11, 75
- [ ] parse.py (not started)
- [ ] fetch the archived captures (not started)
- [ ] corpus.json, build in .tmp-build, check.py, --compare, PUBLISH

## Probe results
- bdlaws.minlaw.gov.bd: direct access works (HTTP 200, no bot challenge). robots.txt is a 404 page. Pages are **UTF-16** HTML. No API, no dated versions. Gives current text only, with amendment footnotes in `<span class='footnote'  title='…'>` (two spaces before `title`), plus a `footnoteListAll` list at the end of the page.
- Full act on one page: `/act-details-<id>.html`. Rows `div.row.lineremoves`: `txt-head` = section heading, `txt-details` = body; `act-part-group` / `act-chapter-group` = Part/Chapter headings; `<div class="clbr">` / `<div class="na">` = paragraph breaks.
- Footnote counts: Constitution 106, Penal Code 159, CrPC 599. They name the amending act and section, but often not the old text ("Substituted for the former article 9 …"). They don't record amendments that were later reversed (4th/5th/8th history), so **reversing the footnotes cannot rebuild pre-2011 text honestly.** Don't do it.
- Commencement rule: General Clauses Act 1897 s.5(1)(b) (substituted by P.O. 147 of 1972): an Act of Parliament not expressed to come into operation on a particular day comes into operation on the day its assent is first published in the official Gazette. Source: http://bdlaws.minlaw.gov.bd/act-73/section-19976.html (cached).
- Official English: the Constitution, Penal Code and CrPC all have an official English text on the site, so build in English. The Constitution's Bangla version is act-957; under art. 153 the Bangla text prevails on conflict. Say so in the README.

## Plan (the exact next step)
Build dated versions from **archived observations**, crediting each diff with the footnote's amending act, dated by that act's in-force day:
- Constitution, old-site full text `print_sections_all.php?id=367` (Wayback): 20120320, 20130317 (both after the 15th Amendment, Act XIV of 2011), 20150330 / 20170118 (after the 16th, Act XIII of 2014), 20181108 (after the 17th, Act 29 of 2018). New site `act-details-367.html`: 57 captures from 20191110 to 20260921, plus today's live copy.
  - Oldest version: the 2012 text, `first_law: null`, dated at the 15th Amendment's in-force day. Record that in decisions.
  - Then the diffs: 16th (art. 96) and 17th (art. 65(3)).
- Penal Code: old-site `print_sections_all.php?id=11` captures 20130509, 20150509, 20160214, 20190531; new site 22 captures from 20191017 to 20260525.
- CrPC: old-site `print_sections_all.php?id=75` captures 20130306, 20141011, 20161117; new site 19 captures from 20191017 to 20260925.
- After 2019 the old-site captures (`print_sections_all`, `pdf_part`) are about 1 KB redirect stubs: ignore them. `pdf_part.php` before 2019 is about 10–24 KB, probably only a section index.
- Next: `wayback.get('http://bdlaws.minlaw.gov.bd/print_sections_all.php?id=367', ts='20120320', cache='.cache')` (and the rest). Then write parse.py to normalise old-site and new-site HTML to the same units, so the 2019 site migration isn't counted as changes, and diff.
- Fetch each amending act's bdlaws page for its date and any commencement clause.

## Open issues to state in the README
- The ministry text still shows art. 96 as substituted by the 16th Amendment. It doesn't reflect the Appellate Division's 2017 judgment (review dismissed in 2024), nor the High Court's December 2024 ruling on parts of the 15th Amendment. Report what the source shows; add no text from outside it.
- Cache: about 7 MB in .cache (3 full acts, 2 GCA pages, CDX listings). Requests are logged in .cache/requests.jsonl.
- WebSearch used: 0 of 3. No background processes left running.
