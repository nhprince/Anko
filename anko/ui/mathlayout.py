"""
Layout + painting of mathtree.Seq objects ("natural textbook display").

layout(seq, fonts)  ->  Box            (pure geometry, can be cached)
box.draw(painter, x, baseline_y, dc)   (dc = DrawState: colours, cursor, hit regions)
"""
from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QFontMetricsF, QPainterPath, QPen

from ..core.mathtree import Seq, Node

BIN_OPS = {"nPr", "nCr", "+", "−", "×", "÷", "=", "<", ">", "≤", "≥", "≠", "→", "∠", "and", "or", "xor", "xnor", "-", "*", "/"}
OPEN_TOKS = {"("}
FONT_FAMILIES = ["Cambria Math", "Segoe UI", "Noto Sans", "DejaVu Sans", "Arial"]


class Fonts:
    """font cache for one base pixel size"""

    def __init__(self, base_px: float, families=None, bold=False):
        self.base = base_px
        self.families = families or FONT_FAMILIES
        self.bold = bold
        self._c = {}

    def get(self, level: int, scale: float = 1.0):
        key = (level, scale)
        if key not in self._c:
            px = max(9.0, self.base * (0.72 ** level) * scale)
            f = QFont()
            f.setFamilies(self.families)
            f.setPixelSize(int(round(px)))
            f.setStyleStrategy(QFont.PreferAntialias)
            f.setWeight(QFont.DemiBold if self.bold else QFont.Normal)
            self._c[key] = (f, QFontMetricsF(f), px)
        return self._c[key]


class DrawState:
    def __init__(self, ink="#111", dim="#9aa39a", accent="#d97706", cursor=None, blink=True, regions=None):
        self.ink = QColor(ink)
        self.dim = QColor(dim)
        self.accent = QColor(accent)
        self.cursor = cursor          # (seq, pos) or None
        self.blink = blink
        self.regions = regions if regions is not None else []
        self.cursor_rect = None


class Box:
    __slots__ = ("w", "asc", "desc", "fn")

    def __init__(self, w, asc, desc, fn=None):
        self.w, self.asc, self.desc, self.fn = w, asc, desc, fn

    @property
    def h(self):
        return self.asc + self.desc

    def draw(self, p, x, y, dc):
        if self.fn:
            self.fn(p, x, y, dc)


# ---------------------------------------------------------------------------
def _text_box(text, fonts: Fonts, level, scale=1.0, color=None):
    f, fm, px = fonts.get(level, scale)
    w = fm.horizontalAdvance(text)

    def fn(p, x, y, dc):
        p.setFont(f)
        p.setPen(color or dc.ink)
        p.drawText(QPointF(x, y), text)
    return Box(w, fm.ascent() * 0.86, fm.descent(), fn)


def _space(w):
    return Box(w, 0, 0)


def _hbox(boxes, aligns=None):
    """place boxes left to right on a common baseline; aligns = per-box vertical shift (+ down)"""
    aligns = aligns or [0] * len(boxes)
    w = sum(b.w for b in boxes)
    asc = max([b.asc - s for b, s in zip(boxes, aligns)] + [0])
    desc = max([b.desc + s for b, s in zip(boxes, aligns)] + [0])

    def fn(p, x, y, dc):
        cx = x
        for b, s in zip(boxes, aligns):
            b.draw(p, cx, y + s, dc)
            cx += b.w
    return Box(w, asc, desc, fn)


def _paren_box(kind, asc, desc, fonts, level, tall_threshold=1.32):
    """'(' or ')' (or '|') that grows with its content"""
    f, fm, px = fonts.get(level)
    nominal = fm.ascent() * 0.86 + fm.descent()
    h = asc + desc
    if h <= nominal * tall_threshold or kind == "|":
        if kind == "|":
            return _bar_box(asc, desc, px)
        return _text_box(kind, fonts, level)
    w = px * 0.34
    top, bot = asc + px * 0.08, desc + px * 0.08

    def fn(p, x, y, dc):
        path = QPainterPath()
        yt, yb = y - top, y + bot
        if kind == "(":
            path.moveTo(x + w * 0.85, yt)
            path.quadTo(x - w * 0.15, (yt + yb) / 2, x + w * 0.85, yb)
        else:
            path.moveTo(x + w * 0.15, yt)
            path.quadTo(x + w * 1.15, (yt + yb) / 2, x + w * 0.15, yb)
        pen = QPen(dc.ink, max(1.2, px * 0.065))
        pen.setCapStyle(Qt.RoundCap)
        p.setPen(pen)
        p.setBrush(Qt.NoBrush)
        p.drawPath(path)
    return Box(w, top, bot, fn)


def _bar_box(asc, desc, px):
    w = px * 0.28

    def fn(p, x, y, dc):
        p.setPen(QPen(dc.ink, max(1.2, px * 0.065)))
        p.drawLine(QPointF(x + w / 2, y - asc - px * 0.05), QPointF(x + w / 2, y + desc + px * 0.05))
    return Box(w, asc + px * 0.05, desc + px * 0.05, fn)


def _placeholder(fonts: Fonts, level):
    f, fm, px = fonts.get(level)
    w, h = px * 0.5, px * 0.78

    def fn(p, x, y, dc):
        pen = QPen(dc.dim, 1.1, Qt.DashLine)
        p.setPen(pen)
        p.setBrush(Qt.NoBrush)
        p.drawRoundedRect(QRectF(x + 1, y - h + px * 0.06, w - 2, h), 2, 2)
    return Box(w, h, px * 0.12, fn)


# ---------------------------------------------------------------------------
def layout(seq: Seq, fonts: Fonts, level=0, editable=False, min_height=True) -> Box:
    f, fm, px = fonts.get(level)
    atoms = []   # [kind, box, item_index]
    prev_kind = None
    n_items = len(seq.items)
    item_first_atom = []

    def add(kind, box, idx):
        atoms.append([kind, box, idx])

    for idx, it in enumerate(seq.items):
        item_first_atom.append(len(atoms))
        if it.kind == "tok":
            t = it.text
            if t.endswith("(") and len(t) > 1:
                add("text", _text_box(t[:-1], fonts, level), idx)
                add("open", None, idx)
            elif t == "(":
                add("open", None, idx)
            elif t == ")":
                add("close", None, idx)
            elif t in BIN_OPS:
                shown = {"-": "−", "*": "×", "/": "÷"}.get(t, t)
                unary = not atoms or atoms[-1][0] in ("op", "open") or (shown == "∠" and False)
                if t in ("and", "or", "xor", "xnor"):
                    shown = f" {t} "
                    unary = False
                if unary and shown in ("−", "+"):
                    add("text", _text_box(shown, fonts, level), idx)
                else:
                    pad = px * (0.22 if shown != "∠" else 0.06)
                    add("op", _hbox([_space(pad), _text_box(shown, fonts, level), _space(pad)]), idx)
            elif t == ",":
                add("text", _hbox([_text_box(",", fonts, level), _space(px * 0.22)]), idx)
            elif t == "ᴇ":
                add("text", _text_box("ᴇ", fonts, level), idx)
            else:
                add("text", _text_box(t, fonts, level), idx)
        else:
            add("node", _layout_node(it, fonts, level, editable), idx)
    # match parentheses and make them tall where needed
    stack = []
    pairs = {}
    for i, a in enumerate(atoms):
        if a[0] == "open":
            stack.append(i)
        elif a[0] == "close" and stack:
            pairs[stack.pop()] = i
    for o, c in list(pairs.items()):
        inner = [atoms[j][1] for j in range(o + 1, c) if atoms[j][1] is not None]
        asc = max([b.asc for b in inner] + [fm.ascent() * 0.86])
        desc = max([b.desc for b in inner] + [fm.descent()])
        atoms[o][1] = _paren_box("(", asc, desc, fonts, level)
        atoms[c][1] = _paren_box(")", asc, desc, fonts, level)
    for a in atoms:
        if a[1] is None:
            a[1] = _text_box("(" if a[0] == "open" else ")", fonts, level)
    # geometry
    xs = []
    x = 0.0
    ai = 0
    boxes = [a[1] for a in atoms]
    for idx in range(n_items):
        xs.append(x)
        first = item_first_atom[idx]
        last = item_first_atom[idx + 1] if idx + 1 < n_items else len(atoms)
        for j in range(first, last):
            x += boxes[j].w
    xs.append(x)
    total_w = x
    if not atoms:
        if editable or True:
            ph = _placeholder(fonts, level)
        empty_box = ph if seq.owner is not None else None
        if empty_box is not None:
            asc, desc, w = empty_box.asc, empty_box.desc, empty_box.w
            total_w = w
        else:
            asc, desc = fm.ascent() * 0.86, fm.descent()
            empty_box = None
    else:
        asc = max(b.asc for b in boxes)
        desc = max(b.desc for b in boxes)
        empty_box = None
    if min_height:
        asc = max(asc, fm.ascent() * 0.86)
        desc = max(desc, fm.descent())
    pad = px * 0.06 if editable else 0

    def fn(p, x0, y, dc):
        cx = x0
        for b in boxes:
            b.draw(p, cx, y, dc)
            cx += b.w
        if empty_box is not None:
            empty_box.draw(p, x0, y, dc)
        rect = QRectF(x0, y - asc, max(total_w, 4), asc + desc)
        dc.regions.append((rect, seq, [x0 + v for v in xs]))
        if dc.cursor is not None and dc.cursor[0] is seq:
            pos = min(dc.cursor[1], n_items)
            cxp = x0 + xs[pos] + (0 if empty_box is None else 0)
            r = QRectF(cxp - 1, y - max(asc, fm.ascent()), 2, max(asc, fm.ascent()) + max(desc, fm.descent()))
            dc.cursor_rect = r
            if dc.blink:
                p.fillRect(r, dc.accent)

    b = Box(total_w, asc, desc, fn)
    b.__class__ = Box
    return b


# ---------------------------------------------------------------------------
def _layout_node(n: Node, fonts: Fonts, level, editable) -> Box:
    f, fm, px = fonts.get(level)
    axis = px * 0.30
    k = n.kind
    if k == "frac":
        num = layout(n.slots[0], fonts, level, editable)
        den = layout(n.slots[1], fonts, level, editable)
        pad = px * 0.14
        w = max(num.w, den.w) + 2 * pad
        gap = px * 0.10
        bar = max(1.0, px * 0.06)
        asc = axis + bar / 2 + gap + num.h
        desc = den.h + gap - axis + bar / 2

        def fn(p, x, y, dc):
            p.setPen(QPen(dc.ink, bar))
            yb = y - axis
            p.drawLine(QPointF(x + pad * 0.5, yb), QPointF(x + w - pad * 0.5, yb))
            num.draw(p, x + (w - num.w) / 2, yb - bar / 2 - gap - num.desc, dc)
            den.draw(p, x + (w - den.w) / 2, yb + bar / 2 + gap + den.asc, dc)
        return Box(w, max(asc, fm.ascent()), max(desc, fm.descent()), fn)

    if k == "mixed":
        whole = layout(n.slots[0], fonts, level, editable)
        fr = _layout_node(_as_frac(n), fonts, level, editable)
        return _hbox([whole, _space(px * 0.08), fr])

    if k in ("sqrt", "root"):
        rad = layout(n.slots[-1], fonts, level, editable)
        return _radical(rad, layout(n.slots[0], fonts, level + 2, editable) if k == "root" else None, fonts, level)

    if k == "sup":
        e = layout(n.slots[0], fonts, level + 1, editable)
        shift = px * 0.44

        def fn(p, x, y, dc):
            e.draw(p, x, y - shift, dc)
        return Box(e.w + px * 0.03, e.asc + shift, max(0, e.desc - shift), fn)

    if k == "logb":
        base = layout(n.slots[0], fonts, level + 1, editable)
        arg = layout(n.slots[1], fonts, level, editable)
        po = _paren_box("(", arg.asc, arg.desc, fonts, level)
        pc = _paren_box(")", arg.asc, arg.desc, fonts, level)
        return _hbox([_text_box("log", fonts, level), base, po, arg, pc], [0, px * 0.22, 0, 0, 0])

    if k == "abs":
        inner = layout(n.slots[0], fonts, level, editable)
        bar = _bar_box(max(inner.asc, fm.ascent() * 0.86), max(inner.desc, fm.descent()), px)
        return _hbox([bar, _space(px * 0.05), inner, _space(px * 0.05), bar])

    if k in ("sigma", "prod"):
        body = layout(n.slots[0], fonts, level, editable)
        lo = layout(n.slots[1], fonts, level + 1, editable)
        hi = layout(n.slots[2], fonts, level + 1, editable)
        eq = _text_box("x=", fonts, level + 1)
        lo_full = _hbox([eq, lo])
        S = px * 1.35
        sf, sfm, _ = fonts.get(level, 1.35)
        glyph = "Σ" if k == "sigma" else "Π"
        gw = sfm.horizontalAdvance(glyph)
        half = S * 0.36
        w = max(gw, hi.w, lo_full.w) + px * 0.1
        gap = px * 0.05
        asc = axis + half + gap + hi.h
        desc = half - axis + gap + lo_full.h

        def sfn(p, x, y, dc):
            p.setFont(sf)
            p.setPen(dc.ink)
            p.drawText(QPointF(x + (w - gw) / 2, y - axis + half), glyph)
            hi.draw(p, x + (w - hi.w) / 2, y - axis - half - gap - hi.desc, dc)
            lo_full.draw(p, x + (w - lo_full.w) / 2, y - axis + half + gap + lo_full.asc, dc)
        sym = Box(w, asc, desc, sfn)
        po = _paren_box("(", body.asc, body.desc, fonts, level)
        pc = _paren_box(")", body.asc, body.desc, fonts, level)
        return _hbox([sym, _space(px * 0.1), po, body, pc])

    if k == "integ":
        body = layout(n.slots[0], fonts, level, editable)
        lo = layout(n.slots[1], fonts, level + 1, editable)
        hi = layout(n.slots[2], fonts, level + 1, editable)
        S = px * 1.55
        sf, sfm, _ = fonts.get(level, 1.55)
        gw = sfm.horizontalAdvance("∫")
        half = S * 0.5

        def ifn(p, x, y, dc):
            p.setFont(sf)
            p.setPen(dc.ink)
            p.drawText(QPointF(x, y - axis + S * 0.30), "∫")
            hi.draw(p, x + gw * 0.95, y - axis - half + hi.asc * 0.55, dc)
            lo.draw(p, x + gw * 0.5, y - axis + half - lo.desc * 0.1, dc)
        lim_w = max(hi.w + gw * 0.95, lo.w + gw * 0.5)
        sign = Box(max(gw, lim_w), axis + half + px * 0.05, half - axis + px * 0.05, ifn)
        dx = _text_box("dx", fonts, level)
        return _hbox([sign, _space(px * 0.08), body, _space(px * 0.12), dx])

    if k == "deriv":
        body = layout(n.slots[0], fonts, level, editable)
        at = layout(n.slots[1], fonts, level + 1, editable)
        d = _layout_node(_frac_of_text("d", "dx"), fonts, level, False)
        po = _paren_box("(", body.asc, body.desc, fonts, level)
        pc = _paren_box(")", body.asc, body.desc, fonts, level)
        bar = _bar_box(body.asc, body.desc, px)
        sub = _hbox([_text_box("x=", fonts, level + 1), at])
        return _hbox([d, po, body, pc, bar, sub], [0, 0, 0, 0, 0, px * 0.3])

    if k == "matrix":
        r, c = map(int, n.text.split("x"))
        cells = [layout(s, fonts, level, editable) for s in n.slots]
        colw = [max(cells[i * c + j].w for i in range(r)) for j in range(c)]
        rowa = [max(cells[i * c + j].asc for j in range(c)) for i in range(r)]
        rowd = [max(cells[i * c + j].desc for j in range(c)) for i in range(r)]
        hgap, vgap = px * 0.7, px * 0.28
        total_w = sum(colw) + hgap * (c - 1)
        total_h = sum(rowa) + sum(rowd) + vgap * (r - 1)
        asc, desc = total_h / 2 + axis, total_h / 2 - axis
        po = _paren_box("(", asc, desc, fonts, level, tall_threshold=0)
        pc = _paren_box(")", asc, desc, fonts, level, tall_threshold=0)
        inner_w = total_w + px * 0.2

        def mfn(p, x, y, dc):
            top = y - asc
            cy = top
            for i in range(r):
                by = cy + rowa[i]
                cx = x + px * 0.1
                for j in range(c):
                    cb = cells[i * c + j]
                    cb.draw(p, cx + (colw[j] - cb.w) / 2, by, dc)
                    cx += colw[j] + hgap
                cy += rowa[i] + rowd[i] + vgap
        body = Box(inner_w, asc, desc, mfn)
        return _hbox([po, body, pc])

    return _text_box("?", fonts, level)


def _as_frac(n: Node) -> Node:
    fr = Node("frac")
    fr.slots = [n.slots[1], n.slots[2]]
    return fr


def _frac_of_text(a, b) -> Node:
    fr = Node("frac")
    for i, t in enumerate((a, b)):
        fr.slots[i].add(Node("tok", t))
    return fr


def _radical(rad: Box, idx: Box | None, fonts: Fonts, level) -> Box:
    f, fm, px = fonts.get(level)
    lead = px * 0.62
    idx_shift = 0.0
    if idx is not None:
        idx_shift = max(0.0, idx.w - px * 0.3)
    w = idx_shift + lead + rad.w + px * 0.12
    over = px * 0.16
    asc = rad.asc + over + px * 0.06
    desc = rad.desc + px * 0.04
    stroke = max(1.1, px * 0.065)

    def fn(p, x, y, dc):
        x0 = x + idx_shift
        yb, yt = y + desc, y - rad.asc - over
        H = yb - yt
        pts = [(x0 + px * 0.03, yt + H * 0.58), (x0 + px * 0.15, yt + H * 0.50), (x0 + px * 0.32, yb),
               (x0 + px * 0.58, yt), (x0 + lead + rad.w + px * 0.08, yt)]
        path = QPainterPath()
        path.moveTo(*pts[0])
        for q in pts[1:]:
            path.lineTo(*q)
        pen = QPen(dc.ink, stroke)
        pen.setJoinStyle(Qt.MiterJoin)
        pen.setCapStyle(Qt.FlatCap)
        p.setPen(pen)
        p.setBrush(Qt.NoBrush)
        p.drawPath(path)
        rad.draw(p, x0 + lead, y, dc)
        if idx is not None:
            idx.draw(p, x, y - rad.asc * 0.45 - px * 0.05, dc)
    return Box(w, asc, desc, fn)


def draw_seq(p, seq: Seq, fonts: Fonts, x, y, dc: DrawState, editable=False):
    b = layout(seq, fonts, 0, editable)
    b.draw(p, x, y, dc)
    return b
