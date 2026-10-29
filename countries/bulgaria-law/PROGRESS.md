# Bulgaria (gitlaw-BG, world wave): progress / handoff

## gitlaw-BG-2 (2026-10-29, done): Constitution history 2008-2024, 4 versions; PUBLISH rewritten
- Versions: 2008-01-01 oldest available (capture 20101222212318; publisher; earlier_laws = 6 events 1991-2007;
  dated by 2007 law § 13), 2015-12-21 dv-2015-100 (capture 20160125101631; 10 provisions, all noted),
  2023-12-25 dv-2023-106 (8 provisions) + 1 unexplained publisher commit (14 placeholders + 5 editorial edits),
  2024-08-09 dv-2024-66 (14 provisions). 5 history commits, 7 tags.
- parse.py: one html_lines + split_units path for the API and the old server-rendered page; header parses month
  names ("18 Декември 2015г."). Today's text is byte-identical to the previously published corpus except the
  three stray U+001F dashes (чл. 22, 25, 150), now "-" (the 2010 page has U+00AD there). RETRIEVED -> 2026-10-29
  (requests.jsonl: 00:01:43 UTC on 10-29). `--out PATH` writes elsewhere than corpus.json.
- fetch.py --history: read 46 of 314 old-page captures (first per quarter + bisection) + the 2 API captures,
  wrote wayback_survey.json. Two texts only: 2010-12-22..2016-01-16 and 2016-01-25..2021-05-06. The API capture of
  2021-06-29 parses identical to the 2021-05-06 page (redesign invariance test); the API capture of 2025-08-20 is
  byte-identical to today's response. Cache .cache/wb 8.2 MB, 52 archive.org requests.
- No text exists for 2023-12-25..2024-08-08 (old page ends 2021-05, API captured only 2021-06-29 and 2025-08-20;
  Common Crawl index unreachable, connect timeout). The 2023 version applies the coordinator's text-before-its-law
  rule: the 14 provisions naming КС 13/2024 read "[Източникът не дава текста, действащ на тази дата.]".
- Verified: scratch build (scratchpad, --docs-date 2026-10-29) check.py 0 mismatches, 0 trailer errors;
  --compare identical (history tip 7373266, main e64210b). corpus.json sha256 fef45d5f…; verification.json updated.
- README version table, dates, sources, Bulgarian section and jurisdiction.json "build" updated.
- Open: Penal Code / ЗЗЛД still not started; Common Crawl could fill 2023-2024 if its index comes back
  (crawls CC-MAIN-2024-10..33, URL www.parliament.bg/api/v1/nav/bg/const).

Status 2026-10-29 (gitlaw-repair): **PUBLISH written.** parse.py fixed: it now derives the 9 law keys
(dv-YYYY-N, issue dates, КС decisions as `court`) from the source's own header and writes them as `earlier_laws`; its
output is byte-identical to the corpus.json that was hand-patched at 00:43. The NotADirectoryError was the missing
target folder: building into an existing empty folder works. Scratch build (--docs-date 2026-10-28): 2 commits
(oldest version + docs), 1 tag; check.py 0 mismatches, 0 trailer errors; --compare identical. Sanity: arts. 1-169 all
present, plus 91а, 91б, 130а-в, 132а. Remote main re-checked read-only (shallow clone): 6010c47 "sources, before any
law", the scaffold. The 04:51 UTC autopush pass had already pushed this corpus to `preview` (3e34d4b, 0 mismatches).
Open: `repo/` has only jurisdiction.json; no README.md/LICENSE yet (the scaffold README and SOURCES.md will be replaced
by the first main build; their one source row is also in the world-law register).

Earlier status 2026-10-29 00:44 UTC: wound down on the coordinator's order.

- Scaffold checked at start: lexifina/bulgaria-law main = 6010c47 "Bulgaria: sources, before any law" only. Recheck before any PUBLISH.
- Clone: C:/Users/alany/Documents/bulgaria-law (scaffold only; autopush owns it).

## Built
- `corpus.json`: Constitution only, one "oldest version available" version (first_law null, publisher credit), 192 units
  (preamble, art-NNN, chapter headings, transitional sections), dated 2024-08-09 (КС Решение № 13/2024, ДВ бр. 66 от 06.08.2024, +3 days, чл. 151 ал. 2).
- Laws dict holds the 9 DV events (1991, 2003, 2005, 2006, 2006 КС, 2007, 2015, 2023, 2024 КС) as earlier_laws.
  **Open bug:** parse.py still writes earlier_laws as display strings; the keys were patched into corpus.json by hand at 00:43.
  Move the `laws` list (keys dv-YYYY-N) into parse.py before the next run.
- A test build into `.tmp-build` failed: first the earlier_laws keys (fixed in corpus.json), then `NotADirectoryError` in build.py
  (probably the `.tmp-build` target was missing; create it first). check.py has not run.

## Sources (probed)
- parliament.bg API `https://www.parliament.bg/api/v1/nav/bg/const`: the official consolidated Constitution (JSON, HTML body),
  with per-paragraph notes "(Нова/Изм./Отм. - ДВ, бр. N от YYYY г.)". Cached in `.cache/`. Current text only, no old versions.
  Other API routes (from /js/app.js): `/act/<id>`, `/bill/<id>`, `/pl-doc/...`: adopted laws as passed. Not yet probed.
- dv.parliament.bg: connection refused/timeouts from this machine (ports 80 and 443). Use archive.org / Common Crawl.
- lex.bg: private, robots.txt `Disallow: /` for all but search engines. Read only via archives, if at all. Not official.
- archive.org: "Temporarily Offline" at 00:35 UTC; CDX for parliament.bg/bg/const not obtained.

## Next steps
1. ~~Fix parse.py's laws/earlier_laws; build; check; PUBLISH~~ done 2026-10-29. Next: write repo/README.md (English, then Bulgarian) and LICENSE.
2. Older Constitution versions: Common Crawl / Wayback captures of the old server-rendered parliament.bg/bg/const (2008-2020),
   plus DV amending acts (via archive) for 2003-2007 and the 1991 text; credit from the inline notes.
3. Наказателен кодекс and Закон за защита на личните данни: check cpdp.bg (ЗЗЛД, official) and the parliament.bg `/act/` texts.
WebSearch used: 1 of 3.

## Coordinator (2026-10-29)
PUBLISH renamed to .PUBLISH.held until repo/README.md (English, then Bulgarian) and repo/LICENSE exist; restore it then.

## gitlaw-docs (2026-10-29)
repo/README.md (English, then Bulgarian) and repo/LICENSE written (scaffold README/SOURCES facts folded in). Scratch
rebuild with them (--docs-date 2026-10-28): check.py 0 mismatches, 0 trailer errors; --compare identical (history tip
982953d, unchanged). Remote main re-checked read-only: still 6010c47 (scaffold). `.PUBLISH.held` renamed back to `PUBLISH`.
Lead for history: `.cache/wb/` holds a Wayback CDX listing with 545 captures under parliament.bg/bg/const (2010-2026).
