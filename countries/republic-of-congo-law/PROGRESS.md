# Republic of the Congo (gitlaw-CG): handoff, 2026-10-29 00:36 UTC

Repo lexifina/republic-of-congo-law: still the bare scaffold (only `main`, one commit 75bae0b "Republic of Congo: sources, before any law", checked at start).
Clone: C:/Users/alany/Documents/republic-of-congo-law (autopush owns it; never build into it or push). tz Africa/Brazzaville, lang fr, future branch `futur`.

## Done
- [x] Probe. sgg.cg (SGG) answers 200 direct; robots.txt allows all. It has: the JO archive as PDFs (`/JO/<year>/congo-jo-<year>-<n>[-sp].pdf`, text layer on recent issues), an HTML consolidation of the 2015 Constitution (editorial: drops some "(90)"-style figures, recases words; cross-check only), a search page (`/droit-congolais/recherche.html?field_titre=...&field_idType=12`) that lists "Modifié par" chains, and 18 "codes consolidés" PDFs. cour-constitutionnelle.cg has an expired TLS certificate (not used). No Common Crawl / archive.org needed so far.
- [x] fetch.py (curl, sha256 cache in `.cache/`, requests.jsonl, ~3 req/s), jo_text.py (two-column JO PDF -> paragraphs: bands, columns, gap/short-line paragraph rules, dehyphenation), parse.py -> corpus.json (written atomically).
- [x] Constitution 2015: 2 versions. 2015-11-06 as promulgated (JO 2015 éd. spéciale n° 8; art. 246 = in force on promulgation), 247 units (préambule + art. 1-246). 2022-01-10: art. 157 replaced by Loi constitutionnelle n° 2-2022 (JO 2022 éd. spéciale n° 1).
- [x] Loi n° 29-2019 (données à caractère personnel): 1 version, 2019-11-07 (JO n° 45), art. 1-101; SGG lists no amendment.
- [ ] NOT verified, so no PUBLISH. Not built with the shared builder or check.py yet.

## Next step to resume
1. `python -X utf8 parse.py` (cache only), then write verify.py: compare letters+digits per article of the parsed text against the raw JO page text (and, as a soft check, the SGG HTML lines, expecting editorial differences), and eyeball paragraph splits (the preamble and columns-boundary paragraphs) and hyphen joins.
2. Test build: `python -X utf8 ../gitlaw_common/build.py . --repo .tmp-build --docs-date 2026-10-28`, then check.py against `.tmp-build`; then `--compare` rebuild.
3. Re-run `git ls-remote https://github.com/lexifina/republic-of-congo-law.git` (must still be the scaffold), then write PUBLISH.
4. Write repo/README.md (English first, then French) + keep scaffold jurisdiction.json in repo/.
5. Phase 2 candidates: Code de procédure pénale 1963 (sgg.cg/codes/congo-code-1963-procedure-penale.pdf, check text layer) with CC decisions 2012-68 / 2013-78/79 on art. 172; Code du travail; recent codes with text layers (Code pénitentiaire 2022, Code du sport 2023, Code minier 2026).

## Not possible
- Code pénal: the SGG lists "code pénal du Congo (Arrêté du 13 février 1882)", i.e. the French code as applied, not published in the JO, no text on sgg.cg; amendments are scattered ordinances. Skipped (45-minute rule).
- Code de la famille 1984: SGG PDF is a scan, no text layer (no OCR rule).

## Sources and cache
- Cache: `.cache/` (sha256(url) names, requests.jsonl). About 12 requests, ~9.5 MB (mostly the scanned Code de la famille).
- JO PDFs used: https://sgg.cg/JO/2015/congo-jo-2015-08-sp.pdf, https://sgg.cg/JO/2022/congo-jo-2022-01-sp.pdf, https://sgg.cg/JO/2019/congo-jo-2019-45.pdf.
- WebSearch used: 0 of 4.
