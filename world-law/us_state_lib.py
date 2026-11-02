"""Shared helpers for the US-state first builds (private). No network."""
import hashlib, json, os, re, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DOCS = Path.home() / 'Documents'


def sha256(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def norm(s: str) -> str:
    """NBSP -> space, collapse spaces, one form of quotes and dashes."""
    s = s.replace(' ', ' ').replace(' ', ' ').replace(' ', ' ')
    s = s.replace('“', '"').replace('”', '"').replace('‘', "'").replace('’', "'")
    s = s.replace('‑', '-').replace('‐', '-').replace('–', '-').replace('—', '-').replace('­', '').replace('﻿', '')
    return re.sub(r'[ \t]{2,}', ' ', s).strip()


def para_text(head: str | None, paras: list[str]) -> str:
    lines = ([f'# {norm(head)}'] if head else []) + [norm(p) for p in paras if norm(p)]
    return '\n'.join(lines) + '\n'


def padkey(prefix: str, ident: str, width: int = 4) -> str:
    """Natural-sorting key: 16-5-21.1 -> prefix-16-0005-0021-0001 ; 2-1-103a -> ...-0103a"""
    out = []
    for part in re.split(r'[-.\s]+', ident.strip().lower()):
        m = re.fullmatch(r'(\d+)([a-z]*)', part)
        if m:
            out.append(f'{int(m.group(1)):0{width}d}{m.group(2)}')
        else:
            out.append(re.sub(r'[^a-z0-9]+', '', part))
    return '-'.join([prefix] + [o for o in out if o])


def write_corpus(folder: Path, corpus: dict) -> None:
    (folder / 'corpus.json').write_text(json.dumps(corpus, ensure_ascii=False, indent=1, sort_keys=True) + '\n',
                                        encoding='utf-8', newline='\n')


def write_repo(folder: Path, readme: str, license_: str, jurisdiction: dict) -> None:
    r = folder / 'repo'
    r.mkdir(exist_ok=True)
    (r / 'README.md').write_text(readme, encoding='utf-8', newline='\n')
    (r / 'LICENSE').write_text(license_, encoding='utf-8', newline='\n')
    (r / 'jurisdiction.json').write_text(json.dumps(jurisdiction, indent=2) + '\n', encoding='utf-8', newline='\n')


def country(code, name, slug, tz, publisher_name, domain, rule_text, rule_source, licence_note):
    return {'code': code, 'name': name, 'slug': slug, 'lang': 'en', 'tz': tz, 'future_branch': 'future',
            'publisher': {'name': publisher_name, 'email': f'legislature@{domain}.invalid'},
            'default_in_force_rule': {'text': rule_text, 'source': rule_source}, 'licence_note': licence_note}
