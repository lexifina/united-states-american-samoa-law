# peachjam.py issues found while finishing Sierra Leone (gitlaw-finisher-2, 2026-10-29)

1. **parse() crashes on a configured act that fetch() could not pin.** fetch() prints "<work>: no usable archived
   page" and leaves the work out of sources.json, but parse() then does `ex = pins["acts"][work]["expressions"]`
   (line 937) and raises `KeyError: '2021/7'`. Suggested: skip the act with a generic decision ("no archived page holds
   its text"). Worked around by moving the act from acts.json `acts` to a `left_out` list.
2. **PDF-only works.** SierraLII's Cyber Security and Crime Act, 2021 (/akn/sl/act/2021/7/eng@2021-11-25) has no Akoma
   Ntoso text, only `source.pdf` in a PDF viewer; `good_expression_page` rightly rejects all its captures, but each one
   costs an archive.org request (10 tried). A cheap check for the "Loading PDF..." viewer shell on the first capture
   would stop early and name the reason.
