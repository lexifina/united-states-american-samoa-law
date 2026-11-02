import datetime as d, sys
for repo in sys.argv[2:]:
    p = f'claims/{repo}.txt'
    try:
        with open(p, 'x', encoding='utf-8', newline='\n') as f:
            f.write('gitlaw-scraper-dell ' + d.datetime.now(d.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ') + f' (South American regional units: {sys.argv[1]})\n')
        print('claimed', repo)
    except FileExistsError:
        print('HELD', repo, open(p, encoding='utf-8').read().strip())
