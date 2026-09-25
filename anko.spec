# -*- mode: python ; coding: utf-8 -*-
# Build:   pyinstaller anko.spec --noconfirm --clean
# One-file exe instead of a folder:   set ANKO_ONEFILE=1   (slower start-up, single Anko.exe)
import os

ONEFILE = os.environ.get("ANKO_ONEFILE") == "1"

EXCLUDES = [
    "tkinter", "numpy", "matplotlib", "scipy", "PIL", "pandas", "unittest", "pydoc", "test",
    "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets", "PySide6.QtWebEngineQuick", "PySide6.QtWebChannel",
    "PySide6.Qt3DCore", "PySide6.Qt3DRender", "PySide6.Qt3DInput", "PySide6.Qt3DLogic", "PySide6.Qt3DAnimation",
    "PySide6.Qt3DExtras", "PySide6.QtQuick", "PySide6.QtQuick3D", "PySide6.QtQml", "PySide6.QtQuickWidgets",
    "PySide6.QtMultimedia", "PySide6.QtMultimediaWidgets", "PySide6.QtCharts", "PySide6.QtDataVisualization",
    "PySide6.QtSql", "PySide6.QtTest", "PySide6.QtBluetooth", "PySide6.QtNfc", "PySide6.QtSensors",
    "PySide6.QtSerialPort", "PySide6.QtPdf", "PySide6.QtPdfWidgets", "PySide6.QtRemoteObjects",
    "PySide6.QtPositioning", "PySide6.QtLocation", "PySide6.QtSvg", "PySide6.QtSvgWidgets",
    "PySide6.QtOpenGL", "PySide6.QtOpenGLWidgets", "PySide6.QtDesigner", "PySide6.QtHelp",
    "PySide6.QtNetworkAuth", "PySide6.QtScxml", "PySide6.QtStateMachine", "PySide6.QtTextToSpeech",
    "PySide6.QtHttpServer", "PySide6.QtSpatialAudio", "PySide6.QtWebSockets", "PySide6.QtVirtualKeyboard",
]

a = Analysis(
    ["main.py"],
    pathex=["."],
    datas=[("anko/assets", "anko/assets")],
    hiddenimports=[],
    excludes=EXCLUDES,
    noarchive=False,
)
pyz = PYZ(a.pure)

if ONEFILE:
    exe = EXE(pyz, a.scripts, a.binaries, a.datas, [], name="Anko", console=False,
              icon="anko/assets/icon.ico", upx=False)
else:
    exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="Anko", console=False,
              icon="anko/assets/icon.ico", upx=False)
    coll = COLLECT(exe, a.binaries, a.datas, name="Anko", upx=False)
