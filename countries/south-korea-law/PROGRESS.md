# South Korea (gitlaw-KR): progress / handoff (2026-10-29 00:36 UTC)

Repo `lexifina/south-korea-law` (private). The scaffold was confirmed on 2026-10-28 at 22:47 UTC (only `main`, single commit fc49274). The clone at `C:/Users/alany/Documents/south-korea-law` is owned by autopush. **Preview pushed: c3e796c.** `main` is still the scaffold: no PUBLISH yet.

## Done
- Source: law.go.kr DRF Open API with `OC=test` (no registration needed; robots.txt `Allow: /`).
  - `lawSearch.do?target=eflaw&query=` lists every version by 시행일자.
  - `lawService.do?target=eflaw&MST=&efYd=&type=XML` gives each version's full text.
  - History goes back to enactment (민법 1958, 헌법 1948).
- Cache: `.cache/` holds 65 MB from 119 requests, all logged in `.cache/requests.jsonl`.
- Phase 1 is parsed into corpus.json:

  | Act | 법령ID | Versions |
  |---|---|---:|
  | 대한민국헌법 | 001444 | 10 |
  | 민법 | 001706 | 36 |
  | 형법 | 001692 | 34 |
  | 개인정보 보호법 | 011357 | 20 (3 on `future`) |

- Test build in `.tmp-build`: 147 commits, 99 law commits, 44 unexplained, 189 tags. check.py found 0 mismatches and 0 trailer errors.
- `verify.py` (against law.go.kr's 현행 target=law, 2026-10-28):
  - 헌법, 민법 and 형법 match exactly, provision by provision.
  - 개인정보 보호법 differs in 2 provisions, 제32조의2 and 제75조. law.go.kr's 현행 text (시행 2026-09-11) already carries wording that its own eflaw dates to 2027-07-01 (법률 제21445호, second commencement). The corpus follows the eflaw dates. **PUBLISH was not written for this reason.** Decide whether this counts as verified, add a decision line, then write PUBLISH.

## Method (parse.py)
- One version per in-force day.
- **Out-of-order laws.** A law can be promulgated before one already in force but take effect after it. For such a law, only its own changes (its text against its predecessor by promulgation) are applied.
- **Wording that appears before its law.** These are found from law.go.kr's `<개정 date>` notes. The text in force the day before is kept, or the provision is left out, or it gets the placeholder text; each case is listed in decisions.
- **Spacing-only differences** (law.go.kr re-spacing, 띄어쓰기) are left as unexplained.
- **Credits** are given only with source evidence:
  - the law is the act's 제정 or 전부개정, or
  - its 개정문 names the provision, or
  - the provision's amendment note names the law's promulgation day, or
  - the provision is that law's own 부칙.
- Diagnostics are in `parse.log`.

## Resume (exact next steps)
1. Write `repo/README.md`. It is a stub now; copy the shape of chile-law/repo/README.md, English first, then Korean. Also write `repo/LICENSE`: statutes are not protected works under 저작권법 제7조; attribute 법제처 국가법령정보센터; Lexifina's parts are CC0.
2. Settle the 개인정보 보호법 현행 question above, then write `PUBLISH`.
3. Phase 2: add acts to `acts.json` (`slug`, `name`, `query`; the `id` resolves automatically), then run `python -X utf8 fetch.py <slug>` and `python -X utf8 parse.py`. Candidates: 상법, 민사소송법, 형사소송법, 근로기준법, 민사집행법, 행정소송법, 주택임대차보호법, 저작권법, 정보통신망법, 독점규제법, 헌법재판소법.
4. Test: `python -X utf8 ../gitlaw_common/build.py . --repo .tmp-build --docs-date 2026-10-28`, then `check.py .tmp-build --corpus corpus.json`, then `verify.py`.

## Open issues
- Constitutional Court rulings (위헌) are not commits; law.go.kr only adds notes for them.
- 별표 (annexes) are not included.
