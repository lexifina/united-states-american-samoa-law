"""One polite GET at a time (gitlaw-scraper-dell, Swiss towns on LexWork, 2026-11-01). Private.

    python -I -X utf8 probe.py <min_gap_s> <url> [<url> ...]

Requests run strictly one after another; each host waits >= min_gap since its last request (state in
probe-cache/last.json, shared across calls). Prints status, bytes, final URL; body saved under probe-cache/.
"""
import hashlib, json, subprocess, sys, time, urllib.parse
from pathlib import Path
HERE = Path(__file__).resolve().parent
C = HERE / 'probe-cache'
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36'
gap = float(sys.argv[1])
st = C / 'last.json'
last = json.loads(st.read_text()) if st.exists() else {}
for url in sys.argv[2:]:
    host = urllib.parse.urlsplit(url).netloc
    w = last.get(host, 0) + gap - time.time()
    if w > 0:
        time.sleep(w)
    r = subprocess.run(['curl', '-s', '-L', '--max-redirs', '3', '-m', '30', '--compressed', '-A', UA,
                        '-w', '\n%{http_code} %{url_effective}', url], capture_output=True)
    last[host] = time.time()
    st.write_text(json.dumps(last))
    body, _, tail = r.stdout.rpartition(b'\n')
    f = C / (hashlib.sha256(url.encode()).hexdigest()[:16] + '.body')
    f.write_bytes(body)
    with open(C / 'requests.jsonl', 'a', encoding='utf-8') as lf:
        lf.write(json.dumps({'at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), 'url': url,
                             'result': tail.decode(errors='replace'), 'curl_rc': r.returncode, 'bytes': len(body)}) + '\n')
    print(f'{url} -> rc={r.returncode} {tail.decode(errors="replace")} {len(body)}B file={f.name}', flush=True)
