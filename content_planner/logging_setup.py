"""Logs locais rotativos para suporte e diagnóstico."""
from __future__ import annotations

import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path


def log_directory() -> Path:
    base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")) if getattr(sys, "frozen", False) else Path(__file__).resolve().parent.parent
    return base / "NeivaPlanner" / "logs" if getattr(sys, "frozen", False) else base / "exports" / "logs"


def configure_logging() -> Path:
    folder = log_directory()
    folder.mkdir(parents=True, exist_ok=True)
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    if not any(isinstance(handler, RotatingFileHandler) and getattr(handler, "baseFilename", "") == str(folder / "neiva.log") for handler in root.handlers):
        handler = RotatingFileHandler(folder / "neiva.log", maxBytes=2_000_000, backupCount=5, encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
        root.addHandler(handler)
    return folder
