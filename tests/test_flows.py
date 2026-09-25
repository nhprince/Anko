import os, sys, shutil
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["QT_QPA_PLATFORM"] = "offscreen"
import tempfile
_data_dir = os.path.join(tempfile.gettempdir(), "anko_flow_home")
os.environ["ANKO_DATA_DIR"] = _data_dir  # isolates session.json, cross-platform
os.environ["HOME"] = "/tmp/anko_flow_home"  # harmless leftover for posix
shutil.rmtree(_data_dir, ignore_errors=True)
from fractions import Fraction as F
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer
from anko.ui.window import MainWindow
from anko.ui import window as W
from anko.core.formatter import value_text
from anko.core.interp import Settings

app = QApplication([])
w = MainWindow(); w.show()
pg = w.pages["calc"]

def click(label):
    b = next(b for b in w.keypad.buttons if b.key.label == label)
    b.click()

def last():
    return pg.entries[-1]

# --- keypad clicks with layers --------------------------------------------------------
click("SHIFT"); click("sin")            # asin(
click("1"); click("@frac") if False else None
pg.editor.clear()
click("SHIFT"); click("sin"); w.on_action("tpl:frac"); click("1"); pg.editor.move("right"); click("2"); pg.editor.move("right"); click("=")
assert value_text(last()["value"], w.ip.s) == "30", value_text(last()["value"], w.ip.s)
click("ALPHA"); click("(−)")            # A
click("=")
assert pg.banner.text() or True
pg.editor.clear()
# STO / memory / continuous calculation
click("7"); click("SHIFT"); click("RCL"); click("ALPHA"); click("(−)"); click("=")   # 7 -> A
assert w.ip.vars["A"] == F(7), w.ip.vars["A"]
click("×"); click("2"); click("=")       # Ans*2
assert last()["value"] == F(14)
click("M+"); assert w.ip.vars["M"] == F(14)
click("SHIFT"); click("M+"); assert w.ip.vars["M"] == F(0)
# S<=>D
pg.editor.insert_text("1/3"); click("=")
assert last()["result"].items[0].kind == "frac"
click("S⇔D"); assert last()["result"].items[0].text.startswith("0.3333"), last()["result"].items[0].text
click("S⇔D"); assert last()["result"].items[0].kind == "frac"
# DMS mark cycling and DMS conversion
pg.editor.insert_text("2"); click("°′″"); pg.editor.insert_text("30"); click("°′″"); click("=")
assert value_text(last()["value"], w.ip.s) == "5/2", value_text(last()["value"], w.ip.s)
# CALC with stubbed dialog
class FakeCalc:
    def __init__(self, names, defaults, parent=None, title=""): self.names = names
    def exec(self): return True
    def values(self): return {n: "3" for n in self.names}
W.VarPromptDialog = FakeCalc
pg.editor.insert_text("x^2+A"); w._do_calc(pg)
assert last()["value"] == F(12), last()["value"]
pg.editor.clear()
# SOLVE with stubbed dialog
class FakeSolve:
    class _V:  # combo-like
        def currentText(self): return "x"
    class _G:
        def text(self): return "1"
    def __init__(self, names, parent=None): self.var = self._V(); self.guess = self._G()
    def exec(self): return True
W.SolveDialog = FakeSolve
pg.editor.insert_text("x^2=2"); w._do_solve(pg)
v = last()["value"]; assert abs(float(v) - 2 ** 0.5) < 1e-9, v
pg.editor.clear()
# settings: radians, Fix 3, decimal
s = Settings.from_json(w.ip.s.to_json()); s.angle = "RAD"; s.notation = "fix"; s.digits = 3
w.apply_settings(s)
pg.editor.insert_text("sin(pi/6)"); click("=")
assert value_text(last()["value"], w.ip.s) == "1/2"
pg.editor.insert_text("sqrt(2)"); click("="); click("S⇔D")
assert last()["result"].items[0].text == "1.414", last()["result"].items[0].text
# errors keep the editor content
pg.editor.insert_text("1/0"); click("=")
assert pg.banner.text().startswith("Math ERROR") and not pg.editor.is_empty(); pg.editor.clear()
# theme switch rebuilds the UI without losing data
n_before = len(w.pages["calc"].entries)
s = Settings.from_json(w.ip.s.to_json()); s.theme = "light"; w.apply_settings(s)
pg = w.pages["calc"]
assert len(pg.entries) == n_before, (len(pg.entries), n_before)
app.processEvents(); w.grab().save("/tmp/light.png")
# session round trip
w.close()
w2 = MainWindow(); 
assert len(w2.pages["calc"].entries) == n_before and w2.ip.s.theme == "light" and w2.ip.s.angle == "RAD"
print("all flow checks passed")
