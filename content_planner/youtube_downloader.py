"""Download de vídeos públicos do YouTube para os quais o usuário tem autorização."""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable
from .ffmpeg_tools import FFmpegNotFoundError, binary


class DownloadError(RuntimeError):
    pass


@dataclass(frozen=True)
class VideoInfo:
    title: str
    channel: str
    duration: int | None
    resolution: str


def is_youtube_url(url: str) -> bool:
    return bool(re.match(r"^https?://(?:www\.)?(?:youtube\.com|youtu\.be)/", url.strip(), re.I))


def duration(seconds: int | None) -> str:
    if seconds is None: return "—"
    hours, remainder = divmod(int(seconds), 3600); minutes, secs = divmod(remainder, 60)
    return f"{hours:02}:{minutes:02}:{secs:02}" if hours else f"{minutes:02}:{secs:02}"


def download(url: str, destination: Path, progress: Callable[[dict[str, Any]], None]) -> Path:
    try:
        import yt_dlp
    except ImportError as exc:
        raise DownloadError("yt-dlp não está instalado. Atualize as dependências do Neiva Planner.") from exc
    destination.mkdir(parents=True, exist_ok=True)
    try:
        ffmpeg = binary("ffmpeg")
    except FFmpegNotFoundError as exc:
        raise DownloadError(str(exc)) from exc
    options: dict[str, Any] = {
        "format": "bestvideo+bestaudio/best",
        "outtmpl": str(destination / "%(title).180B [%(id)s].%(ext)s"),
        "noplaylist": True, "windowsfilenames": True, "merge_output_format": "mp4",
        "progress_hooks": [progress], "quiet": True, "no_warnings": True,
        "retries": 3, "fragment_retries": 3, "overwrites": False,
    }
    options["ffmpeg_location"] = str(Path(ffmpeg).parent)
    try:
        with yt_dlp.YoutubeDL(options) as ydl:
            info = ydl.extract_info(url, download=True)
            video_id = str(info.get("id", ""))
            candidates = sorted((p for p in destination.iterdir() if video_id in p.name), key=lambda p: p.stat().st_mtime, reverse=True)
            return next((p for p in candidates if p.suffix.lower() in {".mp4", ".mkv", ".webm", ".mov"}), Path(ydl.prepare_filename(info)))
    except Exception as exc:
        raise DownloadError(str(exc) or "Não foi possível baixar este vídeo.") from exc


def download_audio(url: str, destination: Path, progress: Callable[[dict[str, Any]], None]) -> Path:
    """Baixa somente o áudio, para análise local de cortes."""
    try:
        import yt_dlp
        ffmpeg = binary("ffmpeg")
    except ImportError as exc:
        raise DownloadError("yt-dlp não está instalado. Atualize as dependências do Neiva Planner.") from exc
    except FFmpegNotFoundError as exc:
        raise DownloadError(str(exc)) from exc
    destination.mkdir(parents=True, exist_ok=True)
    options: dict[str, Any] = {
        "format": "bestaudio/best", "outtmpl": str(destination / "%(title).180B [%(id)s].%(ext)s"),
        "noplaylist": True, "windowsfilenames": True, "progress_hooks": [progress], "quiet": True, "no_warnings": True,
        "retries": 3, "overwrites": False, "ffmpeg_location": str(Path(ffmpeg).parent),
        "postprocessors": [{"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "128"}],
    }
    try:
        with yt_dlp.YoutubeDL(options) as ydl:
            info = ydl.extract_info(url, download=True)
            video_id = str(info.get("id", ""))
        candidates = sorted((p for p in destination.iterdir() if video_id in p.name and p.suffix.lower() in {".mp3", ".m4a", ".webm", ".ogg"}), key=lambda p: p.stat().st_mtime, reverse=True)
        if candidates: return candidates[0]
        raise DownloadError("O download terminou, mas o arquivo de áudio não foi encontrado.")
    except DownloadError:
        raise
    except Exception as exc:
        raise DownloadError(str(exc) or "Não foi possível baixar o áudio.") from exc


def fetch_info(url: str) -> VideoInfo:
    try:
        import yt_dlp
        with yt_dlp.YoutubeDL({"quiet": True, "no_warnings": True, "skip_download": True, "noplaylist": True}) as ydl:
            info = ydl.extract_info(url, download=False)
        heights = [item.get("height") for item in info.get("formats", []) if item.get("vcodec") != "none" and item.get("height")]
        return VideoInfo(info.get("title", "Vídeo sem título"), info.get("channel") or info.get("uploader") or "—", info.get("duration"), f"{max(heights)}p" if heights else "Melhor disponível")
    except Exception as exc:
        raise DownloadError(f"Não foi possível obter informações: {exc}") from exc
