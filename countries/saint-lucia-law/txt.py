import re, html, sys
sys.path.insert(0, __import__('os').path.dirname(__file__))
import fetch
def text(url):
    t = fetch.cached(url).decode('utf8', 'replace')
    t = re.sub(r'<script.*?</script>|<style.*?</style>', '', t, flags=re.S)
    return re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]+>', ' ', t)))
if __name__ == '__main__':
    print(text(sys.argv[1])[:int(sys.argv[2]) if len(sys.argv) > 2 else 4000])
