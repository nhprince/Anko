"""Dialogs used by the main window."""
from __future__ import annotations

from fractions import Fraction

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import (QAbstractItemView, QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFormLayout, QGridLayout,
                               QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem, QPushButton, QSpinBox,
                               QTableWidget, QTableWidgetItem, QToolButton, QVBoxLayout, QWidget, QHeaderView)

from ..core.catalog import CATALOG, CONSTANTS
from ..core.interp import Settings
from ..core.values import Matrix, Vec, MathErr, SyntaxErr
from .theme import T

MODES = [
    ("calc", "Calculate", "±"), ("stat", "Statistics", "σ"), ("dist", "Distribution", "N"),
    ("sheet", "Spreadsheet", "▦"), ("table", "Table", "f(x)"), ("eq", "Equation", "x="),
    ("ineq", "Inequality", "≤"), ("cplx", "Complex", "i"), ("base", "Base-N", "0x"),
    ("mat", "Matrix", "[ ]"), ("vct", "Vector", "→"), ("ratio", "Ratio", "a:b"), ("box", "Math Box", "⚄"),
]


def _glyph_icon(glyph: str, size=44) -> QIcon:
    pm = QPixmap(size * 2, size * 2)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    p.setRenderHint(QPainter.TextAntialiasing)
    p.setBrush(QColor(T.accent))
    p.setPen(Qt.NoPen)
    p.drawRoundedRect(4, 4, size * 2 - 8, size * 2 - 8, 26, 26)
    f = QFont()
    f.setFamilies(["Cambria Math", "Segoe UI", "DejaVu Sans"])
    f.setPixelSize(int(size * (0.62 if len(glyph) < 3 else 0.46)))
    f.setBold(True)
    p.setFont(f)
    p.setPen(QColor(T.accent_text))
    p.drawText(pm.rect(), Qt.AlignCenter, glyph)
    p.end()
    return QIcon(pm)


class MenuDialog(QDialog):
    def __init__(self, parent=None, current="calc"):
        super().__init__(parent)
        self.setWindowTitle("Applications")
        self.choice = None
        g = QGridLayout(self)
        g.setSpacing(10)
        g.setContentsMargins(16, 16, 16, 16)
        for i, (mid, name, glyph) in enumerate(MODES):
            b = QToolButton()
            b.setIcon(_glyph_icon(glyph))
            b.setIconSize(QSize(44, 44))
            b.setText(name)
            b.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
            b.setMinimumSize(104, 92)
            b.setCursor(Qt.PointingHandCursor)
            border = T.accent if mid == current else T.border
            b.setStyleSheet(f"QToolButton {{ background:{T.panel}; border:1px solid {border}; border-radius:12px; padding:8px; }}"
                            f"QToolButton:hover {{ background:{T.panel2}; border:1px solid {T.accent}; }}")
            b.clicked.connect(lambda _=False, m=mid: self._pick(m))
            g.addWidget(b, i // 3, i % 3)

    def _pick(self, m):
        self.choice = m
        self.accept()


class SettingsDialog(QDialog):
    def __init__(self, s: Settings, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.s = Settings.from_json(s.to_json())
        f = QFormLayout()
        f.setContentsMargins(18, 18, 18, 8)
        f.setSpacing(10)
        self.angle = QComboBox()
        self.angle.addItems(["Degree", "Radian", "Gradian"])
        self.angle.setCurrentIndex(["DEG", "RAD", "GRA"].index(s.angle))
        self.notation = QComboBox()
        self.notation.addItems(["Norm 1", "Norm 2", "Fix", "Sci", "Eng"])
        self.notation.setCurrentIndex(["norm1", "norm2", "fix", "sci", "eng"].index(s.notation))
        self.digits = QSpinBox()
        self.digits.setRange(1, 15)
        self.digits.setValue(s.digits)
        self.digits.setToolTip("Significant digits (Norm, Sci, Eng) or decimal places (Fix, max 9)")
        self.style = QComboBox()
        self.style.addItems(["Math (exact fractions, √, π)", "Decimal only"])
        self.style.setCurrentIndex(0 if s.style == "math" else 1)
        self.cx = QComboBox()
        self.cx.addItems(["a + bi", "r∠θ"])
        self.cx.setCurrentIndex(0 if s.complex_fmt == "rect" else 1)
        self.mixed = QCheckBox("Show fractions as mixed numbers (2 1/3)")
        self.mixed.setChecked(s.mixed)
        self.thousands = QCheckBox("Digit grouping (1,234,567)")
        self.thousands.setChecked(s.thousands)
        self.theme = QComboBox()
        self.theme.addItems(["Dark", "Light"])
        self.theme.setCurrentIndex(0 if s.theme == "dark" else 1)
        for lab, w in (("Angle unit", self.angle), ("Number format", self.notation), ("Digits", self.digits),
                       ("Results", self.style), ("Complex format", self.cx), ("", self.mixed), ("", self.thousands),
                       ("Theme", self.theme)):
            f.addRow(lab, w)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        bb.button(QDialogButtonBox.Ok).setObjectName("primary")
        lay = QVBoxLayout(self)
        lay.addLayout(f)
        lay.addWidget(bb)
        self.setMinimumWidth(380)

    def result_settings(self) -> Settings:
        s = self.s
        s.angle = ["DEG", "RAD", "GRA"][self.angle.currentIndex()]
        s.notation = ["norm1", "norm2", "fix", "sci", "eng"][self.notation.currentIndex()]
        s.digits = self.digits.value() if s.notation != "fix" else min(self.digits.value(), 9)
        s.style = "math" if self.style.currentIndex() == 0 else "decimal"
        s.complex_fmt = "rect" if self.cx.currentIndex() == 0 else "polar"
        s.mixed = self.mixed.isChecked()
        s.thousands = self.thousands.isChecked()
        s.theme = "dark" if self.theme.currentIndex() == 0 else "light"
        return s


class CatalogWidget(QWidget):
    chosen = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search functions…")
        self.search.textChanged.connect(self._fill)
        self.list = QListWidget()
        self.list.itemActivated.connect(self._pick)
        self.list.itemClicked.connect(self._pick)
        lay.addWidget(self.search)
        lay.addWidget(self.list, 1)
        self._fill("")

    def _fill(self, q):
        q = q.strip().lower()
        self.list.clear()
        last = None
        for cat, label, desc, act in CATALOG:
            if q and q not in label.lower() and q not in desc.lower() and q not in cat.lower():
                continue
            if cat != last:
                h = QListWidgetItem(cat.upper())
                h.setFlags(Qt.NoItemFlags)
                f = h.font()
                f.setPointSize(8)
                f.setBold(True)
                h.setFont(f)
                h.setForeground(QColor(T.text3))
                self.list.addItem(h)
                last = cat
            it = QListWidgetItem(f"{label}    —    {desc}")
            it.setData(Qt.UserRole, act)
            self.list.addItem(it)

    def _pick(self, it):
        act = it.data(Qt.UserRole)
        if act:
            self.chosen.emit(act)


class CatalogDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Catalog")
        self.choice = None
        lay = QVBoxLayout(self)
        self.w = CatalogWidget()
        self.w.chosen.connect(self._done)
        lay.addWidget(self.w)
        self.resize(420, 560)
        self.w.search.setFocus()

    def _done(self, act):
        self.choice = act
        self.accept()


class ConstDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Scientific constants")
        self.choice = None
        lay = QVBoxLayout(self)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search constants…")
        self.search.textChanged.connect(self._fill)
        self.tbl = QTableWidget(0, 4)
        self.tbl.setHorizontalHeaderLabels(["Symbol", "Constant", "Value", "Unit"])
        self.tbl.verticalHeader().hide()
        self.tbl.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tbl.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.tbl.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.tbl.cellDoubleClicked.connect(self._pick)
        lay.addWidget(self.search)
        lay.addWidget(self.tbl, 1)
        hint = QLabel("Double-click a constant to insert its value.")
        hint.setObjectName("muted")
        lay.addWidget(hint)
        self._fill("")
        self.resize(640, 520)

    def _fill(self, q):
        q = q.strip().lower()
        rows = [c for c in CONSTANTS if not q or q in c[0].lower() or q in c[1].lower()]
        self._rows = rows
        self.tbl.setRowCount(len(rows))
        for i, (n, s, v, u) in enumerate(rows):
            for j, t in enumerate((s, n, v, u)):
                self.tbl.setItem(i, j, QTableWidgetItem(t))
        self.tbl.resizeColumnsToContents()
        self.tbl.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)

    def _pick(self, row, _col):
        self.choice = self._rows[row][2]
        self.accept()


class VarPromptDialog(QDialog):
    """Asks for the values of variables (CALC key)."""

    def __init__(self, names, defaults, parent=None, title="CALC"):
        super().__init__(parent)
        self.setWindowTitle(title)
        f = QFormLayout()
        f.setContentsMargins(18, 18, 18, 8)
        self.edits = {}
        for n in names:
            e = QLineEdit(defaults.get(n, "0"))
            f.addRow(f"{n} =", e)
            self.edits[n] = e
        if names:
            self.edits[names[0]].setFocus()
            self.edits[names[0]].selectAll()
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        bb.button(QDialogButtonBox.Ok).setObjectName("primary")
        lay = QVBoxLayout(self)
        lay.addLayout(f)
        lay.addWidget(bb)
        self.setMinimumWidth(320)

    def values(self):
        return {k: e.text().strip() or "0" for k, e in self.edits.items()}


class SolveDialog(QDialog):
    def __init__(self, names, parent=None):
        super().__init__(parent)
        self.setWindowTitle("SOLVE")
        f = QFormLayout()
        f.setContentsMargins(18, 18, 18, 8)
        self.var = QComboBox()
        self.var.addItems(names or ["x"])
        self.guess = QLineEdit("0")
        f.addRow("Solve for", self.var)
        f.addRow("Initial guess", self.guess)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        bb.button(QDialogButtonBox.Ok).setObjectName("primary")
        lay = QVBoxLayout(self)
        lay.addLayout(f)
        lay.addWidget(bb)
        self.setMinimumWidth(320)


class MatrixEditor(QDialog):
    """edit MatA..D / VctA..D"""

    def __init__(self, interp, vector=False, parent=None):
        super().__init__(parent)
        self.interp, self.vector = interp, vector
        self.setWindowTitle("Vector variables" if vector else "Matrix variables")
        self.setMinimumSize(460, 380)
        lay = QVBoxLayout(self)
        top = QHBoxLayout()
        self.which = QComboBox()
        self.which.addItems([("Vct" if vector else "Mat") + k for k in "ABCD"])
        self.rows = QSpinBox()
        self.cols = QSpinBox()
        self.rows.setRange(1, 4)
        self.cols.setRange(1, 4)
        if vector:
            self.rows.setRange(1, 1)
            self.rows.setValue(1)
            self.cols.setRange(2, 3)
            self.cols.setPrefix("dim ")
        else:
            self.rows.setPrefix("rows ")
            self.cols.setPrefix("cols ")
        top.addWidget(self.which)
        top.addWidget(self.rows)
        top.addWidget(self.cols)
        top.addStretch(1)
        lay.addLayout(top)
        self.tbl = QTableWidget()
        self.tbl.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.tbl.verticalHeader().setSectionResizeMode(QHeaderView.Stretch)
        lay.addWidget(self.tbl, 1)
        self.err = QLabel("")
        self.err.setStyleSheet(f"color:{T.bad}")
        lay.addWidget(self.err)
        hint = QLabel("Cells accept numbers and expressions such as 1/2 or sqrt(2).")
        hint.setObjectName("muted")
        lay.addWidget(hint)
        bb = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Close)
        bb.button(QDialogButtonBox.Save).setObjectName("primary")
        bb.button(QDialogButtonBox.Save).clicked.connect(self._save)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)
        self._loading = False
        self.which.currentIndexChanged.connect(self._load)
        self.rows.valueChanged.connect(self._resize)
        self.cols.valueChanged.connect(self._resize)
        self._load()

    def _store(self):
        return self.interp.vecs if self.vector else self.interp.mats

    def _load(self):
        k = "ABCD"[self.which.currentIndex()]
        cur = self._store()[k]
        self._loading = True
        if cur is None:
            r, c = (1, 3) if self.vector else (2, 2)
            data = [["0"] * c for _ in range(r)]
        elif self.vector:
            r, c, data = 1, len(cur.v), [[self._txt(x) for x in cur.v]]
        else:
            r, c = cur.shape
            data = [[self._txt(x) for x in row] for row in cur.rows]
        self.rows.setValue(r)
        self.cols.setValue(c)
        self.tbl.setRowCount(r)
        self.tbl.setColumnCount(c)
        for i in range(r):
            for j in range(c):
                self.tbl.setItem(i, j, QTableWidgetItem(data[i][j]))
        self._loading = False

    @staticmethod
    def _txt(x):
        if isinstance(x, Fraction):
            return str(x.numerator) if x.denominator == 1 else f"{x.numerator}/{x.denominator}"
        return str(float(x)) if not hasattr(x, "re") else "0"

    def _resize(self):
        if self._loading:
            return
        r, c = self.rows.value(), self.cols.value()
        self.tbl.setRowCount(r)
        self.tbl.setColumnCount(c)
        for i in range(r):
            for j in range(c):
                if self.tbl.item(i, j) is None:
                    self.tbl.setItem(i, j, QTableWidgetItem("0"))

    def _save(self):
        from ..core.interp import Interp
        k = "ABCD"[self.which.currentIndex()]
        r, c = self.tbl.rowCount(), self.tbl.columnCount()
        tmp = Interp(self.interp.s)
        try:
            vals = [[tmp.evaluate(self.tbl.item(i, j).text() or "0", record=False) for j in range(c)] for i in range(r)]
        except (MathErr, SyntaxErr) as e:
            self.err.setText(str(e))
            return
        self.err.setText("")
        self._store()[k] = Vec(vals[0]) if self.vector else Matrix(vals)
        self.err.setStyleSheet(f"color:{T.good}")
        self.err.setText(f"Saved {'Vct' if self.vector else 'Mat'}{k}")
