# gitlaw-UY-batch2: progress

Owner of `scripts/uruguay-law/corpus.d/50-batch2.json` (+ `50-batch2.PUBLISH`) and `scripts/uruguay-law/batch2/`.

- fetch: `python -X utf8 scripts/uruguay-law/batch2/fetch2.py [slugs]` or `--path P...` (one process; IMPO 10.5 s/request, robots Crawl-Delay 10; shared `.cache`). Log: batch2/.tmp/fetch.log.
- build the part: `python -X utf8 scripts/uruguay-law/batch2/batch2.py [slugs] [--dry]` (writes the part atomically + batch2/verification.json); `--vigencia <slug>` lists amending laws' in-force days and candidate vigencia articles.
- batch2.py imports impo_history (no copy) and patches, in its own process only: NOTE kinds "derogado anteriormente por"/"redacción derogada por"/"reincorporado por", "Ordinal" scopes, decree-laws (decreto-ley-N keys, kind decree), extra vigencia readings (LAW_DAY), ordinal-only quotes refused, and text cleanup in impo_paragraphs (empty `<a>` anchors, `<center>` headings, inline "(*)" markers). Post-passes: first text from earlier law, article vigencia, absent between repeal and revival, anachronism rule, and `whole_rewrites` (Código de Comercio Libro IV).

## Status (2026-10-29 ~01:20Z): DONE, PUBLISH written
- [x] CGP (codigo-general-proceso/15982-1988): 28 versions 1989-11-20..2026-01-01, 300 credited unit changes; first version = oldest available (Ley 15.982 + Ley 16.053, in force before the code).
- [x] Código de Comercio (codigo-comercio/817-1865): 14 versions 1866-01-24..2020-07-24, 37 credited unit changes. 2 vigencia articles fetched this session (decretos-ley/14701-1977/127, leyes/16060-1989/511) + leyes/1422-1878, leyes/2666-1900 (headers). Libro IV ranges (arts 1523-1781, 1764-1785): 1865 text, placeholder from 1879-02-01 (Ley 1.422, day from IMPO's summary), removed 2008-11-02 (Ley 18.387).
- [x] CPP (codigo-proceso-penal-2017/19293-2014): 12 versions 2017-11-01..2026-09-24, 114 credited unit changes; earlier_laws keys now present (the 00:44Z autopush failure is fixed).
- [x] impo_check: today and last version == IMPO consolidated text for all three.
- [x] Local verification: full build (corpus.json + part) into `.tmp-build/b2`, docs-date 2026-10-28: 99 commits, 214 tags, 92 laws, 0 unexplained, 0 future; check.py: 7 acts, 120 versions, 0 mismatches, 0 trailer errors, 0 backwards, 0 future-dated; `--compare` (`.tmp-build/b2cmp`) identical + main_identical.
- [x] Published acts unchanged: `GITLAW_VERIFIED_PARTS_ONLY=1` build without the part (`.tmp-build/base`, 64 commits/129 tags) vs full build: all 66 act tags and HEAD trees of constitucion, codigo-civil, codigo-penal, ley-18331 identical. Overlapping law entries (10 keys) are identical in both files.
- [x] `corpus.d/50-batch2.PUBLISH` written. Nothing pushed or committed (the 4-hourly autopush publishes).

## Open / notes for the next agent
- CGP: Ley 20.531 (in force 2027-01-01) not yet in IMPO's consolidated text; add when IMPO consolidates it.
- Código de Comercio: arts 66 and 382 differ from the 1865 original in punctuation/one word with no amending law recorded (sample of 12); kept as IMPO's text, not committed as changes.
- Main corpus.json (not batch2) keeps 5 inline "(*)" markers that batch2 strips; left alone so the published acts do not change.
- Old test dirs batch2/.tmp/uy, uyrepo, uyrepo2 are disposable.
