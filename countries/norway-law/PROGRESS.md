# Norway (gitlaw-NO): progress / handoff

Repo `lexifina/norway-law` (private). Scaffold checked 2026-10-29 01:25 and 02:06 UTC: only `main` (0c85361, "Norway: sources, before any law"). No commits or pushes (CADENCE CHANGE). Local test builds in `.tmp-build` / `.tmp-build2` (gitignored). **PUBLISH written 02:06 UTC.**

## Sources (all Lovdata public data, NLOD 2.0, confirmed in Lovdata's own API description swagger/api.json)
- `lovtidend-avd1-2001-2025.tar.bz2` + `lovtidend-avd1-2026.tar.bz2`: Norsk Lovtidend avd. I, every law / constitutional amendment / central regulation as announced since 2001 (39,334 docs). Lovdata: Lovtidend is "den eneste offisielle og autorative kilden"; Norway has no official consolidations. **All text comes from here.**
- `gjeldende-lover.tar.bz2` (lastModified 2026-10-21): Lovdata's unofficial consolidated text. Used only for the end-to-end check and the per-provision "ikr." in-force notes.
- Cache: `.cache/` 77 MB, 6 requests (`requests.jsonl`), retrieved 2026-10-29. parse.py reads the tars directly (~20 s).

## Method
- `lovdata.py`: tar reading, a small DOM, text normalisation, act walker (parts/chapters/avsnitt), consolidated units, amendment notes.
- `replay.py`: interpreter for amendment instructions: § / ledd / punktum / bokstav / nr. (singular, plural, ranges, "nytt"), bm/nn payloads split at "–", moves of a ledd to another §, word substitutions (lists and inline), new/replaced chapters and parts, headings, "§§ X til Y oppheves", renumbering. Unreadable instructions raise (strict) or are logged (ordinary acts).
- `parse.py`: base text from Lovtidend, replay each amending document, date each changed provision (Lovdata note "ikr."/"i kraft"; else the law's own day; never before the act's first day; "Endres ved ... Kongen bestemmer" = pending, left out), compare with the consolidated text, write corpus.json atomically and parse.log.

## Status
| Act | Slug | Versions | Span | Replay vs consolidated |
|---|---|---:|---|---|
| Kongeriket Norges Grunnlov (bokmål) | grunnloven | 16 | 2014-05-06 (oldest available: language revision, FOR-2014-05-09-613) to 2024-05-21 | 0 mismatches (116 units) |
| Kongeriket Noregs grunnlov (nynorsk) | grunnlova | 16 | same | 0 mismatches (116) |
| Personopplysningsloven | personopplysningsloven | 3 | as enacted 2018-07-20, 2018-12-20, 2022-01-01 | 0 mismatches (44) |
| Arveloven (2019) | arveloven | 7 | as enacted 2021-01-01 to 2023-10-01 (lov 2026 nr. 48 pending, left out) | 0 mismatches (221) |
| Straffeloven (2005) | straffeloven | (69) | WIP, not written anywhere | 26 mismatches of 429 at 02:10 UTC |

- Final local build 02:11 UTC: 27 commits (main f548507 in scratch), 23 laws, 0 unexplained; check.py 0 mismatches, 0 trailer errors; --compare identical. Scaffold re-checked 02:11 (main only). PUBLISH current.

## Checklist
- [x] scaffold check, fetch.py, cache
- [x] Grunnloven bm + nn, personopplysningsloven, arveloven
- [x] README (English first + norsk), LICENSE (åndsverkloven § 14, NLOD 2.0), jurisdiction.json (build: built), tools/gjeldende.py
- [x] local build + check.py + --compare, PUBLISH
- [ ] straffeloven: parse.py replays it every run (69 versions, 81+2 amending laws) and writes `corpus.d/50-straffeloven.json` automatically once mismatches reach 0 (then also write `corpus.d/50-straffeloven.PUBLISH`). 26 left (parse.log "MISMATCH"): kapittel-08-a (heading "Kapitel 8 a" vs Lovdata "8 a."); §§ 5, 37, 48, 59, 79, 80, 274 (bokstav payloads mixing list items and following text, or renumbered letters "Nåværende bokstav i og j blir h og i"); §§ 39, 60, 74, 156, 185, 203, 272 (punktum-level edits, sentence splitting); § 52 b (list item with two sentences); § 91, 301, 303 (later additions/repeals of punktum inside a bokstav); § 107 («det menneskelige legemet» -> «den menneskelige kroppen» phrase edit); § 142, 253 (rewrites by 2012-06-22-49 / 2021-03-05-6 not picked up); §§ 189-191 (våpenlova 2018 amendments, check target phrasing); § 411 (its list of repealed laws). Laws named in notes but not replayed: see parse.log "but the replay changed nothing". Probe with one-op fallback: `python -X utf8 .tmp-tools/strl_probe.py` (gitignored; regenerates its cache pickle).

## Open issues / not included
- Grunnloven before 2014-05-06: old-language text not in the open archive (Lovtidend open data starts 2001 and holds only amendments 2003-2012, not a full text).
- personopplysningsloven: annexed GDPR text (EEA version) not included.
- arveloven §§ 103, 178: lov 19. juni 2026 nr. 48 not yet in force (no day set).
