import datetime, os, sys
p = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'claims', f'switzerland-{sys.argv[2]}-city-law.txt')
if sys.argv[1] == 'claim':
    fd = os.open(p, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    os.write(fd, ('gitlaw-scraper-dell ' + datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
                  + ' Swiss towns on LexWork (municipal tier via global-law-main-composer)\n').encode())
    os.close(fd); print('claimed', p)
else:
    os.remove(p); print('released', p)
