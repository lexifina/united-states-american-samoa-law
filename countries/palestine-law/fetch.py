"""Fetch Al-Muqtafi (Birzeit University) gazette pages into .cache/.

Al-Muqtafi's open gazette mirror (http://muqtafi.birzeit.edu/pg/) lists every
issue of Al-Waqa'i' al-Filastiniyya and serves each published text with
getleg.asp?id=N.  HTTPS times out from this machine; plain HTTP answers.

Usage: python -X utf8 fetch.py URL [URL ...]   (or with no args: the acts in acts.json)
Cache file name = sha256(url).  Every request is logged to .cache/requests.jsonl.
"""
import hashlib, json, os, subprocess, sys, threading, time

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, '.cache')
UA = 'lexifina-watch/1.0 (+https://lexifina.com/watch; corpus@lexifina.com)'
_last = [0.0]
_lock = threading.Lock()


def path_for(url):
    return os.path.join(CACHE, hashlib.sha256(url.encode()).hexdigest())


def get(url, min_gap=0.34):
    p = path_for(url)
    if os.path.exists(p):
        return open(p, 'rb').read()
    os.makedirs(CACHE, exist_ok=True)
    with _lock:
        wait = _last[0] + min_gap - time.time()
        if wait > 0:
            time.sleep(wait)
        _last[0] = time.time()
    tmp = p + '.part'
    r = subprocess.run(['curl', '-s', '--compressed', '-m', '60', '-A', UA, '-o', tmp,
                        '-w', '%{http_code}', url], capture_output=True, text=True)
    code = r.stdout.strip()
    with _lock, open(os.path.join(CACHE, 'requests.jsonl'), 'a', encoding='utf-8') as f:
        f.write(json.dumps({'url': url, 'status': code, 'at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}) + '\n')
    if code != '200':
        if os.path.exists(tmp):
            os.remove(tmp)
        raise RuntimeError(f'{url}: HTTP {code}')
    os.replace(tmp, p)
    return open(p, 'rb').read()


def leg(id_):
    return get(f'http://muqtafi.birzeit.edu/pg/getleg.asp?id={id_}')


if __name__ == '__main__':
    urls = sys.argv[1:]
    if not urls:
        acts = json.load(open(os.path.join(HERE, 'acts.json'), encoding='utf-8'))
        for a in acts:
            for u in a.get('fetch', []):
                urls.append(u)
    for u in urls:
        b = get(u)
        print(len(b), hashlib.sha256(b).hexdigest()[:12], u)
