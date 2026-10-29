# Bosnia and Herzegovina (state level), gitlaw-BA: progress and handoff

Status at 2026-10-29 00:40 UTC: **probing done, sources found, nothing built.** I wrote no corpus.json, so autopush has
nothing to build yet. The run was stopped by the coordinator's wind-down.

- Slug `bosnia-and-herzegovina`, tz Europe/Sarajevo, lang `bs`, future branch `buduce`, on-date tool `tools/na_snazi_dana.py`.
- Texts are also official in Croatian and Serbian. We build the **Bosnian Latin** text and say so in the README.
- The Constitution's only authentic text is the English Annex 4 of Dayton. The Bosnian is a translation (the PDF itself says "Prijevod na bosanski jezik", OHR). The README must say this.

## Checklist

- [x] Read WAVE.md, FANOUT.md, BRIEF.md, SCHEMA.md and memory/git_for_law.md.
- [x] Checked the scaffold: `lexifina/bosnia-and-herzegovina-law` main = 38764bf "Bosnia and Herzegovina: sources, before any law", which is the only commit. It is cloned to `C:/Users/alany/Documents/bosnia-and-herzegovina-law`, and nothing there has been touched.
- [x] fetch.py: curl, sha256 cache, UA, 3 req/s per host, requests.jsonl. 38 requests so far, 4.3 MB cache.
- [ ] parse.py (not started)
- [ ] corpus.json, then a test build into `.tmp-build`, then check.py
- [ ] PUBLISH
- WebSearch calls used: 0 of 3.

## Sources found (all direct, all with a text layer, no OCR needed)

| Source | What | Notes |
|---|---|---|
| Ustavni sud BiH, `https://www.ustavnisud.ba/uploads/documents/ustav-bih-bs_1611076095.pdf` (cached, sha256 file `3c7837a0…`) | Constitution in Bosnian (OHR translation), 16 pp. Holds the 1995 body unchanged, followed by the full text of **Amendment I** (Brčko; PSBiH 327/09 of 26 Mar 2009; Sl. glasnik BiH 25/09; in force "osmog dana od dana objavljivanja") | robots.txt allows everything. The text contains soft hyphens U+00AD: strip them. It also has "SADRŽAJ" running heads and footnote lines ("1 Ustav Bosne i Hercegovine, OHR…"): drop both. |
| Parlament BiH, "Prečišćeni tekstovi zakona" `https://www.parlament.ba/law/Read?categoryId=3&page=N` (135 entries; list in `.scratch/consolidated.txt`) | Unofficial consolidated texts ("Neslužbeni prečišćeni tekst"), each dated. PDF via `/law/DownloadDocument?lawDocumentId=<guid>&langTag=bs` | robots.txt disallows only `/olaw/OLawDetails*` and similar; `/law/*` is allowed. |
| Krivični zakon BiH, consolidated **June 2019** (lawId 1168, guid ddc77cbe-…, cached `0550c163…`) and **May 2023** (lawId 1202, guid bd6316aa-…, cached `85033d96…`) | Footnote 1 lists every amending law: 3/03, 32/03 (ispravka), 37/03, 54/04 (+32/07), 61/04, 30/05, 53/06, 55/06, 8/10, 47/14, 22/15, 40/15, 35/18, 46/21 (OHR), 31/23 (OHR). **Each law's text is marked by its own font style** (bold, italic, underline, dotted or wavy underline, grey or blue shading) | The styles can credit each provision to its law: read PyMuPDF span flags, plus drawings for underline and shading. The 2019 text gives the state after 35/18; diffing 2019 against 2023 gives the 46/21 and 31/23 changes. |
| Zakon o zaštiti ličnih podataka (2006, 49/06, 76/11, 89/11) | Parliament consolidated texts Nov 2016 (lawId 1129) and Jan 2019 (lawId 1156) | Neither is fetched yet. |
| AZLP `https://www.azlp.ba/Novi_zakon_i_obavjestenje/?id=4465` | **New Zakon o zaštiti ličnih podataka, Sl. glasnik BiH 12/25**, plus a notice on when it applies (`?id=4468`) | Neither is fetched yet. |
| Službeni glasnik BiH (sluzbenilist.ba) | The gazette itself, mostly paid | Not used. |

## Exact next steps

1. **Dates needed** (this is the one blocker for the Constitution): the publication day of Sl. glasnik BiH 25/09, which gives Amendment I's in-force day (publication + 8). Also the dates of 35/18, 46/21, 31/23 and any later KZ amendment. Each must come from an official page; one WebSearch is allowed for this. Do not guess.
2. **parse.py for the Constitution.** Base version `from` 1995-12-14 (Art. XII.1: in force on signature of the General Framework Agreement), with `first_law` = the Dayton Annex 4 (kind `treaty`). Units: `preambula`, `clan-01`…`clan-12`, `aneks-1`, `aneks-2`, `izjave`. Version 2 replays Amendment I: insert "4. Brčko Distrikt…" after VI.3 and renumber "4. Odluke" to "5. Odluke". Credit `clan-06` to `amandman-i-2009` (kind `law`). Check by hand that the replayed text equals the amendment wording.
3. **Criminal Code.** v1 = June 2019 consolidation from 35/18's in-force day (`first_law: null`, earlier_laws = the 13 earlier laws). Then the diff against May 2023, credited to 46/21 or 31/23 by font style. Before PUBLISH, check whether there are amendments after 31/23 (for example an OHR 2023 Art. 203a amendment, unverified). If there are and their text can't be sourced, do not publish this act.
4. **Data protection.** Fetch AZLP id=4465 and id=4468. Build the 2025 law as enacted, with its own in-force and application dates (the 2006 law is optionally a repealed act).
5. **Language.** README in English first, then Bosnian. Reuse the scaffold README and SOURCES.md.

## Open issues

None for the shared builder; it was not run.
