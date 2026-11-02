# Brief: Argentine provinces (gitlaw-scraper-dell, 2026-10-30, via global-law-main-composer)

Goal: one public repo per province, `lexifina/argentina-<province>-law`, with a real first build: the provincial
constitution first, then codes, then laws in parts of about 50. The national `lexifina/argentina-law` belongs to
gitlaw-scraper-hp-omen: never touch it or scripts/argentina-law/.

Read first: scripts/world-law/COVERAGE-WAVE.md, FIRST-BUILDS.md, US-STATES.md (Processes + New hosts), and
scripts/REGION-TRIAGE-BRIEF.md (gates). Model: scripts/world-law/mx_states.py.

## The engine (already written; do not edit it, other agents use it)

`scripts/world-law/ar_provinces.py` does claim, scaffold (creates the public repo via `gh api` with the commit
"Argentina (<Name>): sources, before any law"), fetching (one process, one request at a time per host, >= 3.2 s apart,
stops a host on a challenge/403/429; cache `.ar-cache/<host>/`; log `logs/ar-provinces-requests.jsonl`), article
splitting, in-force dating, part writing, the letters-and-digits check, verification and `<part>.PUBLISH`.
Buenos Aires province (class `GBA` in it) is the worked example; published parts in scripts/argentina-buenos-aires-law/.

For a new province write **one adapter module** `scripts/world-law/ar_adapters/<slug with _>.py` defining
`class Adapter` (look at `GBA` for the shape):

- `host` (str), `source` dict: `name`, `url`, `publisher`, `gazette` (e.g. "Boletín Oficial de la Provincia de X"),
  `notes` (what the source gives); optional `dates_note` (README "Dates" bullet) and class attribute `decisions`
  (list of strings) when the generic texts do not fit; `original_only = True` when the source gives texts as enacted.
- `catalogue(self, n_laws) -> {'constitucion': [item], 'codigo': [item], 'ley': [item]}` (items are dicts; `page` is
  used as a unique key). Laws newest first.
- `detail(self, item) -> dict | None` with: `page` (full URL), `kind` ('constitucion'|'ley'|'decreto-ley'|...),
  `number` (digits), `year` (for non-'ley' kinds), `title`, `pub` (publication date ISO; required for dating),
  `promul` (ISO or None), `updated` (ISO date the source last updated the text, or None), `related_later` (list of
  later norms recorded as modifying/related; [] if none or unknown — then the AMEND_NOTE regex still catches
  "(Texto según ...)" style notes), `text_url` (URL of the bytes the text is read from).
- `text(self, d) -> (paragraphs, bytes) | None`: fetch with the module-level `get(url)` (cached, paced); HTML →
  `html_paragraphs(b)`, PDF with a text layer → `pdf_paragraphs(b)` and set `source_letters = staticmethod(
  source_letters_pdf)` on the class (independent reader = poppler pdftotext). No OCR. Never drop text.
- Fetch every page through `get()` (import from ar_provinces). If you need a POST/session, add it inside your module
  but keep the same pacing (one request at a time per host, >= 3.2 s, Crawl-delay obeyed).

Run: `python -X utf8 scripts/world-law/ar_provinces.py run <slug> --laws=200` (add `--max-parts=1` to do the
constitution first and inspect it). It claims, scaffolds, fetches, writes `corpus.d/<part>.json`, verifies
(letters check + scratch build + check.py) and writes `<part>.PUBLISH` only if clean. The streaming autopush
(scripts/world-law/autopush_dell.py, already running) publishes main from claims + PUBLISH; you never push.
`python -X utf8 scripts/world-law/ar_provinces.py letters <slug> <part>` shows letters problems.

Inspect the constitution part before letting laws run: its in-force date (noon local on the in-force day: the
constitution's own vigencia clause, else publication + 9 days) and that articles split sensibly. If a part is wrong
after PUBLISH was written, move both files out of corpus.d at once (before autopush pushes) and fix.

## Gates per province (stop at the first failure; release the claim on a fail)

1. robots.txt: stop on any rule naming ClaudeBot/anthropic-ai/Claude-Web over the law pages, a `*` Disallow over them,
   or a 5xx. Obey Crawl-delay (raise the host's pause: `net().pause[host] = <secs>` in your adapter's __init__).
2. Reproduction policy on the site: if it requires permission first, HOLD: draft an email in
   scripts/FETCH-PERMISSION-EMAILS.md (append; see the SAIJ draft there) and publish nothing.
3. No challenge or 403; never work around one. Never disable TLS verification.
4. Data: official text (legislature, Boletín Oficial, or the government's normativa/digesto), HTML or text-layer PDF.

On a fail: delete your claim file and append the verdict to scripts/REGION-TRIAGE.md under the heading
"## Argentine provinces + CABA" (append only, never rewrite the file). Log every fetch session in
scripts/SCRAPING-LOG.md (append a section like the existing "Argentine provinces" one).

## Already known (2026-10-30)

- SAIJ: HOLD (Reglamento de uso, Res. MJyDH 1427/2011 forbids reproduction). Do not use SAIJ.
- Mendoza: www.legislaturamendoza.gov.ar and www.hcdmza.gob.ar robots disallow ClaudeBot (and anthropic-ai/Claude-Web on
  the first): FAIL for those hosts; other official Mendoza hosts (Senado, Boletín Oficial, government digest) unchecked.
- Tierra del Fuego: www.legistdf.gob.ar robots disallows ClaudeBot on /lp/ (the law archive): FAIL for that host.
- Corrientes: www.hcdcorrientes.gov.ar robots is a bare "Disallow: /": treat as FAIL for that host.
- Santa Fe: www.santafe.gob.ar and www.santafe.gov.ar time out; diputadossantafe.gov.ar has the provincial constitution page
  (/web/camara/constitucion-provincial/), no law database seen.
- Córdoba: web2.cba.gov.ar (leyes.nsf) times out; gld.legislaturacba.gob.ar/Publics/LeyesResoluciones.aspx is an
  ASP.NET search form (no robots.txt); legislaturacba.gob.ar has /constitucion-de-la-provincia-de-cordoba/.
- Salta: www.diputadosalta.gob.ar robots open; /CONSTITUCION_PROVINCIAL_4_11_2022.pdf, /web/digesto (Digesto Ley 7530).
- Chaco: digesto.legislaturachaco.gob.ar/Documentos/Documento/BusquedaPublica (no robots.txt).
- La Rioja: legislaturalarioja.gob.ar/consulta-de-leyes/ (WordPress, REST type `leyes`; law pages give sanción date and a
  PDF, no publication date seen); constitution PDF under wp-content/uploads/2026/06/constitucion-de-la-rioja.pdf.
- Entre Ríos: www.senadoer.gob.ar/ley/ley-n-NNNN/ pages (promulgation + publication dates, PDF download).
- Neuquén: www.legislaturaneuquen.gob.ar (ConstitucionProvincial.aspx), datos.legislaturaneuquen.gob.ar (CKAN, Crawl-Delay 10).
- Tucumán: www.legislaturadetucuman.gob.ar is a JS app (antd); Río Negro: web.legisrn.gov.ar; Misiones:
  www.diputadosmisiones.gov.ar/nuevo/; San Juan: diputadossanjuan.gob.ar (Joomla). Unresolved hosts: www.legislaturasde.gov.ar,
  www.legislatura.lapampa.gob.ar, www.hcdsc.gov.ar, cedom.gob.ar. Timeouts: www.legischubut.gov.ar, www.diputados.sanluis.gov.ar.

- (13:55) Mendoza: www.senadomendoza.gob.ar also disallows ClaudeBot (Cloudflare managed): FAIL. www.mendoza.gov.ar robots
  open (wp-admin only); boe.mendoza.gov.ar (Boletín Oficial) robots 404 = none. Catamarca: www.diputadoscatamarca.gob.ar
  answers robots.txt with HTTP 403 + an auto-refresh challenge page: FAIL, host stopped, never retry it. Chubut:
  boletin.chubut.gov.ar robots `Allow: /`; www.legischubut.gov.ar timed out. Tierra del Fuego: www.tierradelfuego.gob.ar
  robots open, Crawl-delay 10. San Luis: www.diputados.sanluis.gov.ar/.gob.ar time out. Unresolved: legislaturacatamarca,
  legislatura.lapampa.gov.ar, hcdsc.gob.ar, legislaturasantiago.gob.ar.

## Limits

- At most one fetch process per host; your runs at BelowNormal (the engine sets it); pools of at most 4.
- Wait while cpu5 > 92 or RAM > 85 (last line of %LOCALAPPDATA%\gitlaw-cpu.log; the engine waits before each parse).
- Record the Windows PID of every process you start; stop only those. Never kill by name or guess.
- No WebSearch unless a province has no findable official source (shared budget); use curl/requests.
- Never commit in the lexifina repo; never push; never change repo visibility.
- Time-box: about 30 minutes per province to get the constitution part published; if blocked, record and move on.
- Delete the claim when the province is fully published (your planned parts done) or blocked.

## Report per province

source, gate verdict (with the evidence line), parts published (names), and main sha
(`git ls-remote https://github.com/lexifina/<repo>.git refs/heads/main`; autopush may lag a few minutes).
