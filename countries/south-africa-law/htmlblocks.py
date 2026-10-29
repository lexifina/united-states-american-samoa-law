"""Turns the government's Constitution HTML pages (gov.za 1999, info.gov.za 2004-2012, gov.za today) into blocks.

A block is a heading, a paragraph (with the label the list markup gives it: "(1)", "(a)", "(i)") or an amendment
note ("[Sub-s. (1) amended by ...]"). Labels come from the markup, not from the browser's rendering: an <li> that only
wraps a nested list does not take a number (the 1999 pages wrap every sub-list that way).
"""
from __future__ import annotations

import html
import re
from html.parser import HTMLParser

BLOCK = {'p', 'div', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'li', 'ol', 'ul', 'table', 'tr', 'td', 'th', 'blockquote',
         'center', 'dd', 'dt', 'dl', 'body', 'html', 'tbody', 'thead', 'form'}
VOID = {'br', 'hr', 'img', 'meta', 'link', 'input', 'area', 'base', 'col', 'wbr'}
INLINE_KEEP = {'b', 'strong', 'i', 'em', 'u', 'a', 'font', 'span', 'sup', 'sub', 'small', 'big'}


class Node:
    __slots__ = ('tag', 'attrs', 'children', 'parent')

    def __init__(self, tag, attrs=None, parent=None):
        self.tag, self.attrs, self.children, self.parent = tag, dict(attrs or {}), [], parent


class Builder(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = Node('#root')
        self.cur = self.root

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        if tag in ('script', 'style'):
            n = Node(tag, attrs, self.cur)
            self.cur.children.append(n)
            self.cur = n
            return
        if tag == 'p' and self._open('p'):
            self._close('p')          # an unclosed <p> ends at the next <p>
        if tag == 'li':
            # an unclosed <li> ends at the next <li> of the same list
            n = self.cur
            while n is not self.root and n.tag not in ('ol', 'ul', 'li'):
                n = n.parent
            if n.tag == 'li':
                self.cur = n.parent
        n = Node(tag, attrs, self.cur)
        self.cur.children.append(n)
        if tag not in VOID:
            self.cur = n

    def _open(self, tag):
        n = self.cur
        while n is not self.root:
            if n.tag == tag:
                return True
            if n.tag in ('li', 'ol', 'ul', 'td', 'table', 'div', 'blockquote'):
                return False
            n = n.parent
        return False

    def _close(self, tag):
        n = self.cur
        while n is not self.root and n.tag != tag:
            n = n.parent
        if n.tag == tag:
            self.cur = n.parent

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag in VOID:
            return
        n = self.cur
        while n is not self.root and n.tag != tag:
            n = n.parent
        if n.tag == tag:
            self.cur = n.parent

    def handle_startendtag(self, tag, attrs):
        self.cur.children.append(Node(tag.lower(), attrs, self.cur))

    def handle_data(self, data):
        self.cur.children.append(data)


def parse(doc: str) -> Node:
    b = Builder()
    b.feed(doc)
    b.close()
    return b.root


def _roman(n: int) -> str:
    vals = [(10, 'x'), (9, 'ix'), (5, 'v'), (4, 'iv'), (1, 'i')]
    out = ''
    for v, s in vals:
        while n >= v:
            out += s
            n -= v
    return out


def _label(kind: str, n: int) -> str:
    if kind == 'a':
        return '(' + (chr(ord('a') + n - 1) if n <= 26 else chr(ord('a') + n - 27) * 2) + ')'
    if kind == 'A':
        return '(' + chr(ord('A') + n - 1) + ')'
    if kind == 'i':
        return f'({_roman(n)})'
    if kind == 'I':
        return f'({_roman(n).upper()})'
    return f'({n})'


def _clean(s: str) -> str:
    s = s.replace('\r', ' ').replace('\n', ' ')
    return re.sub(r'\s+', ' ', s).strip()


def _layout(tr) -> bool:
    """A table row used for page layout (it holds paragraphs, lists or headings), not a data row."""
    stack = list(tr.children)
    while stack:
        n = stack.pop()
        if isinstance(n, str):
            continue
        if n.tag in ('ol', 'ul', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'table', 'blockquote', 'hr'):
            return True
        if n.tag == 'p' and len([c for c in n.parent.children if not isinstance(c, str) and c.tag == 'p']) > 2:
            return True
        stack.extend(n.children)
    return False


class Walker:
    def __init__(self):
        self.blocks: list[dict] = []
        self.buf: list[str] = []
        self.bold_buf: list[bool] = []
        self.anchor: str | None = None
        self.label: str | None = None
        self.level = 0
        self.heading = False

    def flush(self):
        text = _clean(''.join(self.buf))
        if text:
            b = {'text': text, 'label': self.label, 'level': self.level, 'anchor': self.anchor,
                 'heading': self.heading or (bool(self.bold_buf) and all(self.bold_buf))}
            self.blocks.append(b)
            self.label = None
            self.anchor = None
        self.buf, self.bold_buf = [], []
        self.heading = False

    def text(self, node, bold=False):
        for ch in node.children:
            if isinstance(ch, str):
                if ch.strip():
                    self.bold_buf.append(bold)
                self.buf.append(ch)
                continue
            t = ch.tag
            if t in ('script', 'style', '#comment'):
                continue
            if t == 'a' and (ch.attrs.get('name') or ch.attrs.get('id')):
                nm = ch.attrs.get('name') or ch.attrs.get('id')
                if not _clean(''.join(self.buf)):
                    self.anchor = nm
                else:
                    self.anchor = self.anchor or nm
            if t == 'br':
                self.buf.append(' ')
                continue
            if t in ('ol', 'ul'):
                self.flush()
                self.list(ch)
                continue
            if t in BLOCK and t not in ('li',):
                if t in ('h1', 'h2', 'h3', 'h4', 'h5', 'h6'):
                    self.flush()
                    self.heading = True
                    self.text(ch, True)
                    self.flush()
                    continue
                if t == 'tr' and not _layout(ch):
                    self.flush()
                    cells = []
                    for td in ch.children:
                        if not isinstance(td, str) and td.tag in ('td', 'th'):
                            w = Walker()
                            w.text(td)
                            w.flush()
                            cells.append(' '.join(b['text'] for b in w.blocks))
                    row = ' | '.join(c for c in cells if c)
                    if row:
                        self.buf.append(row)
                        self.flush()
                    continue
                self.flush()
                self.text(ch, bold)
                self.flush()
                continue
            self.text(ch, bold or t in ('b', 'strong') or (t == 'font' and False))

    def has_own_text(self, li) -> bool:
        for ch in li.children:
            if isinstance(ch, str):
                if ch.strip():
                    return True
            elif ch.tag not in ('ol', 'ul', 'br', 'script', 'style'):
                w = Walker()
                w.text(ch)
                w.flush()
                if w.blocks and ch.tag not in ('ol', 'ul'):
                    # text in an inline or <p> child
                    if any(not isinstance(x, str) and x.tag in ('ol', 'ul') for x in ch.children):
                        continue
                    return True
        return False

    def list(self, ol):
        kind = ol.attrs.get('type', '1') if ol.tag == 'ol' else 'ul'
        try:
            n = int(ol.attrs.get('start', '1'))
        except ValueError:
            n = 1
        self.level += 1
        for ch in ol.children:
            if isinstance(ch, str):
                continue
            if ch.tag in ('ol', 'ul'):
                self.list(ch)            # a list nested directly in a list (invalid, but common here)
                continue
            if ch.tag != 'li':
                self.text(ch)
                self.flush()
                continue
            if self.has_own_text(ch):
                self.flush()
                self.label = _label(kind, n) if kind != 'ul' else None
                n += 1
                self.text(ch)
                self.flush()
            else:
                self.text(ch)
                self.flush()
        self.level -= 1


def blocks(doc: str) -> list[dict]:
    root = parse(doc)
    w = Walker()
    w.text(root)
    w.flush()
    for b in w.blocks:
        b['text'] = html.unescape(b['text'])
    return w.blocks
