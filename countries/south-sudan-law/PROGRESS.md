# South Sudan (gitlaw-SS): progress and handoff

Repo: lexifina/south-sudan-law (private scaffold, cloned at C:/Users/alany/Documents/south-sudan-law; untouched).
Stopped at the coordinator's wind-down (2026-10-29, ~00:40 UTC). **No corpus.json / corpus.d written yet, no PUBLISH.**

## Checklist
- [x] Probe sources (see below)
- [x] fetch.py: peachjam.Cache for direct hosts; archive.org through gitlaw_common/wayback.py; WIPO Lex signed-PDF helper
- [x] sources.json: every document pinned (Wayback capture timestamps), all cached in .cache/
- [x] corpus_meta.json: country, sources, laws, decisions, ai_use (all dates sourced)
- [~] parse.py: written, **buggy** (see Open bug); writes corpus.d/10-constitution.json + corpus.d/20-codes.json
- [ ] Build in .tmp-build, check.py, then copy corpus.d in; then 20-codes.PUBLISH + PUBLISH (codes only)
- [ ] repo/README.md, repo/LICENSE, repo/jurisdiction.json (copy scaffold's, set build)

## Sources (probed 2026-10-28)
- mojca.gov.ss "Laws of the Republic": ~80 PDFs as enacted, not consolidated, no amending acts. The site's TLS
  certificate is expired (SEC_E_CERT_EXPIRED), so everything is read from Wayback `id_` captures (not -k).
  Footer: "© Copyright. Ministry of Justice and Constitutional Affairs (MoJCA). 2023. All Rights Reserved."
- WIPO Lex: SS013 (TCRSS 2011: approved 7 Jul 2011, assented/in force 9 Jul 2011), SS018 (TCRSS Amendment Act 2013:
  assented 26 Feb 2013, commenced 1 Mar 2013; **scan, no text layer → left out**), SS019 (constituteproject print,
  reconciliation only). PDF links on details pages are signed and expire in ~1 min (fetch.get_wipo handles it).
- Two ministry copies of the Constitution: uploads/2023/03 (203 arts, PDF made 12 Jul 2011) = enacted text (matches
  Constitute's numbering and Art. 100); uploads/2023/04 (201 arts, sudantribune Word file of 24 Apr 2011) = pre-adoption
  draft, = WIPO SS013 file. Use 2023/03.
- Labour Act 2017 cites the Constitution "(Amended 2015)": a 2015 amendment exists; no official text found.

## Phase 1 choice and dates (all from the sources)
- Constitution 2011, from 2011-07-09 (Art. 198). Preview only: later amendments unavailable as text → never PUBLISH.
- Penal Code Act 2008 (Act 9): in force 2008-08-22 (s.1 + margin "Signed on 22nd August, 2008"); gazette 2009-02-10.
- Code of Criminal Procedure Act 2008 (Act 5): in force 2008-03-20 (margin "Signed on 20th March, 2008"); gazette 2009-02-10.
- Each code = one version (as enacted); ministry list has no amendments → codes can be PUBLISHed (part 20-codes) once
  parsed and checked.

## Cache (.cache/, ~9 MB): requests.jsonl logs every request
laws page capture, uploads CDX, both Constitution PDFs, Penal Code, CCP, Labour Act, Companies Act, WIPO SS013/018/019 + details pages.

## Open bug (exact next step)
`python -X utf8 parse.py .tmp/out` gives units {"constitution": 91, "penal-code": 4, "criminal-procedure": 3}:
expected ~207 / ~398 / ~300. Section starts are missed. Likely causes: (1) gazette section-heading blocks are at
x0≈44 but `num_rx` needs `b.x0 < cfg["left"] + 8` and the `expect` counter blocks resync after any missed number
(drop the strict `== expect` or allow `>= expect`); (2) for the Constitution, article blocks like "61." follow a title
inside the same block ("Seat of the National Legislature\n\n61.\n(1)...", page 30) — split blocks whose first line is
a title and second line is "N."; (3) check `centered()` isn't eating headings. Inspect with the block dumps used in
probing (fitz `get_text('blocks')`, pages 17-18 of the Penal Code, 11-12 and 30 of the Constitution 2023/03 file).
Then: build into .tmp-build, run check.py, write corpus.d atomically (parse.py without args), README/LICENSE.

## Ideas for the next country
- Check for an expired certificate first; Wayback CDX prefix query on /wp-content/uploads/ lists every PDF in one call.
- Gazette PDFs put the signature date in a margin note: read words with x0 > 0.76 * page width.
