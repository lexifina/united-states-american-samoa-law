# Mali (lexifina/mali-law): progress

gitlaw-ML (first pass, to 2026-10-29 00:42 UTC), then gitlaw-ML-2 (finish, 2026-10-29 ~13:30 UTC).
**PUBLISH written 2026-10-29** (remote main was still the scaffold 1649e4e). The push loop publishes main; nobody here
pushes or commits.

## Source
- sgg-mali.ml (Secrétariat général du Gouvernement): every Journal officiel issue 1997–2026 as a PDF with a text
  layer (listing: /fr/journal-officiel/le-journal-officiel.html, 1534 issues), plus "Codes en vigueur"
  (/fr/journal-officiel/les-codes-consolides.html). robots.txt disallows nothing; no licence stated. Direct fetch,
  3 req/s. No LII, Wayback or Common Crawl needed. No OCR.
- Cache: `.cache/` ~411 MB, 809 sgg-mali.ml requests: all JO issues 2013-05-21 → 2026-10-20.
  Unreadable (named in README and decisions): 404 JO n°2020-23 (25 Sep 2020, mali-jo-2020-23.pdf), JO n°2021-04
  (29 Jan 2021, mali-jo-2021-04-3.pdf); not valid PDFs: JO n°2024-32 (8 Sep 2024, mali-jo-2024-32-php-2.pdf, 517 B;
  19 Sep 2024, mali-jo-2024-32-php00-2.pdf, empty).

## Scripts
- `fetch.py` (curl cache, requests.jsonl), `jo_index.py FROM TO --fetch`, `scan.py REGEX FROM TO` (search all cached
  issues for amending laws), `parse.py` (corpus.json), `parse.py --check` (second printings, Codes en vigueur copy,
  coverage of every paragraph/character per act, numbering gaps).
- `repo/`: README.md (English, then French), LICENSE, jurisdiction.json.

## Acts (all built, verified, in PUBLISH)
- [x] Constitution 2023: JO spécial n°13, 22 Jul 2023; 1 version; 191 articles + préambule + plan. Arts 43 and 144
  fixed (they were merged into the preceding CHAPITRE heading). Identical to the JO n°20 reprint.
- [x] Loi 2013-015 (données personnelles): JO n°26, 28 Jun 2013 (69 articles, art. 8 fixed) + Loi 2017-070
  (JO n°53, 29 Dec 2017) replacing arts 21, 25, 36, 42, 49.
- [x] Code pénal 2024 (Loi 2024-027, JO spécial n°21, 13 Dec 2024): 1,125 articles + plan. Duplicate numbers 511-1/2
  and 512-1..9 (Livre V Titre I vs Titres XI/XII) keyed `art-0511-001-titre-i` / `-titre-xi` etc., labelled
  "(Titre N)". Ends at "Bamako, le 13 décembre 2024" (annexed TOC out). Identical to codes/codepenal.pdf.

## What was fixed in parse.py (gitlaw-ML-2)
- HEAD_LINE ended in a literal backspace (\x08, a heredoc artefact) instead of `\b`, so no heading ever matched:
  headings leaked into articles. Fixed (file rewritten with the Write tool; norm() now uses escapes).
- New paragraph at any line starting "Article N :", a heading or "[", across blocks too; at an enumerated item
  ("1°)", "a)", "ii)", "-") after ; : or .; at a new block > 18 pt down the same column (table rows). ']' closes.
- ART_RX accepts "Articles 313-1 :", "Article : 551-7 :", "Article702-1 :".
- units_from: bracketed source notes and numbered sub-headings ("1°) Des …", "II. Des …") go to the plan; wrapped
  headings join with a space ("TITRE V : DES" + "DELITS …"), number-only headings with " : "; one unnumbered
  paragraph (Titre XII opening) kept in the plan; duplicate numbers keyed by Titre.

## Verification (2026-10-29)
- `parse.py --check`: all 4 texts "order and placement ok; text layer identical"; numbering gaps none; Constitution
  2 printings 0 differ; Code pénal JO = Codes en vigueur copy.
- Local build into scratch (docs-date 2026-10-28): 4 commits, 8 tags, check.py 0 mismatches / 0 trailer errors;
  `--compare` rebuild identical (main_identical true).
- BUILD_STATUS.json is written by the push loop; read it after its next pass.

## Phase 2 candidates (all in cache, consolidated by SGG)
- Code de procédure pénale 2024 (JO spécial n°22), Code des personnes et de la famille 2011, Code du travail.

## Open issues
- Default in-force rule: no general delay found; versions dated by JO issue date (recorded in decisions).
- Malian copyright status of official texts not verified; repo stays private.
