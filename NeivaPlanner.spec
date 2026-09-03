# -*- mode: python ; coding: utf-8 -*-
import sys
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files

PYTHON_HOME = Path(sys.base_prefix)
TK_DLLS = PYTHON_HOME / "DLLs"
TK_DATA = PYTHON_HOME / "tcl"
FFMPEG_DIR = Path('assets/ffmpeg')
OPTIONAL_FFMPEG = [
    (str(FFMPEG_DIR / name), 'assets/ffmpeg')
    for name in ('ffmpeg.exe', 'ffprobe.exe')
    if (FFMPEG_DIR / name).is_file()
]
FASTER_WHISPER_DATA = collect_data_files('faster_whisper')
TRELLO_APP_CONFIG = [('assets/trello_app.json', 'assets')] if Path('assets/trello_app.json').is_file() else []


a = Analysis(
    ['content_planner/main.py'],
    pathex=[],
    binaries=[(str(TK_DLLS / '_tkinter.pyd'), '.'), (str(TK_DLLS / 'tcl86t.dll'), '.'), (str(TK_DLLS / 'tk86t.dll'), '.'), *OPTIONAL_FFMPEG],
    datas=[('assets/neiva_logo.png', 'assets'), ('assets/neiva_logo.ico', 'assets'), ('assets/neiva_light.json', 'assets'), (str(TK_DATA / 'tcl8.6'), '_tcl_data'), (str(TK_DATA / 'tk8.6'), '_tk_data'), *FASTER_WHISPER_DATA, *TRELLO_APP_CONFIG],
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
    name='NeivaPlanner_v1',
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
