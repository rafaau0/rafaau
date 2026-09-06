"""Painel rafaau para uma timeline simples do DaVinci Resolve.

Este arquivo é instalado pelo aplicativo na pasta de scripts do Resolve. Ele é
autocontido de propósito: o Python embutido no Resolve não depende do pacote do
aplicativo desktop.
"""
import json
import math
import os
import re
import subprocess
from datetime import datetime
from pathlib import Path


SILENCE_START = re.compile(r"silence_start:\s*(-?\d+(?:\.\d+)?)")
SILENCE_END = re.compile(r"silence_end:\s*(-?\d+(?:\.\d+)?)")


class TimelineContext:
    def __init__(self, project, timeline, video_item, media_item, media_path, fps, source_start, source_end, duration_seconds):
        self.project = project
        self.timeline = timeline
        self.video_item = video_item
        self.media_item = media_item
        self.media_path = media_path
        self.fps = fps
        self.source_start = source_start
        self.source_end = source_end
        self.duration_seconds = duration_seconds


def parse_frame_rate(value):
    match = re.search(r"\d+(?:\.\d+)?", str(value or ""))
    if not match:
        raise RuntimeError("Não foi possível determinar a taxa de quadros da timeline.")
    fps = float(match.group(0))
    if fps <= 0:
        raise RuntimeError("A taxa de quadros da timeline é inválida.")
    return fps


def parse_silences(output, duration):
    intervals = []
    pending_start = None
    for line in output.splitlines():
        start_match = SILENCE_START.search(line)
        if start_match:
            pending_start = max(0.0, float(start_match.group(1)))
        end_match = SILENCE_END.search(line)
        if end_match and pending_start is not None:
            end = min(duration, float(end_match.group(1)))
            if end > pending_start:
                intervals.append((pending_start, end))
            pending_start = None
    if pending_start is not None and pending_start < duration:
        intervals.append((pending_start, duration))
    return intervals


def speaking_intervals(duration, silences, margin, minimum_seconds=0.04):
    """Retorna o complemento dos silêncios, mantendo margem ao redor da fala."""
    cuts = []
    for start, end in sorted(silences):
        cut_start = max(0.0, min(duration, start + margin))
        cut_end = max(0.0, min(duration, end - margin))
        if cut_end > cut_start:
            cuts.append((cut_start, cut_end))

    merged = []
    for start, end in cuts:
        if merged and start <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])

    kept = []
    cursor = 0.0
    for start, end in merged:
        if start - cursor >= minimum_seconds:
            kept.append((cursor, start))
        cursor = max(cursor, end)
    if duration - cursor >= minimum_seconds:
        kept.append((cursor, duration))
    return kept


def _config_path():
    local = os.environ.get("LOCALAPPDATA", "").strip()
    root = Path(local) if local else Path.home() / "AppData" / "Local"
    return root / "NeivaPlanner" / "davinci_integration" / "config.json"


def _ffmpeg_path():
    config_path = _config_path()
    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
        path = Path(config["ffmpeg_path"])
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise RuntimeError("Configuração do painel ausente. Reinstale o painel pelo rafaau.") from exc
    if path.name.casefold() != "ffmpeg.exe" or not path.is_file():
        raise RuntimeError("FFmpeg do painel não foi encontrado. Reinstale o painel pelo rafaau.")
    return path


def _integration_config():
    try:
        config = json.loads(_config_path().read_text(encoding="utf-8"))
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise RuntimeError("Configuração do painel ausente. Reinstale o painel pelo rafaau.") from exc
    command = config.get("transcription_command")
    if not isinstance(command, list) or not command or not all(isinstance(value, str) and value for value in command):
        raise RuntimeError("O gerador local de legendas não está configurado. Atualize o painel pelo rafaau.")
    return config


def _child_environment():
    return {key: value for key, value in os.environ.items() if not key.startswith("_PYI_")}


def _all_items(timeline, track_type):
    items = []
    for track_index in range(1, int(timeline.GetTrackCount(track_type) or 0) + 1):
        items.extend(timeline.GetItemListInTrack(track_type, track_index) or [])
    return items


def inspect_current_timeline(resolve):
    project = resolve.GetProjectManager().GetCurrentProject()
    if not project:
        raise RuntimeError("Abra um projeto do DaVinci Resolve antes de usar o painel.")
    timeline = project.GetCurrentTimeline()
    if not timeline:
        raise RuntimeError("Abra uma timeline antes de usar o painel.")

    video_items = _all_items(timeline, "video")
    audio_items = _all_items(timeline, "audio")
    if len(video_items) != 1 or len(audio_items) != 1:
        raise RuntimeError(
            "Esta versão aceita uma timeline simples: um único vídeo e um único áudio vinculado. "
            "Use uma cópia simplificada do projeto."
        )
    video_item = video_items[0]
    linked_ids = {item.GetUniqueId() for item in (video_item.GetLinkedItems() or [])}
    if audio_items[0].GetUniqueId() not in linked_ids:
        raise RuntimeError("O áudio precisa estar vinculado ao vídeo na timeline.")

    media_item = video_item.GetMediaPoolItem()
    if not media_item:
        raise RuntimeError("Clipes compostos, geradores e timelines aninhadas ainda não são suportados.")
    media_path = Path(str(media_item.GetClipProperty("File Path") or ""))
    if not media_path.is_file():
        raise RuntimeError("O arquivo original do vídeo não está disponível neste computador.")

    fps = parse_frame_rate(timeline.GetSetting("timelineFrameRate"))
    # clipInfo.startFrame/endFrame esperam deslocamentos relativos ao início
    # do arquivo, não o timecode absoluto retornado por GetSourceStartFrame.
    source_start = int(round(float(video_item.GetLeftOffset(False))))
    timeline_frames = int(video_item.GetEnd()) - int(video_item.GetStart())
    source_end = source_start + timeline_frames
    audio_media_item = audio_items[0].GetMediaPoolItem()
    if not audio_media_item or audio_media_item.GetUniqueId() != media_item.GetUniqueId():
        raise RuntimeError("O áudio precisa pertencer ao mesmo arquivo do vídeo nesta primeira versão.")
    audio_source_start = int(round(float(audio_items[0].GetLeftOffset(False))))
    audio_timeline_frames = int(audio_items[0].GetEnd()) - int(audio_items[0].GetStart())
    audio_source_end = audio_source_start + audio_timeline_frames
    if abs(audio_source_start - source_start) > 2 or abs(audio_source_end - source_end) > 2:
        raise RuntimeError("Os recortes do vídeo e do áudio vinculado precisam estar alinhados.")
    source_frames = source_end - source_start
    if source_frames <= 0:
        raise RuntimeError("Vídeos com mudança de velocidade ou retiming ainda não são suportados.")

    return TimelineContext(
        project=project,
        timeline=timeline,
        video_item=video_item,
        media_item=media_item,
        media_path=media_path,
        fps=fps,
        source_start=source_start,
        source_end=source_end,
        duration_seconds=source_frames / fps,
    )


def detect_silences(context, threshold_db, minimum_duration):
    command = [
        str(_ffmpeg_path()),
        "-hide_banner",
        "-nostdin",
        "-ss",
        f"{context.source_start / context.fps:.6f}",
        "-t",
        f"{context.duration_seconds:.6f}",
        "-i",
        str(context.media_path),
        "-vn",
        "-af",
        f"silencedetect=noise={threshold_db}dB:d={minimum_duration}",
        "-f",
        "null",
        "NUL",
    ]
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        result = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            creationflags=flags,
            timeout=max(300, min(21600, int(context.duration_seconds * 4 + 60))),
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("A análise demorou além do limite de segurança e foi interrompida.") from exc
    if result.returncode != 0:
        details = (result.stderr or "").strip().splitlines()
        raise RuntimeError("O FFmpeg não conseguiu analisar o áudio." + (f"\n{details[-1]}" if details else ""))
    return parse_silences(result.stderr, context.duration_seconds)


def _unique_timeline_name(project, base_name):
    existing = {
        project.GetTimelineByIndex(index).GetName()
        for index in range(1, int(project.GetTimelineCount() or 0) + 1)
    }
    stem = f"{base_name} - rafaau {datetime.now():%Y%m%d-%H%M%S}"
    name = stem
    suffix = 2
    while name in existing:
        name = f"{stem}-{suffix}"
        suffix += 1
    return name


def clip_frame_ranges(context, kept):
    ranges = []
    for start_seconds, end_seconds in kept:
        start_frame = context.source_start + int(round(start_seconds * context.fps))
        end_exclusive = context.source_start + int(math.ceil(end_seconds * context.fps))
        start_frame = max(context.source_start, min(context.source_end - 1, start_frame))
        end_exclusive = max(start_frame + 1, min(context.source_end, end_exclusive))
        ranges.append((start_frame, end_exclusive))
    return ranges


def create_clean_timeline(context, kept):
    if not kept:
        raise RuntimeError("Nenhum trecho com fala foi encontrado. Ajuste a sensibilidade e analise novamente.")
    clip_infos = []
    expected_frames = 0
    for start_frame, end_exclusive in clip_frame_ranges(context, kept):
        clip_infos.append(
            {
                "mediaPoolItem": context.media_item,
                "startFrame": start_frame,
                "endFrame": end_exclusive - 1,
            }
        )
        expected_frames += end_exclusive - start_frame

    name = _unique_timeline_name(context.project, context.timeline.GetName())
    media_pool = context.project.GetMediaPool()
    new_timeline = media_pool.CreateEmptyTimeline(name)
    if not new_timeline:
        raise RuntimeError("O DaVinci não conseguiu criar a nova timeline.")
    try:
        new_timeline.SetStartTimecode(context.timeline.GetStartTimecode())
    except Exception:
        pass
    if not context.project.SetCurrentTimeline(new_timeline):
        raise RuntimeError("A timeline vazia foi criada, mas não pôde ser aberta automaticamente.")
    appended = media_pool.AppendToTimeline(clip_infos) or []
    video_items = _all_items(new_timeline, "video")
    actual_frames = sum(int(item.GetEnd()) - int(item.GetStart()) for item in video_items)
    if not appended or len(video_items) != len(clip_infos) or abs(actual_frames - expected_frames) > len(clip_infos):
        raise RuntimeError(
            "O DaVinci não anexou todos os trechos falados. A timeline original permanece intacta; "
            "a cópia incompleta pode ser excluída."
        )
    return new_timeline


def generate_local_captions(context, kept, chars_per_caption):
    config = _integration_config()
    data_dir = _config_path().parent
    captions_dir = data_dir / "captions"
    captions_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    output_path = captions_dir / ("rafaau-legendas-" + stamp + ".srt")
    request_path = data_dir / ("caption-request-" + stamp + ".json")
    result_path = request_path.with_suffix(".result.json")
    request = {
        "input_path": str(context.media_path),
        "output_path": str(output_path),
        "source_start_seconds": context.source_start / context.fps,
        "duration_seconds": context.duration_seconds,
        "kept_intervals": kept,
        "chars_per_caption": chars_per_caption,
        "model": "small",
    }
    request_path.write_text(json.dumps(request, ensure_ascii=False, indent=2), encoding="utf-8")
    command = list(config["transcription_command"]) + [str(request_path)]
    working_directory = config.get("working_directory") or str(data_dir)
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        process = subprocess.run(
            command,
            cwd=working_directory,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            creationflags=flags,
            env=_child_environment(),
            timeout=max(900, min(21600, int(context.duration_seconds * 12 + 300))),
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("A transcrição local demorou além do limite de segurança.") from exc
    try:
        result = json.loads(result_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        detail = (process.stderr or "").strip()
        raise RuntimeError("O gerador local de legendas não respondeu." + (("\n" + detail[-500:]) if detail else "")) from exc
    finally:
        try:
            request_path.unlink()
        except OSError:
            pass
        try:
            result_path.unlink()
        except OSError:
            pass
    if process.returncode != 0 or not result.get("ok"):
        raise RuntimeError(result.get("error") or "Não foi possível gerar as legendas locais.")
    if not output_path.is_file():
        raise RuntimeError("A transcrição terminou sem criar o arquivo SRT.")
    imported = context.project.GetMediaPool().ImportMedia([str(output_path)]) or []
    if not imported:
        try:
            subprocess.Popen(["explorer.exe", "/select,", str(output_path)])
        except OSError:
            pass
    return output_path, bool(imported), int(result.get("captions", 0))


def show_rafaau_dialog(kind, message):
    """Abre a janela temática pelo app, fora do UIManager exclusivo do Studio."""
    config = _integration_config()
    command = config.get("dialog_command")
    if not isinstance(command, list) or not command or not all(isinstance(value, str) and value for value in command):
        raise RuntimeError("A janela do rafaau não está configurada. Atualize o comando pelo aplicativo.")

    data_dir = _config_path().parent
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    request_path = data_dir / ("dialog-request-" + stamp + ".json")
    result_path = request_path.with_suffix(".result.json")
    request_path.write_text(json.dumps({
        "kind": kind,
        "title": "rafaau - DaVinci Resolve",
        "message": message,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        process = subprocess.run(
            list(command) + [str(request_path)],
            cwd=config.get("working_directory") or str(data_dir),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            creationflags=flags,
            env=_child_environment(),
        )
        result = json.loads(result_path.read_text(encoding="utf-8"))
        if process.returncode != 0 or not result.get("ok"):
            raise RuntimeError(result.get("error") or "A janela do rafaau não respondeu.")
        return bool(result.get("approved"))
    finally:
        try:
            request_path.unlink()
        except OSError:
            pass
        try:
            result_path.unlink()
        except OSError:
            pass


def main():
    resolve_api = globals().get("resolve")
    if not resolve_api:
        raise RuntimeError("Este comando deve ser aberto pelo menu Scripts do DaVinci Resolve.")

    # UIManager é um recurso Studio. A janela temática é aberta pelo executável
    # do rafaau; a caixa nativa abaixo permanece como fallback de segurança.
    import ctypes
    user32 = ctypes.windll.user32
    title = "rafaau - Timeline"

    def message(text, kind="info"):
        try:
            return show_rafaau_dialog(kind, str(text))
        except Exception:
            style = 0x24 if kind == "confirm" else (0x10 if kind == "error" else 0x40)
            response = user32.MessageBoxW(None, str(text), title, style)
            return response == 6 if kind == "confirm" else True

    try:
        context = inspect_current_timeline(resolve_api)
        if message(
            "O rafaau vai analisar a timeline aberta usando estas configurações:\n\n"
            "Silêncio: abaixo de -35 dB por pelo menos 0,40 s\n"
            "Margem preservada: 0,15 s\n"
            "Legenda local: português, até 42 caracteres\n\n"
            "A timeline original nunca será alterada. Deseja analisar agora?",
            "confirm",
        ) is not True:
            return

        silences = detect_silences(context, -35.0, 0.40)
        kept = speaking_intervals(context.duration_seconds, silences, 0.15)
        removed = context.duration_seconds - sum(end - start for start, end in kept)
        if message(
            "Análise concluída.\n\n"
            "Timeline: {}\n"
            "Duração: {:.1f} s\n"
            "Silêncios encontrados: {}\n"
            "Tempo estimado a remover: {:.1f} s\n\n"
            "Deseja criar uma NOVA timeline sem silêncios e gerar o SRT local?".format(
                context.timeline.GetName(), context.duration_seconds, len(silences), removed
            ),
            "confirm",
        ) is not True:
            return

        new_timeline = create_clean_timeline(context, kept)
        message(
            "A nova timeline foi criada. Agora o rafaau vai gerar as legendas localmente.\n\n"
            "Na primeira execução, o modelo de português será baixado e esta etapa pode demorar.\n"
            "Clique em OK e aguarde a mensagem de conclusão.",
            "info",
        )
        output, imported, count = generate_local_captions(context, kept, 42)
        location = (
            "O SRT foi importado para o Media Pool. Arraste-o para uma faixa de legenda."
            if imported
            else "A pasta do SRT foi aberta. Arraste o arquivo para uma faixa de legenda."
        )
        message(
            "Processamento concluído.\n\n"
            "Nova timeline: {}\n"
            "Legendas geradas: {}\n"
            "Arquivo SRT: {}\n\n{}\n\nA timeline original foi preservada.".format(
                new_timeline.GetName(), count, output, location
            ),
            "info",
        )
    except Exception as exc:
        message("Não foi possível concluir o processamento.\n\n{}".format(exc), "error")


if __name__ == "__main__":
    main()
