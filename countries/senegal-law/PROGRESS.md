# Senegal (SN): progress of gitlaw-SN (resumed by gitlaw-SN-TG, 2026-10-29)

Spec: scripts/africa-law/QUEUE.md row SN. Repo lexifina/senegal-law (private). Language fr, tz Africa/Dakar, future
branch `futur`, on-date tool `en_vigueur_au`. Remote main = scaffold 5a80c73 (checked read-only 2026-10-29).

## Status (2026-10-29)
Phase 1 built and verified locally; PUBLISH written. Nothing pushed or committed (cadence change: the 4-hourly
autopush pass publishes).

| Act | Slug | Versions | Source | In force |
|---|---|---:|---|---|
| Loi 2008-12 (données à caractère personnel) | `donnees-personnelles` | 1 | JO n° 6406 du 3 mai 2008, jo.gouv.sn web edition (Wayback 20150609214903, spip article6663) | 2008-05-07 |
| Loi organique 2016-23 (Conseil constitutionnel) | `conseil-constitutionnel` | 1 | conseilconstitutionnel.sn/la-loi-organique/ (JORS NS 6946 du 15 juillet 2016) | 2016-07-19 |

Local verification: scratch build (scratchpad sn-build) 3 commits on main (2 acts + docs), 4 tags, check.py 0 mismatches /
0 trailer errors, `--compare` identical, main a1b53fb with docs-date 2026-10-29. parse.py is deterministic
(corpus sha256 stable across runs). repo/ has README (English then French), LICENSE, jurisdiction.json,
tools/en_vigueur_au.py.

## Checklist
- [x] Read FANOUT/BRIEF/SCHEMA/git_for_law; folder, .gitignore, sncache.py
- [x] Probe sources (below)
- [x] Located Loi 2008-12 in the archived JO: rubrique437 = JO 6406 (3 May 2008), article6663 (jo_index approach; full
      rubrique index not needed: rubrique IDs run roughly by date, about 435-439 for April-May 2008)
- [x] fetch.py (pinned captures + direct URLs), parse.py, corpus.json
- [x] Default in-force rule: Loi 70-14 art. 2 (3rd day after the JO's deposit, plus Sundays/holidays) until Loi 2021-21
      art. 10 (JO 7409, 20 March 2021: "un jour franc à compter de leur publication")
- [x] Loi 2008-12 cross-checked with the CDP PDF (13 typographic differences listed in decisions; 2 JO web-edition
      slips corrected: art. 16 "a)", art. 57 "traitements")
- [x] README, LICENSE, jurisdiction.json; scratch build, check, compare; PUBLISH
- [ ] Constitution (skipped this pass, see open issues)
- [ ] Code pénal (scan only: skipped, no OCR)

## Probe (2026-10-28/29)
| Source | Result |
|---|---|
| jo.gouv.sn (Journal officiel, official) | Down (TCP connect fails). Wayback holds 20,606 HTML captures of the SPIP site to about Sept 2018: `spip.php?rubriqueN` = one JO issue, `spip.php?articleN` = full text. Article pages hold the text twice (identical; parse.py asserts it). |
| conseilconstitutionnel.sn (official) | 200; robots allows all but /wp-admin/. `/la-constitution/`: the Conseil's consolidation à jour of LC 2018-14, with notes interleaved. `/la-loi-organique/`: LO 2016-23 as promulgated. |
| www.vie-publique.sn (civic publisher) | robots.txt `Allow: /` (cms.vie-publique.sn is `Disallow: /`, never used). Sitemap (24,537 URLs) lists JO issues to 2026 and many laws; most recent PDFs are image scans. Used for Loi 70-14 (publisher text layer on a scan), Loi 2021-21 (JO 7409, text layer), and to check for later laws. |
| cdp.sn (Commission de Protection des Données Personnelles) | Live site serves a bot challenge: Wayback only. Loi 2008-12 page captured 2017-2026; `protection.pdf` (same bytes as vie-publique's PDF). `code_penal.pdf` and `code_proc_penal.pdf`: image scans. |
| sgg.gouv.sn / assemblee-nationale.sn | Do not resolve / connect fails. |
| Common Crawl index | Timed out 2026-10-28 22:20 UTC and again 2026-10-29 (tried once, as instructed). |

## Open issues
- **Constitution not built.** The only consolidation (Conseil constitutionnel, mirrored by vie-publique as a print PDF) is
  à jour of LC 2018-14 and has about 100 editorial notes and « » markers inside the paragraphs (e.g. art. 7, 9, 34, 66,
  82, 101), with no clean copy to check a de-annotation against: more than the 45-minute budget, and unverifiable.
  LC 2019-10 (JO 7181, 20 May 2019) and LC 2021-41 (JO 7483, 22 Dec 2021; both replace whole articles) are cached as
  vie-publique PDFs with text layers (.tmp/jo7181.txt, .tmp/jo7483.txt). The JO archive holds the 2001 text
  (spip article36) and LC 2003-15 (article1010), so a replay from 2001 is another route.
- **"Loi n° 11/2024 portant révision de la Constitution"** (vie-publique document 5535, dated 14 Dec 2024) is a 2-page
  image scan; whether it is the HCCT/CESE bill rejected on 3 Sept 2024 or an enacted law is not settled. Must be
  resolved before any Constitution PUBLISH. The 2026 revision (loi n° 18/2026) was struck down by décision 6/C/2026
  (9 July 2026) and never took effect.
- Loi 70-14 was amended by Loi 71-07 (21 Jan 1971), not found; deposit receipts for JO 6406 / JORS 6946 not found, so
  the issue date stands in for the deposit date (decision recorded).
- New Code du travail (loi n° 2026-18/19, JO 7931, 17 Sept 2026) exists only as a 73 MB scan.

## Cache
.cache/ about 120 MB (CDX listings, vie-publique sitemap and scans), requests.jsonl 299 lines (archive.org via
wayback.py; direct hosts at 1 rps).
