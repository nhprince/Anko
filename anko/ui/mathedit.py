"""Qt widgets for the natural display: editable line, read-only view, and the result transcript."""
from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QGuiApplication, QPainter, QPen
from PySide6.QtWidgets import QMenu, QWidget, QSizePolicy

from ..core.editmodel import EditModel
from ..core.mathtree import Seq, clone, to_plain
from .mathlayout import DrawState, Fonts, layout
from .theme import T


def _pick(regions, pt):
    best = None
    for rect, seq, xs in regions:
        if rect.adjusted(-2, -6, 2, 6).contains(pt):
            if best is None or rect.width() * rect.height() < best[0].width() * best[0].height():
                best = (rect, seq, xs)
    if best is None and regions:
        # nearest top-level region in x
        best = max(regions, key=lambda r: r[0].width())
    return best


class MathEditor(QWidget):
    executeRequested = Signal()
    navigateHistory = Signal(int)
    changed = Signal()
    focusedIn = Signal(object)

    def __init__(self, parent=None, base_px=28, min_height=56, align_right=False, placeholder=""):
        super().__init__(parent)
        self.model = EditModel()
        self.fonts = Fonts(base_px)
        self._min_h = min_height
        self._pad = 10
        self._xoff = 0.0
        self._blink = True
        self._box = None
        self._regions = []
        self._align_right = align_right
        self.placeholder = placeholder
        self.setFocusPolicy(Qt.StrongFocus)
        self.setCursor(Qt.IBeamCursor)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self._timer = QTimer(self)
        self._timer.setInterval(530)
        self._timer.timeout.connect(self._tick)
        self._timer.start()
        self._refresh()

    # -- content API ------------------------------------------------------------------
    def text(self):
        return self.model.text()

    def plain(self):
        return self.model.plain()

    def is_empty(self):
        return self.model.is_empty()

    def clear(self):
        self.model.clear()
        self._changed()

    def load_seq(self, seq: Seq):
        self.model.load(seq)
        self._changed()

    def seq(self):
        return self.model.root

    def insert_seq(self, seq):
        self.model.insert_seq(seq)
        self._changed()

    def insert_tok(self, t):
        self.model.insert_tok(t)
        self._changed()

    def insert_text(self, t):
        self.model.insert_text(t)
        self._changed()

    def template(self, kind, wrap=False):
        self.model.template(kind, wrap)
        self._changed()

    def sup_with(self, text):
        self.model.template("sup")
        for ch in text:
            self.model.insert_tok("−" if ch == "-" else ch)
        self.model.move_right()
        self._changed()

    def root_with_index(self, idx):
        self.model.template("root")
        for ch in idx:
            self.model.insert_tok(ch)
        self.model.move_right()
        self._changed()

    def backspace(self):
        self.model.backspace()
        self._changed()

    def move(self, d):
        m = self.model
        if d == "left":
            m.move_left()
        elif d == "right":
            m.move_right()
        elif d in ("up", "down"):
            if not m.move_vertical(d == "up"):
                self.navigateHistory.emit(-1 if d == "up" else 1)
        elif d == "home":
            m.home()
        elif d == "end":
            m.end()
        self._blink = True
        self._refresh()

    def undo(self):
        if self.model.undo():
            self._changed()

    def redo(self):
        if self.model.redo():
            self._changed()

    def set_base_px(self, px):
        self.fonts = Fonts(px)
        self._refresh()

    # -- internals ---------------------------------------------------------------------------
    def _changed(self):
        self._blink = True
        self._refresh()
        self.changed.emit()

    def _tick(self):
        if self.hasFocus():
            self._blink = not self._blink
            self.update()

    def _refresh(self):
        self._box = layout(self.model.root, self.fonts, 0, True)
        h = int(max(self._min_h, self._box.h + 2 * self._pad + 4))
        if self.minimumHeight() != h:
            self.setMinimumHeight(h)
            self.updateGeometry()
        self.update()

    def sizeHint(self):
        return QSize(300, int(max(self._min_h, self._box.h + 2 * self._pad)))

    def focusInEvent(self, e):
        super().focusInEvent(e)
        self._blink = True
        self.focusedIn.emit(self)
        self.update()

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.TextAntialiasing)
        box = self._box
        x = self._pad - self._xoff
        if self._align_right and box.w < self.width() - 2 * self._pad:
            x = self.width() - self._pad - box.w
        y = (self.height() - box.h) / 2 + box.asc
        regions = []
        dc = DrawState(T.lcd_ink, T.lcd_dim, T.lcd_ink, cursor=self.model.cursor,
                       blink=self._blink and self.hasFocus(), regions=regions)
        if self.model.is_empty() and self.placeholder and not self.hasFocus():
            p.setPen(QColor(T.lcd_dim))
            p.setFont(self.fonts.get(1)[0])
            p.drawText(QPointF(self._pad, y), self.placeholder)
        box.draw(p, x, y, dc)
        self._regions = regions
        cr = dc.cursor_rect
        if cr is not None:
            w = self.width()
            if cr.right() > w - self._pad:
                self._xoff += cr.right() - (w - self._pad) + 12
                QTimer.singleShot(0, self.update)
            elif cr.left() < self._pad and self._xoff > 0:
                self._xoff = max(0.0, self._xoff - (self._pad - cr.left()) - 12)
                QTimer.singleShot(0, self.update)
        if box.w <= self.width() - 2 * self._pad and self._xoff:
            self._xoff = 0.0
            QTimer.singleShot(0, self.update)

    def mousePressEvent(self, e):
        self.setFocus()
        hit = _pick(self._regions, e.position())
        if hit:
            rect, seq, xs = hit
            px = e.position().x()
            pos = min(range(len(xs)), key=lambda i: abs(xs[i] - px))
            self.model.set_cursor(seq, pos)
            self._blink = True
            self.update()

    def keyPressEvent(self, e):
        key, mods, txt = e.key(), e.modifiers(), e.text()
        ctrl = bool(mods & Qt.ControlModifier)
        if ctrl:
            if key == Qt.Key_Z:
                return self.undo()
            if key == Qt.Key_Y:
                return self.redo()
            if key == Qt.Key_C:
                QGuiApplication.clipboard().setText(self.plain())
                return
            if key == Qt.Key_X:
                QGuiApplication.clipboard().setText(self.plain())
                return self.clear()
            if key == Qt.Key_V:
                return self.insert_text(QGuiApplication.clipboard().text().strip())
            if key == Qt.Key_A:
                return
        if key in (Qt.Key_Return, Qt.Key_Enter):
            return self.executeRequested.emit()
        if key == Qt.Key_Backspace:
            return self.backspace()
        if key == Qt.Key_Delete:
            self.model.delete_forward()
            return self._changed()
        if key == Qt.Key_Escape:
            return self.clear()
        for k, d in ((Qt.Key_Left, "left"), (Qt.Key_Right, "right"), (Qt.Key_Up, "up"), (Qt.Key_Down, "down"),
                     (Qt.Key_Home, "home"), (Qt.Key_End, "end")):
            if key == k:
                return self.move(d)
        if key == Qt.Key_Tab:
            return self.move("right")
        if txt and txt.isprintable() and not ctrl:
            if txt == "=":
                self.insert_tok("=")
            else:
                self.insert_text(txt)
            return
        super().keyPressEvent(e)


class MathView(QWidget):
    """read-only natural display of one Seq"""

    def __init__(self, parent=None, base_px=24, align="left", ink=None):
        super().__init__(parent)
        self.fonts = Fonts(base_px)
        self.align = align
        self.seq: Seq | None = None
        self._box = None
        self._ink = ink
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setMinimumHeight(int(base_px * 1.5))

    def set_seq(self, seq: Seq | None):
        self.seq = seq
        self._box = layout(seq, self.fonts, 0) if seq is not None and seq.items else None
        h = int(max(self.fonts.base * 1.5, (self._box.h + 14) if self._box else 0))
        self.setFixedHeight(h)
        self.update()

    def sizeHint(self):
        return QSize(200, self.height())

    def paintEvent(self, e):
        if not self._box:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.TextAntialiasing)
        b = self._box
        x = 8 if self.align == "left" else max(8, self.width() - 8 - b.w)
        y = (self.height() - b.h) / 2 + b.asc
        b.draw(p, x, y, DrawState(self._ink or T.lcd_ink, T.lcd_dim, T.lcd_ink, blink=False))


class TranscriptView(QWidget):
    """The scrolling list of  expression / result  pairs (the calculator's "screen")."""
    recallExpression = Signal(int)
    recallResult = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.entries = []   # dicts: expr(Seq), result(Seq|None), error(str|None)
        self.efonts = Fonts(22)
        self.rfonts = Fonts(27)
        self._layouts = []
        self._pad = 12
        self.setMinimumHeight(40)
        self.setMouseTracking(True)

    def set_fonts(self, e_px, r_px):
        self.efonts, self.rfonts = Fonts(e_px), Fonts(r_px)
        self.relayout()

    def set_entries(self, entries):
        self.entries = entries
        self.relayout()

    def relayout(self):
        self._layouts = []
        total, maxw = self._pad, 0
        for en in self.entries:
            eb = layout(en["expr"], self.efonts, 0) if en.get("expr") is not None and en["expr"].items else None
            rb = layout(en["result"], self.rfonts, 0) if en.get("result") is not None else None
            ey = total + (eb.h if eb else 0)
            eh = eb.h if eb else 0
            rh = rb.h if rb else self.rfonts.base * 1.2
            top_expr = total
            top_res = total + eh + 4
            total = top_res + rh + 14
            self._layouts.append((eb, rb, top_expr, top_res))
            maxw = max(maxw, (eb.w if eb else 0) + 2 * self._pad, (rb.w if rb else 0) + 2 * self._pad)
        self.setMinimumHeight(int(total + 4))
        self.setMinimumWidth(int(maxw))
        self.resize(max(self.width(), int(maxw)), int(total + 4))
        self.update()

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.TextAntialiasing)
        w = self.width()
        ink = QColor(T.lcd_ink)
        dim = QColor(T.lcd_ink)
        dim.setAlpha(170)
        for en, (eb, rb, ty, ry) in zip(self.entries, self._layouts):
            if ry + (rb.h if rb else 30) < e.rect().top() - 40 or ty > e.rect().bottom() + 40:
                continue
            if eb:
                eb.draw(p, self._pad, ty + eb.asc, DrawState(dim, T.lcd_dim, T.lcd_ink, blink=False))
            if en.get("error"):
                p.setFont(self.rfonts.get(0, 0.62)[0])
                p.setPen(QColor("#a12a1f"))
                p.drawText(QRectF(0, ry, w - self._pad, 30), Qt.AlignRight | Qt.AlignVCenter, en["error"])
            elif rb:
                rb.draw(p, w - self._pad - rb.w, ry + rb.asc, DrawState(ink, T.lcd_dim, T.lcd_ink, blink=False))
            sep = QColor(T.lcd_ink)
            sep.setAlpha(28)
            yy = ry + (rb.h if rb else 30) + 6
            p.setPen(QPen(sep, 1))
            p.drawLine(self._pad, int(yy), w - self._pad, int(yy))

    def contextMenuEvent(self, e):
        y = e.pos().y()
        for en, (eb, rb, ty, ry) in zip(self.entries, self._layouts):
            if ty - 6 <= y <= ry + (rb.h if rb else 30) + 8:
                m = QMenu(self)
                clip = QGuiApplication.clipboard()
                if en.get("result") is not None:
                    m.addAction("Copy result", lambda t=to_plain(en["result"]): clip.setText(t))
                if en.get("expr") is not None:
                    m.addAction("Copy expression", lambda t=to_plain(en["expr"]): clip.setText(t))
                m.exec(e.globalPos())
                return

    def mousePressEvent(self, e):
        if e.button() != Qt.LeftButton:
            return
        y = e.position().y()
        for i, (eb, rb, ty, ry) in enumerate(self._layouts):
            bottom = ry + (rb.h if rb else 30) + 8
            if ty - 6 <= y <= bottom:
                if y < ry - 2 and eb:
                    self.recallExpression.emit(i)
                else:
                    self.recallResult.emit(i)
                return
