# Burkina Faso (gitlaw-BF): progress

Repo: lexifina/burkina-faso-law (PRIVATE). tz Africa/Ouagadougou, lang fr, future branch `futur`, on-date tool
`tools/en_vigueur_au.py`. Clone (autopush-owned): C:/Users/alany/Documents/burkina-faso-law.

## Checklist
- [x] Probe sources (2026-10-28/29)
- [x] fetch.py (curl, sha256(url) cache, requests.jsonl), anindex.py, anpdf.py (Assemblée nationale répertoire)
- [x] parse.py -> corpus.json: Constitution only (1 version, 2015-11-26, LegiBurkina 2015 consolidation) — 2026-10-29
- [ ] Code pénal 2018 / Loi 001-2021: not built (see below; neither can reach today's text)
- [x] repo/README.md (EN + FR), LICENSE, jurisdiction.json, tools/en_vigueur_au.py — 2026-10-29
- [x] scratch build + check.py (0 mismatches, 0 trailer errors) + --compare (identical) — 2026-10-29
- [ ] PUBLISH: NOT possible (see "Why nothing is on main"); corpus streams to `preview` only

## Sources (probe)

| Source | Status | Format | Dated versions | Notes |
|---|---|---|---|---|
| LegiBurkina (legiburkina.bf, SGG-CM) | host down (connect timeout) | was SharePoint + JO HTML | archived consolidations only | Wayback: 5,620 captures 2001-2019. Constitution consolidated after Loi 001-2002/AN (`SitePages/Constitution/c-2012.pdf`, misnamed, text layer, capture 20150615224134); HTML Constitution `SitePages/preambule.aspx`, `titre1..16.aspx` (captures 2015-09-16), consolidated after Lois 023-2012/AN and 033-2012/AN; promulgation decrees 1997-063, 2000-151, 2002-038, 2009-438, 2012-428, 2012-616 are scans (no text layer) |
| Assemblée nationale / ALT / ALP (assembleenationale.bf) | 200, robots `Disallow:` empty | Laravel pages; law PDFs under /storage/Loi/ | adopted texts, adoption date; promulgation date in list (some placeholders: 31/12/2018, 01/01/1900) | Répertoire `/loip?page=1..14` (271 rows, 2018-2024) + detail pages `/loip/<n>` (n up to 443, 2026) |
| sggcm.gov.bf | 500 | | | |
| conseil-constitutionnel.gov.bf, sgg.gov.bf | connect timeout | | | |

Texts found on the Assemblée nationale (text layer unless noted):
- Loi n°025-2018/AN portant code pénal (loip/356), adopted 31 May 2018, 304 pp, text layer. List promulgation "31/12/2018" is a placeholder used for every 2018 law.
- Loi n°001-2021/AN (données à caractère personnel) (loip/143), adopted 30 March 2021, promulgated 15/04/2021 (list), 36 pp text layer. Art. 82 repeals Loi 010-2004/AN.
- Loi constitutionnelle n°045-2023/ALT du 30 décembre 2023 (loip/64), 10 pp text layer; promulgation "01/01/1900" (unknown).
- Loi constitutionnelle n°033-2024/ALT du 29 octobre 2024 (loip/125), promulgated 21/11/2024 (list): SCAN, no text layer. PV of the sitting has a text layer (debate transcript, not the law text).
- Loi constitutionnelle n°004-2026/ALT (loip/410): no law PDF (only PV + compte rendu).
- Loi n°009-2026/ALT portant révision de la Charte de la Transition (loip/415): no law PDF.
- Loi n°037-2026/ALP portant protection des personnes à l'égard du traitement des données à caractère personnel (loip/441): no PDF, no dates.
- Code pénal amendments: Loi n°044-2019/AN du 21 juin 2019 (named in UN CCPR/C/BFA/2; not on the AN site); a new Code pénal was adopted 20 Oct 2026 (press), not on the AN site yet.

## Handoff (wind-down 2026-10-29 ~00:40 UTC)

**Built:** nothing yet. There is no corpus.json and no PUBLISH, on purpose: no act reaches today's official text (see below).

**Cached** (`.cache/`, 35 MB, 619 requests in requests.jsonl):
- All Assemblée nationale `loip/1..443` detail pages and list pages 1–14. The title index is in `.tmp/anall.txt`, and the list rows with dates are in `.tmp/anindex.txt`.
- Law PDFs for loip 356 (Code pénal), 143 (Loi 001-2021), 64 (045-2023/ALT) and 125 (033-2024/ALT, a scan), plus the PV and CRA PDFs for 125 and 410.
- Wayback captures of LegiBurkina: `c-2012.pdf` (2002 consolidation), `codes/constitution_du_burkina_faso.htm` (2002 capture), `La_constitution.aspx`, `preambule.aspx`, `titre1.aspx`, the six decree PDFs (all scans), `c-rhv.pdf` (1977 Constitution) and `KIKI AN VII-330.pdf` (scan).
- CDX listings: LegiBurkina (`.probe_ia.txt`) and sggcm.gov.bf (`.tmp/sggcm_ia.txt`, 8,392 captures, 2016–2019, with JO item pages such as `index.php/item/285-jo-07-01-16`).

**Exact next step:**
1. Write parse.py. Constitution v1 comes from `c-2012.pdf`: from 2002-02-05 (Décret 2002-038/PRES, stated on the document), with `first_law` null and `earlier_laws` set to the 1991 kiti and the 1997, 2000 and 2002 laws. Strip the footnote markers "(1)" and the footnote paragraphs.
   - Constitution v2 is the 2015 HTML pages (`preambule` plus `titre1..16.aspx`), consolidated after Lois 023-2012/AN and 033-2012/AN. Its in-force date is still unsourced: the promulgation decrees 2012-428 and 2012-616 are scans. Look in the sggcm JO item pages and the LegiBurkina `m/Sommaires_JO` captures for the decree dates.
   - Then apply 045-2023/ALT (text layer, "Au lieu de / Lire" format plus restated titles). Its promulgation date is unknown: the AN list says 01/01/1900.
   - 033-2024/ALT (promulgated 21/11/2024, scan) and 004-2026/ALT (no text) cannot be applied. Name both in decisions and the README, and leave the Constitution on preview.
2. Code pénal: one version, Loi 025-2018/AN as adopted 31 May 2018 (articles are `Article 111-1 :` etc.; key them as `art-111-001`). The promulgation date still needs a source, because the AN "31/12/2018" is a placeholder. Loi 044-2019/AN (21 June 2019) is not online, and the 2026 recast was adopted 20 Oct 2026 and is not online. Preview only.
3. Loi 001-2021/AN: one version from 2021-04-15 (promulgation per the AN list; Constitution art. 48 as the in-force rule: a law not promulgated in time "entre automatiquement en vigueur", so promulgation is what puts it in force). Loi 037-2026/ALP (same title, loip/441) has no text and no dates, so whether it is in force is unknown. Preview only unless its promulgation status is found.
4. Write repo/README.md (EN + FR), LICENSE, jurisdiction.json (clone the scaffold first) and tools/en_vigueur_au.py, then do a test build into `.tmp-build`.

**Open:** no bugs. WebSearch: 3 of 4 used. No background processes are running.

## Session gitlaw-BF-GQ (2026-10-29, from ~05:10 UTC)

Remote check (read-only, ls-remote): `main` = 3bf244a "Burkina Faso: sources, before any law" (scaffold), `wip` = f6698a6. Untouched.

**New official portal found** (via the Wayback copy of the sggcm.gov.bf news item "le Secrétariat général du Gouvernement lance LegiBurkina et JOBF", capture 20250414010544):
- **LegiBurkina, relaunched** at `https://www.legiburkina.gov.bf` (Laravel + Inertia; robots `Disallow:` empty; parametre created 2026-09-07; "SGGCM/DSI @2025 - Tous droits réservés"). Lists are `/textesFondamentaux`, `/textesLegislatifs`, `/textesReglementaires` … with `?search=`; the page JSON is in `data-page`; files at `/documents/<uuid>/download`. Counts: 4 fundamental, 1,162 legislative, 6,388 regulatory texts.
  - "Constitution du 02 juin 1991, révisée en 2015" (b157d74c…): **born-digital text layer**, 59 pp, Word 2010 → Ghostscript, title "Constitution consolidée après la relecture du 05 nov 2015-VF", Assemblée nationale consolidation with per-provision footnotes naming the revising law. Lists every revision law and promulgation decree (1991 kiti … Décret 2015-1396/PRES-TRANS du 26 novembre 2015).
  - Loi 004-2026/ALT du 20 janvier 2026 (révision de la constitution): 1-page **scan**, no text layer.
  - Loi 072-2015/CNT: 54-page scan. Loi 001-2021/AN on LegiBurkina: scan (the AN copy has a text layer).
  - Loi 037-2026/ALP du 03 août 2026 (données personnelles; promulgated by Décret 2026-1034/PF du 22 septembre 2026; art. 68 repeals Loi 001-2021/AN): a scan with the **publisher's OCR layer** ("BURICINA", run-together words). Not usable under the no-OCR rule.
  - 045-2023/ALT and 033-2024/ALT are not on LegiBurkina; no promulgation decree for either was found there.
- **JOBF** (`https://jobf.gov.bf`): a React app for paid subscriptions (mobile-money payment routes in app.js). Not an open source.

**Decision:** the Constitution is built on `preview` only, from the 2015 consolidation (one version, from 2015-11-26, the promulgation decree printed on it). It cannot reach today's text: 033-2024/ALT and 004-2026/ALT are scans, and 045-2023/ALT has no sourced promulgation date. No PUBLISH.

## Why nothing is on main (yet)
Every Phase 1 act has a later change whose official text is not online with a text layer (Constitution: 2024 scan,
2026 no text; Code pénal: 2019 amendment not online, 2026 recast; données: Loi 037-2026/ALP not online). So today's
text cannot be shown to equal the latest official expression, and the PUBLISH gate cannot be met honestly.

## Build result (gitlaw-BF-GQ, 2026-10-29)
- `corpus.json`: act `constitution`, 1 version from 2015-11-26 (Décret 2015-1396/PRES-TRANS, listed on the cover), 179 units (preamble, 177 articles incl. 13.1, 96.1, 160.1–160.6, `structure`), `first_law` null, `earlier_laws` = 1991 Constitution + 8 revision laws. Source sha256 94a1b33b… (LegiBurkina b157d74c…/download).
- parse.py: PyMuPDF; drops spans < 11 pt and superscripts (footnotes 9.8 pt, markers 6–9 pt); keeps 9.8 pt list dashes at x 85–100 when their row has body text; paragraphs by sentence end + vertical gap (> 21 pt) or short line; art. 101 layout split ("… indemnités ; La loi détermine …"). Deterministic (same md5 twice).
- Scratch build (scratchpad/bf-build, --docs-date 2026-10-29): 1 law commit + docs; check.py 0 mismatches / 0 trailer errors; `--compare` identical (history tip 43cf785).
- No PUBLISH: today's Constitution needs 045-2023/ALT (undated), 033-2024/ALT (scan), 004-2026/ALT (scan).

**Next steps if resumed:** (1) find a dated source for 045-2023/ALT's promulgation and a text layer for 033-2024/ALT / 004-2026/ALT (JOBF is paywalled; try Common Crawl for assembleenationale.bf / presidencedufaso.bf / lefaso.net-hosted official PDFs); (2) add earlier versions from the Wayback LegiBurkina captures (2002 `c-2012.pdf`, 2012 HTML titres) with credits from the 2015 consolidation's footnotes.
