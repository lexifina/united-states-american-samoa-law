# gitlaw-BE: Belgium progress

Repo: lexifina/belgium-law (PRIVATE, never change). Clone `C:/Users/alany/Documents/belgium-law` is owned by autopush (never build into it or push). tz Europe/Brussels, lang fr (French built; Dutch and German are equally official texts, not built), future branch `futur`, on-date tool `tools/en_vigueur_au.py`. Rules: `scripts/world-law/WAVE.md` -> `scripts/africa-law/FANOUT.md` -> `scripts/south-america-law/BRIEF.md`. Test builds only in `.tmp-build/`.

## Key finding: Justel is robots-disallowed

`https://www.ejustice.just.fgov.be/robots.txt` (fetched 2026-10-28) has `User-agent: *` with `Disallow:` for `/cgi_loi/`, `/eli/`, `/loi/`, `/mopdf/` (the Moniteur belge PDFs), `/cgi/` and every other dynamic path. That covers all of Justel, its archived versions (`article.pl?...&arch=NNN`) and the Moniteur belge.
Following the project rule (Paraguay SILpy, commons.laws.africa, German Länder portals): a robots-disallowed site is not crawled directly; it is read only through Internet Archive `id_` captures. Direct requests made: 2 (robots.txt and one probe of the Constitution ELI page, both 2026-10-28).

Consequences:
- Justel's archived versions (79 for the Constitution, from 1996-04-19) are NOT in the Wayback Machine (0 archived-version text pages for the Constitution, Code civil or Code pénal), so they can't be used.
- The Wayback Machine holds many captures of Justel's CURRENT consolidated text over the years (Constitution fr: ~100 captures 2009-2026; Code pénal 1867: ~360; Code civil 1804 parts: hundreds). History is rebuilt from those dated snapshots plus Justel's inline notes (`<L 2014-01-06/20, art. 1, 048; En vigueur : 31-01-2014>`), which give the amending law and in-force date of every marked change.
- Common Crawl obeys robots.txt, so it has no Justel pages (index query timed out; not pursued).
- Justel's inline notes for the Constitution only start with the 2012 revisions; earlier revisions are dated from the Vlaamse Codex (below).

## Sources probed

| Source | Status | Format | Dated versions | Amendment notes | robots / licence |
|---|---|---|---|---|---|
| Justel ejustice.just.fgov.be | 200 | HTML (ISO-8859-1) | "versions archivées" (not reachable, see above) | inline per change, with En vigueur date | robots disallows all of /cgi_loi/, /eli/, /mopdf/ -> Wayback only |
| Wayback id_ captures of Justel | 200 | same HTML | capture timestamps | same inline notes | archive.org, shared adaptive client |
| Vlaamse Codex open data API codex.opendata.api.vlaanderen.be | 200 JSON, swagger at /swagger/docs/v1 | JSON | per-article versions with dates (Grondwet only; no Burgerlijk Wetboek / Strafwetboek) | "(ing./verv. GW-wijziging <date>, I: <date>)" | no robots on API host; Flemish government open data |

## Facts checked
- New Code pénal (lois du 29 février 2024, Livres 1 et 2), published MB 8 April 2024, in force 8 April 2026 (WebSearch 1 of 4: news.belgium.be, lachambre.be).

## Handoff (2026-10-29 00:41 UTC, run stopped by coordinator)

- Built: nothing yet. No corpus.json, no PUBLISH, no fetch.py/parse.py. No background processes left running.
- Cached (`.cache/`, 13 MB): archive.org CDX lists (one request each) for `www.ejustice.just.fgov.be/cgi_loi/article.pl` (2,905 captures), `/cgi_loi/loi_a1.pl` (37,759), `/eli/constitution/` (27), `/eli/loi/` (3,004); 2 Wayback captures of the Constitution fr text (2016-07-31 loi_a1.pl, 2026-08-24 article.pl), with copies in `.tmp/c2016.html` and `.tmp/c2026.html`.
- Verified: the old `loi_a1.pl` (2009-2020) and the new `article.pl` pages have the same text markup: `<A NAME='Art.N'>`, `<BR>` per paragraph, `[<sup>n</sup> ...]<sup>n</sup>` change markers, and notes `(n)<L yyyy-mm-dd/nn, art. x, nnn; En vigueur : dd-mm-yyyy>`. Lengths in the CDX are compressed WARC sizes (~42 KB ≈ 220 KB HTML = full text).
- Constitution fr captures with full text: about 100 (2009-12-16 .. 2026-08-24), cn 1994021730, found under loi_a1.pl `DETAIL=1994021730%2FF`, `language=fr&la=F&...cn=1994021730`, and article.pl `cn_search=1994021730`. The 2016 page has 43 notes and the 2026 page 48. Notes start with the 2012 revisions; the new ones since 2016 are L 2017-10-24/03, 2019-04-22/06, 2021-03-17/02, 2024-05-15/01, 2025-06-12/07 and 2026-07-15/04.
- Vlaamse Codex: the Grondwet is document 1006998 (`/api/WetgevingDocument/numac/1994021048`). `/Structuur` lists chapters and articles, and `/api/WetgevingArtikel/{id}/Versies` gives article versions. Titles carry "(ing. GW-wijziging 25 april 2007, enig artikel, I: 26 april 2007)", which dates and credits the pre-2012 revisions that Justel doesn't note.
- Exact next step: write fetch.py to (1) dedupe the Constitution fr captures by CDX digest and fetch each through `wayback.get` (shared rate); (2) fetch the Codex Grondwet structure and article versions with curl at 1 req/s. Then write parse.py:
  - parse each snapshot into `art-NNN[-bis]` units, stripping markers and notes;
  - put the distinct states in capture order;
  - date and credit each changed article from the Justel note whose En vigueur date falls between the two captures, or else from the Codex article-version date and revision;
  - if neither explains a change, credit it to the publisher dated by the capture, and record it in `decisions`;
  - the first version is the 2009 capture, dated by the last revision before it (Codex), with `first_law: null`.
  Then do the same for the Code pénal 1867 (cn 1867060801, ~366 captures; repealed when the new Code pénal took effect on 2026-04-08), and the Code civil (old: cn 1804032130-34; new: 2019A12168 and its books 2020A20347, 2022A30600, 2022A32057/8, which have only 1-4 captures each).
- Open question for the coordinator: whether Justel can be fetched directly despite robots.txt. If yes, use the archived versions (`article.pl?language=fr&arch=NNN&...&cn_search=<cn>`) at 1 req/s; that gives full dated history from 1996, and most of the Wayback plan above becomes unnecessary.

## gitlaw-BE-2 (2026-10-29): DONE, all three parts verified and PUBLISHed (not pushed by me)

Remote main was the scaffold 74d1975 at start and when PUBLISH was written. Scratch: `%TEMP%/claude/.../scratchpad/be2/`.

**Sources**
- legalize-be (github.com/legalize-dev/legalize-be, pinned da37dfb18b17; data "Licence ouverte / open data fédéral belge (CC0 par défaut)", pipeline MIT). `fetch_legalize.py`: treeless clone (22 MB) -> `.cache/legalize/index.json`, 256 files via `wayback.host_get` (35 s).
- Justel pages via archive.org `id_` only (robots.txt disallows /cgi_loi/, /eli/, /mopdf/). `fetch_justel.py` lists French current-text captures from the cached CDX (article.pl, loi_a1.pl, eli/loi), one per half-year per text + newest 3 (`--all` for every one); ~250 captures cached. Justel pages from Sept 2026 on are bot challenges (unusable).
- legalize-be history is NOT clean: bootstrap file = oldest text for touched articles + today's text for the rest (incl. later insertions); later files partial and lagging; commit dates = publication (+10 days). Fixed by dating each article wording by the Justel notes it gained (`parse.py` timeline()).

**Parts** (`parse.py` -> corpus.d; `lmd.py` Markdown+notes, `justel.py` HTML->same Markdown)
- 10-constitution: 37 versions 1994-02-27..2026-07-24, 83 laws (titled "Révision de la Constitution du ..."), 1 unexplained (art. 140). Newest text from Justel 2026-08-24 (adds L 2025-06-12/07, L 2026-07-15/04 which legalize lacks). Final = that page exactly.
- 20-code-penal (1867): 178 versions 1990-04-05..2026-05-03, 175 laws incl. 2 court rulings (annulled italic words removed on MB publication day). Final = Justel 2026-05-03 exactly; all pages 2024+ exact. 61 unexplained (mostly Justel typo fixes), 41 "backwards" (euro notes Justel added in 2010), renumbered 417bis-quinquies -> 417/1-4. New Code pénal: NOT built; Justel note on livre I law art. 38: in force moved to 2026-09-01 by L 2026-03-30/01 art. 252 (press says both books took effect 2026-09-01; coordinator's 2026-04-08 is outdated); no official source for livre II's day, so the 1867 Code's replacement is not committed.
- 30-code-civil: ancien-code-civil 115 versions 2009-12-16..2026-05-19 from Justel parts 1804032130-35 (part 36 = pre-1976 matrimonial regime text, excluded; "344.1"/"344-1" labels unified); 114/144 pages exact on their day, each part's newest page exact; 183 unexplained, 27 dropped (Justel removed repealed arts), 10 renumbered. code-civil (2019-) 9 versions: books 1, 2.3, 3, 4, 5, 6, 8, 9.1 from Justel consolidated book pages (12 captures, all exact), each entering on its legalize/Justel "entry_into_force" day credited to its enacting law; 16 placeholders.
- verification/*.json: page-by-page comparison (written by parse.py).

**Local verification (2026-10-29)**: build into empty scratch repo -> 414 commits, 672 tags; check.py 0 mismatches, 0 trailer errors, 0 backwards/future/merges; `--compare` main_identical; parse.py output byte-identical on rerun. PUBLISH + 3 part .PUBLISH written.

**Open / next**: Dutch text; new Code pénal (needs the Justel consolidated "Code pénal" page or Moniteur text of L 2026-03-30/01); old Code civil parts 31/32/34 end at their newest capture (2021-2023); more captures (`fetch_justel.py --all`) would reduce unexplained/missed intermediate wordings in the old Code civil.

## Checklist
- [x] Probe Justel, robots, Wayback CDX, Codex API
- [x] Constitution (fr): legalize-be + Justel capture
- [x] Code pénal 1867 (new Code pénal not built)
- [x] Code civil (old from captures; new books)
- [x] repo/ docs, PUBLISH

WebSearch used: 2 (BE-1: 1; BE-2: 1, new Code pénal in-force date).
