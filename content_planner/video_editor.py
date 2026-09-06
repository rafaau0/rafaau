"""Localiza e inicia o DaVinci Resolve instalado no Windows."""
from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Mapping


DAVINCI_EXECUTABLE = "Resolve.exe"


def installation_candidates(environ: Mapping[str, str] | None = None) -> list[Path]:
    values = os.environ if environ is None else environ
    roots: list[Path] = []
    for variable in ("PROGRAMFILES", "PROGRAMFILES(X86)"):
        value = values.get(variable, "").strip()
        if value:
            root = Path(value)
            if root not in roots:
                roots.append(root)
    return [root / "Blackmagic Design" / "DaVinci Resolve" / DAVINCI_EXECUTABLE for root in roots]


def validate_davinci_executable(value: str | Path) -> Path:
    path = Path(os.path.expandvars(str(value).strip().strip('"'))).expanduser()
    if path.name.casefold() != DAVINCI_EXECUTABLE.casefold():
        raise ValueError(f"Selecione o arquivo {DAVINCI_EXECUTABLE} do DaVinci Resolve.")
    if not path.is_file():
        raise FileNotFoundError(f"DaVinci Resolve não encontrado em: {path}")
    return path.resolve()


def find_davinci(configured_path: str | Path | None = None) -> Path | None:
    if configured_path and str(configured_path).strip():
        try:
            return validate_davinci_executable(configured_path)
        except (FileNotFoundError, ValueError, OSError):
            pass
    for candidate in installation_candidates():
        try:
            return validate_davinci_executable(candidate)
        except (FileNotFoundError, ValueError, OSError):
            continue
    return None


def launch_davinci(configured_path: str | Path | None = None) -> Path:
    executable = find_davinci(configured_path)
    if executable is None:
        raise FileNotFoundError(
            "DaVinci Resolve não foi encontrado. Configure o caminho do Resolve.exe em Configurações."
        )
    subprocess.Popen([str(executable)], cwd=str(executable.parent), close_fds=True)
    return executable
