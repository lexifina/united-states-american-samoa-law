"""Stricter stray-fragment filter for Registro Oficial PDFs whose pages carry many small text fragments over and
between the real columns (Suplemento 497 of 2019: a magnifier-like duplicate of pieces of the text on most pages).

rotext's own `drop_overlaps` skips a block lying at least half inside a fuller block. Here a block is also skipped
when at least 15% of it overlaps a block holding more text (real column blocks never overlap one another), and the
second of two identical blocks (same place, same text: headings printed twice) is skipped.

    python -X utf8 codes/strict.py <pdf-url>      list the extra blocks this filter drops (to review)
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import rotext  # noqa: E402

_orig = rotext._overlapped


def overlapped(blocks: list) -> set[int]:
    out = set(_orig(blocks))
    seen = set()
    for i, b in enumerate(blocks):  # a block printed twice (same place, same text): keep the first
        sig = (round(b[0]), round(b[1]), round(b[2]), round(b[3]), b[4])
        if sig in seen:
            out.add(i)
        seen.add(sig)
    for i, b in enumerate(blocks):
        if i in out:
            continue
        area = max((b[2] - b[0]) * (b[3] - b[1]), 1e-6)
        for j, c in enumerate(blocks):
            if i == j or len(c[4]) <= len(b[4]):
                continue
            w = min(b[2], c[2]) - max(b[0], c[0])
            h = min(b[3], c[3]) - max(b[1], c[1])
            if w > 0 and h > 0 and w * h >= 0.15 * area:
                out.add(i)
                break
    return out


def paragraphs(path) -> list[str]:
    rotext._overlapped = overlapped
    try:
        return rotext.paragraphs(path, drop_overlaps=True)
    finally:
        rotext._overlapped = _orig


def review(path) -> None:
    import fitz
    d = fitz.open(path)
    for pn in range(len(d)):
        blocks = [b for b in d[pn].get_text("blocks", sort=False) if b[6] == 0]
        extra = overlapped(blocks) - _orig(blocks)
        for i in sorted(extra):
            t = blocks[i][4].replace("\n", "|")
            if len(t) > 25:
                print(pn, [round(x) for x in blocks[i][:4]], t[:120])


if __name__ == "__main__":
    import fetch
    review(fetch.cached(sys.argv[1]))
