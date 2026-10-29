import sys, hashlib, json
sys.path.insert(0, r'C:/Users/alany/Documents/lexifina/scripts/sri-lanka-law')
import constitution as C
B='https://www.parliament.lk/files/pdf/constitution/constitution-upto-%sth.pdf'
for ed in sys.argv[1:]:
    u = (B % ed).replace('21th','21st')
    p = r'C:/Users/alany/Documents/lexifina/scripts/sri-lanka-law/.cache/' + hashlib.sha256(u.encode()).hexdigest()
    units, notes = C.parse_edition(p, ed)
    with open(r'C:/Users/alany/Documents/lexifina/scripts/sri-lanka-law/.work/ed%s.txt' % ed, 'w', encoding='utf-8') as f:
        for k, v in units.items():
            f.write('##### %s %s\n' % (k, notes[k]))
            for l in v['lines']:
                f.write(l + '\n')
    keys = list(units)
    print(ed, len(units), keys[:5], keys[-12:])
