"""Main window: LCD, keypad, mode switching, key-action dispatch, session persistence."""
from __future__ import annotations

import json
import os
from fractions import Fraction
from pathlib import Path

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPen, QAction, QKeySequence, QShortcut
from PySide6.QtWidgets import (QApplication, QDialog, QFrame, QHBoxLayout, QLabel, QLineEdit, QMainWindow, QMenu,
                               QMessageBox, QPushButton, QSizePolicy, QStackedWidget, QTabWidget, QTableWidget,
                               QTableWidgetItem, QToolButton, QVBoxLayout, QWidget, QHeaderView, QAbstractItemView)

from ..core import codec
from ..core.formatter import value_seq, value_text, real_seq
from ..core.interp import Interp, Settings
from ..core.mathtree import clone, seq_from, tok
from ..core.values import MathErr, SyntaxErr, ZERO
from . import theme
from .calcpage import CalcPage, friendly
from .dialogs import CatalogDialog, CatalogWidget, ConstDialog, MODES, MenuDialog, SettingsDialog, SolveDialog, VarPromptDialog
from .keypad import Keypad
from .mathedit import MathEditor
from .pages import (DistPage, EquationPage, InequalityPage, MathBoxPage, RatioPage, SheetPage, StatPage, TablePage)
from .theme import T

APP_NAME = "Anko"
MODE_NAMES = {m[0]: m[1] for m in MODES}
KEYPAD_MODES = {"calc", "cplx", "base", "mat", "vct", "table"}
PREFIX_ANS = {"+", "×", "÷", "!", "%", "nPr", "nCr"}


def data_dir() -> Path:
    # ANKO_DATA_DIR overrides on every OS (used by the test suite to avoid touching a
    # real user's saved settings); without it, Windows uses APPDATA and everything
    # else uses ~/.config, as before.
    override = os.environ.get("ANKO_DATA_DIR")
    if override:
        d = Path(override) / APP_NAME
        d.mkdir(parents=True, exist_ok=True)
        return d
    base = os.environ.get("APPDATA") if os.name == "nt" else None
    root = Path(base) if base else Path.home() / ".config"
    d = root / APP_NAME
    d.mkdir(parents=True, exist_ok=True)
    return d


class StatusBar(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(24)
        self.state = dict(shift=False, alpha=False, mode="Calculate", angle="D", fmt="Norm1", style="Math", extra="")

    def set_state(self, **kw):
        self.state.update(kw)
        self.update()

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.TextAntialiasing)
        f = QFont()
        f.setFamilies(["Segoe UI", "Noto Sans", "DejaVu Sans"])
        f.setPixelSize(11)
        f.setBold(True)
        p.setFont(f)
        fm = p.fontMetrics()
        ink, dim = QColor(T.lcd_ink), QColor(T.lcd_status)
        x = 12
        for label, on in (("S", self.state["shift"]), ("A", self.state["alpha"])):
            w = fm.horizontalAdvance(label) + 12
            r = QRectF(x, 4, w, 16)
            if on:
                p.setBrush(ink)
                p.setPen(Qt.NoPen)
                p.drawRoundedRect(r, 4, 4)
                p.setPen(QColor("#e7ede0"))
            else:
                p.setPen(QColor(dim.red(), dim.green(), dim.blue(), 90))
            p.drawText(r, Qt.AlignCenter, label)
            x += w + 5
        p.setPen(dim)
        p.drawText(QRectF(0, 0, self.width(), self.height()), Qt.AlignCenter, self.state["mode"].upper())
        right = "  ".join(t for t in (self.state["extra"], self.state["style"], self.state["fmt"], self.state["angle"]) if t)
        p.drawText(QRectF(0, 0, self.width() - 12, self.height()), Qt.AlignRight | Qt.AlignVCenter, right)


class LcdFrame(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.status = StatusBar()
        self.stack = QStackedWidget()
        v = QVBoxLayout(self)
        v.setContentsMargins(10, 8, 10, 8)
        v.setSpacing(0)
        v.addWidget(self.status)
        v.addWidget(self.stack, 1)

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect()).adjusted(2, 2, -2, -2)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(T.bezel))
        p.drawRoundedRect(r, 16, 16)
        inner = r.adjusted(5, 5, -5, -5)
        g = QLinearGradient(inner.topLeft(), inner.bottomLeft())
        g.setColorAt(0, QColor(T.lcd_top))
        g.setColorAt(1, QColor(T.lcd_bot))
        p.setBrush(g)
        p.setPen(QPen(QColor(0, 0, 0, 90), 1))
        p.drawRoundedRect(inner, 11, 11)
        # subtle inner shadow at the top edge
        sh = QLinearGradient(inner.topLeft(), QPointF(inner.left(), inner.top() + 22))
        sh.setColorAt(0, QColor(0, 0, 0, 38))
        sh.setColorAt(1, QColor(0, 0, 0, 0))
        p.setPen(Qt.NoPen)
        p.setBrush(sh)
        p.drawRoundedRect(inner.adjusted(1, 1, -1, -1), 10, 10)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Anko — Scientific Calculator")
        self.ip = Interp(Settings())
        self.mode = "calc"
        self.pages = {}
        self.kp_pref = {}
        self._load_session_data()
        theme.set_theme(self.ip.s.theme)
        QApplication.instance().setStyleSheet(theme.qss())
        self._build()
        self._restore_pages()
        self.switch_mode(self._saved.get("mode", "calc"))
        self.resize(*self._saved.get("size", (560, 900)))
        self.setMinimumSize(470, 540)

    # ------------------------------------------------------------------ build
    def _build(self):
        central = QWidget()
        central.setObjectName("central")
        central.setStyleSheet(f"#central {{ background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 {T.bg2}, stop:1 {T.bg}); }}")
        self.setCentralWidget(central)   # replaces (and deletes) any previous central widget
        central.show()
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        col = QWidget()
        col.setMinimumWidth(470)
        cv = QVBoxLayout(col)
        cv.setContentsMargins(12, 8, 12, 4)
        cv.setSpacing(6)
        hdr = QHBoxLayout()
        title = QLabel("ANKO")
        title.setStyleSheet(f"color:{T.text2};font-weight:700;letter-spacing:3px;font-size:11px;")
        hdr.addWidget(title)
        hdr.addStretch(1)
        self.kp_btn = self._hdr_btn("Keypad", self.toggle_keypad)
        self.mode_btn = self._hdr_btn("▦  Apps", self.open_menu)
        self.panel_btn = self._hdr_btn("Panel", self.toggle_panel)
        self.set_btn = self._hdr_btn("Settings", self.open_settings)
        for b in (self.kp_btn, self.mode_btn, self.panel_btn, self.set_btn):
            hdr.addWidget(b)
        cv.addLayout(hdr)

        self.lcd = LcdFrame()
        self.lcd.setMinimumHeight(250)
        cv.addWidget(self.lcd, 5)
        self.keypad = Keypad()
        self.keypad.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        cv.addWidget(self.keypad, 7)
        self.keypad.action.connect(self.on_action)
        self.keypad.layerChanged.connect(lambda s, a: self.refresh_status())
        root.addWidget(col, 1)

        self.panel = QTabWidget()
        self.panel.setFixedWidth(330)
        self._build_panel()
        root.addWidget(self.panel)
        self.panel.hide()

        self.pages = {
            "calc": CalcPage(self.ip, "calc"), "cplx": CalcPage(self.ip, "cplx"), "base": CalcPage(self.ip, "base"),
            "mat": CalcPage(self.ip, "mat"), "vct": CalcPage(self.ip, "vct"),
            "stat": StatPage(self.ip), "dist": DistPage(self.ip), "sheet": SheetPage(self.ip), "table": TablePage(self.ip),
            "eq": EquationPage(self.ip), "ineq": InequalityPage(self.ip), "ratio": RatioPage(self.ip), "box": MathBoxPage(self.ip),
        }
        for pg in self.pages.values():
            self.lcd.stack.addWidget(pg)
            if isinstance(pg, CalcPage):
                pg.settingsChanged.connect(self.refresh_status)

        QShortcut(QKeySequence("Ctrl+M"), self, activated=self.open_menu)
        QShortcut(QKeySequence("Ctrl+,"), self, activated=self.open_settings)
        QShortcut(QKeySequence("F1"), self, activated=self.show_help)
        self.var_timer = QTimer(self)
        self.var_timer.setInterval(600)
        self.var_timer.timeout.connect(self.refresh_vars)
        self.var_timer.start()

    def _hdr_btn(self, text, slot):
        b = QToolButton()
        b.setText(text)
        b.setFocusPolicy(Qt.NoFocus)
        b.setCursor(Qt.PointingHandCursor)
        b.setStyleSheet(f"QToolButton{{color:{T.text2};background:transparent;border:1px solid {T.border};border-radius:7px;padding:3px 10px;font-size:11px;}}"
                        f"QToolButton:hover{{color:{T.text};border:1px solid {T.border_strong};}}")
        b.clicked.connect(slot)
        return b

    def _build_panel(self):
        self.vars_tbl = QTableWidget(0, 2)
        self.vars_tbl.setHorizontalHeaderLabels(["Variable", "Value"])
        self.vars_tbl.verticalHeader().hide()
        self.vars_tbl.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.vars_tbl.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.vars_tbl.cellDoubleClicked.connect(self._var_dbl)
        self.panel.addTab(self.vars_tbl, "Variables")
        self.cat = CatalogWidget()
        self.cat.chosen.connect(self.on_action)
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(6, 6, 6, 6)
        lay.addWidget(self.cat)
        self.panel.addTab(w, "Catalog")

    def toggle_keypad(self):
        self.kp_pref[self.mode] = not self.keypad.isVisible()
        self._apply_kp()

    def _apply_kp(self):
        self.keypad.setVisible(self.kp_pref.get(self.mode, self.mode in KEYPAD_MODES))

    def toggle_panel(self):
        vis = not self.panel.isVisible()
        self.panel.setVisible(vis)
        if vis:
            self.resize(self.width() + 340, self.height())
            self.refresh_vars()
        else:
            self.resize(max(self.minimumWidth(), self.width() - 340), self.height())

    def refresh_vars(self):
        if not self.panel.isVisible():
            return
        s = self.ip.s
        rows = [("Ans", self.ip.ans), ("PreAns", self.ip.preans)] + list(self.ip.vars.items())
        rows += [(f"Mat{k}", v) for k, v in self.ip.mats.items() if v is not None]
        rows += [(f"Vct{k}", v) for k, v in self.ip.vecs.items() if v is not None]
        self.vars_tbl.setRowCount(len(rows))
        for i, (n, v) in enumerate(rows):
            self.vars_tbl.setItem(i, 0, QTableWidgetItem(n))
            try:
                self.vars_tbl.setItem(i, 1, QTableWidgetItem(value_text(v, s)))
            except Exception:  # noqa: BLE001
                self.vars_tbl.setItem(i, 1, QTableWidgetItem("?"))

    def _var_dbl(self, row, col):
        n = self.vars_tbl.item(row, 0).text()
        self.on_action("t:" + n)

    # ------------------------------------------------------------------ helpers
    @property
    def page(self):
        return self.pages[self.mode]

    def current_editor(self):
        fw = QApplication.focusWidget()
        if isinstance(fw, MathEditor):
            return fw
        if isinstance(fw, QLineEdit):
            return None
        return self.page.active_editor()

    def refresh_status(self):
        s = self.ip.s
        fmt = {"norm1": "Norm1", "norm2": "Norm2", "fix": f"Fix{s.digits}", "sci": f"Sci{s.digits}", "eng": "Eng"}[s.notation]
        extra = ""
        if self.mode == "cplx":
            extra = "r∠θ" if s.complex_fmt == "polar" else "a+bi"
        self.lcd.status.set_state(shift=self.keypad.shift, alpha=self.keypad.alpha, mode=MODE_NAMES[self.mode],
                                  angle={"DEG": "D", "RAD": "R", "GRA": "G"}[s.angle], fmt=fmt,
                                  style="Math" if s.style == "math" else "Dec", extra=extra)
        self.setWindowTitle(f"Anko — {MODE_NAMES[self.mode]}")

    def switch_mode(self, mode):
        if mode not in self.pages:
            mode = "calc"
        self.mode = mode
        self.lcd.stack.setCurrentWidget(self.pages[mode])
        self.ip.complex_mode = mode == "cplx"
        self._apply_kp()
        self.refresh_status()
        self.pages[mode].refresh()
        QTimer.singleShot(0, self.pages[mode].default_focus)

    def apply_settings(self, s: Settings):
        old_theme = self.ip.s.theme
        self.ip.s.__dict__.update(s.__dict__)
        if old_theme != s.theme:
            self._retheme()
        for pg in self.pages.values():
            pg.refresh()
        self.refresh_status()

    def _retheme(self):
        """rebuild the whole UI in the new theme, keeping data"""
        state = self._collect_state()
        theme.set_theme(self.ip.s.theme)
        QApplication.instance().setStyleSheet(theme.qss())
        geo = self.geometry()
        panel_vis = self.panel.isVisible()
        self._saved = state
        self._build()
        self._restore_pages()
        self.switch_mode(self.mode)
        if panel_vis:
            self.panel.show()

    # ------------------------------------------------------------------ dialogs
    def open_menu(self):
        d = MenuDialog(self, self.mode)
        if d.exec() and d.choice:
            self.switch_mode(d.choice)

    def open_settings(self):
        d = SettingsDialog(self.ip.s, self)
        if d.exec():
            self.apply_settings(d.result_settings())

    def show_help(self):
        QMessageBox.information(self, "Anko — quick help", (
            "<b>Keyboard</b><br>Type numbers and operators directly. <b>/</b> makes a fraction from what you just typed, "
            "<b>^</b> starts an exponent, <b>sqrt(</b> starts a root. Arrow keys move through fractions and roots "
            "(→ leaves the current box). <b>Enter</b> = , <b>Esc</b> clears, <b>Ctrl+Z / Ctrl+Y</b> undo / redo.<br><br>"
            "<b>Keypad</b><br>SHIFT (gold labels) and ALPHA (red labels) apply to the next key only. "
            "▲ at the start of the line replays earlier expressions. Click an old expression or result to reuse it.<br><br>"
            "<b>CALC</b> evaluates the expression for chosen variable values, <b>SOLVE</b> solves an equation "
            "(use the = key: SHIFT + x). <b>S⇔D</b> toggles exact/decimal.<br><br>"
            "<b>Shortcuts</b><br>Ctrl+M apps menu · Ctrl+, settings · F1 this help."))

    # ------------------------------------------------------------------ actions
    def on_action(self, act: str):
        kind, _, arg = act.partition(":")
        ed = self.current_editor()
        pg = self.page
        if kind == "cmd":
            return self._cmd(arg, ed, pg)
        if ed is None:
            return self._line_insert(kind, arg, pg)
        is_calc = isinstance(pg, CalcPage)
        if is_calc and ed is pg.editor and ed.is_empty() and (
                (kind == "t" and arg in PREFIX_ANS) or (kind == "sup" and pg.variant != "base")):
            ed.insert_tok("Ans")
        if kind == "t":
            ed.insert_tok(arg)
        elif kind == "f":
            ed.insert_tok(arg)
        elif kind == "tpl":
            if arg == "cbrt":
                ed.root_with_index("3")
            else:
                ed.template(arg)
        elif kind == "sup":
            ed.sup_with(arg)
        ed.setFocus()
        self.pages[self.mode].banner.hide() if is_calc else None

    def _line_insert(self, kind, arg, pg):
        le = QApplication.focusWidget()
        if not isinstance(le, QLineEdit):
            return
        mp = {"×": "*", "÷": "/", "−": "-", "ᴇ": "E", "π": "pi", "′": "'", "″": '"'}
        if kind == "t":
            le.insert(mp.get(arg, arg))
        elif kind == "f":
            le.insert(arg)
        elif kind == "tpl":
            le.insert({"frac": "/", "sqrt": "sqrt(", "cbrt": "cbrt(", "sup": "^", "root": "root(", "abs": "abs("}.get(arg, ""))
        elif kind == "sup":
            le.insert(f"^({arg})")

    def _cmd(self, c, ed, pg):
        calc = isinstance(pg, CalcPage)
        le = QApplication.focusWidget() if isinstance(QApplication.focusWidget(), QLineEdit) else None
        if c in ("left", "right", "up", "down"):
            if ed is not None:
                ed.move(c)
            elif le is not None and c in ("left", "right"):
                le.cursorBackward(False) if c == "left" else le.cursorForward(False)
        elif c == "del":
            if ed is not None:
                ed.backspace()
            elif le is not None:
                le.backspace()
        elif c == "ac":
            if ed is not None:
                ed.clear()
                if calc:
                    pg.banner.hide()
            elif le is not None:
                le.clear()
        elif c == "undo" and ed is not None:
            ed.undo()
        elif c == "redo" and ed is not None:
            ed.redo()
        elif c == "eq":
            pg.execute() if calc else pg.on_enter()
        elif c == "menu":
            self.open_menu()
        elif c == "settings":
            self.open_settings()
        elif c == "catalog":
            d = CatalogDialog(self)
            if d.exec() and d.choice:
                self.on_action(d.choice)
        elif c == "const":
            d = ConstDialog(self)
            if d.exec() and d.choice:
                self._insert_literal(d.choice, ed)
        elif c == "minus":
            if calc and ed is pg.editor and ed.is_empty() and pg.variant != "base":
                ed.insert_tok("Ans")
            (ed.insert_tok("−") if ed is not None else self._line_insert("t", "−", pg))
        elif c in ("tenx", "ex", "times10") and ed is not None:
            if c == "times10":
                if calc and ed.is_empty():
                    ed.insert_tok("Ans")
                ed.insert_tok("×")
            base = {"tenx": "10", "ex": "e", "times10": "10"}[c]
            for ch in base:
                ed.insert_tok(ch)
            ed.template("sup")
        elif c == "dmsmark" and ed is not None:
            ed.insert_tok(self._next_dms_mark(ed))
        elif c == "rcl":
            self._rcl_menu(ed)
        elif c in ("mplus", "mminus") and calc:
            self._memory(pg, c == "mplus")
        elif calc and c == "sd":
            pg.toggle_decimal()
        elif calc and c == "eng":
            pg.toggle_eng()
        elif calc and c == "clear_history":
            pg.clear_history()
        elif calc and c == "calc":
            self._do_calc(pg)
        elif calc and c == "solve":
            self._do_solve(pg)
        if ed is not None:
            ed.setFocus()

    @staticmethod
    def _next_dms_mark(ed):
        items = ed.model.seq.items[:ed.model.pos]
        run = []
        for n in reversed(items):
            if n.kind == "tok" and (n.text.isdigit() or n.text in ".°′″"):
                run.append(n.text)
            else:
                break
        if "°" not in run:
            return "°"
        if "′" not in run:
            return "′"
        return "″"

    def _insert_literal(self, s, ed):
        if ed is None:
            le = QApplication.focusWidget()
            if isinstance(le, QLineEdit):
                le.insert(s)
            return
        m, _, e = s.upper().partition("E")
        ed.insert_text(m)
        if e:
            ed.insert_tok("×")
            ed.insert_tok("1")
            ed.insert_tok("0")
            ed.sup_with(e)

    def _rcl_menu(self, ed):
        m = QMenu(self)
        s = self.ip.s
        for n, v in [("Ans", self.ip.ans)] + list(self.ip.vars.items()):
            try:
                txt = value_text(v, s)
            except Exception:  # noqa: BLE001
                txt = "?"
            a = m.addAction(f"{n}    =    {txt}")
            a.triggered.connect(lambda _=False, name=n: self.on_action("t:" + name))
        m.exec(self.cursor().pos())

    def _memory(self, pg, plus):
        from ..core.values import add, sub
        if not pg.editor.is_empty():
            pg.execute()
        if pg.variant == "base":
            return
        v = self.ip.ans
        self.ip.vars["M"] = add(self.ip.vars["M"], v) if plus else sub(self.ip.vars["M"], v)

    # --- CALC / SOLVE -----------------------------------------------------------------------------
    def _do_calc(self, pg):
        text = pg.editor.text()
        if not text:
            return
        try:
            names = [n for n in self.ip.needed_vars(text) if n != "theta"]
            if not names:
                return pg.execute()
            defaults = {n: (value_text(self.ip.vars[n], self.ip.s) if n in self.ip.vars else "0") for n in names}
            d = VarPromptDialog(names, defaults, self, "CALC")
            if not d.exec():
                return
            vals = {}
            for k, t in d.values().items():
                vals[k] = self.ip.evaluate(t, record=False, allow_assign=False)
                if k in self.ip.vars:
                    self.ip.vars[k] = vals[k]
            self.ip.complex_mode = pg.variant == "cplx"
            v = self.ip.calc_with(text, vals)
            self.ip.record(v)
            pg.add_entry(clone(pg.editor.seq()), v, value_seq(v, self.ip.s))
            pg.banner.hide()
        except Exception as e:  # noqa: BLE001
            pg.show_error(friendly(e))

    def _do_solve(self, pg):
        text = pg.editor.text()
        if not text:
            return
        try:
            names = [n for n in self.ip.needed_vars(text) if n != "theta"] or ["x"]
            d = SolveDialog(names, self)
            if not d.exec():
                return
            var = d.var.currentText()
            guess = float(self.ip.evaluate(d.guess.text() or "0", record=False).__float__())
            self.ip.complex_mode = False
            root, resid = self.ip.solve(text, var, guess)
            if var in self.ip.vars:
                self.ip.vars[var] = root
            rseq = seq_from(var, "=")
            for it in real_seq(root, self.ip.s).items:
                rseq.add(it)
            rseq.add(tok("   L−R="))
            for it in real_seq(0.0 if abs(resid) < 1e-9 else resid, self.ip.s, decimal=True).items:
                rseq.add(it)
            pg.add_entry(clone(pg.editor.seq()), root, rseq)
            pg.entries[-1]["result"] = rseq
            pg.banner.hide()
        except Exception as e:  # noqa: BLE001
            pg.show_error(friendly(e))

    # ------------------------------------------------------------------ persistence
    def _collect_state(self):
        st = {"settings": self.ip.s.to_json(), "mode": self.mode, "size": (self.width(), self.height()),
              "vars": {k: codec.encode(v) for k, v in self.ip.vars.items()},
              "ans": codec.encode(self.ip.ans), "preans": codec.encode(self.ip.preans),
              "mats": {k: codec.encode(v) for k, v in self.ip.mats.items() if v is not None},
              "vecs": {k: codec.encode(v) for k, v in self.ip.vecs.items() if v is not None},
              "pages": {}}
        for k, pg in self.pages.items():
            try:
                st["pages"][k] = pg.to_json()
            except Exception:  # noqa: BLE001
                pass
        return st

    def _load_session_data(self):
        self._saved = {}
        f = data_dir() / "session.json"
        try:
            self._saved = json.loads(f.read_text(encoding="utf-8"))
            self.ip.s = Settings.from_json(self._saved.get("settings"))
            for k, v in (self._saved.get("vars") or {}).items():
                if k in self.ip.vars and (dv := codec.decode(v)) is not None:
                    self.ip.vars[k] = dv
            self.ip.ans = codec.decode(self._saved.get("ans")) or ZERO
            self.ip.preans = codec.decode(self._saved.get("preans")) or ZERO
            for k, v in (self._saved.get("mats") or {}).items():
                self.ip.mats[k] = codec.decode(v)
            for k, v in (self._saved.get("vecs") or {}).items():
                self.ip.vecs[k] = codec.decode(v)
        except Exception:  # noqa: BLE001 - a broken session file must never stop the app
            self._saved = {}

    def _restore_pages(self):
        for k, d in (self._saved.get("pages") or {}).items():
            if k in self.pages and d is not None:
                try:
                    self.pages[k].from_json(d)
                except Exception:  # noqa: BLE001
                    pass

    def closeEvent(self, e):
        try:
            (data_dir() / "session.json").write_text(json.dumps(self._collect_state()), encoding="utf-8")
        except Exception:  # noqa: BLE001
            pass
        super().closeEvent(e)
