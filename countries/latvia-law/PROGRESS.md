# Latvia (gitlaw-LV): progress

Agent: gitlaw-LV (fork wave L–Z). Rules: scripts/world-law/FORK.md (incl. FETCH RULE, rule 6), WAVE.md, africa-law/FANOUT.md, south-america-law/BRIEF.md.
Models: new-zealand-law (consolidations + history notes), norway-law, gitlaw_common.

## Checklist
- [x] Scaffold check 1 (2026-10-29 ~13:25 UTC): `git ls-remote` showed only `main` = 2ec6b39 "Latvia: sources, before any law".
- [x] Scaffold check 2 (~14:20 UTC): `main` still 2ec6b39; `wip` and `preview` exist and are the coordinator's snapshots/builds of THIS folder (wip commits "Work in progress: scripts/latvia-law at ..."). Expected.
- [x] Probe sources (below)
- [x] Satversme: 17 versions (16 likumi.lv redakcijas 1922-11-07 .. 2019-01-01, plus 2002-11-05 dated by note), 15 amending laws + the 1922 enactment, 1 unexplained (art. 52 capitalisation, publisher). verify.py OK.
- [x] Krimināllikums: 83 versions 1999-04-01 .. 2026-10-15. Base version = the act as published in Latvijas Vēstnesis 199/200 (vestnesis.lv/ta/id/88966; no capture of likumi.lv's base version exists); 81 archived likumi.lv versions; 2014-04-09 not archived and no note names it (no commit). 4 unexplained units. verify.py OK (534 units = newest capture 2026-10-19, version 2026-10-15).
- [x] Fizisko personu datu apstrādes likums: 3 versions (2018-07-05 base = gazette LV Nr. 132, 04.07.2018, vestnesis.lv/ta/id/300099; 2019-05-31; 2021-06-04), 2 amending laws. verify.py OK (58 units).
- [x] Final local build (.tmp/b1, docs-date 2026-10-29): 122 commits, 207 tags, 115 law commits, 4 unexplained commits (5 units: Satversme art. 52 1933; KL arts 55, 58.1 2006-01-01, 225 2015-01-01, 289 2022-01-01); check.py 0 mismatches / 0 trailer errors / 0 backwards / 0 future; --compare identical (main 1f8ecad).
- [x] PUBLISH rewritten (all 3 acts). repo/README.md (English + Latvian section), LICENSE, jurisdiction.json written.
- [x] Scaffold check 3: remote main 2f50e94 = the coordinator's push of this folder's build (PUBLISH existed), plus wip/preview and tags from this corpus. No other session.

## Source probe (2026-10-29)
| Source | Result |
|---|---|
| likumi.lv (VSIA Latvijas Vēstnesis, consolidated texts) | HTTPS (443) times out from this machine; port 80 only 302s to HTTPS. Read via archive.org `id_` captures only. Each version page carries per-article notes `(dd.mm.yyyy. likuma redakcijā, kas stājas spēkā dd.mm.yyyy.)` linking the amending law and the version, plus the full version list as JSON (`ver_date`). |
| archive.org CDX `likumi.lv/ta/id/<id>` prefix | Satversme 16/16 versions; KL 81/84 (base 1999-04-01 and 2014-04-09 missing); FPDAL 2/3 (base missing). |
| Common Crawl (byte-range index fallback) | Works (likumi.lv/ prefix: 26,750 captures in 2 s), but holds only main act pages (current text), no `redakcijas-datums` version pages. Not used for history. |
| www.vestnesis.lv (official gazette) | 200 direct; robots.txt Crawl-delay 1 (kept). `/ta/id/<id>` = official publication as published; used for amending-law metadata and for base versions. |
| vestnesis.lv/atkalizmantosana | Re-use of officially published information "is to be agreed with the official publisher in writing", fees per MK noteikumi Nr. 536. Recorded in licence_note/LICENSE; repo stays private. |
| data.gov.lv (CKAN API) | No legislation dataset or bulk route (searched; Saeima has only `saeimas-sedes`, TM 5 statistics sets, all CC0). |
| legalize-dev/legalize-lv | Checked (blob:none clone, 16,511 commits). LICENSE data: "brīvi pieejams (oficiālie valsts izdevumi nav aizsargāti ar autortiesībām)". Not usable as history: Krimināllikums and FPDAL have ONE commit each ("[bootstrap] ... versión original 1998/2018") that holds today's text; Satversme's 191 commits are 1970-01-02 bootstrap + 2026 "[reform]" re-snapshots. No text taken. |

## Files
fetch.py (CDX + pinned captures -> captures.json; `--laws` fetches vestnesis.lv law pages), likumi.py (page -> units/notes), vestnesis.py (1990s gazette page -> units), parse.py (-> corpus.json), verify.py (replay == newest capture), acts.json, captures.json. Cache .cache/ (107 MB, 302 requests, gitignored).

## Open issues
- Licence: vestnesis.lv says re-use of official publications needs a written agreement with the publisher (MK noteikumi Nr. 536). Repo must stay private until the user decides.
- KL version 2014-04-09 not archived (no note names it; no commit). Satversme 1934-1993 interruption described in README only.
- Phase 2 not started (Civillikums, Darba likums ...): same pipeline, archive.org coverage to check per act.
- none for the builder.
