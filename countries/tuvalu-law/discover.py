"""Fetch the act lists (one POST per letter) and print each act's version history table."""
from __future__ import annotations
import html, re, sys
import fetch

LIST = "https://tuvalu-legislation.tv/cms/legislation/acts_only/by-alphabetical-order.html"
PIT = "2026-10-28 00:00:00"
BASE = "https://tuvalu-legislation.tv"


def letter_page(letter: str) -> str:
    return fetch.get(LIST, data=f"submit4={letter}&pointintime_post_alpha={PIT}").decode("utf-8", "replace")


def histories(page: str) -> dict[str, list[dict]]:
    """{act title: [{version, pdf, commenced, details, superseded}]} from the history modals."""
    out = {}
    for m in re.finditer(r'id="myModalLabel">(.*?)</h5>(.*?)</div>\s*</div>\s*<div class="modal-footer', page, re.S):
        title = html.unescape(m.group(1)).strip()
        rows = []
        for r in re.finditer(r'class="rowHistory">(.*?)(?=<div class="rowHistory">|$)', m.group(2), re.S):
            b = r.group(1)
            pdf = re.search(r'href="([^"]+\.pdf)"', b)
            ver = re.search(r'<b>Version:</b>\s*(\d+)', b)
            def field(name):
                f = re.search(rf'<b>{name}:</b>(.*?)</div>', b, re.S)
                return re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]+>', ' ', f.group(1)))).strip() if f else None
            rows.append({"version": int(ver.group(1)) if ver else None, "pdf": BASE + pdf.group(1) if pdf else None,
                         "commenced": field("Date Commenced"), "details": field("Details"),
                         "superseded": field("Date Superseded")})
        out[title] = rows
    return out


if __name__ == "__main__":
    for L in sys.argv[1:]:
        h = histories(letter_page(L))
        for t, rows in h.items():
            print(t)
            for r in rows:
                print("   ", r)
