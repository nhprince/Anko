"""Generates anko/assets/icon.png and icon.ico (run once:  python tools/make_icon.py)"""
import os, sys
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtGui import QColor, QFont, QGuiApplication, QImage, QLinearGradient, QPainter, QPen
from PySide6.QtCore import QRectF, Qt

app = QGuiApplication(sys.argv)
here = os.path.dirname(os.path.abspath(__file__))
out = os.path.join(here, "..", "anko", "assets")
os.makedirs(out, exist_ok=True)


def draw(size):
    img = QImage(size, size, QImage.Format_ARGB32)
    img.fill(Qt.transparent)
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)
    p.setRenderHint(QPainter.TextAntialiasing)
    r = QRectF(size * 0.04, size * 0.04, size * 0.92, size * 0.92)
    g = QLinearGradient(r.topLeft(), r.bottomRight())
    g.setColorAt(0, QColor("#2b2d33"))
    g.setColorAt(1, QColor("#111216"))
    p.setPen(Qt.NoPen)
    p.setBrush(g)
    p.drawRoundedRect(r, size * 0.22, size * 0.22)
    # LCD strip
    lcd = QRectF(size * 0.16, size * 0.16, size * 0.68, size * 0.26)
    lg = QLinearGradient(lcd.topLeft(), lcd.bottomLeft())
    lg.setColorAt(0, QColor("#e4e9dd"))
    lg.setColorAt(1, QColor("#cbd3c0"))
    p.setBrush(lg)
    p.drawRoundedRect(lcd, size * 0.05, size * 0.05)
    f = QFont("DejaVu Sans")
    f.setPixelSize(int(size * 0.2))
    f.setBold(True)
    p.setFont(f)
    p.setPen(QColor("#121512"))
    p.drawText(lcd, Qt.AlignCenter, "π√2")
    # keys
    key = QColor("#3b3e45")
    for i in range(3):
        for j in range(2):
            kr = QRectF(size * (0.16 + i * 0.235), size * (0.52 + j * 0.16), size * 0.2, size * 0.12)
            p.setPen(Qt.NoPen)
            if i == 2 and j == 1:
                p.setBrush(QColor("#f2a93b"))
            else:
                p.setBrush(key)
            p.drawRoundedRect(kr, size * 0.03, size * 0.03)
    p.end()
    return img


draw(256).save(os.path.join(out, "icon.png"))
ok = draw(256).save(os.path.join(out, "icon.ico"))
print("icon.png written; icon.ico:", "ok" if ok else "FAILED (create it with any PNG->ICO converter)")
