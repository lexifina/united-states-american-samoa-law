# Angola (AO) git-for-law: progress (gitlaw-CI-AO, 2026-10-29 05:55 UTC)

Repo lexifina/angola-law (private). Clone C:/Users/alany/Documents/angola-law is owned by autopush (4-hourly pass).
Not a Peachjam LII: sources are government sites, fetched directly at 1 req/s (fetch.py); archive.org only through
gitlaw_common/wayback.py.

**Published:** the 04:51 UTC pass pushed main **1a73c15** (Constitution only; 0 mismatches) and preview 48e24ed
(all three parts). PUBLISH and corpus.d/10-constituicao.PUBLISH were written at 02:25 after the local checks below;
remote main was still the scaffold 68d2648 at 02:24.

## Checklist
- [x] Probe sources, fetch.py (curl cache, requests.jsonl). Fixed: main() now reads the act entries + 'checks' of
      sources.json (was reading a nonexistent 'files' key)
- [x] parse.py fixes: ordinal superscripts kept ("n.os", "2.os" were dropped as footnote markers); a hard hyphen at
      a line end joins without the hyphen only if the whole word is printed elsewhere in the Gazette ("exe-cução",
      "parti- culares" fixed); "ARTIGO 534.°" (degree sign) accepted (CPP lost 4 articles before)
- [x] meta.json: country block, laws, per-part act metadata, decisions, ai_use
- [x] corpus.d/10-constituicao.json: 257 units (preâmbulo, 244 articles + 7 "-A", estrutura, anexo-01..03,
      formula-final), one version 2021-08-16, first_law null, earlier_laws [cra-2010, lei-18-21]
- [x] Cross-check vs TC Edição Especial Actualizada 2022, word for word, every article + preamble + annexes +
      formula: equal except 5 edition differences (36.º n.º 3 "f)" vs "e)"; 42.º n.º 3 a) "proteção"/"protecção";
      173.º n.º 1 "A requerimento … Republica"/"O requerimento … República"; 174.º n.º 4 "extra-judicial"; 242.º
      n.º 2 "esetabelece") -> Gazette kept, listed in decisions. 4 TC-side line-split artefacts (16, 83, 95, 96).
- [x] corpus.d/20-codigo-penal.json (473 articles, 2021-02-09, Lei 38/20 art. 9.º + TS acórdão 6089/21) and
      30-codigo-processo-penal.json (604 articles, 2021-02-09, Lei 39/20 art. 6.º): preview only, no .PUBLISH
- [x] repo/README.md (EN + PT), LICENSE, jurisdiction.json, tools/vigente_em.py
- [x] Local builds into empty scratch repos: all parts (3 versions) and GITLAW_VERIFIED_PARTS_ONLY=1 (1 version):
      check.py 0 mismatches, 0 trailer errors; --compare identical both times
- [ ] Código Penal: Lei 12/24 de 4 de Julho (DR I Série n.º 126) with a text layer not found -> stays on preview
- [ ] CPP: later amendments not researched -> stays on preview

## Sources (all in .cache/, 33 files, 29 MB)
| What | URL | Status |
|---|---|---|
| DR I Série n.º 154, 16 Aug 2021: Lei 18/21 + full republication of the Constitution (art. 4.º) | plataformacipra.gov.ao/.../Gov_AngolaConstituição190102230948141675284494.pdf | used; Lei 18/21 art. 6.º in force on publication |
| DR I Série n.º 179, 11 Nov 2020: Lei 38/20 Código Penal + Lei 39/20 CPP | plataformacipra.gov.ao/.../Gov_AngolaLegislação982801221101131643367673.pdf | used (preview); both 90 days after publication |
| CP in-force date | Tribunal Supremo acórdão Proc. 6089/21 (IA capture 20260606051758) | "entrou em vigor a 9 de Fevereiro de 2021" |
| TC Edição Especial Actualizada 2022 | tribunalconstitucional.ao/media/d11gvf0z/edicao-especial-actualizada-2022.pdf | cross-check only |
| Constitution 2010 original, DR I Série n.º 23, 5 Feb 2010 | jurisprudencia.tribunalconstitucional.ao (IA 20220725130307) | scan -> left out (no OCR) |
| Lei 22/11 Protecção de Dados (APD) | apd.ao | scans -> left out |
| imprensanacional.gov.ao | | no connection |

## Open issues
- Any change to 10-constituicao must keep the published main verified: re-run the TC cross-check
  (scratchpad scripts ao_tc.py/ao_tc2.py logic: split TC by "Artigo N.º", cut trailing TÍTULO/CAPÍTULO/SECÇÃO) and the
  local build/check/--compare before writing.
- WebSearch used: 3 of 4.
