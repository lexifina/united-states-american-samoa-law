# Peachjam LIIs: probe record and how-to

`scripts/africa-law/peachjam.py` is the one adapter for every Laws.Africa Peachjam legal information institute.
A country folder holds only configuration. This file records what was probed on 2026-10-28 and how to add the next
country in about 30 minutes.

## 1. Probe record (2026-10-28)

### robots.txt (identical template on all three LIIs)

- `User-agent: *` gets `Allow: /` with `Crawl-delay: 5`, and disallows `/api/`, `/search/`, `/judgments/`,
  `/gazettes/`, `/akn/*/provision/*`, `/akn/<cc>/judgment/`, `/akn/<cc>/officialGazette/`.
- `Content-Signal: ai-train=no, search=yes, ai-input=no`. ClaudeBot, anthropic-ai, GPTBot and the other named AI
  crawlers get `Disallow: /`. We fetch with curl and the lexifina-watch User-Agent; parsing is deterministic code and
  no legal text is given to a model.
- `Crawl-delay: 5` is stricter than our 1 request per second, so peachjam.py waits 5 s between requests to any LII
  host (`DEFAULT_DELAY`; only ZambiaLII's and ULII's open listing pages are ever requested). archive.org requests go
  through `scripts/gitlaw_common/wayback.py` (one adaptive rate for the whole machine), and Common Crawl is tried
  first (see "Archives" below).
- `new.kenyalaw.org` now 301-redirects to `kenyalaw.org`.

### Terms of use (`/terms-of-use/`)

| LII | Operator | Licence of content | Fetching |
|---|---|---|---|
| kenyalaw.org | National Council for Law Reporting (NCLR) | Only "documents as received from the source in their original unannotated form (raw documents)" are CC BY-NC 4.0. "Automated data scraping, bulk extraction, commercial redistribution, or training of machine learning/AI models without an explicit Licensing Agreement from NCLR is strictly prohibited." | Scraping, unauthorised bots and bulk downloading prohibited; bulk access by email (info@kenyalaw.org). |
| zambialii.org | SAIPAR (Southern African Institute for Policy and Research) | Primary and secondary law content CC BY-NC 4.0, crediting ZambiaLII as the source. | "Scraping and bulk downloading from this website is strictly prohibited"; bulk access by email. |
| ulii.org | Judiciary of Uganda (Library, Research, Law Reporting Committee) | Same wording as ZambiaLII: CC BY-NC 4.0, crediting ULII. | Same wording as ZambiaLII. |

Consequences:
- **The user's decision (2026-10-28, relayed by the coordinator):** "scraping wayback is fair game, dont overdo it,
  we need this data and it is legal". So: never fetch an LII's document pages and never touch its bot challenge;
  read only archived copies (Common Crawl, Internet Archive `id_` captures), pinned; only the acts built.
  Each country's `decisions` records the LII's terms and this decision; README and LICENSE give the licence and
  attribution exactly. The repositories stay private (CC BY-NC 4.0 is non-commercial; Kenya's grant covers raw
  documents only).

### Document pages are behind a bot challenge

| Request | ZambiaLII | ULII | Kenya Law |
|---|---|---|---|
| `/legislation/`, `/legislation/?years=Y` | 200 | 302 to `/en/legislation/`, then 200 | (not tried) |
| `/akn/<cc>/act/...` (work or expression) | 403, `Cf-Mitigated: challenge` (Cloudflare) | 403, Cloudflare challenge | 202 empty, `x-amzn-waf-action: challenge` (AWS WAF) |

### Archives

We do not get around a challenge. Every expression page is read from an archived copy, and the copy is pinned in
`sources.json` with its sha256:
- **Common Crawl first** (coordinator, 2026-10-28: about 100 times faster than archive.org, which throttles this
  machine). `cc_index` runs one prefix query per host, path prefix and crawl over `/akn/<cc>/act/` (newest 12 crawls,
  `"cc_crawls"` in acts.json), and `wayback.cc_get` reads each page by byte range from data.commoncrawl.org (pinned:
  crawl, WARC file, offset, length). In practice Common Crawl held few Peachjam act pages for these three LIIs; it is
  checked first because it costs seconds.
- **The Internet Archive for the rest**, in the raw `id_` form (`https://web.archive.org/web/<ts>id_/<original>`),
  found through the CDX API (with `length`, so full pages are tried before 2026 script-loaded shells), fetched through
  `wayback.fetch`. Its capture timestamp and sha256
are pinned in the country's `sources.json`.

### What a Peachjam expression page holds

Work `/akn/<cc>/act/<year>/<num>` (Uganda also `act/ord/1950/12`, `act/statute/1995/constitution`; subsidiary law
`act/si/...`, notices `act/genn/...`); expression `.../eng@YYYY-MM-DD`. One page holds:

- `<script id="track-page-properties">` JSON: `work_frbr_uri`, `expression_frbr_uri` (used to validate a capture).
  Older pages (before about 2024) lack it; the expression is then identified by the TOC's
  `api.laws.africa/v3<expression>/!main~...` URLs. Some 2026 captures load the document by script and hold no
  `akn-akomaNtoso` at all: they are rejected and an older capture is used.
- The coverpage: title (`h1`), `li.commencement-date` "Commenced on D", `li.as-at-date-notice`
  "[This is the version of this document from D.]", `li.verification-notice` (who consolidated, as at what date,
  "All subsequent amendments have been researched and applied by Laws.Africa"), and `ol.amendment-list`:
  "[Amended by <title> (Act N of YYYY) on D]".
- The History tab, in two layouts: older pages `div.vertical-timeline__item` with an `h5` date; 2026 pages
  `li.document-history__item` with `<time datetime>`, and a badge "amendment not yet applied" in the card of an
  amendment the LII has not applied. One item per dated event, each with "Amended by <a href=work>",
  "Consolidation" (with e.g. "Chapter 128 / Revised Laws 2023"), "Commenced" or "Repealed by", and a
  "Read this version" link when that date has its own expression. **Not every amendment has an expression**: in
  Uganda the 2021 and 2023 amendments to the Penal Code exist only inside the 2023 revised edition.
- The document: `<span class="akn-akomaNtoso">`, Akoma Ntoso rendered as HTML (`akn-section`, `akn-article`,
  `akn-subsection`, `akn-paragraph`, `akn-num`, `akn-p`, `akn-attachment` for schedules, `data-eid` on each).
- Editorial remarks inside provisions, `span.akn-remark`, e.g. "[clause (2) substituted by section 2(a) of
  <a href="/akn/zm/act/2025/13">Act 13 of 2025</a>]": the LII's own per-provision amendment notes.
- `script#akn_toc_json`: the table of contents with `basic_unit` flags.
- No public Akoma Ntoso XML: the XML is in the paid Laws.Africa API (`api.laws.africa/v3`), which we do not use.
  `.../eng@D/source` (and `source.pdf`) is the gazette or revised-edition PDF the LII worked from; archived for some
  expressions only. Not used.

### Dates: what an expression date means

Laws.Africa's terminology guide (https://docs.laws.africa/getting-started/terminology-guide): "Amendments to
Principal works come into force on the Commencement date of the Amending work", and the first point in time is "the
work as originally published". So:
- an amendment's expression date is the day it took effect: used as the version's `from` as it stands;
- an act's original expression is dated by Gazette publication; the page states the commencement separately
  ("Commenced on 1 April 2021 by Data Protection Act (Commencement) Order, 2021"), and the first version is dated by
  that (decision recorded per act), earlier or later than publication (Kenya's Constitution: in force 2010-08-27 by
  promulgation, published 2010-09-03). If the act was amended on its commencement day (Kenya's Tax Procedures Act,
  2016-01-19), the amendment's version follows on the same day (`same_day`). If the page gives no single date
  (Kenya's Companies Act: "Commenced" plus a note naming Parts and dates), parse.py keeps the publication date,
  records it in `decisions` and lists the act under `staged_commencement` in verification.json: drop such an act or
  handle it by hand.
- a consolidation (revised edition) is dated by the date the edition is as at ("Consolidation", "Revised Laws 2023").

### Credits

- One amending law in the History between two versions, and no consolidation: every changed provision is credited
  to it.
- Several laws, or a consolidation, in one step (an amendment without its own expression, or an expression with no
  archived copy): a provision is credited to a law only if the LII's own editorial note inside it names that law,
  by link (ZambiaLII, ULII) or in plain text ("[Act No. 19 of 2015, s. 143.]" on Kenya Law, matched by number and year);
  the rest are unexplained (publisher), and the version note names the laws the step takes in.
- Amendments marked "not yet applied" are never credited or applied; each goes into `decisions`.
- "Revised by 24th Annual Supplement" (Kenya) and "Consolidation" (ZambiaLII, ULII) are the publisher's revisions:
  unexplained unless a note names a law.

## 2. How to add the next LII country (about 30 minutes)

1. **Copy a country folder.** `scripts/zambia-law/{fetch.py,parse.py}` are generic: copy them to
   `scripts/<slug>-law/` and change only the country name in the docstrings. They vendor `peachjam.py` into the folder
   (so the repository ships the exact adapter) and call `peachjam.fetch` / `peachjam.parse`.
2. **Write `acts.json`.** Copy `scripts/zambia-law/acts.json` and change:
   - `lii`: `name` (the LII's own name, e.g. "MalawiLII"), `hosts` (current host first; add old hosts that the archive
     holds, as Kenya has `new.kenyalaw.org`), `cc` (the AKN country code), `path_prefixes` (`["", "/en"]` if the site
     serves `/en/akn/...`, as ULII does), `listing_prefix` (`"/en"` for ULII-style sites), and `"listing": false` if
     the listing page is behind the challenge too (Kenya). Never set `law_pages` unless you need amending laws'
     assent dates: it costs two CDX queries per law and they are rarely archived.
   - `country`: code, name, slug, `tz`, publisher, `licence_note` (the exact attribution line from the LII's
     `/terms-of-use/`, s. 9 in every Peachjam LII so far).
   - `sources[0].licence`: the LII's licence and terms, quoted.
   - `decisions`: why these acts, the terms, and the user's Wayback decision (copy Zambia's wording).
3. **Choose the acts by archive coverage, before fetching any page.** `python -X utf8 -u
   scripts/africa-law/survey.py <slug> --top 40` lists the best-archived works from one CDX query;
   `survey.py <slug> <work> ...` prints each work's History against the archive (`+` an expression the LII lists,
   `-` an event without one, `*` archived). Take the Constitution plus acts where every `+` has a `*`. An act whose versions have gaps gets late-dated credits; leave it out and say so in `decisions`.
   Pages that show only the source PDF (no `akn-akomaNtoso`) cannot be used (no OCR).
   - Git Bash rewrites an argument like `/en` into a Windows path: pass prefixes in acts.json, not on the command line.
4. **Fetch.** `python -X utf8 -u scripts/<slug>-law/fetch.py > scripts/<slug>-law/.tmp/fetch.log 2>&1`, in the
   background. It writes `sources.json` (one pinned capture per expression, with its sha256). "not an expression
   page" lines are script-loaded or login-gated 2026 captures being skipped. Re-running is free for everything cached.
   Kenya (3 acts, 51 expressions) took about 11 minutes when archive.org was throttling; ULII 14 minutes.
5. **Parse.** `python -X utf8 scripts/<slug>-law/parse.py` writes `corpus.json` (atomically; autopush builds it to
   `preview` within 3 minutes), `verification.json`, and `repo/README.md`, `repo/LICENSE` and the `build` line of
   `repo/jurisdiction.json` (copy `jurisdiction.json` from the scaffold clone first). Country notes go in
   `README.extra.md` (in the country folder), which the README includes.
6. **Verify.** In `verification.json`: every `*:listing` entry `ok` (the last version is the expression the LII's own
   listing names as current, where the listing is readable); every `*:archive` entry with `history_after_last: []`
   (the newest archived page lists no later amendment; `captured` says how fresh it is); every `fidelity` entry with `units_differing: []` and
   `text_outside_units_chars: 0` (every character of every version is in a provision file, headings aside). Then a test
   build: `python -X utf8 scripts/gitlaw_common/build.py scripts/<slug>-law --repo scripts/<slug>-law/.tmp-build
   --docs-date <retrieved>` and `check.py` (0 mismatches), and the `--compare` rebuild into `.tmp/` (hash-identical).
   Read two or three provision files and one diff by eye.
7. **Publish.** Write `scripts/<slug>-law/PUBLISH` with one line saying what was verified. Watch
   `BUILD_STATUS.json`.

### Per-LII quirks found so far

| LII | Quirk |
|---|---|
| ZambiaLII | The Constitution of Zambia Act's Constitution is its Schedule (`att_1`): `"attachment_prefix": {"att_1": ""}` files its articles as `art-NNN`; its Preamble is a schedule subpart and becomes `preamble`. Many 2026 captures are script-loaded. The Penal Code is barely archived (2 of 11 expressions). |
| ULII | Older expressions captured in 2025-26 are often login-gated shells (no text): use pre-2025 captures (the CDX `length` ordering does this). The Data Protection and Privacy Act's current (2023-12-31) expression is not archived, so it was dropped. Pages live under `/en/akn/...` as well as `/akn/...` (both prefixes are queried). Works have subtypes: `act/statute/1995/constitution`, `act/ord/1950/12`, `act/genn/2024/2917` (a corrigendum General Notice, kind `decree`). The Revised Laws 2023 (as at 2023-12-31) is a consolidation that renumbered chapters and folds in the 2021 and 2023 amendments, which have no expressions of their own; files keep their number, so a file can change provision on 2023-12-31 (`README.extra.md` explains it). The amendment list cites amending Acts by their 2023 chapter ("(Chapter 120)"): labels come from the work URI instead. |
| Kenya Law | `new.kenyalaw.org` (archived URLs) now redirects to `kenyalaw.org`; both hosts are queried. AWS WAF challenge on every page, including the listing (`"listing": false`). Terms: only raw documents are CC BY-NC 4.0; automated extraction and redistribution need an NCLR licence (user decision recorded). Best archived of the three: up to 38 expressions per act. Editorial notes are plain text, without links. Commencement notices appear in the History as "Amended by ... Commencement" without versions. Tables of empty cells used for layout (the national anthem) are dropped to their text. |

### What a licensed route would need

The Laws.Africa content API (`api.laws.africa/v3`, paid, from ZAR 42,000 per country per month) serves the same
expressions as Akoma Ntoso XML with amendment metadata, without any archive gaps; `peachjam.py`'s unit and credit logic
works on the same element names, so an XML reader would replace only `fetch` and `units_of`. Alternatively each LII
offers bulk access by e-mail (terms s. 4 and 5).
