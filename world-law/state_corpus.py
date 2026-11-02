"""Shared helpers for the US-state first builds (no network). Used by scripts/united-states-<state>-law/parse.py."""
import hashlib, html, json, os, re

TAG = re.compile(r'<[^>]+>')


def clean(s):
    """HTML fragment -> plain text: tags dropped, entities decoded, typesetting normalised."""
    s = TAG.sub('', s)
    s = html.unescape(s)
    s = s.replace(' ', ' ').replace(' ', ' ').replace(' ', ' ').replace(' ', ' ').replace(' ', ' ').replace('﻿', '').replace('­', '')
    s = s.replace('‘', "'").replace('’', "'").replace('“', '"').replace('”', '"')
    s = s.replace('–', '-').replace('—', '-').replace('‒', '-').replace('‑', '-')
    s = re.sub(r'[ \t\r\n]+', ' ', s)
    return s.strip()


def unit_key(raw, prefix='sec'):
    """Lowercase ASCII key; the leading number is zero-padded to 4 digits so keys sort naturally."""
    s = raw.strip().lower()
    s = re.sub(r'[^a-z0-9]+', '-', s).strip('-')
    s = re.sub(r'^\d+', lambda m: m.group().zfill(4), s)
    return f'{prefix}-{s}' if prefix else s


def add_unit(units, key, unit):
    """Add a unit; a duplicate key gets -dupN so no text is lost."""
    k, n = key, 1
    while k in units:
        n += 1
        k = f'{key}-dup{n}'
    units[k] = unit
    return k


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


def sha256_bytes(b):
    return hashlib.sha256(b).hexdigest()


def write(path, corpus):
    s = json.dumps(corpus, ensure_ascii=False, indent=1) + '\n'
    with open(path + '.tmp', 'w', encoding='utf-8', newline='\n') as f:
        f.write(s)
    os.replace(path + '.tmp', path)
