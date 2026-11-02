"""Read each register source's robots.txt and record what it says about AI agents. Standard library + curl.

  python scripts/world-law/robots_check.py

For every source URL in register.json, fetch https://<host>/robots.txt once (with curl: Python's TLS fails on this
machine) and ask, for the source's own path, whether ClaudeBot, anthropic-ai, GPTBot and any crawler (*) may fetch it,
and what Crawl-delay applies. Writes the result into each row as `robots`:
  {"ai": "allowed" | "disallowed" | "partly", "all": "allowed" | "disallowed", "delay": seconds or null, "checked": date}
"""
from __future__ import annotations

import datetime as dt
import json
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib import robotparser
from urllib.parse import urlsplit

HERE = Path(__file__).resolve().parent
AGENTS = ('ClaudeBot', 'anthropic-ai', 'Claude-Web', 'GPTBot')


def fetch(host: str) -> tuple[str, str | None]:
    done = subprocess.run(['curl', '-sL', '-m', '20', '-A', 'Mozilla/5.0 (robots.txt check)', '-w', '\n%{http_code}',
                           f'https://{host}/robots.txt'], capture_output=True, encoding='utf-8', errors='replace')
    body, _, code = done.stdout.rpartition('\n')
    if done.returncode or not code.startswith('2') or '<html' in body[:500].lower():
        return host, None  # no robots.txt: everything is allowed by convention
    return host, body


def main() -> None:
    reg_path = HERE / 'register.json'
    reg = json.loads(reg_path.read_text(encoding='utf-8'))
    base = {urlsplit(s['u']).netloc for s in reg['sources'] if s['u'].startswith('http')}
    # The bare host and the www host can serve different files (seylii.org disallows AI agents, www.seylii.org
    # does not), so read both and keep the stricter answer.
    hosts = sorted(base | {h.removeprefix('www.') for h in base} | {'www.' + h for h in base if not h.startswith('www.')})
    with ThreadPoolExecutor(12) as pool:
        texts = dict(pool.map(fetch, hosts))
    today = dt.date.today().isoformat()
    counts = {'disallowed': 0, 'partly': 0, 'allowed': 0}
    for s in reg['sources']:
        if not s['u'].startswith('http'):
            continue
        parts = urlsplit(s['u'])
        bare = parts.netloc.removeprefix('www.')
        found = [t for t in (texts.get(bare), texts.get('www.' + bare)) if t is not None]
        text = '\n'.join(found) if found else None
        signal = sorted({line.split(':', 1)[1].strip() for t in found for line in t.splitlines()
                         if line.lower().startswith('content-signal:')})
        if text is None:
            s['robots'] = {'ai': 'allowed', 'all': 'allowed', 'delay': None, 'checked': today, 'note': 'no robots.txt'}
            counts['allowed'] += 1
            continue
        rp = robotparser.RobotFileParser()
        rp.parse(text.splitlines())
        path = parts.path or '/'
        ai = [rp.can_fetch(a, path) for a in AGENTS]
        state = 'allowed' if all(ai) else 'disallowed' if not any(ai) else 'partly'
        blocked = [a for a, ok in zip(AGENTS, ai) if not ok]
        delay = rp.crawl_delay('ClaudeBot') or rp.crawl_delay('*')
        if any('ai-train=no' in x.replace(' ', '') or 'ai-input=no' in x.replace(' ', '') for x in signal) and state == 'allowed':
            state = 'partly'  # Content-Signal opts out of AI training or input, though fetching is allowed
        s['robots'] = {'ai': state, 'all': 'allowed' if rp.can_fetch('*', path) else 'disallowed', 'delay': delay,
                       'checked': today, **({'blocks': blocked} if blocked else {}), **({'content_signal': signal} if signal else {})}
        counts[state] += 1
    reg_path.write_bytes(json.dumps(reg, ensure_ascii=False, indent=1).encode('utf-8'))
    print(f'{len(hosts)} hosts; sources: {counts}')
    for s in reg['sources']:
        r = s.get('robots') or {}
        if r.get('ai') != 'allowed' or r.get('delay'):
            print(f"  {r.get('ai'):<10} delay={r.get('delay')}  {s.get('c', '')[:22]:<22} {s['n'][:40]:<40} {r.get('blocks', '')}")


if __name__ == '__main__':
    main()
