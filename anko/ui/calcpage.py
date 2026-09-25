"""The main calculation page. One class serves Calculate, Complex, Base-N, Matrix and Vector."""
from __future__ import annotations

from fractions import Fraction

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (QButtonGroup, QFrame, QHBoxLayout, QLabel, QPushButton, QScrollArea, QVBoxLayout, QWidget)

from ..core import basen, codec
from ..core.formatter import has_alt_form, value_seq
from ..core.interp import Interp, PairVal, Settings
from ..core.mathtree import clone, seq_from, seq_to_json, json_to_seq
from ..core.values import CNum, Matrix, MathErr, SyntaxErr, Vec
from .dialogs import MatrixEditor
from .mathedit import MathEditor, TranscriptView
from .theme import T


def friendly(e: Exception) -> str:
    if isinstance(e, (MathErr, SyntaxErr)):
        return str(e)
    if isinstance(e, RecursionError):
        return "Stack ERROR"
    if isinstance(e, (ZeroDivisionError, OverflowError, ValueError)):
        return "Math ERROR"
    return f"Error: {e}"


class CalcPage(QWidget):
    settingsChanged = Signal()

    def __init__(self, interp: Interp, variant="calc", parent=None):
        super().__init__(parent)
        self.ip = interp
        self.variant = variant
        self.base = 10
        self.entries: list[dict] = []
        self._hist_idx = None
        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)

        self.toolbar = QWidget()
        tb = QHBoxLayout(self.toolbar)
        tb.setContentsMargins(10, 4, 10, 0)
        tb.setSpacing(6)
        self._build_toolbar(tb)
        v.addWidget(self.toolbar)
        self.toolbar.setVisible(variant != "calc")

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)
        self.scroll.setStyleSheet("QScrollArea, QScrollArea > QWidget > QWidget { background: transparent; }")
        self.tv = TranscriptView()
        self.scroll.setWidget(self.tv)
        v.addWidget(self.scroll, 1)

        self.banner = QLabel("")
        self.banner.setStyleSheet("color:#a12a1f; font-weight:600; padding:2px 12px;")
        self.banner.setAlignment(Qt.AlignRight)
        self.banner.hide()
        v.addWidget(self.banner)
        self.base_panel = QLabel("")
        self.base_panel.setStyleSheet(f"color:{T.lcd_status}; padding:2px 12px; font-family:Consolas,'DejaVu Sans Mono',monospace; font-size:12px;")
        self.base_panel.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.base_panel.setVisible(variant == "base")
        v.addWidget(self.base_panel)

        line = QFrame()
        line.setFixedHeight(1)
        line.setStyleSheet(f"background: rgba(0,0,0,0.18);")
        v.addWidget(line)
        self.editor = MathEditor(base_px=30, min_height=64)
        v.addWidget(self.editor)
        self.editor.executeRequested.connect(self.execute)
        self.editor.changed.connect(self._on_edit)
        self.editor.navigateHistory.connect(self._navigate)
        self.tv.recallExpression.connect(self._recall_expr)
        self.tv.recallResult.connect(self._recall_result)

    # -- toolbar -------------------------------------------------------------------
    def _chip(self, text, checked=False):
        b = QPushButton(text)
        b.setCheckable(True)
        b.setChecked(checked)
        b.setFocusPolicy(Qt.NoFocus)
        b.setCursor(Qt.PointingHandCursor)
        b.setStyleSheet("QPushButton{padding:3px 10px;border-radius:10px;font-size:11px;background:rgba(0,0,0,0.10);"
                        "color:%s;border:none;} QPushButton:checked{background:%s;color:#e9eee3;}" % (T.lcd_ink, T.lcd_ink))
        return b

    def _build_toolbar(self, tb):
        if self.variant == "cplx":
            self.grp = QButtonGroup(self)
            for i, (txt, key) in enumerate((("a + bi", "rect"), ("r ∠ θ", "polar"))):
                b = self._chip(txt, self.ip.s.complex_fmt == key)
                self.grp.addButton(b, i)
                b.clicked.connect(lambda _=False, k=key: self._set_cx(k))
                tb.addWidget(b)
            hint = QLabel("i = imaginary unit · r∠θ input supported")
            hint.setStyleSheet(f"color:{T.lcd_status};font-size:11px;")
            tb.addWidget(hint)
        elif self.variant == "base":
            self.grp = QButtonGroup(self)
            for i, name in enumerate(basen.BASES):
                b = self._chip(name, name == "DEC")
                self.grp.addButton(b, i)
                b.clicked.connect(lambda _=False, n=name: self._set_base(n))
                tb.addWidget(b)
            hint = QLabel("32-bit · use ALPHA for A–F")
            hint.setStyleSheet(f"color:{T.lcd_status};font-size:11px;")
            tb.addWidget(hint)
        elif self.variant in ("mat", "vct"):
            vec = self.variant == "vct"
            b = QPushButton("Edit Vct A–D" if vec else "Edit Mat A–D")
            b.setStyleSheet("QPushButton{padding:3px 12px;border-radius:10px;font-size:11px;background:%s;color:#e9eee3;border:none;}" % T.lcd_ink)
            b.setFocusPolicy(Qt.NoFocus)
            b.clicked.connect(lambda: MatrixEditor(self.ip, vec, self).exec())
            tb.addWidget(b)
            hint = QLabel("use MatA…MatD, Det( Trn( Dot( Cross(  from CATALOG" if not vec else "use VctA…VctD, Dot( Cross( Angle(  from CATALOG")
            hint.setStyleSheet(f"color:{T.lcd_status};font-size:11px;")
            tb.addWidget(hint)
        tb.addStretch(1)

    def _set_cx(self, key):
        self.ip.s.complex_fmt = key
        self.refresh()
        self.settingsChanged.emit()

    def _set_base(self, name):
        self.base = basen.BASES[name]
        self.base_name = name
        self._update_base_panel(None)

    def _update_base_panel(self, iv):
        if iv is None:
            self.base_panel.setText("")
            return
        a = basen.all_bases(iv)
        self.base_panel.setText("   ".join(f"{k}: {v}" for k, v in a.items()))

    # -- editor helpers ---------------------------------------------------------------
    def active_editor(self):
        return self.editor

    def default_focus(self):
        self.editor.setFocus()

    def _on_edit(self):
        self.banner.hide()
        self._hist_idx = None

    def show_error(self, msg):
        self.banner.setText(msg)
        self.banner.show()

    # -- execution ----------------------------------------------------------------------
    def evaluate_editor(self):
        """returns (value, result_seq) for the editor content or raises"""
        text = self.editor.text()
        self.ip.complex_mode = self.variant == "cplx"
        if self.variant == "base":
            iv = basen.evaluate(text, self.base)
            self._update_base_panel(iv)
            return Fraction(iv), seq_from(basen.to_base(iv, self.base))
        v = self.ip.evaluate(text)
        return v, value_seq(v, self.ip.s)

    def execute(self):
        if self.editor.is_empty():
            return
        expr = clone(self.editor.seq())
        try:
            v, rseq = self.evaluate_editor()
        except Exception as e:  # noqa: BLE001 - shown to the user
            self.show_error(friendly(e))
            return
        self.add_entry(expr, v, rseq)
        self.editor.clear()
        self.banner.hide()

    def add_entry(self, expr, v, rseq, keep_editor=False):
        self.entries.append({"expr": expr, "value": v, "result": rseq, "decimal": False, "eng": False, "error": None})
        self.entries = self.entries[-200:]
        self._sync()
        self._hist_idx = None

    def _sync(self):
        self.tv.set_entries(self.entries)
        QTimer.singleShot(0, lambda: self.scroll.verticalScrollBar().setValue(self.scroll.verticalScrollBar().maximum()))

    def _render(self, en):
        v = en["value"]
        if self.variant == "base" and isinstance(v, Fraction):
            en["result"] = seq_from(basen.to_base(int(v), self.base))
            return
        s = self.ip.s
        if en.get("eng"):
            s = Settings.from_json(s.to_json())
            s.notation, s.digits = "eng", max(s.digits, 4)
            en["result"] = value_seq(v, s, decimal=True)
        else:
            en["result"] = value_seq(v, s, decimal=en.get("decimal", False))

    def refresh(self):
        for en in self.entries:
            if en.get("error") is None:
                self._render(en)
        self._sync()

    def toggle_decimal(self):
        if not self.entries:
            return
        en = self.entries[-1]
        if has_alt_form(en["value"], self.ip.s) or self.ip.s.style == "decimal":
            en["decimal"] = not en["decimal"]
            en["eng"] = False
            self._render(en)
            self._sync()

    def toggle_eng(self):
        if self.entries:
            en = self.entries[-1]
            en["eng"] = not en["eng"]
            self._render(en)
            self._sync()

    def clear_history(self):
        self.entries = []
        self._sync()

    # -- recall -----------------------------------------------------------------------------
    def _recall_expr(self, i):
        self.editor.insert_seq(self.entries[i]["expr"])
        self.editor.setFocus()

    def _recall_result(self, i):
        en = self.entries[i]
        v = en["value"]
        if isinstance(v, Matrix):
            self.editor.insert_tok("MatAns")
        elif isinstance(v, Vec):
            self.editor.insert_tok("VctAns")
        elif isinstance(v, bool) or self.variant == "base":
            self.editor.insert_text(en["result"] and "".join(n.text for n in en["result"].items if n.kind == "tok"))
        else:
            self.editor.insert_tok("(")
            self.editor.insert_seq(en["result"])
            self.editor.insert_tok(")")
        self.editor.setFocus()

    def _navigate(self, d):
        if not self.entries:
            return
        if self._hist_idx is None:
            if d > 0:
                return
            self._hist_idx = len(self.entries) - 1
        else:
            self._hist_idx += d
            if self._hist_idx >= len(self.entries):
                self._hist_idx = None
                self.editor.clear()
                return
            self._hist_idx = max(0, self._hist_idx)
        keep = self._hist_idx
        self.editor.load_seq(self.entries[keep]["expr"])
        self._hist_idx = keep

    # -- session -------------------------------------------------------------------------------
    def to_json(self):
        out = []
        for en in self.entries[-80:]:
            ev = codec.encode(en["value"])
            if ev is not None:
                out.append({"expr": seq_to_json(en["expr"]), "value": ev, "decimal": en["decimal"]})
        return out

    def from_json(self, data):
        self.entries = []
        for d in data or []:
            try:
                v = codec.decode(d["value"])
                if v is None:
                    continue
                en = {"expr": json_to_seq(d["expr"]), "value": v, "decimal": d.get("decimal", False), "eng": False, "error": None,
                      "result": None}
                self._render(en)
                self.entries.append(en)
            except Exception:  # noqa: BLE001
                continue
        self._sync()
