# Solomon Islands (gitlaw-SB): progress / handoff

Owner: gitlaw-SB (stopped at the 00:44 UTC wind-down, 2026-10-29). Repo lexifina/solomon-islands-law (private, still the bare scaffold d481ec8). Clone C:/Users/alany/Documents/solomon-islands-law (autopush owns it).
Rules: scripts/world-law/FORK.md -> WAVE.md -> africa-law/FANOUT.md -> south-america-law/BRIEF.md. Language: English (official).

## Status
- [x] Scaffold check: only `main` d481ec8 "Solomon Islands: sources, before any law".
- [x] Probe: PacLII returns a Cloudflare challenge (403), so read it through archive.org `id_` only. index.commoncrawl.org was unreachable (connect timeout) all session. parliament.gov.sb/business/acts lists Acts by JS only. solomons.gov.sb is behind Sucuri, and its archive.org captures hold no consolidated Constitution or Penal Code.
- [~] corpus.json written: the Constitution as made (Schedule to S.I. 1978/783), one version from 1978-07-07, 147 units. **Not verified; no PUBLISH.** Known parse gap: ss. 114 and 117 are merged into the preceding section (the heading detection missed them). Fix this in `constitution_units()` before anything else.
- [ ] Constitution amendment Acts (replay)
- [ ] Penal Code (Cap. 26)
- [ ] third core act

## Sources found (all cached in .cache/, keyed by sha256 of the archive.org id_ URL; see cachepath.py)
- Constitution as made: PacLII consol_act/c1978167/ capture 20230620190023 (full HTML text of S.I. 1978/783 + Schedule).
- Constitution, 1996 Revised Edition consolidation: consol_act/cosi353/ capture 20060616143918 (full HTML text; includes s. 69A/69B; Standing Orders and subsidiary legislation follow after "Subsidiary Legislation"; cut there).
- Current consolidation consol_act/cosi1978353 is PDF-only (cosi1978353.pdf), with **no archive.org capture**. Try Common Crawl when the index is back.
- Constitution (Amendment) Acts on PacLII num_act with HTML text (cached): 1982 No 14 (ca1982268, commenced 23/09/83), 1989 No 1 (ca1989268, on Gazette publication), 1992 No 10 (ca1992268, 30/12/92, GN 227/92), 2001 No 2 (ca2001268 / ca2001252, amnesty), 2008 No 10 (ca2008268, deemed in force 1 Apr 2008), 2009 No 9 (ca2009268, by notice). 2022 (ca2022268) is PDF only, not fetched. Note: `ca*` codes also cover Citizenship, Companies, Copyright etc.; the 268 suffix is Constitution (Amendment).
- Penal Code [Cap 26] Rev. Ed. 1996: consol_act/pc66/ capture 20250129140350 and pc2683.html capture 20020930193548 (full HTML, with margin notes naming amending Acts/LNs). pcc2683.pdf (2025) is not fetched and may be the newer consolidation. Penal Code (Amendment) Acts 1986-1990 are in num_act (PDF).
- CDX listings: .cache/ia-paclii.org_sb_legis_consol_act_.json, ia-paclii.org_sb_legis_num_act_.json, ia-www4.paclii.org_sb_legis_.json (all paclii), ia-solomons.gov.sb_.json.

## Scripts
- fetch.py TS URL ...: archive.org id_ fetch via gitlaw_common/wayback.py (shared rate).
- grab.py CDXJSON REGEX: fetch the latest capture of each matching PacLII path.
- probe_ia.py / probe_cc.py: CDX / Common Crawl listings. txt.py: HTML to text for debugging. cachepath.py: key to cache path.
- parse.py: writes corpus.json atomically.

## Exact next step
1. Fix the s.114/s.117 split in parse.py, then rerun `python -X utf8 parse.py`.
2. Add a version at the 1996 Revised Edition from cosi353 (find the Revised Edition commencement date first). Replay 1982/1989/1992 as dated versions before it, and credit them from the Act texts. Leave the remaining diffs uncredited (publisher).
3. Penal Code: start from the pc66 1996 Rev. Ed. as "oldest version available" (`first_law: null`).
4. PUBLISH only after the latest version matches an official consolidated text.
