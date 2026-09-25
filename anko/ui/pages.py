"""Mode pages other than the plain calculation page."""
from __future__ import annotations

import random
import re
from fractions import Fraction

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QAbstractItemView, QCheckBox, QComboBox, QFrame, QGridLayout, QHBoxLayout, QHeaderView,
                               QLabel, QLineEdit, QPushButton, QScrollArea, QSpinBox, QStyledItemDelegate,
                               QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget)

from ..core import solvers, stats
from ..core.formatter import decimal_text, real_seq, value_seq, value_text
from ..core.interp import Interp
from ..core.mathtree import Seq, frac_node, seq_from, tok
from ..core.values import CNum, Exact, MathErr, SyntaxErr, ZERO, fl, is_real
from .calcpage import friendly
from .mathedit import MathEditor, MathView
from .theme import T

LCD_LABEL = "color:%s; font-size:12px;"


def lcd_label(text, bold=False):
    l = QLabel(text)
    l.setStyleSheet(f"color:{T.lcd_status};font-size:12px;{'font-weight:600;' if bold else ''}")
    return l


def lcd_button(text, primary=False):
    b = QPushButton(text)
    b.setFocusPolicy(Qt.NoFocus)
    b.setCursor(Qt.PointingHandCursor)
    if primary:
        b.setStyleSheet(f"QPushButton{{background:{T.lcd_ink};color:#eaf0e3;border:none;border-radius:8px;padding:6px 16px;font-weight:600;}}"
                        f"QPushButton:hover{{background:#2b3128;}}")
    else:
        b.setStyleSheet(f"QPushButton{{background:rgba(0,0,0,0.10);color:{T.lcd_ink};border:none;border-radius:8px;padding:6px 12px;}}"
                        f"QPushButton:hover{{background:rgba(0,0,0,0.18);}}")
    return b


LCD_INPUT_QSS = (f"QLineEdit, QComboBox, QSpinBox {{ background: rgba(255,255,255,0.45); color:{T.lcd_ink}; border:1px solid rgba(0,0,0,0.20);"
                 f"border-radius:6px; padding:4px 6px; selection-background-color:{T.lcd_ink}; selection-color:#eaf0e3; }}"
                 f"QLineEdit:focus, QComboBox:focus {{ border:1px solid {T.lcd_ink}; }}"
                 f"QComboBox QAbstractItemView {{ background:#e8eddf; color:{T.lcd_ink}; selection-background-color:{T.lcd_ink}; selection-color:#eaf0e3; }}"
                 f"QTableWidget {{ background: rgba(255,255,255,0.35); color:{T.lcd_ink}; border:1px solid rgba(0,0,0,0.15); border-radius:6px; gridline-color: rgba(0,0,0,0.12); }}"
                 f"QTableWidget::item:selected {{ background:{T.lcd_ink}; color:#eaf0e3; }}"
                 f"QHeaderView::section {{ background: rgba(0,0,0,0.08); color:{T.lcd_status}; border:none; border-right:1px solid rgba(0,0,0,0.10); padding:3px 6px; }}"
                 f"QLabel {{ color:{T.lcd_ink}; }} QCheckBox {{ color:{T.lcd_ink}; }}")


def clear_layout(lay, keep_last=0):
    while lay.count() > keep_last:
        it = lay.takeAt(0)
        w = it.widget()
        if w is not None:
            w.hide()
            w.setParent(None)
            w.deleteLater()
        elif it.layout() is not None:
            clear_layout(it.layout())


class ResultList(QScrollArea):
    """vertical list of  label | natural-display value"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.NoFrame)
        self.setStyleSheet("QScrollArea, QScrollArea > QWidget > QWidget { background: transparent; }")
        self.body = QWidget()
        self.lay = QVBoxLayout(self.body)
        self.lay.setContentsMargins(8, 4, 8, 4)
        self.lay.setSpacing(0)
        self.lay.addStretch(1)
        self.setWidget(self.body)

    def set_rows(self, rows, base_px=22):
        clear_layout(self.lay, keep_last=1)
        total = 8
        for label, val in rows:
            row = QWidget()
            h = QHBoxLayout(row)
            h.setContentsMargins(0, 0, 0, 0)
            l = QLabel(label)
            l.setStyleSheet(f"color:{T.lcd_status};font-size:13px;font-weight:600;")
            l.setFixedWidth(64)
            h.addWidget(l)
            if isinstance(val, str):
                val = seq_from(val)
            mv = MathView(base_px=base_px, align="right")
            mv.set_seq(val)
            h.addWidget(mv, 1)
            row.setFixedHeight(mv.height())
            total += mv.height() + 1
            self.lay.insertWidget(self.lay.count() - 1, row)
            sep = QFrame()
            sep.setFixedHeight(1)
            sep.setStyleSheet("background: rgba(0,0,0,0.10);")
            self.lay.insertWidget(self.lay.count() - 1, sep)
        self.body.setMinimumHeight(total)

    def clear(self):
        self.set_rows([])


class Page(QWidget):
    """base for the form-style pages"""

    def __init__(self, interp: Interp, parent=None):
        super().__init__(parent)
        self.ip = interp
        self.setStyleSheet(LCD_INPUT_QSS)
        self.err = QLabel("")
        self.err.setStyleSheet("color:#a12a1f;font-weight:600;")
        self.err.setWordWrap(True)

    def settings(self):
        return self.ip.s

    def active_editor(self):
        return None

    def default_focus(self):
        pass

    def refresh(self):
        pass

    def on_enter(self):
        pass

    def num(self, text, allow_complex=False):
        self.ip.complex_mode = allow_complex
        v = self.ip.evaluate(text.strip() or "0", record=False, allow_assign=False)
        if not allow_complex and not is_real(v):
            raise MathErr("Math ERROR")
        return v

    def fail(self, e):
        self.err.setText(friendly(e))

    def to_json(self):
        return None

    def from_json(self, d):
        pass


def _grid(rows, cols, headers):
    t = QTableWidget(rows, cols)
    t.setHorizontalHeaderLabels(headers)
    t.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
    t.verticalHeader().setDefaultSectionSize(26)
    t.setEditTriggers(QAbstractItemView.AllEditTriggers)
    return t


# ---------------------------------------------------------------------------
# Statistics
# ---------------------------------------------------------------------------
class StatPage(Page):
    def __init__(self, interp, parent=None):
        super().__init__(interp, parent)
        v = QVBoxLayout(self)
        v.setContentsMargins(10, 6, 10, 6)
        v.setSpacing(5)
        top = QHBoxLayout()
        self.kind = QComboBox()
        self.kind.addItems(["1-Variable", "2-Variable"])
        self.reg = QComboBox()
        self.reg.addItems(stats.REGRESSIONS)
        self.reg.setEnabled(False)
        self.freq = QCheckBox("Freq")
        top.addWidget(self.kind)
        top.addWidget(self.reg, 1)
        top.addWidget(self.freq)
        v.addLayout(top)
        self.tbl = _grid(40, 2, ["x", "Freq"])
        v.addWidget(self.tbl, 3)
        b = QHBoxLayout()
        self.go = lcd_button("Calculate", True)
        self.clr = lcd_button("Clear data")
        b.addWidget(self.go)
        b.addWidget(self.clr)
        b.addStretch(1)
        v.addLayout(b)
        v.addWidget(self.err)
        self.res = ResultList()
        v.addWidget(self.res, 4)
        pr = QHBoxLayout()
        self.px = QLineEdit()
        self.px.setPlaceholderText("x → ŷ")
        self.py = QLineEdit()
        self.py.setPlaceholderText("y → x̂")
        self.pred = QLabel("")
        pr.addWidget(self.px)
        pr.addWidget(self.py)
        pr.addWidget(self.pred, 1)
        self.pr_w = QWidget()
        self.pr_w.setLayout(pr)
        pr.setContentsMargins(0, 0, 0, 0)
        v.addWidget(self.pr_w)
        self.pr_w.hide()
        self._fn = None
        self.kind.currentIndexChanged.connect(self._layout)
        self.freq.toggled.connect(self._layout)
        self.go.clicked.connect(self.calculate)
        self.clr.clicked.connect(self._clear)
        self.px.returnPressed.connect(self._predict)
        self.py.returnPressed.connect(self._predict)
        self._layout()

    def _layout(self):
        two = self.kind.currentIndex() == 1
        heads = ["x"] + (["y"] if two else []) + (["Freq"] if self.freq.isChecked() else [])
        old = self._read_cells()
        self.tbl.setColumnCount(len(heads))
        self.tbl.setHorizontalHeaderLabels(heads)
        self.reg.setEnabled(two)
        self.pr_w.setVisible(False)
        self.res.clear()

    def _read_cells(self):
        return [[(self.tbl.item(r, c).text() if self.tbl.item(r, c) else "") for c in range(self.tbl.columnCount())]
                for r in range(self.tbl.rowCount())]

    def _clear(self):
        self.tbl.clearContents()
        self.res.clear()
        self.err.setText("")

    def calculate(self):
        self.err.setText("")
        two = self.kind.currentIndex() == 1
        xs, ys, fs = [], [], []
        try:
            for row in self._read_cells():
                if not row[0].strip():
                    continue
                xs.append(self.num(row[0]))
                i = 1
                if two:
                    if not row[1].strip():
                        raise MathErr("Math ERROR (missing y value)")
                    ys.append(self.num(row[1]))
                    i = 2
                fs.append(self.num(row[i]) if self.freq.isChecked() and row[i].strip() else Fraction(1))
            if not xs:
                raise MathErr("No data")
            s = self.settings()
            if not two:
                rows = stats.one_var(xs, fs)
                self._fn = None
                self.pr_w.hide()
            else:
                rows, pred, inv = stats.two_var(xs, ys, fs, self.reg.currentIndex())
                self._fn = (pred, inv)
                self.pr_w.show()
            self.res.set_rows([(k, value_seq(v, s)) for k, v in rows], 20)
        except Exception as e:  # noqa: BLE001
            self.fail(e)

    def _predict(self):
        try:
            pred, inv = self._fn
            s = self.settings()
            out = []
            if self.px.text().strip():
                out.append("ŷ = " + decimal_text(pred(fl(self.num(self.px.text()))), s))
            if self.py.text().strip():
                out.append("x̂ = " + decimal_text(inv(fl(self.num(self.py.text()))), s))
            self.pred.setText("   ".join(out))
        except Exception as e:  # noqa: BLE001
            self.pred.setText(friendly(e))

    def on_enter(self):
        self.calculate()

    def to_json(self):
        return {"cells": self._read_cells(), "kind": self.kind.currentIndex(), "reg": self.reg.currentIndex(),
                "freq": self.freq.isChecked()}

    def from_json(self, d):
        if not d:
            return
        self.kind.setCurrentIndex(d.get("kind", 0))
        self.reg.setCurrentIndex(d.get("reg", 0))
        self.freq.setChecked(d.get("freq", False))
        for r, row in enumerate(d.get("cells", [])):
            for c, t in enumerate(row):
                if t and c < self.tbl.columnCount():
                    self.tbl.setItem(r, c, QTableWidgetItem(t))


# ---------------------------------------------------------------------------
# Distribution
# ---------------------------------------------------------------------------
DISTS = {
    "Normal PD": (["x", "σ", "μ"], ["0", "1", "0"]),
    "Normal CD": (["Lower", "Upper", "σ", "μ"], ["-1", "1", "1", "0"]),
    "Inverse Normal": (["Area", "σ", "μ"], ["0.975", "1", "0"]),
    "Binomial PD": (["x", "N", "p"], ["3", "10", "0.5"]),
    "Binomial CD": (["x", "N", "p"], ["3", "10", "0.5"]),
    "Inverse Binomial": (["Area", "N", "p"], ["0.5", "10", "0.5"]),
    "Poisson PD": (["x", "λ"], ["2", "3"]),
    "Poisson CD": (["x", "λ"], ["2", "3"]),
    "Inverse Poisson": (["Area", "λ"], ["0.5", "3"]),
}


class DistPage(Page):
    def __init__(self, interp, parent=None):
        super().__init__(interp, parent)
        v = QVBoxLayout(self)
        v.setContentsMargins(10, 6, 10, 6)
        self.kind = QComboBox()
        self.kind.addItems(list(DISTS))
        v.addWidget(self.kind)
        self.form = QGridLayout()
        self.form.setColumnStretch(1, 1)
        v.addLayout(self.form)
        self.edits = []
        self.go = lcd_button("Calculate", True)
        row = QHBoxLayout()
        row.addWidget(self.go)
        row.addStretch(1)
        v.addLayout(row)
        v.addWidget(self.err)
        self.res = ResultList()
        v.addWidget(self.res, 1)
        self.kind.currentIndexChanged.connect(self._rebuild)
        self.go.clicked.connect(self.calculate)
        self._rebuild()

    def _rebuild(self):
        clear_layout(self.form)
        names, defaults = DISTS[self.kind.currentText()]
        self.edits = []
        for i, (n, d) in enumerate(zip(names, defaults)):
            self.form.addWidget(lcd_label(n, True), i, 0)
            e = QLineEdit(d)
            e.returnPressed.connect(self.calculate)
            self.form.addWidget(e, i, 1)
            self.edits.append(e)
        self.res.clear()
        self.err.setText("")

    def calculate(self):
        self.err.setText("")
        k = self.kind.currentText()
        try:
            a = [float(fl(self.num(e.text()))) for e in self.edits]
            n = lambda x: int(round(x))
            if k == "Normal PD":
                out = [("p", stats.normal_pd(a[0], a[2], a[1]))]
            elif k == "Normal CD":
                out = [("p", stats.normal_cd(a[0], a[1], a[3], a[2]))]
            elif k == "Inverse Normal":
                out = [("x", stats.inv_normal(a[0], a[2], a[1]))]
            elif k == "Binomial PD":
                out = [("p", stats.binom_pd(n(a[0]), n(a[1]), a[2]))]
            elif k == "Binomial CD":
                out = [("p", stats.binom_cd(n(a[0]), n(a[1]), a[2]))]
            elif k == "Inverse Binomial":
                out = [("x", float(stats.inv_binom(a[0], n(a[1]), a[2])))]
            elif k == "Poisson PD":
                out = [("p", stats.poisson_pd(n(a[0]), a[1]))]
            elif k == "Poisson CD":
                out = [("p", stats.poisson_cd(n(a[0]), a[1]))]
            else:
                out = [("x", float(stats.inv_poisson(a[0], a[1])))]
            self.res.set_rows([(l, real_seq(v, self.settings())) for l, v in out], 26)
        except Exception as e:  # noqa: BLE001
            self.fail(e)
            self.res.clear()

    def on_enter(self):
        self.calculate()

    def to_json(self):
        return {"kind": self.kind.currentIndex(), "vals": [e.text() for e in self.edits]}

    def from_json(self, d):
        if d:
            self.kind.setCurrentIndex(d.get("kind", 0))
            for e, t in zip(self.edits, d.get("vals", [])):
                e.setText(t)


# ---------------------------------------------------------------------------
# Spreadsheet
# ---------------------------------------------------------------------------
class RawDelegate(QStyledItemDelegate):
    def __init__(self, page):
        super().__init__(page.tbl)
        self.page = page

    def setEditorData(self, editor, index):
        editor.setText(self.page.raw.get((index.column(), index.row()), ""))


_rng_re = re.compile(r"\$?([A-E])\$?(\d{1,2}):\$?([A-E])\$?(\d{1,2})")
_cell_re = re.compile(r"\$?([A-E])\$?(\d{1,2})(?![\d(])")


class SheetPage(Page):
    COLS, ROWS = 5, 45

    def __init__(self, interp, parent=None):
        super().__init__(interp, parent)
        self.raw = {}
        self._stack = []
        self._refreshing = False
        v = QVBoxLayout(self)
        v.setContentsMargins(8, 6, 8, 6)
        self.bar = QLineEdit()
        self.bar.setPlaceholderText("cell contents  ( = formulas: =A1+B1, =SUM(A1:A5), =MEAN(B1:B9) )")
        v.addWidget(self.bar)
        self.tbl = QTableWidget(self.ROWS, self.COLS)
        self.tbl.setHorizontalHeaderLabels(list("ABCDE"))
        self.tbl.setVerticalHeaderLabels([str(i + 1) for i in range(self.ROWS)])
        self.tbl.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.tbl.verticalHeader().setDefaultSectionSize(26)
        self.tbl.setItemDelegate(RawDelegate(self))
        v.addWidget(self.tbl, 1)
        v.addWidget(self.err)
        h = QHBoxLayout()
        self.clr = lcd_button("Clear sheet")
        h.addWidget(self.clr)
        h.addStretch(1)
        v.addLayout(h)
        self.tbl.itemChanged.connect(self._changed)
        self.tbl.currentCellChanged.connect(self._sel)
        self.bar.returnPressed.connect(self._bar_enter)
        self.clr.clicked.connect(self._clear)

    def _prep(self, expr):
        expr = _rng_re.sub(lambda m: f"rng({ord(m[1]) - 64},{int(m[2])},{ord(m[3]) - 64},{int(m[4])})", expr)
        return _cell_re.sub(lambda m: f"cell({ord(m[1]) - 64},{int(m[2])})", expr)

    def value(self, c, r):
        key = (c, r)
        raw = self.raw.get(key, "").strip()
        if not raw:
            return None
        if key in self._stack:
            raise MathErr("Circular reference")
        self._stack.append(key)
        try:
            self.ip.complex_mode = False
            self.ip.sheet_cb = self._hook
            if raw.startswith("="):
                return self.ip.evaluate(self._prep(raw[1:]), record=False, allow_assign=False)
            try:
                return self.ip.evaluate(raw, record=False, allow_assign=False)
            except (MathErr, SyntaxErr):
                return None
        finally:
            self._stack.pop()

    def _hook(self, name, args):
        if name == "cell":
            v = self.value(int(fl(args[0])) - 1, int(fl(args[1])) - 1)
            return ZERO if v is None else v
        c1, r1, c2, r2 = (int(fl(a)) for a in args)
        out = []
        for c in range(min(c1, c2) - 1, max(c1, c2)):
            for r in range(min(r1, r2) - 1, max(r1, r2)):
                v = self.value(c, r)
                if v is not None and is_real(v):
                    out.append(v)
        return out

    def _show(self):
        self._refreshing = True
        self.err.setText("")
        for (c, r), raw in list(self.raw.items()):
            it = self.tbl.item(r, c)
            if it is None:
                it = QTableWidgetItem()
                self.tbl.setItem(r, c, it)
            try:
                v = self.value(c, r)
                it.setText(raw if v is None else value_text(v, self.settings()))
            except Exception as e:  # noqa: BLE001
                it.setText("ERR")
                self.err.setText(f"{'ABCDE'[c]}{r + 1}: {friendly(e)}")
        self._refreshing = False

    def _changed(self, item):
        if self._refreshing:
            return
        txt = item.text()
        if txt.strip():
            self.raw[(item.column(), item.row())] = txt
        else:
            self.raw.pop((item.column(), item.row()), None)
        self._show()
        self.bar.setText(self.raw.get((item.column(), item.row()), ""))

    def _sel(self, r, c, *_):
        self.bar.setText(self.raw.get((c, r), ""))

    def _bar_enter(self):
        c, r = self.tbl.currentColumn(), self.tbl.currentRow()
        if c < 0:
            return
        t = self.bar.text()
        if t.strip():
            self.raw[(c, r)] = t
        else:
            self.raw.pop((c, r), None)
            it = self.tbl.item(r, c)
            if it:
                self._refreshing = True
                it.setText("")
                self._refreshing = False
        self._show()

    def _clear(self):
        self.raw = {}
        self._refreshing = True
        self.tbl.clearContents()
        self._refreshing = False
        self.bar.clear()

    def refresh(self):
        self._show()

    def on_enter(self):
        self._bar_enter()

    def to_json(self):
        return {f"{c},{r}": t for (c, r), t in self.raw.items()}

    def from_json(self, d):
        self.raw = {tuple(map(int, k.split(","))): v for k, v in (d or {}).items()}
        self._show()


# ---------------------------------------------------------------------------
# Table
# ---------------------------------------------------------------------------
class TablePage(Page):
    def __init__(self, interp, parent=None):
        super().__init__(interp, parent)
        v = QVBoxLayout(self)
        v.setContentsMargins(10, 6, 10, 6)
        v.setSpacing(4)
        self.fx = MathEditor(base_px=22, min_height=44, placeholder="f(x) =  (use the x key)")
        self.gx = MathEditor(base_px=22, min_height=44, placeholder="g(x) =  (optional)")
        for lab, ed in (("f(x)", self.fx), ("g(x)", self.gx)):
            row = QHBoxLayout()
            row.addWidget(lcd_label(lab, True))
            row.addWidget(ed, 1)
            v.addLayout(row)
            ed.executeRequested.connect(self.generate)
        self._last = self.fx
        self.fx.focusedIn.connect(lambda w: setattr(self, "_last", w))
        self.gx.focusedIn.connect(lambda w: setattr(self, "_last", w))
        row = QHBoxLayout()
        self.start, self.end, self.step = QLineEdit("1"), QLineEdit("5"), QLineEdit("1")
        for lab, w in (("Start", self.start), ("End", self.end), ("Step", self.step)):
            row.addWidget(lcd_label(lab))
            row.addWidget(w)
        self.go = lcd_button("Generate", True)
        row.addWidget(self.go)
        v.addLayout(row)
        v.addWidget(self.err)
        self.tbl = QTableWidget(0, 3)
        self.tbl.setHorizontalHeaderLabels(["x", "f(x)", "g(x)"])
        self.tbl.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.tbl.verticalHeader().setDefaultSectionSize(26)
        self.tbl.setEditTriggers(QAbstractItemView.NoEditTriggers)
        v.addWidget(self.tbl, 1)
        self.go.clicked.connect(self.generate)

    def active_editor(self):
        return self._last

    def default_focus(self):
        self.fx.setFocus()

    def generate(self):
        self.err.setText("")
        try:
            a, b, st = self.num(self.start.text()), self.num(self.end.text()), self.num(self.step.text())
            if fl(st) == 0 or (fl(b) - fl(a)) / fl(st) < 0:
                raise MathErr("Math ERROR (step)")
            n = int((fl(b) - fl(a)) / fl(st) + 1e-9) + 1
            if n > 45:
                raise MathErr("Too many rows (max 45)")
            funcs = [t for t in (self.fx.text(), self.gx.text())]
            if not funcs[0]:
                raise SyntaxErr("Syntax ERROR (enter f(x))")
            self.tbl.setRowCount(n)
            from ..core.values import add, mul
            s = self.settings()
            for i in range(n):
                x = add(a, mul(st, Fraction(i)))
                self.tbl.setItem(i, 0, QTableWidgetItem(value_text(x, s)))
                for j, f in enumerate(funcs):
                    if not f:
                        self.tbl.setItem(i, j + 1, QTableWidgetItem(""))
                        continue
                    self.ip.complex_mode = False
                    try:
                        y = self.ip.evaluate(f, record=False, env={"x": x}, allow_assign=False)
                        txt = value_text(y, s)
                    except (MathErr, SyntaxErr):
                        txt = "ERROR"
                    self.tbl.setItem(i, j + 1, QTableWidgetItem(txt))
        except Exception as e:  # noqa: BLE001
            self.fail(e)

    def on_enter(self):
        self.generate()

    def to_json(self):
        from ..core.mathtree import seq_to_json
        return {"f": seq_to_json(self.fx.seq()), "g": seq_to_json(self.gx.seq()),
                "r": [self.start.text(), self.end.text(), self.step.text()]}

    def from_json(self, d):
        if d:
            from ..core.mathtree import json_to_seq
            self.fx.load_seq(json_to_seq(d["f"]))
            self.gx.load_seq(json_to_seq(d["g"]))
            self.start.setText(d["r"][0])
            self.end.setText(d["r"][1])
            self.step.setText(d["r"][2])


# ---------------------------------------------------------------------------
# Equation
# ---------------------------------------------------------------------------
SUBSCRIPT = "₁₂₃₄₅₆"


class EquationPage(Page):
    KINDS = ["Simultaneous 2 unknowns", "Simultaneous 3 unknowns", "Simultaneous 4 unknowns",
             "Polynomial degree 2", "Polynomial degree 3", "Polynomial degree 4"]

    def __init__(self, interp, parent=None):
        super().__init__(interp, parent)
        v = QVBoxLayout(self)
        v.setContentsMargins(10, 6, 10, 6)
        self.kind = QComboBox()
        self.kind.addItems(self.KINDS)
        v.addWidget(self.kind)
        self.form = QGridLayout()
        v.addLayout(self.form)
        self.edits = []
        row = QHBoxLayout()
        self.go = lcd_button("Solve", True)
        row.addWidget(self.go)
        row.addStretch(1)
        v.addLayout(row)
        v.addWidget(self.err)
        self.res = ResultList()
        v.addWidget(self.res, 1)
        self.kind.currentIndexChanged.connect(self._rebuild)
        self.go.clicked.connect(self.solve)
        self._rebuild()

    def _rebuild(self):
        clear_layout(self.form)
        k = self.kind.currentIndex()
        self.edits = []
        if k < 3:
            n = k + 2
            names = "xyzw"
            for c in range(n + 1):
                head = "abcd"[c] if c < n else "="
                self.form.addWidget(lcd_label(head, True), 0, c, Qt.AlignHCenter)
            for r in range(n):
                row = []
                for c in range(n + 1):
                    e = QLineEdit("0")
                    e.setAlignment(Qt.AlignRight)
                    e.returnPressed.connect(self.solve)
                    self.form.addWidget(e, r + 1, c)
                    row.append(e)
                self.edits.append(row)
            hint = "a₁x + b₁y" + (" + c₁z" if n > 2 else "") + (" + d₁w" if n > 3 else "") + " = constant"
            self.form.addWidget(lcd_label(hint), n + 1, 0, 1, n + 1)
        else:
            deg = k - 1
            row = []
            for c in range(deg + 1):
                self.form.addWidget(lcd_label("abcde"[c], True), 0, c, Qt.AlignHCenter)
                e = QLineEdit("0")
                e.setAlignment(Qt.AlignRight)
                e.returnPressed.connect(self.solve)
                self.form.addWidget(e, 1, c)
                row.append(e)
            self.edits.append(row)
            terms = ["ax²+bx+c", "ax³+bx²+cx+d", "ax⁴+bx³+cx²+dx+e"][deg - 2]
            self.form.addWidget(lcd_label(terms + " = 0"), 2, 0, 1, deg + 1)
        self.res.clear()
        self.err.setText("")

    def solve(self):
        self.err.setText("")
        k = self.kind.currentIndex()
        s = self.settings()
        try:
            self.ip.complex_mode = True
            vals = [[self.num(e.text(), True) for e in row] for row in self.edits]
            if k < 3:
                sol = solvers.solve_linear(vals)
                rows = [("xyzw"[i], value_seq(x, s)) for i, x in enumerate(sol)]
            else:
                roots = solvers.solve_poly(vals[0])
                if len(roots) == 2 and roots[0] == roots[1]:
                    rows = [("x", value_seq(roots[0], s))]
                else:
                    rows = [(f"x{SUBSCRIPT[i]}", value_seq(r, s)) for i, r in enumerate(roots)]
            self.res.set_rows(rows, 24)
        except Exception as e:  # noqa: BLE001
            self.fail(e)
            self.res.clear()

    def on_enter(self):
        self.solve()

    def to_json(self):
        return {"k": self.kind.currentIndex(), "v": [[e.text() for e in r] for r in self.edits]}

    def from_json(self, d):
        if d:
            self.kind.setCurrentIndex(d.get("k", 0))
            for row, vals in zip(self.edits, d.get("v", [])):
                for e, t in zip(row, vals):
                    e.setText(t)


# ---------------------------------------------------------------------------
# Inequality
# ---------------------------------------------------------------------------
class InequalityPage(Page):
    def __init__(self, interp, parent=None):
        super().__init__(interp, parent)
        v = QVBoxLayout(self)
        v.setContentsMargins(10, 6, 10, 6)
        top = QHBoxLayout()
        self.deg = QComboBox()
        self.deg.addItems(["Degree 2", "Degree 3", "Degree 4"])
        self.op = QComboBox()
        self.op.addItems(["> 0", "< 0", "≥ 0", "≤ 0"])
        top.addWidget(self.deg)
        top.addWidget(self.op)
        v.addLayout(top)
        self.form = QGridLayout()
        v.addLayout(self.form)
        self.edits = []
        row = QHBoxLayout()
        self.go = lcd_button("Solve", True)
        row.addWidget(self.go)
        row.addStretch(1)
        v.addLayout(row)
        v.addWidget(self.err)
        self.res = ResultList()
        v.addWidget(self.res, 1)
        self.deg.currentIndexChanged.connect(self._rebuild)
        self.go.clicked.connect(self.solve)
        self._rebuild()

    def _rebuild(self):
        clear_layout(self.form)
        d = self.deg.currentIndex() + 2
        self.edits = []
        for c in range(d + 1):
            self.form.addWidget(lcd_label("abcde"[c], True), 0, c, Qt.AlignHCenter)
            e = QLineEdit("0")
            e.setAlignment(Qt.AlignRight)
            e.returnPressed.connect(self.solve)
            self.form.addWidget(e, 1, c)
            self.edits.append(e)
        self.res.clear()

    def solve(self):
        self.err.setText("")
        s = self.settings()
        try:
            coefs = [self.num(e.text()) for e in self.edits]
            op = ["<", ">"][0] if False else [">", "<", "≥", "≤"][self.op.currentIndex()]
            r = solvers.solve_inequality(coefs, op)
            if r == "ALL":
                rows = [("x", seq_from("All real numbers"))]
            elif r == "NONE":
                rows = [("x", seq_from("No solution"))]
            else:
                rows = []
                for i, (lo, li, hi, hi_in) in enumerate(r):
                    q = Seq()
                    if lo is None:
                        q.add(tok("x"))
                        q.add(tok("≤" if hi_in else "<"))
                        for it in real_seq(hi, s).items:
                            q.add(it)
                    elif hi is None:
                        q.add(tok("x"))
                        q.add(tok("≥" if li else ">"))
                        for it in real_seq(lo, s).items:
                            q.add(it)
                    elif lo is not None and hi is not None and fl(lo) == fl(hi):
                        q.add(tok("x"))
                        q.add(tok("="))
                        for it in real_seq(lo, s).items:
                            q.add(it)
                    else:
                        for it in real_seq(lo, s).items:
                            q.add(it)
                        q.add(tok("≤" if li else "<"))
                        q.add(tok("x"))
                        q.add(tok("≤" if hi_in else "<"))
                        for it in real_seq(hi, s).items:
                            q.add(it)
                    rows.append(("" if i == 0 else "or", q))
            self.res.set_rows(rows, 22)
        except Exception as e:  # noqa: BLE001
            self.fail(e)
            self.res.clear()

    def on_enter(self):
        self.solve()

    def to_json(self):
        return {"d": self.deg.currentIndex(), "op": self.op.currentIndex(), "v": [e.text() for e in self.edits]}

    def from_json(self, d):
        if d:
            self.deg.setCurrentIndex(d.get("d", 0))
            self.op.setCurrentIndex(d.get("op", 0))
            for e, t in zip(self.edits, d.get("v", [])):
                e.setText(t)


# ---------------------------------------------------------------------------
# Ratio
# ---------------------------------------------------------------------------
class RatioPage(Page):
    def __init__(self, interp, parent=None):
        super().__init__(interp, parent)
        v = QVBoxLayout(self)
        v.setContentsMargins(10, 6, 10, 6)
        self.kind = QComboBox()
        self.kind.addItems(["A : B = X : D", "A : B = C : X"])
        v.addWidget(self.kind)
        g = QGridLayout()
        self.a, self.b, self.c = QLineEdit("1"), QLineEdit("2"), QLineEdit("3")
        self.lab = [lcd_label("A", True), lcd_label("B", True), lcd_label("D", True)]
        for i, (l, e) in enumerate(zip(self.lab, (self.a, self.b, self.c))):
            g.addWidget(l, i, 0)
            g.addWidget(e, i, 1)
            e.returnPressed.connect(self.solve)
        v.addLayout(g)
        row = QHBoxLayout()
        self.go = lcd_button("Solve", True)
        row.addWidget(self.go)
        row.addStretch(1)
        v.addLayout(row)
        v.addWidget(self.err)
        self.res = ResultList()
        v.addWidget(self.res, 1)
        self.kind.currentIndexChanged.connect(self._lab)
        self.go.clicked.connect(self.solve)

    def _lab(self):
        self.lab[2].setText("D" if self.kind.currentIndex() == 0 else "C")
        self.res.clear()

    def solve(self):
        self.err.setText("")
        try:
            from ..core.values import div, mul
            a, b, c = self.num(self.a.text()), self.num(self.b.text()), self.num(self.c.text())
            x = div(mul(a, c), b) if self.kind.currentIndex() == 0 else div(mul(b, c), a)
            self.res.set_rows([("X", value_seq(x, self.settings()))], 28)
        except Exception as e:  # noqa: BLE001
            self.fail(e)
            self.res.clear()

    def on_enter(self):
        self.solve()

    def to_json(self):
        return {"k": self.kind.currentIndex(), "v": [self.a.text(), self.b.text(), self.c.text()]}

    def from_json(self, d):
        if d:
            self.kind.setCurrentIndex(d.get("k", 0))
            for e, t in zip((self.a, self.b, self.c), d.get("v", [])):
                e.setText(t)


# ---------------------------------------------------------------------------
# Math Box
# ---------------------------------------------------------------------------
FACES = "⚀⚁⚂⚃⚄⚅"


class MathBoxPage(Page):
    def __init__(self, interp, parent=None):
        super().__init__(interp, parent)
        v = QVBoxLayout(self)
        v.setContentsMargins(10, 6, 10, 6)
        self.kind = QComboBox()
        self.kind.addItems(["Dice roll", "Coin toss", "Random integers"])
        v.addWidget(self.kind)
        row = QHBoxLayout()
        self.n = QSpinBox()
        self.n.setRange(1, 1000)
        self.n.setValue(2)
        self.hi = QSpinBox()
        self.hi.setRange(1, 1000000)
        self.hi.setValue(100)
        self.nl = lcd_label("Dice:")
        self.hl = lcd_label("Max:")
        row.addWidget(self.nl)
        row.addWidget(self.n)
        row.addWidget(self.hl)
        row.addWidget(self.hi)
        self.go = lcd_button("Roll", True)
        row.addWidget(self.go)
        v.addLayout(row)
        self.big = QLabel("")
        self.big.setAlignment(Qt.AlignCenter)
        self.big.setStyleSheet(f"font-size:44px;color:{T.lcd_ink};")
        self.info = QLabel("")
        self.info.setAlignment(Qt.AlignCenter)
        self.info.setStyleSheet(f"font-size:15px;color:{T.lcd_status};")
        self.info.setWordWrap(True)
        self.tally = QLabel("")
        self.tally.setAlignment(Qt.AlignCenter)
        self.tally.setStyleSheet(f"font-size:12px;color:{T.lcd_status};")
        v.addStretch(1)
        v.addWidget(self.big)
        v.addWidget(self.info)
        v.addWidget(self.tally)
        v.addStretch(2)
        self.heads = self.tails = 0
        self.kind.currentIndexChanged.connect(self._mode)
        self.go.clicked.connect(self.roll)
        self._mode()

    def _mode(self):
        k = self.kind.currentIndex()
        self.nl.setText(["Dice:", "Tosses:", "Count:"][k])
        self.n.setRange(1, 6 if k == 0 else 1000)
        self.n.setValue(2 if k == 0 else 1 if k == 1 else 5)
        self.hl.setVisible(k == 2)
        self.hi.setVisible(k == 2)
        self.go.setText(["Roll", "Toss", "Generate"][k])
        self.big.setText("")
        self.info.setText("")
        self.tally.setText("")

    def roll(self):
        k = self.kind.currentIndex()
        n = self.n.value()
        if k == 0:
            d = [random.randint(1, 6) for _ in range(n)]
            self.big.setText(" ".join(FACES[x - 1] for x in d))
            self.info.setText(f"{' + '.join(map(str, d))} = {sum(d)}" if n > 1 else str(d[0]))
        elif k == 1:
            t = [random.random() < 0.5 for _ in range(n)]
            h = sum(t)
            self.heads += h
            self.tails += n - h
            self.big.setText("H" if n == 1 and t[0] else "T" if n == 1 else f"{h} : {n - h}")
            self.info.setText("Heads" if n == 1 and t[0] else "Tails" if n == 1 else f"Heads {h}   Tails {n - h}")
            self.tally.setText(f"Total so far — Heads {self.heads}, Tails {self.tails}")
        else:
            xs = [random.randint(1, self.hi.value()) for _ in range(n)]
            self.big.setText(str(xs[0]) if n == 1 else "")
            self.info.setText(", ".join(map(str, xs)))

    def on_enter(self):
        self.roll()
