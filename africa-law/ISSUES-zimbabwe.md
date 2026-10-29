# peachjam.py issue from gitlaw-ZW (2026-10-29)

`captures()` ignores Wayback captures whose original URL percent-encodes the "@": the regex
`/eng@(\d{4}-\d{2}-\d{2})/?$` does not match `.../eng%402017-09-07`. On ZimLII, 7 of the 13 captures of
/akn/zw/act/2013/1 at that expression are in this form (e.g. 20230510081044, 20240527092602). Suggested fix: match
`eng(?:@|%40)` and keep the original as archived when building the raw `id_` URL.
