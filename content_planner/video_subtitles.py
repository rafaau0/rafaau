"""Serviços locais de transcrição e renderização de legendas."""
from __future__ import annotations

import json
import logging
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from .ffmpeg_tools import FFmpegNotFoundError, binary


class VideoError(RuntimeError):
    """Erro compreensível para exibir na interface."""


@dataclass
class Subtitle:
    start: float
    end: float
    text: str
    words: list = field(default_factory=list)

@dataclass
class Word:
    text: str
    start: float
    end: float


@dataclass
class VideoProject:
    video_path: Path
    subtitles: list[Subtitle] = field(default_factory=list)
    caption_font: str = "Arial"
    caption_style: str = "Viral"
    caption_position: str = "Centro"
    caption_size: int = 42
    effect_preset: str = "Viral"
    animation: str = "Word Highlight"
    keywords: set[str] = field(default_factory=set)
    export_quality: str = "Alta"
    dynamic_edit_enabled: bool = False
    dynamic_zoom_enabled: bool = False
    dynamic_zoom_amount: int = 6
    effect_speed: float = 1.0
    video_motion: str = "Auto Mix"
    video_motion_enabled: bool = True
    motion_smoothing_enabled: bool = True
    motion_segments: list[tuple[float, float]] = field(default_factory=list)
    caption_fixed: bool = True


def _ffmpeg() -> str:
    try:
        return binary("ffmpeg")
    except FFmpegNotFoundError as exc:
        raise VideoError(str(exc)) from exc


def probe(path: Path) -> tuple[float, int, int]:
    try:
        ffprobe = binary("ffprobe")
    except FFmpegNotFoundError as exc:
        raise VideoError(str(exc)) from exc
    result = subprocess.run(
        [ffprobe, "-v", "error", "-select_streams", "v:0", "-show_entries", "format=duration:stream=width,height", "-of", "json", str(path)],
        capture_output=True, text=True, check=False,
    )
    if result.returncode:
        raise VideoError(result.stderr.strip() or "Não foi possível ler este vídeo.")
    data = json.loads(result.stdout)
    try:
        stream = data["streams"][0]
        return float(data["format"]["duration"]), int(stream["width"]), int(stream["height"])
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        raise VideoError("O arquivo não possui uma faixa de vídeo válida.") from exc


def probe_fps(path: Path) -> float:
    try:
        ffprobe = binary("ffprobe")
        result = subprocess.run([ffprobe,"-v","error","-select_streams","v:0","-show_entries","stream=avg_frame_rate","-of","default=noprint_wrappers=1:nokey=1",str(path)],capture_output=True,text=True,check=False)
        top,bottom=result.stdout.strip().split("/")
        return max(1.0,float(top)/float(bottom))
    except Exception:
        return 25.0


def _time(seconds: float, vtt: bool = False) -> str:
    milliseconds = round(max(0, seconds) * 1000)
    hours, milliseconds = divmod(milliseconds, 3_600_000)
    minutes, milliseconds = divmod(milliseconds, 60_000)
    seconds, milliseconds = divmod(milliseconds, 1000)
    return f"{hours:02}:{minutes:02}:{seconds:02}{'.' if vtt else ','}{milliseconds:03}"


def write_captions(subtitles: list[Subtitle], output: Path, vtt: bool = False) -> None:
    lines: list[str] = ["WEBVTT", ""] if vtt else []
    for index, subtitle in enumerate(subtitles, 1):
        if not vtt:
            lines.append(str(index))
        lines.extend([f"{_time(subtitle.start, vtt)} --> {_time(subtitle.end, vtt)}", subtitle.text, ""])
    output.write_text("\n".join(lines), encoding="utf-8")


def transcribe(video: Path, model_name: str, max_words: int, progress=None) -> list[Subtitle]:
    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:
        raise VideoError("A biblioteca faster-whisper não está instalada. Instale as dependências do Neiva Planner.") from exc
    with tempfile.TemporaryDirectory(prefix="neiva_legendas_") as folder:
        audio = Path(folder) / "audio.wav"
        if progress: progress("Extraindo áudio…", 5)
        result = subprocess.run([_ffmpeg(), "-y", "-i", str(video), "-vn", "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", str(audio)], capture_output=True, text=True)
        if result.returncode:
            raise VideoError(result.stderr[-1200:] or "Não foi possível extrair o áudio do vídeo.")
        if progress: progress("Carregando modelo de transcrição…", 12)
        try:
            # CPU/int8 é a opção mais estável no Windows e funciona mesmo sem GPU NVIDIA.
            # O carregamento inicial baixa o modelo escolhido para o cache local do usuário.
            model = WhisperModel(model_name, device="cpu", compute_type="int8")
            if progress: progress("Modelo pronto. Transcrevendo fala…", 30)
            segments, _ = model.transcribe(str(audio), language="pt", word_timestamps=True, vad_filter=True, beam_size=5)
            original = [Subtitle(segment.start, segment.end, segment.text.strip(), [Word(w.word.strip(),w.start,w.end) for w in (segment.words or []) if w.word.strip()]) for segment in segments if segment.text.strip()]
        except Exception as exc:
            logging.exception("Erro na transcrição de %s", video)
            raise VideoError(f"Falha durante a transcrição: {exc}") from exc
    result: list[Subtitle] = []
    for subtitle in original:
        words = subtitle.text.split()
        for start in range(0, len(words), max_words):
            part = words[start:start + max_words]
            ratio_start, ratio_end = start / len(words), min(len(words), start + max_words) / len(words)
            duration = subtitle.end - subtitle.start
            selected=subtitles_words=subtitle.words[start:start + max_words]
            result.append(Subtitle(subtitle.start + duration * ratio_start, subtitle.start + duration * ratio_end, " ".join(part), selected))
    if progress: progress("Legendas prontas para revisão.", 100)
    return result


def render(project: VideoProject, output: Path, video_format: str, fit_mode: str, progress=None, burn_subtitles: bool = True) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary_srt = output.with_suffix(".ass")
    style = getattr(project, "caption_style", "Viral")
    position = getattr(project, "caption_position", "Centro")
    font = getattr(project, "caption_font", "Arial")
    size = getattr(project, "caption_size", 42)
    if burn_subtitles:
        from .effects import write_ass
        caption_animation = "Word Highlight" if getattr(project, "caption_fixed", True) else getattr(project,"animation","Word Highlight")
        write_ass(project.subtitles, temporary_srt, font, size, position, getattr(project,"effect_preset","Viral"), caption_animation, getattr(project,"keywords",set()))
    escaped = str(temporary_srt.resolve()).replace("\\", "/").replace(":", "\\:").replace("'", "\\'")
    alignment = {"Superior": 8, "Centro": 5, "Inferior": 2}.get(position, 5)
    presets = {
        "Viral": "PrimaryColour=&H0000FFFF&,OutlineColour=&H00000000&,Outline=3,Shadow=1,Bold=1",
        "Clean": "PrimaryColour=&HFFFFFF&,OutlineColour=&H00000000&,Outline=2,Shadow=1,Bold=0",
        "Impacto": "PrimaryColour=&HFFFFFF&,OutlineColour=&H00000000&,Outline=4,Shadow=2,Bold=1",
    }
    force_style = f"FontName={font},FontSize={size},{presets.get(style, presets['Viral'])},Alignment={alignment},MarginV=60"
    subtitles_filter = f"ass='{escaped}'"
    # Primeiro edita o vídeo; a legenda é aplicada apenas no último estágio.
    filters = "null"
    if video_format == "Vertical 9:16":
        resize = "scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2:black" if fit_mode == "Ajustar" else "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920"
        filters = resize
    elif video_format == "Quadrado":
        filters = "scale=1080:1080:force_original_aspect_ratio=decrease,pad=1080:1080:(ow-iw)/2:(oh-ih)/2:black"
    elif video_format == "Horizontal":
        filters = "scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2:black"
    if getattr(project, "dynamic_zoom_enabled", False) or getattr(project, "video_motion_enabled", False):
        _, width, height = probe(project.video_path)
        fps = probe_fps(project.video_path)
        if video_format == "Vertical 9:16": width, height = 1080, 1920
        elif video_format == "Quadrado": width, height = 1080, 1080
        elif video_format == "Horizontal": width, height = 1920, 1080
        zoom_enabled=getattr(project, "dynamic_zoom_enabled", False)
        amount = max(1, min(15, int(getattr(project, "dynamic_zoom_amount", 8)))) / 100 if zoom_enabled else .03
        effect_speed = max(0.5, min(2.0, float(getattr(project, "effect_speed", 1.0))))
        motion=getattr(project,"video_motion","Auto Mix")
        # Movimento linear: evita a oscilação/tremor causada por funções senoidais.
        group="mod(floor(on/75),5)"; phase="mod(on,75)/75"
        auto_zoom = None
        if motion == "Pan Esquerda": x=f"(iw-iw/zoom)*(1-{phase})"; y="ih/2-(ih/zoom/2)"
        elif motion == "Pan Direita": x=f"(iw-iw/zoom)*{phase}"; y="ih/2-(ih/zoom/2)"
        elif motion == "Vertical": x="iw/2-(iw/zoom/2)"; y=f"(ih-ih/zoom)*{phase}"
        elif motion == "Zoom Out": x="iw/2-(iw/zoom/2)"; y="ih/2-(ih/zoom/2)"
        elif motion == "Zoom In": x="iw/2-(iw/zoom/2)"; y="ih/2-(ih/zoom/2)"
        else:
            # Auto Mix não usa pan: os efeitos são somente zoom, centralizados.
            x="iw/2-(iw/zoom/2)"; y="ih/2-(ih/zoom/2)"
        segments=getattr(project,"motion_segments",[])
        if motion == "Auto Mix" and segments:
            zoom_parts=[]
            for index,(start,end) in enumerate(segments):
                local_phase=f"min(max(((on/{fps:.6f}-{start})/{max(.1,end-start)})*{effect_speed:.2f},0),1)"
                condition=f"between(on/{fps:.6f},{start},{end})"
                # Alterna sempre um corte com zoom e outro totalmente sem efeito.
                # A sequência é: In, nenhum, Out, nenhum, seco, nenhum.
                effect = index % 6
                if effect == 0: value=f"1+{amount}*{local_phase}"          # Zoom In
                elif effect == 2: value=f"1+{amount}*(1-{local_phase})"    # Zoom Out
                elif effect == 4: value=f"1+{amount}"                       # Zoom seco
                else: value="1"                                              # Sem efeito
                zoom_parts.append((condition, value))
            auto_zoom="1"
            for condition,value in reversed(zoom_parts):
                auto_zoom=f"if({condition},{value},{auto_zoom})"
        # Zoom gradual, sem pulso/oscilação. Movimento funciona mesmo com zoom desligado.
        direction=f"min((on/300)*{effect_speed:.2f},1)" if zoom_enabled and motion != "Zoom Out" else (f"1-min((on/300)*{effect_speed:.2f},1)" if zoom_enabled else "1")
        zoom_value = auto_zoom or f"1+{amount}*{direction}"
        zoom = f"zoompan=z='{zoom_value}':x='{x}':y='{y}':d=1:s={width}x{height}:fps={fps:.3f}"
        # O zoompan já calcula uma posição contínua em cada quadro do vídeo.
        # Não interpolamos para 60 FPS: isso é muito caro, pode criar artefatos
        # e não melhora um vídeo que já foi gravado a 30/60 FPS.
        filters = f"{filters},{zoom}"
        # Em vídeos de 24/30 FPS, os quadros intermediários deixam pan e zoom
        # mais suaves. Arquivos já próximos de 60 FPS não precisam desse custo.
        if getattr(project, "motion_smoothing_enabled", True) and fps < 47:
            filters = f"{filters},minterpolate=fps=48:mi_mode=mci:mc_mode=obmc:me_mode=bidir:vsbmc=0"
    if burn_subtitles:
        filters = f"{filters},{subtitles_filter}"
    if progress: progress("Renderizando vídeo…", 20)
    quality = getattr(project, "export_quality", "Alta")
    crf = {"Alta": "18", "Média": "23", "Baixa": "28"}.get(quality, "18")
    # CRF mantém a qualidade escolhida; o preset rápido reduz o tempo de codificação.
    encoder_preset = {"Alta": "fast", "Média": "veryfast", "Baixa": "superfast"}.get(quality, "fast")
    result = subprocess.run([_ffmpeg(), "-y", "-i", str(project.video_path), "-vf", filters, "-c:v", "libx264", "-crf", crf, "-preset", encoder_preset, "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(output)], capture_output=True, text=True)
    if result.returncode:
        raise VideoError(result.stderr[-1600:] or "Falha na renderização.")
    if progress: progress("Vídeo exportado.", 100)
