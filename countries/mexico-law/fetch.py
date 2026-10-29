"""gitlaw-MX fetcher. The Cámara de Diputados site (www.diputados.gob.mx, LeyesBiblio) does not answer from this
machine (TCP connect timeout), so every byte comes from Internet Archive `id_` captures through the shared client
scripts/gitlaw_common/wayback.py (one adaptive machine-wide rate; cache by sha256 of URL; requests.jsonl log).

    python -X utf8 fetch.py index            # CDX listings of every file family we use -> .cache/cdx-*.json
    python -X utf8 fetch.py texts <act>      # every distinct capture of the act's consolidated PDF
    python -X utf8 fetch.py refs <act>       # the act's reform list page (latest capture)

Resumable: everything is cached; rerunning only fetches what is missing.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, r'C:/Users/alany/Documents/lexifina/scripts/gitlaw_common')
import wayback  # noqa: E402

HERE = Path(__file__).resolve().parent
CACHE = HERE / '.cache'
CACHE.mkdir(exist_ok=True)

# Diputados file names. The current text has lived at pdf/<n>.pdf, pdf/<n>_<ddmmyy>.pdf and pdf/<CODE>.pdf.
ACTS = {
    'constitucion': {'num': '1', 'code': 'CPEUM', 'ref': 'ref/cpeum.htm', 'crono': 'ref/cpeum_crono.htm'},
    'codigo-civil-federal': {'num': '2', 'code': 'CCF', 'ref': 'ref/ccf.htm'},
    'codigo-penal-federal': {'num': '9', 'code': 'CPF', 'ref': 'ref/cpf.htm'},
    'lfpdppp': {'num': 'LFPDPPP', 'code': 'LFPDPPP', 'ref': 'ref/lfpdppp.htm'},
}
BASE = 'diputados.gob.mx/LeyesBiblio/'


def cdx(prefix: str, match: str = 'prefix') -> list[dict]:
    caps = wayback.captures(BASE + prefix, match=match, cache=CACHE)
    return sorted(caps, key=lambda c: c['timestamp'])


def text_captures(act: str) -> list[dict]:
    a = ACTS[act]
    caps = []
    seen = set()
    for p in sorted({f"pdf/{a['num']}.pdf", f"pdf/{a['num']}_", f"pdf/{a['code']}"}):
        for c in cdx(p, 'exact' if p.endswith('.pdf') else 'prefix'):
            if c['mimetype'] not in ('application/pdf', 'application/octet-stream', 'unk'):
                continue
            if c['digest'] in seen:
                continue
            seen.add(c['digest'])
            caps.append(c)
    return sorted(caps, key=lambda c: c['timestamp'])


def get_capture(c: dict) -> bytes | None:
    return wayback.get(c['original'], ts=c['timestamp'], cache=CACHE)


def main(argv: list[str]) -> None:
    cmd = argv[0]
    if cmd == 'texts':
        act = argv[1]
        caps = text_captures(act)
        (CACHE / f'caps-{act}.json').write_text(json.dumps(caps, indent=0), encoding='utf-8')
        print(act, len(caps), 'distinct captures')
        limit = int(argv[2]) if len(argv) > 2 else None
        for c in caps[:limit]:
            b = get_capture(c)
            print(c['timestamp'], c['original'].split('LeyesBiblio/')[1], len(b) if b else None, flush=True)
    elif cmd == 'list':
        act = argv[1]
        caps = text_captures(act)
        (CACHE / f'caps-{act}.json').write_text(json.dumps(caps, indent=0), encoding='utf-8')
        for c in caps:
            print(c['timestamp'], c['length'], c['original'].split('LeyesBiblio/')[1])
        print(len(caps))
    elif cmd == 'refs':
        act = argv[1]
        for k in ('ref', 'crono'):
            if k in ACTS[act]:
                caps = cdx(ACTS[act][k], 'exact')
                b = wayback.get('https://www.diputados.gob.mx/LeyesBiblio/' + ACTS[act][k], ts=caps[-1]['timestamp'], cache=CACHE)
                print(k, caps[-1]['timestamp'], len(b) if b else None)
    elif cmd == 'url':
        b = wayback.get(argv[1], ts=argv[2] if len(argv) > 2 else '2', cache=CACHE)
        print(len(b) if b else None)


if __name__ == '__main__':
    main(sys.argv[1:])
