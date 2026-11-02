# Thin national repos: survey (gitlaw-scraper-hp-omen, 2026-10-31 ~18:10 UTC)

Private working note (scripts/world-law is never shipped to a country repo).

## Method

- Owned slugs: `autopush.owned()` imported from `scripts/south-america-law/autopush.py` (OWN minus FOREIGN and
  HARD_FOREIGN, plus ADOPTED.txt, plus this session's claims): **98 countries**.
- Published acts = acts in `corpus.json` + acts in each `corpus.d/<part>.json` that has `<part>.PUBLISH`, counted only
  when the folder-level `PUBLISH` exists (autopush pushes main only then). "All" = every act in the folder.
- Thin = 0 or 1 published act. Claims in `scripts/world-law/claims/`: none of the thin slugs is claimed by another
  session; no thin slug is HARD_FOREIGN (owned() already drops those).

## Thin countries

| slug | published / all | what is published | blocker (from PROGRESS.md) | status |
|---|---|---|---|---|
| angola | 1 / 3 | Constitution (2021 republication) | Código Penal: amending Lei 12/24 has no text-layer copy; CPP amendments not researched; 2010 Constitution and data law (Lei 22/11) are scans; imprensanacional.gov.ao unreachable | open (source gap) |
| botswana | 1 / 2 | Penal Code (not the Constitution) | Constitution: Act 29/2022 commencement (S.I. 93/2024) members-only; e-Laws members-only; botswanalaws.com robots blocks AI bots (archived copies only, all post-2022 captures are teasers) | held-ish (robots + paywall); skipped |
| bulgaria | 1 / 1 | Constitution, 4 versions | no consolidated text of other acts on parliament.bg; ЗЗЛД / НК need a replay engine over every amending law; dv.parliament.bg unreachable | open (engineering) |
| burkina-faso | 1 / 1 | Constitution (2015 consolidation) | Code pénal: no promulgation date source; Code du travail 2026 and later constitutional laws are scans; data law 037-2026/ALP scan with publisher OCR | open (scans) |
| cameroon | 1 / 1 | Constitution (2008 consolidation) | Penal Code and data law: prc.cm scans only; CPP no official copy; minjustice.gov.cm unreachable | open (scans) |
| lithuania | 1 / 1 | Constitution, 12 versions | e-TAR / e-seimas / data.gov.lt behind bot challenge or WAF (never touched); current editions of core codes not archived | held (bot challenge) |
| mauritius | 1 / 1 | Constitution, 4 versions | core acts not started; see re-check below (AG Revised Laws frozen at 30 June 2017, terms limit commercial use) | blocked (see below) |
| moldova | 1 / 1 | Constitution, 3 versions | every other act only on legis.md (bot challenge, never touched) or paid Monitorul Oficial; archived copies too few | held (bot challenge) |
| guinea-bissau | 0 / 4 (no PUBLISH) | none (4 metadata acts: WIPO / treaty catalogues) | no official online source; Código Penal BO scan with OCR layer; copyright position rules out third-party transcription | open (no source) |
| jamaica | 0 / 4 (no PUBLISH) | none (4 metadata acts: catalogues, treaties) | laws.moj.gov.jm down; revised laws are page-image PDFs; see re-check below | blocked (scans) |
| kiribati | 0 / 1 (no PUBLISH) | none (Constitution as made 1979, built, not published) | PacLII excluded; Penal Code and Companies Act 2021 official copies are scans; see re-check below | open (scans) |
| saint-kitts-and-nevis | 0 / 2 (no PUBLISH) | remote main holds an earlier OCR first build of the 1983 Order | **terms hold**: lawcommission.gov.kn Terms of Use forbid reuse; Copyright Act 2024 has no official-text exemption | held (terms); skipped |
| saint-vincent-and-the-grenadines | 0 / 3 (no PUBLISH) | remote main holds an earlier OCR first build of the 1979 Order | legal.gov.vc down (503); assembly.gov.vc has no core statutes | blocked (host down) |

Not thin but small (2 published acts): equatorial-guinea, haiti, malaysia, micronesia, montenegro, nepal, nigeria,
north-macedonia, senegal, somalia (claimed by this session). Not surveyed further.

## Re-checks this session (light requests only; robots.txt read first)

CPU log read before each request (cpu5 80-84). No worker processes started.

1. **Jamaica.** laws.moj.gov.jm still answers 503 with a maintenance notice, which now points to the **Legal
   Information Portal of Jamaica, lipj.gov.jm** (official; robots.txt `Disallow:` empty). Its Strapi API
   (`/cms/api/records`, `/cms/api/categories`) is open without login: 11 categories, all marked free, including
   "Revised Laws" (613 records, each with `operationalDate` / `lastAmendment` / `editionYear` fields) and "Acts of
   Parliament". Gazette records carry the portal's own OCR. One revised-law PDF sampled (Access to Information Act,
   last amendment 2015): **Adobe Paper Capture scan, OCR text layer** ("Docu~ncnts affecting personill pri\.ac!").
   Result: not usable under the no-OCR rule. Lead for later: check whether any "Acts of Parliament" records (recent
   Acts) are born-digital PDFs; the record list gives title + operational date, which would date them.
2. **Saint Vincent and the Grenadines.** legal.gov.vc: server answers (robots.txt 404, no rules), but the app at
   `/legal/` still returns 503. Still blocked.
3. **Kiribati.** president.gov.ki robots allows `/images/`. The "Gazettes & Instruments" page lists 33 PDFs (2025-26):
   Cybersecurity Act 2026, Trademark Act 2019, amendment Acts, regulations, and the **commencement notices** for the
   Data Protection Act and the National Digital Identification Act 2025, but not the Data Protection Act text itself.
   No core statute. Not added. Lead: if the DPA 2025 text turns up as a text-layer PDF, its commencement notice is
   here to date it (folder PUBLISH would also publish the 1979 Constitution as made, a decision for the coordinator).
4. **Mauritius** (no blocker recorded; checked as the best candidate for core acts). attorneygeneral.govmu.org has no
   robots.txt. Its Terms of Use page says the online Revised Laws are **updated only to 30 June 2017** (LexisNexis
   2016 edition is the sole authoritative text) and: "You should not publish, disseminate or incorporate, in written
   or electronic form, the legislations for commercial use without the prior approval of the Solicitor General."
   Result: revised acts would not reach today's text, so nothing added. **Flag for the coordinator:** the published
   Mauritius Constitution comes from this site; whether a public Lexifina repo counts as "commercial use" under these
   terms needs a decision (contact named there: the Solicitor General, sgo@govmu.org).

## Published this session

Nothing. No source clearly allows more law under the rules (no OCR, official sources only, today's text verifiable).
