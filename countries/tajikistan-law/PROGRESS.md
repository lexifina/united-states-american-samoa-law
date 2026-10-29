# Tajikistan (gitlaw-TJ) progress and handoff (stopped 2026-10-29 ~00:40 UTC, coordinator wind-down)

Repo lexifina/tajikistan-law: scaffold checked 2026-10-28 (only `main`, one commit "Tajikistan: sources, before any law"). Clone at C:/Users/alany/Documents/tajikistan-law (autopush owns it). Never push.

## Done
- [x] scaffold check, source probe
- [x] corpus.json: Constitution, ONE version ("oldest version available", first_law null), 1999+2003 edition, Tajik, from parlament.tj/konstitutsiyai-jt/ IA capture 20170607141323. 100 articles + preamble + chapter headings. Test build in .tmp-build: check.py 0 mismatches.
- [ ] PUBLISH not written: not yet cross-verified unit by unit (a second official copy exists: majmilli.tj capture 20180307012116, same 1999+2003 edition).
- [ ] Known gap: chapter 9 heading (bob-09) not matched by parse.py's ordinal map; check the source spelling.

## Sources found (all .tj hosts time out from this machine; read via archive.org `wayback.get`, Common Crawl index was unreachable)
- adlia.tj (Ministry of Justice "Adlia", Russian): anonymous view = first 1,500 chars only; full text/redactions need paid login. Not usable.
- parlament.tj/konstitutsiyai-jt/ (2017-06-07, 2018-12-02 captures): Constitution 1999+2003 edition.
- majmilli.tj (Majlisi milli) WordPress pages, 2017-2019 captures: Constitution (2003 edition), Civil Code parts 1-3 (`кодекси-граждании-ҷумҳурии-тоҷикист`, `-2`, `-3`), Criminal Code (`кодекси-ҷиноятии-ҷумҳурии-тоҷикисто/` @20170829123004, consolidated to AMOJT 2016 No 11, with per-provision notes like "(қҷт аз 17.05.04 №35)" = credits). CDX list: .cache file 937c5363eba4… (majmilli.tj prefix, collapse=urlkey, limit 5000).
- parlament.tj 2013 RAR archives `/files/konunho/<year>/kodeksi_*.rar` (1998 kodeksi_jinoyati, 1999 kodeksi_grajdani_1/_2, 2005 kodeksi_grajdani_3, ...). Windows `C:/Windows/System32/tar.exe -xf` extracts them; `antiword -m UTF-8.txt` reads the .doc, BUT the Tajik letters are in a legacy font encoding (ҷ→љ, қ→ќ, ҳ→њ, ӣ→ї, ғ→ѓ, ӯ→ў): map them back in parse. kodeksi_jinoyati.doc is consolidated to AMOJT 2011 No 3 (not as enacted).
- No 2016-edition Constitution text located yet. Background CDX search output: .tmp/cdx3.txt (mmk.tj, majmilli.tj, president.tj, mfa.tj, ncz.tj, parlament.tj filtered for "konstitu").
- qonunguzori.tj = journal PDFs, not law text.

## Scripts
- probe.py / cdxq.py / cdxall.py / cdxf.py: CDX listings via gitlaw_common/wayback.py (cache .cache/, log .cache/requests.jsonl).
- peek.py URL TS: print a capture's text.
- parse.py: cache -> corpus.json (atomic).
- Test: `python -X utf8 ../gitlaw_common/build.py . --repo .tmp-build --docs-date 2026-10-28` then `check.py .tmp-build --corpus corpus.json`.

## Next step to resume
1. Read .tmp/cdx3.txt for a 2016-edition Tajik Constitution (try majmilli.tj new site, mmk.tj, president.tj, mfa.tj); add it as version 2 credited to a `raypursi-2016-05-22` referendum law (only referendum between 2003 and 2016, so all changes are its). Confirm the in-force day of the 2016 amendments.
2. Cross-check 2003 edition against majmilli capture; write PUBLISH.
3. Criminal Code: version A = parlament.tj RAR (to 2011 No 3, decode legacy font), version B = majmilli 2017 (to 2016 No 11); credit changed provisions from the "(қҷт аз DD.MM.YY №N)" notes.
4. Civil Code: majmilli parts 1-3 (2017 captures) + RAR originals.
WebSearch used: 1 of 4.
