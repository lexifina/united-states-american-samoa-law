"""Quoted provisions in a Malaysian amending Act (gitlaw-MY): "... is amended by substituting for section 305 the
following section: “<heading> 305. ...”." / "... by inserting after section 424 the following sections: “...”."

ops(pdf) returns, in the Act's order, [(act section, op, target sections, {key: unit})], where op is 'substitute',
'insert' or 'delete', read from the Act's own words, and each unit is formatted like layout.parse's sections
("# Section 305. <heading>", then one paragraph per line). Paragraphs: a line starting with a tab and a label, or
after a gap wider than 1.45 lines, starts a new one; other lines are joined with one space.
"""
import re

import fitz

import layout

OP_RE = re.compile(r'(substituting for section (\d+[A-Z]?)|inserting after section (\d+[A-Z]?)|deleting section '
                   r'(\d+[A-Z]?))', re.I)


def despace(t):
    """Letter-spaced justified lines ("a  l i c e n s e d  I s l a m i c") come out of the text layer with one space
    between letters and two between words: join the letters of each such word."""
    if not re.search(r'(?:(?<!\S)\S ){4,}\S(?!\S)', t):
        return t
    parts = re.split(r'( {2,}|	)', t)
    return ''.join(re.sub(' ', '', x) if re.fullmatch(r'(?:\S ){2,}\S\s*', x) else x for x in parts)


def lines_of(pdf):
    d = fitz.open(stream=pdf, filetype='pdf')
    out = []
    for i in range(d.page_count):
        for ln in layout.page_lines(d[i]):
            ln['page'] = i
            ln['text'] = despace(ln['text'])
            out.append(ln)
    return out


def key(num):
    m = re.match(r'^(\d+)([A-Z]*)$', num)
    return f'sec-{int(m.group(1)):03d}{m.group(2).lower()}'


def ops(pdf):
    L = lines_of(pdf)
    text = []
    res = []
    i = 0
    cur_act_sec = None
    instr = ''
    while i < len(L):
        ln = L[i]
        t = layout.clean(ln['text'])
        m = re.match(r'^(\d+)\.\s', t)
        if ln['bold'] and m and not t.startswith('"'):
            cur_act_sec = int(m.group(1))
            instr = t
        elif not t.startswith('"'):
            instr += ' ' + t
        if t.startswith('"') and re.search(r'the following sections?:$', instr):
            j = i
            block = []
            while j < len(L):
                block.append(L[j])
                if layout.clean(L[j]['text']).endswith('".'):
                    break
                j += 1
            om = OP_RE.search(instr)
            op = 'substitute' if om.group(2) else 'insert'
            target = om.group(2) or om.group(3)
            res.append((cur_act_sec, op, target, units(block)))
            instr = ''
            i = j + 1
            continue
        dm = re.search(r'is amended by deleting section (\d+[A-Z]?)\.$', instr)
        if dm:
            res.append((cur_act_sec, 'delete', dm.group(1), {}))
            instr = ''
        i += 1
    return res


def units(block):
    out = {}
    cur = None
    heading = []
    para = None
    last = None
    for n, ln in enumerate(block):
        t = layout.clean(ln['text'])
        first = n == 0                                   # the opening quotation mark is roman, the heading bold
        if t.startswith('"'):
            t = t[1:].lstrip()
        if t.endswith('".'):
            t = t[:-2].rstrip()
        gap = None if last is None or ln['page'] != last['page'] else ln['y'] - last['y']
        last = ln
        m = re.match(r'^(\d+[A-Z]*)\.(\s|$)', t)
        if (ln['bold'] or first) and not m:
            if heading and gap is not None and gap < 1.45 * ln['size'] and para is None:
                heading[-1] += ' ' + t
            else:
                if para is not None:
                    cur['lines'].append(para)
                    para = None
                heading = [t]
            continue
        if (ln['bold'] or first) and m:
            if para is not None:
                cur['lines'].append(para)
            num = m.group(1)
            head = ' '.join(heading) if heading else None
            heading = []
            cur = {'num': num, 'lines': [f'# Section {num}' + (f'. {head}' if head else '')]}
            out[key(num)] = cur
            para = f'{num}. ' + t[m.end():].strip()
            continue
        new = ((ln['lead_tab'] and layout.LABEL_RE.match(ln['text'])) or (gap is not None and gap > 1.45 * ln['size'])
               or (layout.LABEL_RE.match(t) and para is not None and re.search(r'([;:—]|(and|or))$', para)))
        if new or para is None:
            if para is not None:
                cur['lines'].append(para)
            para = t
        else:
            para += t if para.endswith(('-', '—')) else ' ' + t
    if para is not None:
        cur['lines'].append(para)
    return {k: {'label': f's. {u["num"]}', 'kind': 'sec', 'text': '\n'.join(re.sub(r'[ \t]+', ' ', x).strip()
                                                                             for x in u['lines']) + '\n'}
            for k, u in out.items()}
