"""Shared reading helpers for the Lithuania build: cache lookup and paragraph extraction from the Word-generated HTML
that e-TAR (rs/legalact, rs/actualedition) and the Seimas site (lrs.lt) serve. No network here."""
import hashlib
import html
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
CACHE = HERE / '.cache'


SUP = str.maketrans('0123456789', '⁰¹²³⁴⁵⁶⁷⁸⁹')


def wb_url(ts: str, url: str) -> str:
    return f'https://web.archive.org/web/{ts}id_/{url}'


def cached(ts: str, url: str) -> bytes:
    """Bytes of one pinned capture, from the cache wayback.get filled (sha256 of the id_ URL)."""
    p = CACHE / hashlib.sha256(wb_url(ts, url).encode()).hexdigest()
    return p.read_bytes()


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def norm(t: str) -> str:
    """Publisher typesetting, normalised once: NBSP and other spaces to one space, straight or curly double quotes
    to the Lithuanian „…“ pair, a spaced hyphen used as a dash to an en dash, soft hyphens dropped."""
    t = html.unescape(t)
    t = t.replace('­', '').replace('​', '')
    t = re.sub(r'[     \t]', ' ', t)
    t = re.sub(r'\s+', ' ', t).strip()
    t = t.replace('”', '“').replace('″', '“')
    # straight double quotes: opening before a word, closing after one
    t = re.sub(r'"(?=\w)', '„', t)
    t = t.replace('"', '“')
    t = t.replace(' - ', ' – ').replace(' — ', ' – ')
    t = t.replace('…', '...')
    return t


def paragraphs(b: bytes, br_split: bool = False) -> list[str]:
    """Every non-empty <p>/<h*> paragraph of the document body, in order, normalised. With br_split, a <br> also
    ends a paragraph (the lrs.lt page sets a whole chapter in one <p>, one paragraph per <br>)."""
    m = re.search(rb'charset=["\']?([\w-]+)', b[:4000])
    enc = m.group(1).decode() if m else 'utf-8'
    s = b.decode(enc, 'replace')
    i = s.lower().find('<body')
    s = s[i:] if i >= 0 else s
    s = re.sub(r'<(script|style)\b.*?</\1>', '', s, flags=re.S | re.I)
    s = re.sub(r'<br\s*/?>', '</p><p>' if br_split else ' ', s, flags=re.I)
    # article numbers such as 7<sup>1</sup> ("7¹ straipsnis"): keep the superscript as a superscript digit
    s = re.sub(r'<sup>\s*(\d+)\s*</sup>\s*', lambda m: m.group(1).translate(SUP) + ' ', s, flags=re.I)
    out = []
    for p in re.findall(r'<(?:p|h\d)\b[^>]*>(.*?)</(?:p|h\d)>', s, flags=re.S | re.I):
        t = norm(re.sub(r'<[^>]+>', '', p))
        if t:
            out.append(t)
    return out
