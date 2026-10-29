STATUS 2026-10-29 ~02:00Z: Grondwet published (main 71b4bac). Round 2 adds three verified corpus.d parts with PUBLISH
files, waiting for the 4-hourly autopush pass: 20-burgerlijk-wetboek (new BW 2024, Boeken 1-8), 30-rechtsvordering
(new Rv 2024), 40-kiesregeling (S.B. 2025 no. 16). Local build .tmp-build/v4a: 6 commits + docs, 9 tags, check.py 0
mismatches / 0 trailer errors, --compare identical. Nothing pushed or committed by this agent.

## Round 2 (2026-10-29): what was added and how

- Discovery: sris.sr is WordPress; https://sris.sr/wp-json/wp/v2/media?per_page=100&page=1..18 lists all 1,757
  uploads (title, date, URL). That found the NEW Burgerlijk Wetboek (S.B. 2024 no. 164) and Wetboek van Burgerlijke
  Rechtsvordering (S.B. 2024 no. 170), both Word-made PDFs with text layers, in force 2025-05-01 by Resolutie
  S.B. 2025 no. 14; and the Kiesregeling current text S.B. 2025 no. 16. Listing kept in scratchpad only (discovery, not
  parse input); the PDFs are in fetch.py FILES (second round).
- parse_codes.py (new) writes corpus.d/20-, 30-, 40-*.json; verify_codes.py bw|rv|kr is the completeness check
  (independent word extraction, windowed alignment, plus a "heading swallowed into article" check). Results:
  bw 3 explained diffs, rv 2 (preamble/signature), kr 1 (title paragraph); 0 headings inside articles.
- Unit keys: BW boek-<n>-art-<NNNN><suffix> (each Book numbers its own articles), boek-<n>-indeling; Rv art-<NNNN>,
  art-a, art-b, indeling; Kiesregeling art-<NNNN>, indeling.
- Paragraph rule: new paragraph on a list marker, or when the next line's first word would have fitted on the line
  before (Times metrics, per-page-size margins: Letter 43.2-579.2, A4 43.2-562.4). Hyphens: keep when the hyphenated
  form is more frequent inside lines than the closed form.
- Kiesregeling footnotes (Courier/Times 6-8 pt refs, 9-10 pt notes) are dropped; superscript ordinals kept.
- Boek 7A (old BW Derde Boek remains via Aanpassingswet S.B. 2024 no. 168) left out: changes only, base text unusable.
- parse.py: only the decision about WvSr/old BW/data protection was reworded (Grondwet act data unchanged; acts and
  laws in corpus.json identical, sources request counts changed). Note: the Kiesregeling commit (2025-02-07) sorts
  before the Grondwet's 2025-02-07 commit, so that one Grondwet commit gets a new hash on main (content identical).
- Skipped (>45 min or not sourceable without OCR): Wetboek van Strafrecht (S.B. 2014/118 scan; 2020/42, 2023/133,
  2023/135 scans with scanner OCR layers; 2017/85 not listed). Data protection: only a 2020 bill (Ontwerpwet
  Bescherming Privacy en Persoonsgegevens). Old Wetboek van Koophandel: rewritten piecemeal by S.B. 2024 no. 168.

# Suriname (gitlaw-SR): progress

Repo: lexifina/suriname-law (PRIVATE), clone at C:/Users/alany/Documents/suriname-law. tz America/Paramaribo, lang nl,
future branch `toekomst`, on-date tool `tools/geldend_op.py`.

## Checklist

- [x] Probe sources (2026-10-28)
- [x] fetch.py (curl now has `--compressed` per coordinator 2026-10-28; cached bytes unchanged, no refetch) (40 requests, .cache 26 MB)
- [x] parse.py Grondwet clean: 3 versions 1992-04-08 / 2023-10-27 (arts 60,61,161,163 -> sb-2023-157) / 2025-02-07 (20 units, uncredited publisher)
- [x] repo/README.md (EN+NL), repo/LICENSE, repo/jurisdiction.json, repo/tools/geldend_op.py
- [x] test build in .tmp-build: 3 law commits + docs, 4 tags, check.py 0 mismatches, --compare identical, tool works
- [x] PUBLISH created 2026-10-28 ~17:25Z (autopush now pushes main + tags)
- [x] main pushed by autopush: head 71b4bac (2026-10-28T17:28Z), law commits 77fceec / c2f1201 / 952d498, tags grondwet/1992-04-08, grondwet/2023-10-27, grondwet/2025-02-07, law/sb-2023-157; check 0 mismatches; --compare identical
- [-] Wetboek van Strafrecht: NOT buildable to today (see Phase 2); stopped, documented in README + decisions
- [-] old Burgerlijk Wetboek (1860): NOT buildable to today (see Phase 2); stopped, documented
- [x] NEW Burgerlijk Wetboek (S.B. 2024 no. 164), 1 version 2025-05-01, 2,426 units; PUBLISH written 2026-10-29
- [x] NEW Wetboek van Burgerlijke Rechtsvordering (S.B. 2024 no. 170), 1 version 2025-05-01, 839 units; PUBLISH
- [x] Kiesregeling (S.B. 2025 no. 16), 1 version 2025-02-07, 152 units; PUBLISH
- [x] repo/README.md + jurisdiction.json updated for the three acts; cache 60 MB, 63 requests logged
- [ ] after the next autopush pass: read BUILD_STATUS.json and confirm main has the 3 parts

## Sources (probe, 2026-10-28)

| Source | Status | Format | Dated versions | Amendment notes | robots / licence |
|---|---|---|---|---|---|
| DNA wetgeving https://www.dna.sr/wetgeving/surinaamse-wetten/ | 200 | Umbraco HTML pages, each with one PDF under /media/ | no; three lists: "Geldende teksten t/m 2005" (consolidations, 2005 PDFs), "Wetten na 2005", "Wijzigingen na 2005" (scanned Staatsblad PDFs) | consolidations carry footnotes per article: "Gew. bij S.B. 1992 no.38", "Ingev. bij", "Vervallen bij" | robots.txt 404 (none). /copyright/auteursrechten/ page; legislation is official public text |
| sris.sr (Surinaams Rechtsinformatiesysteem) | 200 | PDF with text layer | S.B. 2025 no. 15 = official consolidated Grondwet after S.B. 2023 no. 157 (Resolutie 6 Feb 2025) | footnotes "Gew. bij S.B. 2023 no. 157" | none seen |
| gov.sr | 200 | PDF (2011 copy of the 1992 consolidation) | no | same footnotes | |
| Staatsblad 2023 no. 157 (dna.sr media) | 200 | scanned PDF, no text layer | n/a | amending act | |
| WIPO Lex 8816 | 200 | EN + NL PDFs of the 1992 consolidation only | no | | |

No online official copy of the original 1987 text (S.B. 1987 no. 116) or of the 1992 amending act (S.B. 1992 no. 38)
was found (dna.sr, Wayback CDX of dna.sr, sris.sr, gov.sr, WIPO). So the Grondwet starts at the 1992 consolidation.

## Grondwet facts verified

- Grondwet S.B. 1987 no. 116, in force 30 Oct 1987 (art. 186 lid 3 of its own text).
- Amended by Wet van 8 april 1992 (S.B. 1992 no. 38): ~75 articles footnoted "Gew./Ingev./Vervallen bij S.B. 1992 no.38".
- Amended by Wet van 25 oktober 2023 (S.B. 2023 no. 157), uitgegeven 26 oktober 2023, art. II lid 2: in force the day
  after afkondiging = 2023-10-27. Changes arts. 60, 61, 161 (new lid 4), 163. Follows Constitutioneel Hof CH-02 of
  5 Aug 2022 (S.B. 2022 no. 85) on the Kiesregeling (that ruling struck Kiesregeling arts. 9 and 24, not Grondwet text).
- S.B. 2025 no. 15 (Resolutie 6 feb 2025) republishes the text as amended by 1992 and 2023 only: no other amendment.
- Pending, not law: initiative proposals to amend the Grondwet (DNA 25/1986 Dec 2025; VIDS petition 2025).

## Default in-force rule

Grondwet art. 80 lid 1: bills approved and ratified "verkrijgen kracht van wet na afkondiging"; art. 118: the manner of
afkondiging and the time laws become binding are set by law; Wet Algemene Bepalingen (G.B. 1868 no. 14) art. 1: no
regulation binds until afkondiging. So: a law binds from its afkondiging (the Staatsblad issue date) unless its own
slotbepaling says otherwise (most say "de dag volgende op die van haar afkondiging").

## Exact endpoints (all in fetch.py; cache name = sha256(url))

- 1992 consolidation (use this): https://www.dna.sr/media/vyjchhar/grondwet-suriname.pdf (45 pp, text layer, 2005 PDF)
- 1992 consolidation, 2nd copy (cross-check only): https://gov.sr/wp-content/uploads/2023/09/grondwet_suriname.pdf
  It has its own typos (art. 56 lid 2 lacks "oorlog"; art. 148 "Rege-ring"); the 12 dna/gov differences are these
  source typos plus parse layout, not mismatches of ours. Record them as decisions, not as errors.
- Current text: S.B. 2025 no. 15 https://sris.sr/wp-content/uploads/2025/04/RESOLUTIE-van-6-februari-2025-no.14.22724-houdende-plaatsing-staatsblad-republiek-suriname-thans-geldende-tekst-grondwet-rep-sur-S.B.-2025-no.-15.pdf
  (text starts on page index 2; page header "2025 -N- No. 15"; footnotes "Gew. bij S.B. 2023 no. 157")
- S.B. 2023 no. 157 (scan, no text layer): https://www.dna.sr/media/o4jhmh2z/sb_2023___157.pdf
- 1992 MvT: https://www.sris.sr/wp-content/uploads/2020/06/Grondwet-met-Mvt.pdf
- Wetboek van Strafrecht consolidation to 2005: https://www.dna.sr/media/ancdliva/wetboek_van_strafrecht.pdf ;
  amendments (scans, mostly): S.B. 2006 no. 42, 2009 no. 34, 2009 no. 122 (zeden), 2011 no. 96, 2012 no. 70, 2014 no. 118,
  2015 no. 44 (Wet 30 mrt 2015, big revision), 2020 no. 42, 2023 no. 133. URLs in the fetch log / fetch.py ACT_PAGES.
- Burgerlijk Wetboek consolidation to 2005: https://www.dna.sr/media/kjwc3hl3/burgerlijk_wetboek.pdf ; "Nieuw burgerlijk
  wetboek" page has no single PDF link captured (check page); amendments: Wet 9 mei 2016 (S.B. 2016 no. 67?)
  /media/gq0j2hnx/..., S.B. 2022 no. 34.
- No data protection law found in the DNA lists (only Wet Elektronisch Rechtsverkeer). Say so in README.

## Grondwet: done (2026-10-28)

Fixed after restart: (1) `` in joinlines had become a literal backspace (Bash heredoc ate it; edit .py with
Edit/Write or byte-level Python); (2) S.B. 2025 note 60 (art. 163) sets its number in Courier: footnote-only lines now
keep Courier digits; (3) hyphen joins: "Vice-"+"President" keeps hyphen, "VOLKSRAAD-"+"PLEGING" drops it, "uit- en"
kept; (4) relayout(): 1992 units take S.B. 2025 line breaks where the words agree (preamble, 66, 93, 114, 142).
Verification: verify_text.py word sequence check vs PDF (0 unexplained for 2025); HEAD files == fresh
parse of S.B. 2025 no. 15 (188/188). S.B. 2023 no. 157 page images compared by eye: arts 60/61/163 identical, art 161
lid 4 act has "per ressort, en de" (comma) that S.B. 2025 lacks: recorded in decisions, NOT applied (would be
transcribing a scan). art. 56 "oorlog": dna.sr + sris MvT have it, gov.sr + S.B. 2025 lack it -> 2025 uncredited.
Publisher renamed to "Staatsblad van de Republiek Suriname (dna.sr, sris.sr)" <staatsblad@dna.invalid>.

## Phase 2 feasibility (text layer per cached PDF, PyMuPDF)

- WvSr 2005 consolidation: 117 pp, text. Amending acts: 2006/42 SCAN, 2009/34 SCAN, 2009/122 SCAN, 2011/96 text
  (terrorisme), 2012/70 text (belaging), 2014/118 SCAN, 2015/44 text (237 pp, big revision), 2020/42 text, 2023/133 SCAN.
- BW 2005 consolidation: 384 pp, text. 2016 (Wet 9 mei 2016) SCAN, 2022/34 SCAN.
- No current official consolidation of WvSr or BW online -> today's text cannot be verified against an official text.
- 2015/44 re-enacts WvSr Books I-III in full ("komen te luiden als volgt"), so a 2005 -> 2015 history is possible,
  but later: S.B. 2017 no. 85 (not in DNA lists), 2020/42 (publisher OCR layer with errors "Straftecht",
  "belcrachtigd"), 2023/133 (scan) -> the text in force today cannot be built. Decision: stop Phase 2; a WvSr frozen
  at 2015-2020 would give wrong on-date answers for today.

## Next steps (only if someone wants more)

0. More born-digital acts on sris.sr that look buildable as "as enacted, not amended" single versions (check the
   media listing for later amendments first): Handelsregisterwet (S.B. 2024 no. 169), Algemene termijnenwet
   (S.B. 2024 no. 167), Overgangswet nieuw BW (S.B. 2024 no. 166), Wet Constitutioneel Hof (2019, check amendments),
   Comptabiliteitswet 2024 (S.B. 2024 no. 178, amended S.B. 2026 no. 51: two versions if both have text layers).
1. If an OCR policy is agreed (e.g. Windows.Media.Ocr, disclosed, human-checked), WvSr 2015 + 2017/2020/2023 replay
   becomes possible; fetch S.B. 2017 no. 85 first.
2. Art. 161 lid 4 comma (S.B. 2023 no. 157 scan vs S.B. 2025 no. 15): a human may add an explicit, sourced erratum.

## Gotchas

- Scratchpad is shared with other agents; use a subfolder (sr/).
- Footnote superscripts are separate small spans (size<=8); body is size 12; DNA page numbers are CourierNew.
- Never transcribe scanned Staatsblad pages with a model (no model writes legal text).
- autopush.py owns wip/preview/main pushes; never build into the clone. Test in .tmp-build (gitignored).
