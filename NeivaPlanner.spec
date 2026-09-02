# -*- mode: python ; coding: utf-8 -*-
import sys
from pathlib import Path

PYTHON_HOME = Path(sys.base_prefix)
TK_DLLS = PYTHON_HOME / "DLLs"
TK_DATA = PYTHON_HOME / "tcl"


a = Analysis(
    ['content_planner/main.py'],
    pathex=[],
    binaries=[(str(TK_DLLS / '_tkinter.pyd'), '.'), (str(TK_DLLS / 'tcl86t.dll'), '.'), (str(TK_DLLS / 'tk86t.dll'), '.')],
    datas=[('assets/neiva_logo.png', 'assets'), ('assets/neiva_logo.ico', 'assets'), (str(TK_DATA / 'tcl8.6'), '_tcl_data/tcl8.6'), (str(TK_DATA / 'tk8.6'), '_tcl_data/tk8.6')],
    hiddenimports=['tkinter', 'tkinter.messagebox'],
    hookspath=['hooks'],
    hooksconfig={},
    runtime_hooks=['content_planner/rth_tk.py'],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='NeivaPlanner',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['assets/neiva_logo.ico'],
)
