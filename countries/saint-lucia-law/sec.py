import sys, re, html
sys.path.insert(0, __import__('os').path.dirname(__file__))
import fetch
def sec(url):
    t = fetch.cached(url).decode('utf8')
    i = t.find('<section id="document">'); j = t.find('</section>', i)
    return t[i:j]
if __name__ == '__main__':
    s = sec(sys.argv[1])
    if len(sys.argv) > 2: print(s[:int(sys.argv[2])])
    else: print(re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]+>', ' ', s))))
