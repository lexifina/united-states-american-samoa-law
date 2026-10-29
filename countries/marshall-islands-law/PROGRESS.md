# gitlaw-MH: Marshall Islands law history (2026-10-29)

Slug `marshall-islands`, repo `lexifina/marshall-islands-law` (private).
- Checked 2026-10-29: `git ls-remote` shows only `main` (f768113).
- History: 6aa6222 "Marshall Islands: sources, before any law", then f768113 "Paused, not yet law: the site's rights
  statement needs permission for reuse". The coordinator said this state is expected.
- tz Pacific/Majuro, lang en. Marshallese versions exist, but the Revised Code is published in English.

## State: BLOCKED ON PERMISSION (branch 3). This folder holds no legal text.

- No official publisher was found whose terms allow commercial reuse (table below).
- `PERMISSION_REQUEST.md` holds the email to the Attorney General's Chambers, with their contact details and where each
  was found. Someone at Lexifina has to send it; sender placeholders are left in.
- No act PDF was downloaded, not even into `.cache/`. `.cache/` (gitignored, never pushed) holds only listing pages and
  metadata (`index.json`).
- There is no corpus.json and no PUBLISH, so the push loop will not pick this folder up. Keep it that way until
  permission arrives.
- WebSearch used: 3 of 4.

## Sources checked, with their exact terms

| Candidate | Official? | Exact terms | Verdict |
|---|---|---|---|
| Nitijela, Office of the Legislative Counsel: rmiparliament.org/cms | Yes. It publishes the MIRC, and the Legislative Counsel is the Commissioner of the MIRC. | `<meta name="rights">` on every page: "Legislation can be downloaded and printed for private use. Any commercial entity is required to obtain permission to reuse the data from the Marshall Islands Attorney General's Chambers." The footer reads "© 2026 the Marshall Islands - All Rights Reserved". robots.txt allows /cms/images/LEGISLATION/. | Needs permission |
| Attorney General: rmiagoffice.com | Yes | The live site shows a Cloudflare "Just a moment..." challenge, which we did not touch. archive.org has 11 captures of `/`, all from 2024-04-15 to 2025-09-16; the latest is a "COUNT DOWN... OUR WEBSITE IS ON THE WAY" placeholder with no content and no terms. Common Crawl returned no captures. | No laws published |
| RMI Government: rmi.gov.mh, rmigovernment.org | rmi.gov.mh: no DNS answer. rmigovernment.org: the domain has lapsed and is now a football-betting site. | n/a | None |
| RMI Judiciary: rmicourts.org | An official body, but it labels its copy of the code unofficial. It hosts MIRC Vol. 1–2 [December 2014] as per-chapter PDFs and a `wp-content/uploads/2025-Const.pdf`. | The MIRC page says: "This version of the Marshall Islands Revised Code ... is an unofficial version of the Code, amended as of the 2014 Session of the Nitijela ... Users may utilize this unofficial version of the Code as a research tool". The footer reads "© 2008-2026 Republic of the Marshall Islands Judiciary. All rights reserved." The /disclaimer/ page grants no reuse licence. | No reuse grant; unofficial |
| WIPO Lex (MH profile, 6 texts incl. the Constitution "MIRC 2005", mh001en.pdf) | A deposit copy of the MIRC 2005 | wipo.int/tools/en/disclaim.html: CC BY 4.0 covers WIPO's own content only. "This Open Access Policy is not applicable to third party content." "anyone wishing to use such content is solely responsible for clearing the rights". | Sends you back to the AG |
| ILO NATLEX | Lists entries and links to the national sources | The ILO holds copyright in its own site content, and copyright in third-party material must be respected. NATLEX: "inclusion ... does not imply responsibility for, or approval of, their content". It grants no licence for national texts. | Sends you back to the AG |
| HCCH, UN mission (un.int/marshallislands) | Contacts only | n/a | No law texts |
| PacLII / AustLII | n/a | Excluded by rule: its terms forbid this use, and it uses Cloudflare. | Not used |
| Constitute Project | Unofficial | CC BY-NC 3.0, which is non-commercial | Fails |

## What a builder needs once permission arrives

Record the permission (date, who gave it, the attribution wording) in sources.py and in the README credit. Then follow
`scripts/tonga-law/`; the site is the same Joomla "com_legislation" component that Tonga's AGO uses.

- **Index of all current principal acts.** `index.py` fetches and parses the full, unpaginated A–Z list from
  https://rmiparliament.org/cms/legislation/acts-of-nitijela/by-title.html (GET): 306 principal acts.
  - Each row gives the legislation number (`YYYY-NNNN`), the current PDF and the version number `[n]`.
  - Each row has a history modal with every version's PDF, "Date Commenced", "Details" and "Date Changed".
  - Some rows have "amended by..." child rows: 27 on the whole site.
- **Acts in one MIRC title.** POST `catid=<1..52>` to the same URL. `index.py` maps every title, and 305 of the 306
  acts fall in a title.
- **PDF paths.** Principal acts: `https://rmiparliament.org/cms/images/LEGISLATION/PRINCIPAL/<YYYY>/<YYYY-NNNN>/<YYYY-NNNN>_<v>.pdf`.
  Amending acts: `.../LEGISLATION/AMENDING/<YYYY>/<YYYY-NNNNA>/<YYYY-NNNNA>.pdf`.
- **Acts by year, 1930–2026, with both kinds of PDF.** POST `year=<YYYY>` to
  https://rmiparliament.org/cms/legislation/acts-of-nitijela/acts-by-year.html. `index.fetch` caches these pages.
- **Public Laws by year.** https://rmiparliament.org/cms/library/public-laws-by-years.html links to pages such as
  `/cms/library/rmi-regulations/3-public-laws/<id>-<year>.html`.
- **Also on the site:** repealed acts (`/cms/legislation/repealed.html`) and acts not in force
  (`/cms/legislation/acts-not-in-force.html`).
- **Main dating problem:** the version history gives every version the principal act's own commencement date.
  - The Constitution's v1–v3 all read "01 May 1979, Initial Version". The Criminal Code's v1–v6 all read 17 Oct 2011.
  - So a version's real date has to come from the amending Act: its own commencement in the acts-by-year list, plus
    the endnotes or history notes inside each "as amended" PDF.
- **Commencement rule:** check the General Interpretation Act (1966-0001, Title 1) and Constitution Art. IV
  (certification by the Speaker) before dating anything.

## MIRC structure (52 titles; principal acts per title, from catid)

01 General Provisions (13) | 02 Elections and Referenda (6) | 03 Central Government (13) | 04 Local Government Affairs (3) | 05 Public Offices and Agencies (12) | 06 Public Proceedings and Records (4) | 07 Public Health Safety and Welfare (19) | 08 Animal Quarantine and Protection of Endangered Species (3) | 09 Public Lands and Resources (2) | 10 Planning and Economic Development (22) | 11 Finance (15) | 12 Civil Aviation (2) | 13 Motor Vehicles (7) | 14 Education (7) | 15 Anti-Terrorism Laws (2) | 16 Labor and Industrial Relations (8) | 17 Banks and Financial Institutions (4) | 18 Cooperatives and Non-Profit Corporations (4) | 19 Regulation of Professions and Occupations (7) | 20 Business Regulation and Practice (9) | 21 Intoxicating Liquor (2) | 22 Administration of RMI Ports (1) | 23 Law of Sales (1) | 24 Property (4) | 25 Wills Probate and Guardianship (2) | 26 Family (11) | 27 The Court and Court Officers (9) | 28 Evidence (2) | 29 Civil Procedures (1) | 30 Civil Remedies and Special Proceedings (7) | 31 Crimes and Punishments (5) | 32 Criminal Procedures (4) | 33 Marine Zones and Protection of Mammals (3) | 34 Admiralty and Maritime Affairs (3) | 35 Environment (6) | 36 Securities; Cooperatives and Non-Profit Corporations (3) | 37 Reserved (0) | 38 Postal Service (2) | 39 Customs and Traditions (8) | 40 Communications (5) | 41 Compact of Free Association (4) | 42 Nuclear Claims (3) | 43 Foreign Affairs Citizenship and Immigration (17) | 44 Government Procurement (1) | 45 Historic and Cultural Preservation (2) | 46 Churches (2) | 47 Maritime (9) | 48 Taxation (10) | 49 Social Security (2) | 50 Trusts (3) | 51 Management of Marine Resources (5) | 52 Associations Law (7)

## Phase 1 plan (no PDFs fetched yet)

1. **Constitution of the Republic of the Marshall Islands**, 1979-0000, commenced 1 May 1979. It is filed under
   Title 1.
   - PDFs: `PRINCIPAL/1979/1979-0000/1979-0000_{1,2,3}.pdf`; v3 is current.
   - The amendments of 1990 and 1995 have to be dated from the PDFs' own notes, because the site has no amending-act
     rows for them.
   - Related Acts:
     - Referendum (Constitutional Amendment) Act 2018: `PRINCIPAL/2018/2018-0069/2018-0069_1.pdf`.
     - Referendum (Constitutional Amendment) Act 2025: `AMENDING/2025/2025-0023A/2025-0023A.pdf`.
     - Constitutional Convention Acts of 2015, 2016–2018 and 2026: 2015-0046, 2016-0006A/0008A/0009A/0025A,
       2017-0041A–0044A/0051A, 2018-0066A, 2026-0062 and 2026-0080A.
   - The Rules of Procedure of the Nitijela (1979-0002) are a separate Title 1 item.
2. **Title 31, Crimes and Punishments (5 acts).**
   - Criminal Code, 2011 (2011-0059, commenced 17 Oct 2011). It has v1–v6, `PRINCIPAL/2011/2011-0059/2011-0059_{1..6}.pdf`.
     It repealed the old 31 MIRC Ch. 1. Known amending Acts: Criminal Code (Defenses) (Amendment) Act 2020
     (`AMENDING/2020/2020-0016A/2020-0016A.pdf`) and Criminal Code Amendment Act 2025 (`AMENDING/2025/2025-0045A/2025-0045A.pdf`).
     For the rest, scan acts-by-year from 2012 to 2026.
   - Cybercrimes Act 2025 (2025-0040, v1, commenced 6 Oct 2025).
   - Gaming and Recreation Prohibition Act 1998 (1998-0064, v2).
   - Proceeds of Crime Act, 2002 (2002-0068, v2).
   - Treason and Sedition Act 1988 (1988-0008, v1).
3. **A short second title**, one of these:
   - Title 28, Evidence: Evidence Act of 1989 (1989-0071, v1) and Foreign Evidence Act, 2002 (2002-0066, v1). Neither
     has a version history.
   - Title 23, Law of Sales: Uniform Commercial Code (Reference) Act, 2018 (2018-0085, v1).

Check `git ls-remote` again before writing PUBLISH (FORK.md rule 4). The first build replaces the placeholder history;
it must not append to it.

## Scripts

- `index.py`: metadata only. It fetches at most 3 requests a second, caches under `.cache/pages/` and logs to
  `.cache/requests.jsonl`. It never downloads PDFs.
  - Run: `python -X utf8 scripts/marshall-islands-law/index.py`, optionally with `--titles 31 1`.
