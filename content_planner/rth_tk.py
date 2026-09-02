"""Configura os dados do Tcl/Tk no executável empacotado."""
from __future__ import annotations

import os
import sys
from pathlib import Path

if getattr(sys, "frozen", False):
    base = Path(sys._MEIPASS) / "_tcl_data"
    os.environ.setdefault("TCL_LIBRARY", str(base / "tcl8.6"))
    os.environ.setdefault("TK_LIBRARY", str(base / "tk8.6"))
