# peachjam.py issues found by gitlaw-MW (2026-10-28)

1. First version after a same-day amendment: when the oldest archived expression was made by an amendment on that day
   (Malawi 2023/10 @2025-09-05, Act 32 of 2025), parse() notes it "the act as published" and puts nothing in
   earlier_laws (only amendments before first_day are added). Workaround: malawi-law/parse.py first_version_fix.
2. good_expression_page rejects pre-Peachjam LII pages (MalawiLII 2021-2022 captures) that name the expression as
   escaped JSON `"expression_frbr_uri":"\/akn\/mw\/act\/1994\/20\/eng@2014-12-31"`; units_of parses them fine.
   Workaround: malawi-law/lii.py good_page.
3. as_enacted is decided from the latest page's timeline only: an older consolidation expression the LII no longer
   lists (Malawi Constitution @2014-12-31) has no consolidation event there, so it is treated as the act as enacted
   and redated to the commencement (1994-05-18). Workaround: acts.json "skip".
