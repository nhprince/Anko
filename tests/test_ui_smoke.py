"""Fires every keypad action through the window (offscreen) and checks nothing raises."""
import os, sys, shutil
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import tempfile
os.environ["ANKO_DATA_DIR"] = os.path.join(tempfile.gettempdir(), "anko_test_home")  # isolates session.json, cross-platform
os.environ["HOME"] = "/tmp/anko_test_home"  # harmless leftover for posix; ANKO_DATA_DIR above is what actually isolates it
shutil.rmtree("/tmp/anko_test_home", ignore_errors=True)
from PySide6.QtWidgets import QApplication
from anko.ui.window import MainWindow
from anko.ui.keypad import ROWS_FN, ROWS_NUM, ROW_NAV

DIALOG_CMDS = {"cmd:catalog", "cmd:const", "cmd:menu", "cmd:settings", "cmd:rcl", "cmd:calc", "cmd:solve"}


def main():
    app = QApplication([])
    w = MainWindow()
    w.show()
    n = 0
    for mode in ("calc", "cplx", "base", "mat", "vct"):
        w.switch_mode(mode)
        for keys in [ROW_NAV] + ROWS_FN + ROWS_NUM:
            for k in keys:
                for act in (k.act, k.sact, k.aact):
                    if not act or act in DIALOG_CMDS or act in ("cmd:shift", "cmd:alpha"):
                        continue
                    w.on_action(act)
                    n += 1
                    if act in ("cmd:eq",):
                        w.pages[mode].editor.clear()
        w.pages[mode].editor.clear()
    print("actions fired:", n, "- OK")


if __name__ == "__main__":
    main()
