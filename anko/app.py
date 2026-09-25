"""Application bootstrap."""
from __future__ import annotations

import os
import sys


def resource_path(rel: str) -> str:
    """works from source and from a PyInstaller bundle"""
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    if hasattr(sys, "_MEIPASS"):
        return os.path.join(base, "anko", rel)
    return os.path.join(base, rel)


def run(argv=None) -> int:
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QFont, QIcon
    from PySide6.QtWidgets import QApplication

    argv = list(argv or sys.argv)
    selftest = "--selftest" in argv
    if selftest:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    app = QApplication(argv)
    app.setApplicationName("Anko")
    app.setOrganizationName("Anko")
    f = QFont()
    f.setFamilies(["Segoe UI", "Noto Sans", "DejaVu Sans"])
    f.setPointSize(10)
    app.setFont(f)
    icon = QIcon(resource_path(os.path.join("assets", "icon.png")))
    app.setWindowIcon(icon)
    from .ui.window import MainWindow
    w = MainWindow()
    w.setWindowIcon(icon)
    if selftest:
        pg = w.pages["calc"]
        pg.editor.insert_text("sqrt(8)+sin(30)")
        w.on_action("cmd:eq")
        from .core.formatter import value_text
        out = value_text(pg.entries[-1]["value"], w.ip.s)
        print("selftest:", out)
        return 0 if out == "2√2+1/2" or out.replace(" ", "") in ("(1+4√2)/2", "1/2+2√2") else 1
    w.show()
    return app.exec()
