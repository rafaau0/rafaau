"""Instala o painel rafaau no menu de scripts do DaVinci Resolve."""
from __future__ import annotations

import json
import os
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from .ffmpeg_tools import binary


SCRIPT_FILENAME = "rafaau_timeline.py"
INTEGRATION_VERSION = 3


@dataclass(frozen=True, slots=True)
class DavinciIntegrationStatus:
    installed: bool
    script_path: Path
    ffmpeg_path: Path


def _app_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent))
    return Path(__file__).resolve().parent.parent


def script_source() -> Path:
    return _app_root() / "assets" / "davinci" / SCRIPT_FILENAME


def scripts_directory(environ: Mapping[str, str] | None = None) -> Path:
    values = os.environ if environ is None else environ
    roaming = values.get("APPDATA", "").strip()
    root = Path(roaming) if roaming else Path.home() / "AppData" / "Roaming"
    return root / "Blackmagic Design" / "DaVinci Resolve" / "Support" / "Fusion" / "Scripts" / "Edit"


def integration_data_directory(environ: Mapping[str, str] | None = None) -> Path:
    values = os.environ if environ is None else environ
    local = values.get("LOCALAPPDATA", "").strip()
    root = Path(local) if local else Path.home() / "AppData" / "Local"
    return root / "NeivaPlanner" / "davinci_integration"


def integration_status(environ: Mapping[str, str] | None = None) -> DavinciIntegrationStatus:
    script_path = scripts_directory(environ) / SCRIPT_FILENAME
    ffmpeg_path = integration_data_directory(environ) / "ffmpeg.exe"
    config_path = ffmpeg_path.parent / "config.json"
    configured_ffmpeg = None
    config = {}
    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
        configured_ffmpeg = Path(config["ffmpeg_path"])
    except (OSError, ValueError, KeyError, TypeError):
        pass
    installed = (
        script_path.is_file()
        and ffmpeg_path.is_file()
        and configured_ffmpeg is not None
        and configured_ffmpeg.resolve() == ffmpeg_path.resolve()
        and config.get("schema_version") == INTEGRATION_VERSION
        and isinstance(config.get("transcription_command"), list)
        and bool(config["transcription_command"])
        and isinstance(config.get("dialog_command"), list)
        and bool(config["dialog_command"])
    )
    return DavinciIntegrationStatus(installed, script_path, ffmpeg_path)


def install_integration(environ: Mapping[str, str] | None = None) -> DavinciIntegrationStatus:
    source_script = script_source()
    if not source_script.is_file():
        raise FileNotFoundError("O painel de integração com o DaVinci não foi encontrado. Reinstale o rafaau.")

    source_ffmpeg = Path(binary("ffmpeg"))
    if not source_ffmpeg.is_file():
        raise FileNotFoundError("O FFmpeg necessário para analisar os silêncios não foi encontrado.")

    script_dir = scripts_directory(environ)
    data_dir = integration_data_directory(environ)
    script_dir.mkdir(parents=True, exist_ok=True)
    data_dir.mkdir(parents=True, exist_ok=True)

    installed_script = script_dir / SCRIPT_FILENAME
    installed_ffmpeg = data_dir / "ffmpeg.exe"
    shutil.copy2(source_script, installed_script)
    if source_ffmpeg.resolve() != installed_ffmpeg.resolve():
        shutil.copy2(source_ffmpeg, installed_ffmpeg)

    if getattr(sys, "frozen", False):
        command = [str(Path(sys.executable).resolve())]
        working_directory = str(Path(sys.executable).resolve().parent)
    else:
        command = [str(Path(sys.executable).resolve()), "-m", "content_planner"]
        working_directory = str(_app_root().resolve())
    config = {
        "schema_version": INTEGRATION_VERSION,
        "ffmpeg_path": str(installed_ffmpeg.resolve()),
        "transcription_command": command + ["--davinci-transcribe"],
        "dialog_command": command + ["--davinci-dialog"],
        "working_directory": working_directory,
    }
    config_path = data_dir / "config.json"
    temporary_config = data_dir / "config.json.tmp"
    temporary_config.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary_config.replace(config_path)
    return integration_status(environ)
