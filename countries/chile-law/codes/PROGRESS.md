# gitlaw-CL-codes: Chile Phase 2 (helper agent)

Owns `corpus.d/50-codes.json` only (atomic writes: `.tmp`, then rename). The main agent owns corpus.json
(constitucion, codigo-civil, ley-19628). PUBLISH exists, so autopush pushes `main` on every part change: write the part
only after verify + test build are clean. Test builds: `.tmp-build/codes/` (NOT `.tmp-build-codes/`: autopush's wip
snapshot skips only `.tmp-build`, `.tmp`, `tmp`, so a sibling folder broke the 17:57Z wip snapshot with
"Invalid path wip/.tmp-build-codes/repo/.git/config"; moved at 17:59Z; one 18 MB ccom.json reached wip 15daf2c and
drops out at the next snapshot).

## Scripts (codes/)

- `fetch_codes.py [slug...]`: verified idNorma chains (`CHAINS`), reuses fetch.py (same cache/UA/log), 1 req/s; also
  fetches the unversioned current text for verify.
- `parse_codes.py [--acts ...] [--out PATH]`: imports parse.py (act_versions, Laws, read_version, key scheme) unchanged;
  adds ACT_META for the codes; stops if a law key names a different norm than corpus.json; writes the part atomically.
- `anachronism.py slug`: per version, notes naming a norm published after the version day (by D.O. date, or by a Ley
  number >= a Ley published > 60 days later). Cut rule: only when LeyChile's "Texto Original" holds no article text
  (CCom): start after the last anachronistic version. Otherwise single-provision defects are disclosed in version notes
  + decisions, history kept.
- `verify_codes.py [--corpus PATH]`: runs main verify.py on the part (today's text == LeyChile current text, every
  version's sha256 in the cache).
- `probe.py ids...`: prints cached versions list / refundidos chain for ids.

## Ids (verified 2026-10-28 by get_cadena_refundidos + get_versiones)

| act | chain | versions | notes |
|---|---|---|---|
| codigo-penal | 1984 | 165 (164 kept) | Texto Original 1875-03-01 has full text; first_law codigo-penal-1874 |
| codigo-comercio | 1974 | 38 (22 kept) | Texto Original 1865-11-23 = PDF link only; 1865-11-24..1988-01-20 anachronistic (e.g. art 180 holds Ley 18.528 1986 text) → starts 1988-10-20, first_law null |
| codigo-trabajo | 3471 → 207436 | 21 + 134 | Ley 18.620 (30011, 1987) has one undated "Única" version → not used; starts DFL 1 1994 (first_law null) |
| codigo-procedimiento-civil | 22740 | 45 | Ley 1.552 (1902) |
| codigo-procesal-penal | 176595 | 56 | Ley 19.696 (2000) |

## State (2026-10-28 18:35Z): DONE, all five codes on main; part stored as deltas

- [x] All five fetched (1 req/s), parsed, verify_codes.py 0 differences for every act (vs dated version and current
      page), every version sourced. Test build (`.tmp-build/codes/`): 495 commits, 958 tags, check.py 0 mismatches /
      0 trailer errors, --compare identical (main tip differs only by verification.json in REPRODUCE.md, as designed).
- [x] corpus.d/50-codes.json written 18:20Z (188 MB, sha256 4e41ffd7…), corpus.d/50-codes.PUBLISH written
      (coordinator rule: a part reaches main only with its own <part>.PUBLISH).
- [x] BUILD_STATUS 18:23:48Z: main pushed 8fc2c53, 8 acts, 519 versions, 0 mismatches, 490 commits.
- [x] Deltas (coordinator, SCHEMA.md "Large acts"): parse_codes.to_changes writes every version after the first as
      `changes` ({key: unit or null}); parse_codes.expand is the inverse (same as build.load); verify_codes.py expands
      to `.tmp-build/codes/verify-expanded.json` before running verify.py. Expanded delta part == old full part (exact);
      verify 0 differences; full vs delta build --compare: identical (history tip ef47415, 489 commits, 958 tags); the
      main tips differ only in REPRODUCE.md / data/corpus.sha256 (input corpus hash). Part rewritten 18:34Z: 6.8 MB
      (was 188 MB), sha256 ebc6f3f8…; 50-codes.PUBLISH kept. BUILD_STATUS 18:34:29Z: main pushed 761fcab, 8 acts,
      519 versions, 0 mismatches.
- CPP first version moved to 2000-12-16 by its own art. 484 (ACT_META `first`, like the Constitution).
- CT: DFL 1 1994 leaves named alike ("Artículo 40" for 40 bis A..D) re-keyed from their own text (parse_codes.rekeyed),
  so files line up with DFL 1 2003; no effect on the other codes.
- Open/ideas: CT 2003-2008 and CP 1977-1996 carry anachronistic notes on a few articles (disclosed in version notes +
  decisions); CP 583 changes unexplained (e.g. Ley 19.450 of 1996 has no LeyChile version; its changes appear on
  1997-05-17).

## Stats

- CP: 164 versions, 680 units now, 1622 unit changes, 1039 credited, 583 unexplained (e.g. Ley 19.450 of 1996 has no
  LeyChile version; its changes appear 1997-05-17, uncredited).
- CCom: 22 versions, 1528 units, 756 changes, 646 credited, 110 unexplained.
- CT: 149 versions (1994-01-24..2028-04-26; 6 future → futuro), 749 units, 1457 changes, 1364 credited, 93 unexplained.
- CPC: 14 versions from 2004-08-30 (Texto Original 1902 = no article text; 1902-08-31..2004-05-17 anachronistic), 1 unexplained.
- CPP: 55 versions from 2000-12-16, 1 unexplained.
- Cache: shared `.cache/` (main agent's), 505 MB total after this phase. WebSearch used: 0. Processes killed: none.

## Part 60-more (2026-10-28 19:16Z): DONE, on main

- Ids verified (get_cadena_refundidos + get_versiones): Código Tributario DL 830 = 6374 (92 versions from 1975-01-01);
  Código Sanitario DFL 725 = 5595 (94); Código de Aguas DFL 1.122 = 5605 (31, one 2222 event version left out);
  Ley 18.046 = 29473 (22); Ley 19.496 = 61438 (18) then DFL 3 2021 texto refundido = 1160403 (9). Fetched at 1 req/s.
- `parse_codes.py --part more` writes corpus.d/60-more.json (deltas, 4.1 MB); `--part codes` (default) writes 50-codes.
  The law-key clash check now also reads the other corpus.d parts.
- New in parse_codes (apply to both parts):
  - `unwrap`: a "doble articulado" norm (metadatos.doble_articulado: DL 830's "Artículo 1°.- Apruébase el siguiente texto
    del Código Tributario", DFL 3 2021's "Artículo único.- Fíjase el siguiente texto refundido") is read as the text it
    enacts; "(DEL ART. 1)" dropped from names. No effect on the codes part.
  - `lettered`: collision keys for "Artículo 54 O" / "54 Ñ" / "152 quáter Ñ" (parse.unit_key reads O as a degree
    sign and folds Ñ into N) become art-054-o / art-054-nn / art-152-quater-nn. This changed 50-codes.json (CT, CPP
    keys only); it was re-verified (0 differences) and rewritten; 50-codes.PUBLISH still holds.
- verify_codes.py: 0 differences for all 10 acts; test build of corpus.json + both parts: 692 commits, check 0
  mismatches / 0 trailer errors, --compare identical (history tip f0b26b4).
- Wrote 50-codes.json, 60-more.json and 60-more.PUBLISH 19:11Z. BUILD_STATUS 19:15:37Z: main pushed 0719e37, 13 acts,
  740 versions, 0 mismatches, 685 commits.
- Stats: CTrib 92 versions (1 future, 2026-11-01), 74 unexplained; CSan 52 (42 LeyChile versions identical to the one
  before, skipped), 13 unexplained; CAguas 30, 4 unexplained; Ley 18.046 22, 153 unexplained; Ley 19.496 25, 1
  unexplained.
- Ley 18.046's 1981-10-23 version holds later text (art. 69 bis of Ley 18.660, 1987); resolved by the correction below.

## Anachronism correction (coordinator decision, 2026-10-28 19:25Z): DONE, on main

- Rule (parse_codes.correct, replaces the old disclose-only notes; applies to both parts): a provision whose note, in
  a version dated D, names a norm published after D (codes/anachronism.py) is corrected only in that run of versions:
  new in the run with no norm in force that day credited → left out (the late norm inserted it); otherwise, where
  its text differs from the text before the run → "[La fuente no da el texto vigente en esta fecha.]", uncredited
  (publisher). In the first version after the run the LeyChile wording arrives, credited to the norm(s) the notes
  name (laws registered with parse.Laws.from_note); version notes on both ends; one decision line per act lists
  every corrected provision with its span.
- Examples: Ley 18.046 art. 69 bis absent 1981-10-23..1981-10-31, arrives 1987-10-20 (Ley 18.660); CP art. 367
  placeholder 1977-12-14..1996-03-08, wording from 1997-05-17 credited to Ley 19.450 (LeyChile has no version on its
  day, D.O. 1996-03-18); CT arts. 415-424 placeholder from 2003-01-16, arriving with Ley 20.022 (2005-05-30) / Ley
  20.252 (2008-03-29).
- verify_codes.py: 0 differences for all 10 acts (today's text unchanged); test build 706 commits, check 0 mismatches /
  0 trailer errors, --compare identical (history tip 8d6072d). Parts rewritten 19:25Z (50-codes 6.8 MB, 60-more
  4.1 MB); both .PUBLISH kept. BUILD_STATUS 19:25:01Z: main pushed 38228f9, 13 acts, 740 versions, 0 mismatches.
- Unexplained now: CP 592, CCom 110, CT 104, CPC 1, CPP 2, CTrib 75, CSan 13, CAguas 4, Ley 18.046 178, Ley 19.496 1.

## Part 70-batch3 (2026-10-28 20:10Z): DONE, on main

- Ids verified (get_cadena_refundidos + get_versiones), fetched at 1 req/s: Código Orgánico de Tribunales Ley 7.421 =
  25563 (229 versions); Código de Minería Ley 18.248 = 29668 (17); Código Aeronáutico Ley 18.916 = 30287 (11); Código
  de Justicia Militar Decreto 2.226 of 1944 = 18914 (39; DL 806 of 1925 = 6363 has one version only, not used,
  first_law null); Ley 20.393 = 1008668 (10); Ley 19.880 = 210676 (9; 2026-11-01 → futuro); Ley 18.010 = 29438 (12).
- `parse_codes.py --part batch3` → corpus.d/70-batch3.json (deltas, 4.0 MB) + 70-batch3.PUBLISH. Anachronism rule
  applied (COT: 23 flagged versions 1950-2018; CJM: 30 flagged 1944-2005, many provisions left out until the law
  that inserted them, e.g. arts. 3 and 5 until Ley 19.047, 1991).
- Fixes in parse_codes (no change to 50-codes / 60-more, regenerated byte-identical):
  - law-key clash: parse.law_key gives numberless norms of one type+year one key ("SEN S/N de 2009"); when another
    part uses the key for a different idNorma, this part's law becomes `<key>-<idNorma>` (sen-s-n-2009-1004668).
  - LeyChile tipoVersion "Con Vigencia Diferida por Evento y Derogación Diferida por evento" (CMin, dated 2222-02-02)
    is not caught by parse.py's exact match and broke git fast-import ("invalid raw date 7955161200"); such versions
    are now left out too, with a decision line.
- verify_codes.py: 0 differences for all 7; test build (corpus.json + 3 parts): 988 commits, check 0 mismatches / 0
  trailer errors, --compare identical (history tip 1076b6d). BUILD_STATUS 20:10:27Z: main pushed 933949e6, 20 acts,
  1057 versions, 0 mismatches, 981 commits.
- Unexplained: COT 104, CMin 8, CAer 0, CJM 7, Ley 20.393 0, Ley 19.880 0, Ley 18.010 4.

## Part 80-batch4 (2026-10-28 20:40Z): DONE, on main

- Ids verified (get_cadena_refundidos + get_versiones), fetched at 1 req/s. Chains of textos refundidos as LeyChile
  gives them: Ley 18.695 = 30077 → Decreto 662/1992 (14962) → DFL 2/2000 (150973) → DFL 1/2002 (197482) → DFL 1/2006
  (251693); Ley 18.575 = 29967 → DFL 1/2001 (191865); Ley 19.039 = 30406 → DFL 3/2006 (250708) → DFL 4/2022
  (1179684). Single norms: Ley 20.000 235507, Ley 17.336 28933, Ley 18.045 29472, Ley 20.720 1058072, DFL 1 2005
  Salud 249177 (refundido of DL 2.763, Leyes 18.469, 18.933; first_law null, law key dfl-1-2006-249177 since
  published 2006), Ley 16.744 28650.
- `parse_codes.py --part batch4` → corpus.d/80-batch4.json (deltas, 4.9 MB) + 80-batch4.PUBLISH (20:34Z). Anachronism
  rule applied (Leyes 18.695, 18.575, 19.039, 18.045, 16.744, DFL 1 Salud have corrected provisions; listed in
  decisions). Parts 50/60/70 regenerate byte-identical.
- verify_codes.py: 0 differences for all 9; test build (corpus.json + 4 parts): 1166 commits, 29 acts, 1277 versions,
  check 0 mismatches / 0 trailer errors, --compare identical (history tip 42cbf30). autopush: main pushed 0ee975db
  (20:40:02Z), 29 acts.
- Versions / unexplained: Ley 18.695 81/156, Ley 18.575 15/14, Ley 20.000 8/0, Ley 17.336 12/3, Ley 19.039 9/2,
  Ley 18.045 31/67, Ley 20.720 5/0, DFL 1 Salud 35/1 (1 future 2027-05-25), Ley 16.744 24/9.

## Part 90-batch5 (2026-10-28 21:09Z): DONE, on main

- Ids verified (get_cadena_refundidos + get_versiones), fetched at 1 req/s: Ley 19.300 30667; Ley 18.834 30210 → DFL 29
  of 2005 (236392); DL 3.500 7147; Ley 21.595 1195119; Ley 19.913 219119; Ley 18.290 29708 → DFL 1 of 2009 (1007469);
  Ley 19.968 229557; Ley 20.084 244803; Ley 19.947 225128 and Ley 14.908 27977 (my first guesses 225377 / 27458 were
  wrong; found with `get_norma_json?idNorma=&idLey=<number>`, whose metadatos.id_norma gives the norm: 2 uncached
  lookups, not in requests.jsonl). Ley 14.908 continues from 2000-05-30 as art. 7 of DFL 1 of 2000 (172986).
- parse_codes additions (parts 50-80 regenerate byte-identical):
  - NORM_PART {172986: 7}: per-norm `part` (read_version + width_for wrappers), so Ley 14.908 reads only art. 7 of the
    DFL; DFL versions changing only other articles are skipped as identical.
  - any LeyChile version dated 2222-02-02 not typed exactly "Con Vigencia Diferida por Evento" (Ley 20.084's is typed
    "Última Versión") is left out, with a decision line.
- verify_codes.py now has one documented exception: an act passes when it equals the dated version in force and the
  unversioned page equals LeyChile's own 2222-02-02 (event-pending) version (Ley 20.084: arts. 7, 9, 35, 57 differ there).
- Decision added: Ley 20.084's art. 1 transitorio defers entry into force 18 months; LeyChile's dates kept.
- verify 0 differences for all 10; test build (corpus.json + 5 parts): 1397 commits, 39 acts, 1574 versions, check 0
  mismatches / 0 trailer errors, --compare identical (history tip cec7409). 90-batch5.json 5.8 MB + 90-batch5.PUBLISH
  written 21:08Z. BUILD_STATUS 21:09:07Z: main pushed d813fd85, 39 acts, 1574 versions, 0 mismatches, 1387 commits.
- Versions / unexplained: Ley 19.300 17/1, Ley 18.834 32/88, DL 3.500 75/327, Ley 21.595 4/0, Ley 19.913 23/0,
  Ley 18.290 87/45, Ley 19.968 24/1, Ley 20.084 10/55, Ley 19.947 9/0, Ley 14.908 16/0.

## Delayed vigencia (coordinator correction, 2026-10-28 21:31Z): DONE, on main

- Rule: commits are dated by when the text took effect. parse_codes.VIGENCIA + fold_vigencia: the first version is
  dated the day the act's own vigencia clause gives (quoted in the version note); LeyChile versions dated before it are
  folded into it (it holds the text in force that day; the note names, per folded version, the laws LeyChile credits
  and the provisions they changed). Day by Código Civil art. 48 (complete periods to midnight of the last day; months
  end on the same-numbered day, or the month's last day; days count from the day after publication; in force the next
  day). Check: Ley 20.720's "nueve meses después" (pub 2014-01-09) gives 2014-10-10 = LeyChile's own first day.
- codes/vigencia_scan.py lists every act's own entry-into-force sentences in its original text. Fixed (whole act
  deferred, LeyChile dated from publication): Ley 20.084 → 2007-06-08 (folds 2005-12-07, 2005-12-16, 2006-06-01
  Ley 20.110, 2007-06-02 Ley 20.191); Ley 19.947 → 2004-11-18; Ley 19.496 → 1997-06-06; Código de Minería →
  1983-12-14; Código Aeronáutico → 1990-08-09; Ley 18.695 → 1988-05-01.
- Already right in LeyChile: CTrib 1975-01-01, Ley 18.290 1985-01-01, Ley 19.968 2005-10-01, Ley 20.720 2014-10-10;
  CPP handled before (2000-12-16).
- Not fixed, no fixed day in the text: Ley 16.744 ("dentro del plazo de tres meses"), Ley 19.039 (from the publication
  of its reglamento), and the main agent's Ley 19.628 ("dentro del plazo de sesenta días"; not my part). Partial
  deferrals only (kept): Ley 19.300 (SEIA on its reglamento), Ley 19.913 (Párrafo 2° Título I, 150 days), Ley 18.575
  (arts. 24, 29, 45, 51, one year), Ley 18.046, Ley 18.010. CJM's "regirá desde el 1° de Marzo de 1926" is the 1925
  code's day, repeated in the 1944 texto refundido.
- All 5 parts verified (0 differences); test build 1394 commits, 39 acts, 1571 versions, 0 mismatches, --compare
  identical (tip 0ae9ab4). 60/70/80/90 rewritten 21:31Z (50 unchanged), .PUBLISH kept. BUILD_STATUS 21:31:34Z: main
  pushed 1eab4b06, 1571 versions, 0 mismatches.

## Part 95-batch6 + retroactive exemption (2026-10-28 22:15Z): DONE, on main

- Ids (get_norma_json?idLey=<n> → metadatos.id_norma, fetched through fetch.py so cached + logged; then chain +
  versions): Ley 19.537 81505; Ley 18.101 29526; Ley 20.285 276363; Ley 18.700 30082 → DFL 2 of 2017 (1108229); Ley
  20.584 1039348; Ley 19.733 186049; Ley 20.529 1028635; Ley 21.091 1118991. Skipped as told: Ley 21.719, Ley
  19.039's successor, Ley 21.400.
- Vigencia scan: Ley 20.285 "ocho meses después de publicada" (pub 2008-08-20) → first version 2009-04-21 (CC art.
  48 rule; NOTE: some sources give 2009-04-20, coordinator may want to check); Ley 20.584 ("primer día del sexto mes
  siguiente") = LeyChile's 2012-10-01 already; 18.700 and 21.091 from publication.
- anachronism.py change: a note is not anachronistic when LeyChile's versions list puts the norm it names in force on
  that version's day (retroactive law). Found via Ley 20.529: Ley 21.827, published 2026-08-12, in force 2026-07-01
  per LeyChile; without the exemption today's text got the placeholder and verify failed. This also drops earlier
  corrections where LeyChile dates the law to the version's day: CP arts. 375-381 + Títulos (Ley 19.335, published
  1994-09-23, LeyChile inicioVigencia 1993-12-24: looks like a LeyChile data error, 1993 for 1994; flag for the
  coordinator) and CT art. 48 (Ley 20.899). 50/70/80/90 rewritten; 60 unchanged.
- Rate rule from the user noted (up to 3 req/s, 3 parallel, halve + wait 60 s on 429/503): not yet needed, batch 6
  fetched at 1 req/s before it arrived. fetch.py's retry (sleep 5/10/15 s) does not halve; a wrapper is needed first.
- All 6 parts verified (44 acts, 0 differences; Ley 20.084's current-page exception as before); test build 1466
  commits, 47 acts, 1667 versions, 0 mismatches, --compare identical (tip 0d38537). BUILD_STATUS 22:15:15Z: main
  pushed 4dd2b363, 47 acts, 1667 versions, 0 mismatches, 1456 commits.
- Batch 6 versions / unexplained: 19.537 9/0, 18.101 6/5, 20.285 5/0, 18.700 40/57, 20.584 13/0, 19.733 6/0,
  20.529 12/2, 21.091 5/0.
