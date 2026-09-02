"""Configura os dados do Tcl/Tk no executável empacotado."""
from __future__ import annotations

import os
import sys
from pathlib import Path

if getattr(sys, "frozen", False):
    base = Path(sys._MEIPASS)
    # Usa o layout esperado pelo runtime hook oficial do PyInstaller.
    os.environ["TCL_LIBRARY"] = str(base / "_tcl_data")
    os.environ["TK_LIBRARY"] = str(base / "_tk_data")
