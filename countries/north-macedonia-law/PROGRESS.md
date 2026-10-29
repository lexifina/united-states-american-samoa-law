# North Macedonia (gitlaw-MK): progress / handoff

Repo `lexifina/north-macedonia-law` (private). Scaffold checked 2026-10-29 02:13 UTC: only `main` (4ca86e4, "North Macedonia: sources, before any law"). No commits or pushes (CADENCE CHANGE). Scaffold copy in `.scaffold/` (gitignored); local test builds go in `.tmp-build*`.

## Checklist
- [x] scaffold check (02:13 UTC)
- [ ] probe sources (slvesnik.com.mk, sobranie.mk, ENER/pravda.gov.mk, archives)
- [x] Constitution 1991 + amendments I-XXXVI: corpus.json written (9 versions 1991-11-17 .. 2019-02-12, 152 units, 37 laws, every amendment's target checked against its instruction; parse.log)
- [~] Criminal Code (1996): SKIPPED. 37/1996 is an ABBYY scan (OCR layer only, no-OCR rule), 31 amending laws (list from 188/2023 art. 1), no official consolidated text (MoJ, Assembly, LDBIS page all lack one). Law of Obligations 18/2001 also a scan; MoJ consolidated file (portal.mdt.gov.mk zakoni-justice-file-uV8A.pdf, 280 pp.) is unofficial and undated, so not used.
- [x] Law on Personal Data Protection (2020): zzlp.py, 3 versions (2020-02-24, 2022-01-04, 2025-05-21), 150 units; as-enacted text = publisher's single-act copy word for word (verify.py -> verification.json); PUBLISH updated 12:03
- [x] README (English + Македонски), LICENSE, jurisdiction.json (build: built); local build .tmp-build 37 commits, 46 tags, main d57d2a6; check.py 0 mismatches / 0 trailer errors; --compare identical; PUBLISH written 11:55 UTC

## Probe (02:15-02:45 UTC)
- **slvesnik.com.mk** (Official Gazette): robots allows. Free issues via JSON API: `POST https://slvesnik.com.mk/FreeIssue/GetIssuesByYear {"year":Y}` (header `FROM-ANGULAR: true`) -> issue numbers + FileName; PDF at `https://slvesnik.com.mk/Issues/<FileName>.pdf`. Years 1945-2025. 1991/1992 issues have an OCR text layer (errors: "делот" for "денот", "па" for "на"); 2019 issue 6 is born-digital (clean).
- **sobranie.mk** (Assembly): `WBStorage/Files/UstavnaRmizmeni.pdf` (2011, Word-made, clean text): 1991 Constitution + Amendments I-XXXII with each promulgation decision, certified copy ("Дека преписот е верен на оригиналот"). `content/Odluki USTAV/UstavSRSM.pdf` (2019) = same + 2 scanned pages (XXXIII-XXXVI, no text layer). English `content/EN DOKUMENTI/USTAVen.pdf` (original + amendments, not consolidated). **Its Macedonian copy merges some paragraphs** (Art. 3, 4: 3 stavs in the gazette and English, 2 in the copy), so paragraph division must come from the gazette.
- **ldbis.pravda.gov.mk** (MoJ LDBIS): `PregledNaZakon.aspx?id=N` gives metadata (gazette no., publication date, in-force date, application date) and the chain of linked/amending laws with ids. Text not on that page.
- **portal.mdt.gov.mk** (MoJ files): some laws and "пречистен текст" PDFs/DOCs (from pravda.gov.mk/mk-MK/regulativa/zakoni).
- No official consolidated Constitution exists: officially it is the 1991 text plus Amendments I-XXXVI, each "составен дел на Уставот".
- Gazette issues: 52/1991 (Устав, 22.11.1991), 1/1992 (I-II), 31/1998 (III), 91/2001 (IV-XVIII), 84/2003 (XIX), 107/2005 (XX-XXX), 3/2009 (XXXI), 49/2011 (XXXII), 6/2019 (XXXIII-XXXVI + constitutional law).

## Method (Constitution)
- `fetch.py` (curl, cache .cache/sha256(url), requests.jsonl, POST support for the gazette API), `pdftext.py` (PDF lines, gazette indentation paragraphing, word alignment), `ustav.py` (Assembly copy + gazette reading), `ustav_replay.py` (operation table OPS transcribed from each amendment's instruction point; replay engine), `parse.py` (cache only -> corpus.json, parse.log).
- Words: Assembly copy for 1991 + I-XVIII; born-digital gazette for XIX-XXXVI (XIX-XXXII compared word by word with the Assembly copy: only XIX differs in 4 words, XXVI has 2 glued words in the copy). Paragraphs: gazette layout aligned to the copy.
- Dates: promulgation day (each amendment says so); XXXIII-XXXVI 2019-02-12 per Government notice in 36/2019.

## Status 11:55 UTC
- Rate-limit pause 02:20-11:50 UTC. Coordinator: pushes allowed again, but never by me.
- Scaffold re-checked 11:54: main 4ca86e4 only; a `wip` branch exists = autopush snapshot of scripts/north-macedonia-law (commits 05:03, 11:51), i.e. this folder, not another session.
- Next: Law on Personal Data Protection (42/2020) then the Criminal Code (1996; ~35 amending laws, likely current text only, FORK rule 1).

## Status 12:00 UTC
- corpus.json: ustav (9 versions) + zakon-za-zastita-na-licnite-podatoci (3). Local build .tmp-build: 40 commits, 52 tags, main ee38807; check.py 0/0; --compare identical. PUBLISH current. Remote re-checked 12:03: main + wip (autopush snapshot) only.
- zakon.py = generic reader for born-digital gazette laws (bold titles, centered headings, indented paragraphs, size filter for footnotes/headers, hyphen join). Reusable for the Criminal Code if a born-digital consolidated text exists.
- Next: Criminal Code (Кривичен законик 37/1996, ~35 amending laws). 1996 gazette is a scan (OCR layer only), so the 1996 text cannot be used; look for an official born-digital consolidated text (Сл. весник пречистен текст?) -> one "oldest version available" version (FORK rule 1).

## Status 12:04 UTC (final for this session)
- Acts: ustav (9 versions), zakon-za-zastita-na-licnite-podatoci (3). PUBLISH current. No commits, no pushes by me.
- Ideas to resume: the Criminal Code could be rebuilt from the born-digital amending laws (2002+) only if a verified base text appears; a Macedonian amending-law instruction parser ("се менува и гласи", "се брише", "по зборот ... се додаваат зборовите") would generalise zzlp.py's hand-transcribed OPS. Law on Criminal Procedure (150/2010, born-digital, 4 amending laws) is the most promising next act.
- Final: local build main 0e1e0f2, 40 commits; check.py 0/0; --compare identical; remote main 4ca86e4 + wip only (12:03). Cache 300 MB, 71 requests.
