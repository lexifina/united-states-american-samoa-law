# Togo (TG): progress of gitlaw-TG (resumed by gitlaw-SN-TG, 2026-10-29)

Repo lexifina/togo-law (private). Language fr, tz Africa/Lome, future branch `futur`, on-date tool `en_vigueur_au`.
Remote main = scaffold 26f4786 ("Togo: sources, before any law" + the scaffold's "Paused, not yet law" README note),
checked read-only 2026-10-29. preview = a33a6c3 (the earlier first cut, superseded). No PROGRESS.md existed before
this pass; this file reconstructs the state from the cache, request log and corpus.

## Status (2026-10-29)
Phase 1 built and verified locally; PUBLISH written. Nothing pushed or committed (cadence change: the 4-hourly
autopush pass publishes).

| Act | Slug | Versions | Source | In force |
|---|---|---:|---|---|
| Constitution 2024 (Loi 2024-005) + annexed Déclaration | `constitution` | 1 | JO 69e année n° 42 bis, 6 May 2024 | 2024-05-06 |
| Loi 2019-014 (données à caractère personnel) | `donnees-personnelles` | 1 | JO 64e année n° 26 ter, 29 Oct 2019 (signed 30 Oct) | 2019-10-30 |
| Code du travail (Loi 2021-012) | `code-du-travail` | 2 | JO 66e année n° 26 ter, 18 June 2021; art. 190 replaced by Loi 2022-019 (JO 67e année n° 49 bis) | 2021-06-18, 2022-11-15 |

Local verification: scratch build (scratchpad tg-build) 5 commits on main (4 law commits + docs), 8 tags, check.py
0 mismatches / 0 trailer errors, `--compare` identical, main d4b5d4d with docs-date 2026-10-29. parse.py deterministic.
repo/ has README (English then French), LICENSE, jurisdiction.json, tools/en_vigueur_au.py.

## What changed in this pass
- parse.py rewritten: paragraphs from the PDF layout (vertical gaps, bold heads, column order) instead of line ends.
  The first cut (preview a33a6c3) dropped the preamble's opening sentence and let six heading fragments
  ("ET DE LA SOUVERAINETE", "CONSTITUES", ...) into articles; both fixed. Non-bold heads (2019-014 arts. 30, 56) and
  "Article 214 :" (Code du travail) handled; "Dépôt légal" and running heads dropped; ﬁ/ﬂ ligatures and line-end
  hyphens normalised (rule in decisions).
- Added Loi 2019-014 and the Code du travail (+ Loi 2022-019). Found via the JO search (jo_search.py, body text) and
  node pages: node/15570 (Loi 2021-012), node/15631 (Loi 2022-019, "portant modification de la loi n° 2021-012").
- fetch.py with no arguments refetches (or reuses) everything parse.py reads.

## Checks done
- Loi 2019-014 vs the Assemblée nationale's text adopted in plenary 23 Oct 2019 (Wayback 20230605220852): all 97
  articles agree apart from spacing and "l'Etat"/"l'État".
- Constitution vs the Assemblée nationale's JO-styled copy (Wayback 20240711213129): identical except art. 60,
  "Président du Conseil des ministres" (AN) vs "Président du Conseil" (JO); JO kept.
- Nothing dropped: only title, enacting formula, headings, article numbers, signatures are outside units.
- Amendment search (2026-10-29): JO body searches for "code du travail", "données à caractère personnel",
  "révision de la constitution", "Constitution du 06 mai 2024" and reference "2019-014"/"2021-012": the only
  amending law is 2022-019. Titles read for 11 later Assembly texts (finance laws, ratifications, LO 2024-002 on
  députés, 2025-004 OTR, 2025-006 climate). Newest JO issue online: n° 98 bis, 23 Oct 2025.

## Probe (2026-10-28, previous agent; from the request log)
| Source | Result |
|---|---|
| jo.gouv.tg | 200; robots.txt Crawl-delay 10 (honoured). Issue PDFs; born-digital (doPDF) from about 2017, earlier issues are scans with an OCR layer (e.g. Code pénal Loi 2015-010, JO 24 Nov 2015, 241 pages). Search: /recherche?field_nature_tid=&title=&field_corps_du_texte_value= ; node pages give reference, signature date, JO number, page. |
| assemblee-nationale.tg | Wayback only: Constitution 2024 copy, data law as adopted, constitution-TAB/LOI-AN 2021 (1992 text), CODE-PENAL-loi-AN/TAB 2023. |
| courconstitutionnelle.tg | Wayback: LA-CONSTITUTION-DE-2003.pdf (1992 text as of 2003). |
| legitogo.gouv.tg | Expired TLS certificate; http gives a script shell with no text. |
| presidence.gouv.tg, republiquetogolaise.com, justice.gouv.tg | CDX listings cached; not used. |

## Open issues / next
- 1992 Constitution history (repealed by 2024): JO texts of 1992 (jo_1992-036), 2002-029 (jo_2002-042), 2005
  (jo_2005-005-2, jo_2005-008-2), 2007-008 (jo_2007-007-2), LC 2019-003 (JO 11 ter, 15 May 2019, born-digital) are
  cached; 1992-2007 pages are scans (OCR layer only), so only the 2019 revision has a clean text. Was the previous
  agent's thread ("reading JO node 1978 metadata" = node/1978, the 2007 revision).
- Code pénal 2015 (and its 2022/2023 amendments): scans only, skipped (no OCR).
- Phase 2 candidates with born-digital JO texts: Loi 2021-025 (Cour des comptes), Loi 2022-005 (police des
  étrangers), other post-2017 laws.

## Cache
.cache/ about 120 MB (several CDX listings and scans), requests.jsonl 84 lines.
