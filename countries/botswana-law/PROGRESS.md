# Botswana (gitlaw-BW, then gitlaw-BW-MZ): progress and handoff

Repo lexifina/botswana-law (private). tz Africa/Gaborone, lang en, future branch `future`.
Status 2026-10-29 (gitlaw-BW-MZ): **built and verified locally; PUBLISH written** (main = Penal Code only).
Remote main was the scaffold `57f62e4` when PUBLISH was written. Nothing pushed or committed by this agent;
the 4-hourly autopush pass publishes.

## Checklist
- [x] Probe LII and government sources (below)
- [x] fetch.py (curl cache, `.cache/requests.jsonl`; archive.org through gitlaw_common/wayback.py); `sources.json` lists every URL parse.py reads (`fetch.py --all`)
- [x] parse.py: Blackhall HTML -> units (`s-001`, `s-051-a`, `s-020-to-029`, `schedule-1`); writes corpus.json (country, sources, shared decisions) + `corpus.d/10-constitution.json` + `corpus.d/20-penal-code.json`
- [x] Constitution: 2 versions (2019-05-26 oldest available; 2021-02-05 Act 1 of 2021, s 68). **No .PUBLISH** (preview only), see below
- [x] Penal Code (Cap. 08:01): 1 version 2024-12-04, 405 sections. `corpus.d/20-penal-code.PUBLISH` written
- [x] repo/README.md, LICENSE, jurisdiction.json
- [x] Local verification (docs-date 2026-10-29): full build 3 commits / 4 tags, check.py 0 mismatches 0 trailer errors, --compare identical; verified-only build (GITLAW_VERIFIED_PARTS_ONLY=1) 1 law commit + docs, check 0/0, --compare identical
- [x] PUBLISH
- [ ] Public Health Act (2019 capture) not built: only a 2019 text, today's text unknown (members-only)

## Decisions (also in corpus decisions)
- **Act 29 of 2022 (s 58: 57 -> 61 Elected Members), commenced by S.I. 93 of 2024: LEFT OUT.** Bulletin says "Date of Commencement: On Notice"; the S.I. 93/2024 page and the 2024 subsidiary list are members-only; one WebSearch found no open source for the date. So the Constitution's last version (2021-02-05) is not today's text and the part has no .PUBLISH.
- Constitution v2 = 2019 text with s 68 from today's e-Laws page (notes name only Act 1 of 2021 for s 68; bulletin: commencement 5 Feb 2021, "Amends: s 68"). parse.py asserts both.
- Today's e-Laws Constitution differs from 2019 in ~30 sections by unexplained editorial changes (authorize->authorise, "Vice-President", "(Cap. 01:04)" refs, "[Repealed by 32 of 1982, s. 2.]"); not built (no date). `python -X utf8 parse.py --diff` lists them.
- Oldest versions dated by the archive capture day (2019-05-26, 2024-12-04); publisher's as-at dates not stated.
- Penal Code is today's text: amendment list identical on the 2024-12-04 and 2026-03-23 captures; e-Laws bulletin search "penal code" (2026-10-29) lists nothing after S.I. 93/2023.
- Licence: "All right reserved. Government of Botswana." recorded in README/LICENSE; copyright status of legislation not verified; repo stays private.

## Sources probed
| Source | Result |
|---|---|
| BotswanaLII (www.botswanalii.org) | Cloudflare challenge; Wayback: cases only, no legislation. Not usable. |
| elaws.gov.bw (old AGC e-Laws) | Timeout. Wayback: Constitution only as a chapter export. Not used. |
| e-laws.botswanalaws.com (current official e-Laws, Blackhall) | Constitution page open (to S.I. 93/2024, per-provision notes). Everything else members-only (never bypassed). wp-json search/posts open (bulletin excerpts). |
| botswanalaws.com via Wayback | Captures with leaked paywall tag: Constitution 2019-05-26, Penal Code 2024-12-04, Public Health Act 2019-05-24. Paywalled captures still show amendment lists. |
| parliament.gov.bw | Hansard, bills; no Acts. |
| Common Crawl | index unreachable from here at probe time. |

## Cache
`.cache/`: ~75 files, ~10 MB, requests in `.cache/requests.jsonl`.

## Open issues
- If an open source for S.I. 93 of 2024's commencement appears, add Constitution v3 = today's e-Laws page (the editorial differences then become an "unexplained" publisher commit on that day, or a separate earlier publisher version) and write `corpus.d/10-constitution.PUBLISH`.
- WebSearch used: 4 (3 by gitlaw-BW, 1 by gitlaw-BW-MZ).
