"""Caminhos graváveis compartilhados pelo desktop e pelo executável."""
from __future__ import annotations

import os
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
INSTALL_ROOT = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else PROJECT_ROOT
if getattr(sys, "frozen", False):
    LOCAL_DATA_ROOT = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / "NeivaPlanner"
else:
    LOCAL_DATA_ROOT = PROJECT_ROOT
EXPORTS_DIR = LOCAL_DATA_ROOT / "exports"
