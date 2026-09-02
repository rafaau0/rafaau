"""Localiza FFmpeg em desenvolvimento e no executável empacotado."""
from __future__ import annotations

import shutil
import sys
from pathlib import Path


class FFmpegNotFoundError(RuntimeError):
    pass


def app_root() -> Path:
    return Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent.parent


def binary(name: str) -> str:
    system_binary = shutil.which(name)
    if system_binary:
        return system_binary
    extension = ".exe" if sys.platform.startswith("win") else ""
    bundled = app_root() / "assets" / "ffmpeg" / f"{name}{extension}"
    if bundled.is_file():
        return str(bundled)
    raise FFmpegNotFoundError(
        f"{name}{extension} não foi encontrado. Reinstale o aplicativo ou configure o FFmpeg no PATH."
    )
