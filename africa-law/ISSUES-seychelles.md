# peachjam.py issues found while finishing Seychelles (gitlaw-finisher-2, 2026-10-29)

Worked around locally in scripts/seychelles-law/parse.py (`clean()`); the adapter itself is unchanged.

1. **Remark-only subprovisions leave a bare number or term.** When a paragraph, subsection or definition's whole
   printed content is an `akn-remark` (for example `(8) [clause (8) added by ... and repealed by ...]`,
   `"interment" [definition of "interment" repealed by section 2(a) of Act 45 of 2021]`, or the Civil Status Act's
   "Notes to the 1991 Ed" paragraphs (1)-(3)), `unit_lines` drops the remark but keeps the number/term, so the unit gets a
   line `(8)` or `"interment"`. The provision-level rule ("keep the remark where there is no other text") is not applied
   per line. Seen in Seychelles: Constitution arts. 66A(11)-(12), 81(2A), 112(c), 115C(4A), 146(8), Schedule 2
   "Electoral Commissioner"; Civil Status Act s. 2 "interment", s. 34(b), Schedule B (1)-(3); Licences Act s. 20(3)-(4),
   Schedule 14., 15., 24. Local fix: remove lines matching `^(\(\w+\)|\d+[A-Z]?\.|"[^"]+")$`.
2. **En dash vs em dash.** `norm()` only maps a *spaced* en dash to an em dash. SeyLII typeset the Licences Act's
   chapeaux with an unspaced en dash ("In this Act–") until 2024 and an em dash after, so typesetting-only changes in
   ss. 18 and 26 were credited to Act 2 of 2024. Local fix: an en dash not between two digits becomes an em dash.
