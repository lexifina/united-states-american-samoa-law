"""Fetch Norway's official open law data from Lovdata's public API (NLOD 2.0).

Source: api.lovdata.no public data sets (https://api.lovdata.no/publicData), published by
Stiftelsen Lovdata under the Norwegian Licence for Open Government Data (NLOD 2.0).
  - v1/publicData/list                                 the data sets and their lastModified stamps
  - v1/publicData/get/gjeldende-lover.tar.bz2          current laws, consolidated with amendments
  - v1/publicData/get/lovtidend-avd1-2001-2025.tar.bz2 Norsk Lovtidend avd. I (laws as promulgated)
  - v1/publicData/get/lovtidend-avd1-2026.tar.bz2      Norsk Lovtidend avd. I, current year

Everything is cached under .cache/ by the sha256 of the URL, fetched with curl (Python TLS fails on
this machine), and logged to .cache/requests.jsonl. Resumable: a cached file is never fetched again.
The list response is kept too, so the lastModified stamp of every archive is on record.

    python -X utf8 fetch.py
"""
import hashlib, json, os, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, '.cache')
UA = 'lexifina-watch/1.0 (+https://lexifina.com/watch; corpus@lexifina.com)'
BASE = 'https://api.lovdata.no/v1/publicData/'
FILES = ['gjeldende-lover.tar.bz2', 'lovtidend-avd1-2001-2025.tar.bz2', 'lovtidend-avd1-2026.tar.bz2']


def path_for(url):
    return os.path.join(CACHE, hashlib.sha256(url.encode()).hexdigest() + '.bin')


def get(url):
    p = path_for(url)
    if os.path.exists(p) and os.path.getsize(p) > 0:
        return p
    os.makedirs(CACHE, exist_ok=True)
    for attempt in range(4):
        t0 = time.time()
        r = subprocess.run(['curl', '-sS', '-L', '--compressed', '-A', UA, '-m', '900', '-w', '%{http_code}',
                            '-o', p + '.part', url], capture_output=True, text=True)
        code = r.stdout.strip()
        size = os.path.getsize(p + '.part') if os.path.exists(p + '.part') else 0
        with open(os.path.join(CACHE, 'requests.jsonl'), 'a', encoding='utf-8') as f:
            f.write(json.dumps({'url': url, 'status': code, 'bytes': size,
                                'at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
                                'secs': round(time.time() - t0, 2), 'file': os.path.basename(p)}) + '\n')
        if code == '200' and size > 0:
            os.replace(p + '.part', p)
            return p
        time.sleep(60 if code in ('429', '503') else 3 * (attempt + 1))
    raise RuntimeError(f'failed: {url} ({code})')


RECORD = ['https://api.lovdata.no/swagger/api.json',   # the API description: "Public data released under the NLOD 2.0 license"
          'https://api.lovdata.no/publicData']         # the Lovtidend data set page: Lovtidend is the only official source


def main():
    for u in RECORD:
        get(u)
        time.sleep(1)
    get(BASE + 'list')
    for name in FILES:
        p = get(BASE + 'get/' + name)
        print(name, os.path.getsize(p), os.path.basename(p))
        time.sleep(1)


if __name__ == '__main__':
    main()
