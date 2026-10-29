"""Build gazette_index.json: every Al-Waqa'i' issue Al-Muqtafi lists, with each text's title and getleg id.

Reads year pages /pg/YY/ and each issue page (getlist.asp?issue=N or a special-issue .html).
Uses fetch.get (cached).  Deterministic given the cache.
"""
import html, json, os, re, sys
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import fetch  # noqa: E402

BASE = 'http://muqtafi.birzeit.edu/pg/'
YEARS = ['94', '95', '96', '97', '98', '99'] + ['%02d' % y for y in range(0, 27)]


def clean(s):
    s = html.unescape(re.sub(r'<[^>]+>', ' ', s))
    return re.sub(r'\s+', ' ', s).strip()


def issues_for_year(yy):
    t = fetch.get(BASE + yy + '/').decode('cp1256', 'replace')
    out = []
    for href, label in re.findall(r'<a href=["\']?([^ "\'>]+)["\']?[^>]*>(.*?)</a>', t, flags=re.S | re.I):
        if 'getlist.asp' in href or (href.endswith('.html') and '/' not in href):
            url = BASE + href.replace('../', '') if 'getlist' in href else BASE + yy + '/' + href
            out.append({'year': yy, 'label': clean(label), 'url': url})
    return out


def texts_in_issue(url):
    t = fetch.get(url).decode('cp1256', 'replace')
    head = re.search(r'العدد[^<]*?،\s*([0-9]{1,2}-[0-9]{1,2}-[0-9]{4})', t)
    out = []
    for id_, label in re.findall(r'getleg\.asp\?id=(\d+)["\']?[^>]*>(.*?)</a>', t, flags=re.S | re.I):
        out.append({'id': int(id_), 'title': clean(label).strip('[] ')})
    return (head.group(1) if head else None), out


def main():
    issues = []
    for yy in YEARS:
        issues += issues_for_year(yy)
    with ThreadPoolExecutor(3) as ex:
        res = list(ex.map(lambda i: texts_in_issue(i['url']), issues))
    for i, (d, texts) in zip(issues, res):
        i['date'] = d
        i['texts'] = texts
    tmp = os.path.join(HERE, 'gazette_index.json.tmp')
    json.dump(issues, open(tmp, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    os.replace(tmp, os.path.join(HERE, 'gazette_index.json'))
    print(len(issues), 'issues', sum(len(i['texts']) for i in issues), 'texts')


if __name__ == '__main__':
    main()
