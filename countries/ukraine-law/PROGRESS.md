# gitlaw-UA: Ukraine progress (handoff, 2026-10-29 00:42 UTC)

Repo lexifina/ukraine-law (PRIVATE). Clone at `C:/Users/alany/Documents/ukraine-law` (scaffold only, owned by autopush).
tz Europe/Kyiv, lang uk, future branch `maibutnie`, on-date tool `tools/chynne_na.py` (not written yet).
Rules: scripts/world-law/WAVE.md, then scripts/africa-law/FANOUT.md and scripts/south-america-law/BRIEF.md.

## State

- **Not built yet.** There is no corpus.json and no PUBLISH, so autopush has nothing to build.
- **Sources.** zakon.rada.gov.ua and data.rada.gov.ua time out at TCP connect from this machine (geoblock). index.commoncrawl.org also timed out, so Common Crawl is out. Everything comes from archive.org `id_` captures through `gitlaw_common/wayback.py`.
- **Cache.** 12 MB, 41 logged requests, in `.cache/` (gitignored).

## What works

- `fetch.py <slug>` writes `.cache/<slug>.plan.json`. For each act it lists the editions ("редакції"), taken from the edition `<option>`s on the newest complete capture of the current page. It then picks one complete capture per edition, newest first, preferring `/edYYYYMMDD/print`.
- **Constitution (`konstytutsiia`, code `254к/96-вр`): DONE, all 10 editions archived and complete.** The editions are 1996-06-28, 2006-01-01, 2010-09-30, 2011-02-04, 2013-10-06, 2014-02-22, 2014-03-02, 2016-09-30, 2019-02-21 and 2020-01-01. The current text is capture 20261023112930. Captures are pinned in the plan file and their bodies are cached.
- **Civil Code (435-15) and Criminal Code (2341-14):** the CDX `/ed` prefix listings are cached. `.cache/probe/cdx_cc_ed.txt` shows 756 ed-URLs and `cdx_kk_ed.txt` shows 612. Most of these are crawler-made dates, not real editions. Their plan has not been run.

## Source facts (verified on captures)

- Rada edition dates are in-force dates. Each edition page has a banner: "Редакція від DD.MM.YYYY, підстава - <law code>". That gives the credit for each edition.
- Amendment notes in the text look like this: `{Пункт 5 … в редакції Закону № 2680-VIII від 07.02.2019}`, inside `<em><p class=rvps2>`.
- There are two HTML formats:
  - **2022 and later:** `<p class=rvps2><a name="nNNN">`, UTF-8. Articles start with `<span class=rvts9>Стаття N. </span>`.
  - **2018 and old editions:** a `<pre>` block with `<a name="oN">` paragraphs and `<br>` soft wraps, in cp1251. Articles start with `<b>Стаття N.</b>`.
  - **Normalisation:** join the soft wraps, collapse spaces, use one form of apostrophe (' and ’), and drop the `{…}` notes from the text, using them only to credit laws.
- **2014-02-22 has no basis law** on the 2018 card. It is the Rada Resolution 750-VII restoring the 2004 text. The 2010-09-30 edition is the Constitutional Court ruling 20-рп/2010 (kind `court`).

## Next steps

1. Write `parse.py`. Split each cached edition into units (`art-NNN` and the transitional sections) and credit each edition to its "підстава" law(s). Credit units only from the notes; everything else is "unexplained".
2. Test-build into `.tmp-build/` and run check.py. Compare the 2020-01-01 edition with capture 20261023112930. Then write corpus.json and PUBLISH.
3. Run `fetch.py tsyvilnyi-kodeks kryminalnyi-kodeks`. Check that the 2018 captures of the large codes are not paginated ("сторінка 1 з N"). Build only the editions that are archived, and list the missing ones in the README.
4. Write the repo docs: README in English then Ukrainian, LICENSE with CC BY 4.0 attribution to the Verkhovna Rada, and `tools/chynne_na.py`.

## Open issues

See ISSUES.md. The shared wayback client does not use curl `--globoff`, so `[]{}` in a URL fan out into many requests. Common Crawl's index is unreachable.
WebSearch calls used: 0 of 4.
