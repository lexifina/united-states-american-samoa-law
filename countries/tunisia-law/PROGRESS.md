# Tunisia (gitlaw-TN): progress / handoff (wound down 2026-10-29 ~00:35 UTC)

Repo lexifina/tunisia-law: still the bare scaffold (ls-remote 2026-10-28: only main, 274c506 "sources, before any law").
Clone: C:/Users/alany/Documents/tunisia-law (autopush owns it; nothing built into it). Language target: Arabic (the JORT
French edition is printed "TRADUCTION FRANÇAISE POUR INFORMATION", so Arabic is the only authentic text).

## Status
- [x] scaffold check
- [x] probe sources (below)
- [ ] Constitution 2022 (2014 as the earlier version of the same act, as Madagascar did): NO TEXT IN HAND YET
- [ ] core act 1 (Loi organique 2004-63, personal data) and core act 2 (Code pénal / المجلة الجزائية)
- [ ] corpus.json, PUBLISH. None written: nothing parsed yet.
No fetch.py or parse.py yet. The only throwaway probe scripts are in C:/Users/alany/AppData/Local/Temp/tn_tools and /tmp/tn_*.py.
Downloads are in C:/Users/alany/AppData/Local/Temp/tn_dl. Every archive.org response is cached in .cache/ (requests.jsonl).

## Source findings (2026-10-28)
- **iort.gov.tn** (http only) and **https://www.iort.tn/siteiort/** (live, 200) are WebDev apps (session URLs, JS form posts).
  The homepage lists "أمر رئاسي عدد 691 لسنة 2022 ... بختم دستور الجمهورية التونسية" (link `_JSL(_PAGE_,'A45')`) and a
  "دستور الجمهورية التونسية" menu item (`_JEM('M16')`, `M26`). There is also "المجلات ومجموعات النصوص القانونية", the consolidated
  codes. Navigation is a POST of form PAGE_PRINCIPAL (action /siteiort/PAGE_Principal/<ctx>) with WD_ACTION_ / WD_BUTTON_CLICK_ set
  to the control id, plus cookie wbNavigateurLargeur=1400 and a cookie jar. NEXT STEP: drive that POST with curl
  (WD_BUTTON_CLICK_=A45 or M26) to get the Arabic constitution PDF; try the codes collection for المجلة الجزائية too.
- **Constitution 2022**: promulgated by Décret présidentiel 2022-691 of 17 Aug 2022, JORT n° 91 of 18 Aug 2022 p. 2473
  (French copy cached: Wayback 20240713165058 of pist.tn/jort/2022/2022F/Jo0912022.pdf). It orders publication of the text
  "dans un numéro spécial du JORT", and that special issue is not on Wayback/pist. The draft is JORT n° 74 (decree 2022-578,
  30 Jun 2022), with a corrected draft in July 2022. In-force date: check the final article (entry into force on the ISIE's
  proclamation of final results, decision 2022-22 of 16 Aug 2022) before dating.
- **pist.tn** (CNUDST JORT PDFs, pattern jort/YYYY/YYYYA/JaNNNYYYY.pdf, French in YYYYF/Jo...): the live site times out. Wayback
  has many French issues but few Arabic ones (2022A: 030, 102, 103 only; 2004A: 029, 060; no 2014A). Common Crawl has 0.
  Arabic JORT PDFs from 2022 have a good Unicode text layer (Ja1022022 tested).
- **legislation.tn**: the live site gives 503. Wayback has 18,820 captures under /sites/default/files (2014–2021): codes/PenalArabe.pdf
  (2014-04-12, 2015-09-30, 2017-02-19, 2018-07-13), Penal.pdf (fr, 2014, 2015), constitution/constitution.pdf (2015–2016,
  probably 2014 Constitution), constitutionarabe.pdf (2014-01-04, likely 1959). **The Arabic IORT code PDFs have a broken text
  layer** (CFF fonts without Unicode mapping; PenalArabe 2018 tested), so they're unusable without OCR. The French Penal.pdf should be
  tested next (fallback language per the brief: say so in the README).
- Loi organique 2004-63: JORT n° 61 of 30 Jul 2004, not on Wayback/pist (2004A only 029, 060). Try the iort.tn search.
- WebSearch used: 1 of 4.
