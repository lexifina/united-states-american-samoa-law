# gitlaw-FR: France progress

## State 2026-10-29 02:10 UTC (gitlaw-FR, second agent)

**BLOCKER for PUBLISH: remote main is NOT the scaffold.** Read-only check (ls-remote + fetch into a throwaway bare repo, since deleted): `refs/heads/main` = `a6e16b1` "SOURCES, BEFORE ANY LAW, BYPASSED TEMPORARILY TO UPLOAD THESE LAWS." by alan-yahya at 2026-10-29 00:22 UTC, on top of `acb80b1` and a separate 187,164-commit France build (top-level `codes/ constitution/ textes/ corpus.json data/ tools/`; arrêtés/décrets up to 23 Oct 2026). A PUBLISH here would let autopush force-push our build over that upload, so **no PUBLISH files were written**. Needs a user decision. remote `wip` = 9a01402 (autopush snapshot).

Done (all local, nothing pushed or committed):
- [x] parse.py -> corpus.json (country + Constitution), corpus.d/20-code-civil.json, corpus.d/30-code-penal.json. `python -X utf8 parse.py [slugs] [--report]` (~11 s); `--report` writes `.tmp-build/credits-<slug>.tsv`.
- [x] `extract.py --titles` -> `.cache/legi-texts/<cid>/` (2,849 of 3,115 linked texts; list in `.cache/legi-texts.json`), used for law labels/titles/nature/publication dates. ~35 min.
- [x] test_parse.py: 10 tests pass (17 Constitution changes, Code civil traps).
- [x] verify.py: on 2026-10-28 each act = LEGI versions in force = VIGUEUR set = texte/struct listing, 0 differences: Constitution 109, Code civil 2,899, Code pénal 1,301.
- [x] Local build into empty `.tmp-build/repo-a` (docs-date 2026-10-28): 584 commits, 1,060 tags, 550 law commits, 31 unexplained commits, 3 future; check.py 0 mismatches, 0 trailer errors, 575 versions; `--compare` rebuild identical (main_identical true).
- [x] repo/README.md (EN + FR), LICENSE (Etalab 2.0 attribution + CC0), jurisdiction.json, tools/en_vigueur_au.py.

Acts (start dates, see START_REASONS in parse.py):
| act | start | versions | changed provisions | credited | unexplained |
|---|---|---|---|---|---|
| constitution | 1958-10-05 as enacted (first_law constitution-1958-10-04, referendum) | 24 | 148 | 146 | 2 (art. 28 1963, art. 7 1976: LEGI names no text) |
| code-civil | 1994-01-01 oldest version available | 222 (3 on futur) | 3,656 | 3,597 | 59 (29 gaps -> placeholder, 2004 arts 2284-2302, ...) |
| code-penal | 1994-03-01 (commencement), earlier_laws 92-683/684/685/686, 92-1336 | 329 (1 on futur) | 2,926 | 2,906 | 20 |

Crediting rule (settled on the Constitution; all 25 revisions 1960-2024 land on their LEGI day with the right law):
- new wording = version's own CREATION/CREE/MODIFICATION/MODIFIE/TRANSFERT/TRANSFERE/DEPLACEMENT/DEPLACE links (either sens), signed <= DATE_DEBUT, minus links the previous version carried when it took effect (same cid + amending article), latest signing date only.
- removal = ABROGATION/ABROGE/TRANSFERT/TRANSFERE/DEPLACEMENT/DEPLACE links on the ended version, signed <= end, minus inherited, minus transfer links of its own creating provision (explicit ABROGE from it counts: loi 2016-1087 art. 4, arts 1386-19..25), latest only.
- abrogated-state version (ETAT ABROGE*, no gap, same words as previous, no new creator, abrogation link <= DATE_DEBUT) = absence (Code civil arts 9, 10 in 1927).
- gap after a MODIFIE-ended version = placeholder "[La source ne donne pas le texte en vigueur à cette date.]", unexplained.
- Sanity: no credited text signed > 3 years before its change except ordonnance 2025-1091 (in force 2029-01-01, futur).

Open / next:
- [ ] User decision on remote main (see blocker). If the scaffold is restored or our build is wanted on main: re-run the read-only check, then write PUBLISH (corpus.json) and corpus.d/20-code-civil.PUBLISH, corpus.d/30-code-penal.PUBLISH with one line each: "2026-10-29: verify.py: text in force on 2026-10-28 equals the LEGI article versions in force (and VIGUEUR, and texte/struct) article by article; check.py 0 mismatches, 0 trailer errors; --compare identical."
- [ ] Compare with steeve/france.code-civil (prior art, reconciliation only) once the Code civil has a pre-2015 overlap: ours starts 1994, theirs ends 2015-03.
- [ ] Phase 2: Loi 78-17, CPC, Code du travail (all extracted in .cache/legi; add to ACTS with a start date each).
- Never push/commit; autopush pass every 4 h.

---

# Previous handoff (first agent)


Repo lexifina/france-law (PRIVATE; scaffold `acb80b1`, cloned at `C:/Users/alany/Documents/france-law`, owned by autopush). tz Europe/Paris, lang fr, future branch `futur`, on-date tool to write: `repo/tools/en_vigueur_au.py` (wrapper around tools/on.py, like chile-law's en_vigor_el.py). Rules: `scripts/world-law/WAVE.md` → `scripts/africa-law/FANOUT.md` → `scripts/south-america-law/BRIEF.md`.

## State

- **No corpus.json yet, no PUBLISH.** Nothing built or pushed beyond the scaffold.
- [x] fetch.py: LEGI dumps from https://echanges.dila.gouv.fr/OPENDATA/LEGI/ (Licence Ouverte / Etalab 2.0). Cached: `Freemium_legi_global_20250713-140000.tar.gz` (1.1 GB) + all 479 daily increments after it, to `LEGI_20261028-212713` (3.6 GB total, 480 archives, all pass `gzip -t`). plan.json lists them. fetch.py now gzip-tests every archive (two arrived truncated with HTTP 200 after a 600 s stall; refetched).
- [x] extract.py: replays global + increments (deletions from liste_suppression_legi.dat first, then files) into `.cache/legi/<dir id>/` for the 6 texts. Done: 201,725 files written, 5 deleted; log in `.cache/extract.json`. Takes ~6 min.
  - Constitution 1958 `JORFTEXT000000571356` (LEGITEXT000006071194): 244 article versions, NUMs 1–93 + `PREAMBULE`
  - Code civil `LEGITEXT000006070721`: ~6,400 versions, from 1804-03-21 (some 1803)
  - Code pénal `LEGITEXT000006070719`: ~3,700; Loi 78-17 `JORFTEXT000000886460` (LEGITEXT000006068624): ~470; CPC `LEGITEXT000006070716`: ~4,500; Code du travail `LEGITEXT000006072050`: ~42,000
- [ ] parse.py (not started) → corpus.json; [ ] repo/ docs (README EN+FR, LICENSE Etalab 2.0 attribution "Source : DILA, Légifrance, base LEGI", jurisdiction.json from the clone, tools/en_vigueur_au.py); [ ] verify against current Légifrance text (= LEGI VIGUEUR versions); [ ] PUBLISH.
- Prior art (reconciliation only, never copy): `steeve/france.code-civil` bare clone in `.cache/priorart/cc.git`: 281 commits, 1803 (clamped 1970) to 2015-03, 2,803 files `Livre/Titre/Article N.md`. Compare its law list and a few articles' text on 2015-03-31 once built.
- WebSearch used: 0 of 4.

## Findings on LEGI article XML (for parse.py)

- One file per article version: `META_ARTICLE/{NUM,ETAT,DATE_DEBUT,DATE_FIN}`, text in `BLOC_TEXTUEL/CONTENU` (HTML: `<br/>`, `<p>`, tables), `NOTA` (editorial, keep out of text), `VERSIONS` (all versions of the article, with ids and dates).
- Skip versions with DATE_DEBUT >= DATE_FIN (`MODIFIE_MORT_NE`: 8 in the Constitution, 37 in the Code civil). DATE_FIN `2999-01-01` = open. `VIGUEUR_DIFF` versions with future DATE_DEBUT go to `futur`.
- **Crediting (key finding):** the law that made a version is NOT reliably in the version's own `sens="source"` links: those accumulate the article's whole history (e.g. art. 2103 version of 1971 lists MODIFICATION links of 1955, 1959 and 1971), and for 2010s+ versions they are often absent (Code civil: 899/908 versions of 201x have no source-side creating link). The current version of art. 1240 (2016-10-01) instead carries `sens="cible" typelien="MODIFIE"` → Ordonnance n°2016-131 du 10 février 2016 - art. 2. Next step: test the rule "credit = links (either sens) of type CREATION/CREE/MODIFICATION/MODIFIE/TRANSFERT/DEPLACEMENT on the new version with datesignatexte <= DATE_DEBUT, the latest signing date only; removal = ABROGATION/ABROGE/TRANSFERT links on the ended version with date <= DATE_FIN", measure explained/unexplained per decade (script idea in `.tmp-build/scratch/gaps.py`), and leave the rest "unexplained" (publisher DILA).
- **Abrogated-state versions:** e.g. Code civil art. 9 has a version 1927-08-14 → 1970-07-19, ETAT ABROGE, still holding the old text, with an ABROGATION link (Loi du 10 août 1927) dated before its DATE_DEBUT. Treat such a version (ETAT ABROGE and abrogating link dated <= DATE_DEBUT) as the article being absent from DATE_DEBUT; list every case in decisions.
- **Old history is incomplete:** the Code civil has 1,427 versions from 1803–1804, but e.g. art. 9 has no version between 1804 and 1889. Same-NUM gaps without abrogation are rare (≤24 per decade), so measure "articles first appearing without a creating law" per decade and choose a start date per code (`first_law: null`, "oldest version available"), stating it plainly in README. Constitution: start 1958-10-05 with first_law the Constitution (check all its versions' creation links).
- Unit keys from NUM: `art-NNNN[-NNN…]` (pad first number to the act's max width, later numbers to 3), prefixes `l-`, `r-`, `d-` for codes with parts (Code du travail L/R/D, Code pénal R); `PREAMBULE` → `preambule`. Handle `R*` and duplicates (two live versions of one NUM: 2 overlaps in 180x, 19 in 199x in the Code civil) by taking the latest DATE_DEBUT and logging.
- Law keys from link attributes: `naturetexte`+`numtexte` (`loi-2016-1547`, `ordonnance-2016-131`), else nature+signing date+NOR; label from the link text before " - art."; url `https://www.legifrance.gouv.fr/jorf/id/<cidtexte>`; kinds LOI/LOI_ORGANIQUE/LOI_CONSTIT/ORDONNANCE → law, DECRET/ARRETE → decree, DECISION (Conseil constitutionnel) → court; Loi 62-1292 and Loi constitutionnelle 2000-964 → referendum.
- Default in-force rule: Code civil art. 1 (laws enter into force on the date they fix or, failing that, the day after publication in the JO); LEGI's DATE_DEBUT already applies it.
- Use `changes` versions (SCHEMA.md "Large acts") for the codes; Code du travail is ~42k versions.

## Exact next step

Write `parse.py` (reads `.cache/legi/` only), test-build the Constitution alone into `.tmp-build/repo`, run check.py, then add Code civil and Code pénal; write corpus.json atomically; PUBLISH only after comparing the 2026-10-29 state with the VIGUEUR versions and checking credits on a sample against Légifrance.

## Background processes

None running (fetch and extract finished).
