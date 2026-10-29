# gitlaw-UY-3: progress

Owner of `scripts/uruguay-law/corpus.d/60-batch3.json` (+ `60-batch3.PUBLISH`) and `scripts/uruguay-law/batch3/`.

- fetch: `python -X utf8 scripts/uruguay-law/batch3/fetch3.py [slugs]` or `--path P...` (one process; IMPO 10.5 s/request; shared `.cache`). Log: batch3/.tmp/fetch.log.
- build the part: `python -X utf8 scripts/uruguay-law/batch3/batch3.py [slugs] [--dry]` (writes the part atomically + batch3/verification.json); `--vigencia <slug>` lists amending laws' days and candidate vigencia articles.
- batch3.py reuses batch2.build_one (impo_history + batch 2's note readings, post-pass, impo check) unchanged, and adds in its own process only: (1) an original link `<original_prefix>/<n>` for amended articles IMPO gives no TEXTO ORIGINAL link for (used only if IMPO served a non-empty JSON text); (2) trailing section headings dropped from original texts (all caps, or a short unpunctuated line); (3) dotted CNA articles ("Artículo 133.1", key art-133-1): label, quote lookup, and "added by" the earliest law that worded them when the parent's original lacks the number; (4) `suspensions`: wording-unchanged versions for laws that only suspended vigencia (CAROU: Leyes 19.322, 19.394), with a law note; (5) VIGENCIA / LAW_DAY tables read by hand.

## Status (2026-10-29 ~13:30Z): DONE, 60-batch3.PUBLISH written
- [x] Probe: all six candidates on IMPO JSON. LUC (Ley 19.889) dropped: 253 of 476 articles in IMPO's consolidated text are "(*)" pointers to the laws they amended (decision recorded).
- [x] Fetch: 480 IMPO requests at 10.5 s (06:55-08:40Z, round 2 at 12:30Z), all HTTP 200. Each act well under 45 min (CNA ~32 min).
- [x] Código Tributario (codigo-tributario/14306-1974): 10 versions 1974-12-16..2026-01-01, 17 credited unit changes, 13 laws.
- [x] Ley 16.060 (leyes/16060-1989): 21 versions 1989-12-31..2021-01-01, 86 credited unit changes, 21 laws.
- [x] Ley 17.250 (leyes/17250-2000): 7 versions 2000-08-27..2024-01-01, 11 credited unit changes. Ley 20.531 (2027) not in IMPO's text yet.
- [x] CNA (codigo-ninez-adolescencia/17823-2004): 22 versions 2004-09-24..2024-06-02, 150 credited unit changes, 24 laws.
- [x] CAROU (codigo-aduanero/19276-2014): 9 versions 2015-03-18..2025-09-13, 86 credited (incl. 2 x 35 wording-unchanged suspension credits).
- [x] impo_check: today and last version == IMPO for all five; 0 unresolved, 0 placeholders. Law in-force days agree with corpus.json/batch 2 for every shared law (0 mismatches).
- [x] Local verification (scratchpad, docs-date 2026-10-29): 12 acts, 189 versions, 137 commits, 320 tags, 125 laws, 0 unexplained, 0 future; check.py 0 mismatches, 0 trailer errors, 0 backwards, 0 future-dated; --compare identical (history tip f8f07707), main identical on the third rebuild.
- [x] Published acts unchanged: GITLAW_VERIFIED_PARTS_ONLY=1 build (99 commits/214 tags) vs full: all 120 act tags of the 7 published acts have identical act trees; main trees identical.
- [x] Commit messages that change because a law shares its in-force day with a published act (the commit now names the new acts' provisions too, so its hash and every later hash change): Leyes 17.243 (2000-07-16), 17.930 (2006-01-01), 18.214 (2008-01-10), 18.387 (2008-11-02), 18.719 (2011-01-01), 18.996 (2013-01-01), 19.075 (2013-08-01), 19.119 (2013-08-24), 19.149 (2014-01-01), 19.355 (2016-01-01), 19.438 (2017-01-01), 19.889 (2020-07-24), 19.924 (2021-01-01), 20.075 (2023-01-01), 20.141 (2023-06-08), 20.212 (2024-01-01), 20.446 (2026-01-01); plus the docs commit. 17 law commits.
- [x] The docs date of the whole country moves to 2026-10-29 (autopush takes the latest `retrieved`).
- [x] repo/README.md table: rows for batch 2's three codes (were missing) and the five batch-3 acts; two "does not show" bullets (LUC, CT art. 40).
- [x] Nothing pushed or committed.

## Notes for the next agent
- Ley 20.531 (in force 2027-01-01) substitutes Ley 17.250 art. 16 and art. 42 acápite/C/F (and CGP arts 64, 64 BIS): add when IMPO consolidates it (the quotes are cached: leyes/20531-2026/108, /117).
- CT art. 40: words with no recorded amendment (decisions). CNA arts 28, 199: editorial differences from the original (decisions).
- Scratch repos in the scratchpad are disposable.
