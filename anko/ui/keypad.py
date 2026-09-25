"""On-screen keypad in the style of the fx-991CW (SHIFT / ALPHA layers)."""
from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QPointF, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QLinearGradient, QPainter, QPen, QBrush
from PySide6.QtWidgets import QAbstractButton, QGridLayout, QWidget, QSizePolicy

from ..core.mathtree import seq_from, frac_node, sqrt_node, sup_node, structure, Seq
from .mathlayout import DrawState, Fonts, layout
from .theme import T

BOX = "□"


def _label_seq(name: str) -> Seq:
    b = lambda: seq_from(BOX)
    if name == "@frac":
        return seq_from(frac_node(b(), b()))
    if name == "@mixed":
        return seq_from(BOX, frac_node(b(), b()))
    if name == "@sqrt":
        return seq_from(sqrt_node(b()))
    if name == "@cbrt":
        return seq_from(structure("root", seq_from("3"), b()))
    if name == "@root":
        return seq_from(structure("root", b(), b()))
    if name == "@sq":
        return seq_from("x", sup_node(seq_from("2")))
    if name == "@cube":
        return seq_from("x", sup_node(seq_from("3")))
    if name == "@pow":
        return seq_from("x", sup_node(seq_from("y")))
    if name == "@inv":
        return seq_from("x", sup_node(seq_from("−1")))
    if name == "@tenx":
        return seq_from("10", sup_node(seq_from("x")))
    if name == "@ex":
        return seq_from("e", sup_node(seq_from("x")))
    if name == "@ten":
        return seq_from("×10", sup_node(seq_from("x")))
    if name == "@int":
        return seq_from(structure("integ", b(), seq_from(""), seq_from("")))
    if name == "@deriv":
        return seq_from(structure("deriv", b(), seq_from("")))
    if name == "@sum":
        return seq_from(structure("sigma", b(), seq_from(""), seq_from("")))
    if name == "@prod":
        return seq_from(structure("prod", b(), seq_from(""), seq_from("")))
    if name == "@logb":
        return seq_from(structure("logb", seq_from("a"), b()))
    if name in ("@sin-1", "@cos-1", "@tan-1"):
        return seq_from(name[1:4], sup_node(seq_from("−1")))
    return seq_from(name)


@dataclass
class Key:
    label: str
    shift: str = ""
    alpha: str = ""
    act: str = ""
    sact: str = ""
    aact: str = ""
    role: str = "fn"


ROW_NAV = [
    Key("SHIFT", act="cmd:shift", role="shift"), Key("ALPHA", act="cmd:alpha", role="alpha"),
    Key("◀", act="cmd:left", role="nav"), Key("▲", act="cmd:up", role="nav"),
    Key("▼", act="cmd:down", role="nav"), Key("▶", act="cmd:right", role="nav"),
]
ROWS_FN = [
    [Key("CATALOG", "CONST", "", "cmd:catalog", "cmd:const"), Key("CALC", "SOLVE", "", "cmd:calc", "cmd:solve"),
     Key("∫", "d/dx", "", "tpl:integ", "tpl:deriv"), Key("Σ", "Π", "", "tpl:sigma", "tpl:prod"),
     Key("MENU", "SETUP", "", "cmd:menu", "cmd:settings"), Key("x", "=", "", "t:x", "t:=")],
    [Key("@frac", "a b/c", "", "tpl:frac", "tpl:mixed"), Key("@sqrt", "@cbrt", "", "tpl:sqrt", "tpl:cbrt"),
     Key("@sq", "@cube", "", "sup:2", "sup:3"), Key("@pow", "@root", "", "tpl:sup", "tpl:root"),
     Key("log", "@tenx", "@logb", "f:log(", "cmd:tenx", "tpl:logb"), Key("ln", "@ex", "", "f:ln(", "cmd:ex")],
    [Key("(−)", "∠", "A", "t:−", "t:∠", "t:A"), Key("°′″", "▸DMS", "B", "cmd:dmsmark", "f:dms(", "t:B"),
     Key("@inv", "x!", "C", "sup:-1", "t:!", "t:C"), Key("sin", "@sin-1", "D", "f:sin(", "f:asin(", "t:D"),
     Key("cos", "@cos-1", "E", "f:cos(", "f:acos(", "t:E"), Key("tan", "@tan-1", "F", "f:tan(", "f:atan(", "t:F")],
    [Key("RCL", "STO", "X", "cmd:rcl", "t:→", "t:X"), Key("ENG", "i", "Y", "cmd:eng", "t:i", "t:Y"),
     Key("(", "%", "", "t:(", "t:%"), Key(")", ",", "", "t:)", "t:,"),
     Key("S⇔D", "e", "", "cmd:sd", "t:e"), Key("M+", "M−", "M", "cmd:mplus", "cmd:mminus", "t:M")],
]
ROWS_NUM = [
    [Key("7", act="t:7", role="num"), Key("8", act="t:8", role="num"), Key("9", act="t:9", role="num"),
     Key("DEL", "UNDO", "", "cmd:del", "cmd:undo", role="del"), Key("AC", "CLR", "", "cmd:ac", "cmd:clear_history", role="del")],
    [Key("4", act="t:4", role="num"), Key("5", act="t:5", role="num"), Key("6", act="t:6", role="num"),
     Key("×", "nPr", "", "t:×", "t:nPr", role="op"), Key("÷", "nCr", "", "t:÷", "t:nCr", role="op")],
    [Key("1", act="t:1", role="num"), Key("2", act="t:2", role="num"), Key("3", act="t:3", role="num"),
     Key("+", "Pol", "", "t:+", "f:Pol(", role="op"), Key("−", "Rec", "", "cmd:minus", "f:Rec(", role="op")],
    [Key("0", "Ran#", "", "t:0", "t:Ran#", role="num"), Key(".", "RanInt", "", "t:.", "f:RanInt(", role="num"),
     Key("@ten", "π", "", "cmd:times10", "t:π", role="num"), Key("Ans", "PreAns", "", "t:Ans", "t:PreAns", role="num"),
     Key("=", "", "", "cmd:eq", role="eq")],
]

SHIFT_FONT_PX = 10.5


class KeyButton(QAbstractButton):
    def __init__(self, key: Key, parent=None):
        super().__init__(parent)
        self.key = key
        self.setFocusPolicy(Qt.NoFocus)
        self.setCursor(Qt.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.shift_on = False
        self.alpha_on = False
        self.active = False
        big = key.role in ("num", "eq", "op", "del")
        self.setMinimumSize(58, 44 if big else 38)
        self._lab = _label_seq(key.label)
        self._slab = _label_seq(key.shift) if key.shift else None
        self._alab = _label_seq(key.alpha) if key.alpha else None
        px = 21 if key.role in ("num", "eq") else 19 if key.role == "op" else 13.5
        if key.label in ("SHIFT", "ALPHA", "MENU", "CATALOG", "CALC", "RCL", "ENG", "DEL", "AC", "S⇔D", "Ans", "M+"):
            px = 11.5
        if key.label.startswith("@") or key.label in ("sin", "cos", "tan", "log", "ln", "∫", "Σ"):
            px = 15
        if key.label in ("◀", "▲", "▼", "▶"):
            px = 12
        self._fonts = Fonts(px, bold=key.role in ("num", "eq", "op", "shift", "alpha"))
        self._sfonts = Fonts(SHIFT_FONT_PX)

    def sizeHint(self):
        return QSize(66, 42)

    def _colors(self):
        r = self.key.role
        if r == "num":
            return T.key_num_top, T.key_num_bot
        if r == "op":
            return T.key_op_top, T.key_op_bot
        if r == "del":
            return T.key_del_top, T.key_del_bot
        if r == "eq":
            return T.key_eq_top, T.key_eq_bot
        if r == "nav":
            return T.key_nav_top, T.key_nav_bot
        if r in ("shift", "alpha"):
            return T.key_nav_top, T.key_nav_bot
        return T.key_fn_top, T.key_fn_bot

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.TextAntialiasing)
        down = self.isDown()
        r = QRectF(self.rect()).adjusted(2, 1, -2, -4)
        if down:
            r.translate(0, 2)
        rad = 9
        # ambient shadow
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(0, 0, 0, 120 if T.name == "dark" else 55))
        p.drawRoundedRect(r.translated(0, 3), rad, rad)
        top, bot = self._colors()
        g = QLinearGradient(r.topLeft(), r.bottomLeft())
        g.setColorAt(0, QColor(top))
        g.setColorAt(1, QColor(bot))
        if down:
            g = QLinearGradient(r.topLeft(), r.bottomLeft())
            g.setColorAt(0, QColor(bot))
            g.setColorAt(1, QColor(bot).lighter(108))
        p.setBrush(QBrush(g))
        p.setPen(QPen(QColor(255, 255, 255, 26 if T.name == "dark" else 120), 1))
        p.drawRoundedRect(r.adjusted(0.5, 0.5, -0.5, -0.5), rad, rad)
        # inset top highlight
        hl = QLinearGradient(r.topLeft(), QPointF(r.left(), r.top() + r.height() * 0.5))
        hl.setColorAt(0, QColor(255, 255, 255, 38 if T.name == "dark" else 90))
        hl.setColorAt(1, QColor(255, 255, 255, 0))
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(hl))
        p.drawRoundedRect(r.adjusted(1, 1, -1, -1), rad - 1, rad - 1)
        # labels
        key = self.key
        has_small = bool(key.shift or key.alpha)
        col = QColor(T.key_text)
        if key.role == "eq":
            col = QColor(T.accent_text)
        if key.role == "shift":
            col = QColor(T.key_shift)
        elif key.role == "alpha":
            col = QColor(T.key_alpha)
        if (key.role == "shift" and self.shift_on) or (key.role == "alpha" and self.alpha_on):
            p.setBrush(QColor(T.key_shift if key.role == "shift" else T.key_alpha))
            p.setPen(Qt.NoPen)
            p.drawRoundedRect(r, rad, rad)
            col = QColor("#1a1206")
        dc = DrawState(col, col, col, blink=False)
        box = layout(self._lab, self._fonts, 0)
        cy = r.center().y() + (5 if has_small else 0)
        box.draw(p, r.center().x() - box.w / 2, cy - box.h / 2 + box.asc - (0 if key.label[0] != "@" else 1), dc)
        if self._slab is not None:
            c = QColor(T.key_shift)
            if not self.shift_on and self.alpha_on:
                c.setAlpha(110)
            elif self.shift_on:
                c = c.lighter(125)
            sb = layout(self._slab, self._sfonts, 0)
            sb.draw(p, r.left() + 7, r.top() + 4 + sb.asc, DrawState(c, c, c, blink=False))
        if self._alab is not None:
            c = QColor(T.key_alpha)
            if self.alpha_on:
                c = c.lighter(125)
            elif self.shift_on:
                c.setAlpha(110)
            ab = layout(self._alab, self._sfonts, 0)
            ab.draw(p, r.right() - 7 - ab.w, r.top() + 4 + ab.asc, DrawState(c, c, c, blink=False))

    def set_layer(self, shift, alpha):
        if (shift, alpha) != (self.shift_on, self.alpha_on):
            self.shift_on, self.alpha_on = shift, alpha
            self.update()


class Keypad(QWidget):
    action = Signal(str)
    layerChanged = Signal(bool, bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.shift = False
        self.alpha = False
        self.buttons = []
        g = QGridLayout(self)
        g.setContentsMargins(6, 4, 6, 6)
        g.setHorizontalSpacing(4)
        g.setVerticalSpacing(2)
        row = 0
        rows6 = [ROW_NAV] + ROWS_FN
        for keys in rows6:
            for i, k in enumerate(keys):
                self._add(g, k, row, i * 5, 5)
            g.setRowStretch(row, 1)
            row += 1
        g.setRowMinimumHeight(row, 4)
        row += 1
        for keys in ROWS_NUM:
            for i, k in enumerate(keys):
                self._add(g, k, row, i * 6, 6)
            g.setRowStretch(row, 1)
            row += 1
        for c in range(30):
            g.setColumnStretch(c, 1)

    def _add(self, grid, key, row, col, span):
        b = KeyButton(key)
        b.clicked.connect(lambda _=False, k=key: self._pressed(k))
        grid.addWidget(b, row, col, 1, span)
        self.buttons.append(b)

    def _pressed(self, key: Key):
        if key.act == "cmd:shift":
            self.shift, self.alpha = not self.shift, False
            return self._emit_layer()
        if key.act == "cmd:alpha":
            self.alpha, self.shift = not self.alpha, False
            return self._emit_layer()
        act = key.act
        if self.shift and key.sact:
            act = key.sact
        elif self.alpha and key.aact:
            act = key.aact
        self.shift = self.alpha = False
        self._emit_layer()
        if act:
            self.action.emit(act)

    def _emit_layer(self):
        for b in self.buttons:
            b.set_layer(self.shift, self.alpha)
        self.layerChanged.emit(self.shift, self.alpha)

    def reset_layers(self):
        if self.shift or self.alpha:
            self.shift = self.alpha = False
            self._emit_layer()

    def set_layers(self, shift, alpha):
        self.shift, self.alpha = shift, alpha
        self._emit_layer()
