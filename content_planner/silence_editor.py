"""Detecção e remoção segura de silêncios com remapeamento de legendas."""
from __future__ import annotations
import re, subprocess, tempfile, uuid
from dataclasses import dataclass
from pathlib import Path
from .ffmpeg_tools import binary
from .video_subtitles import Subtitle, VideoError, Word

PROCESS_TIMEOUT_SECONDS = 60 * 60 * 2

@dataclass(frozen=True)
class Cut: start: float; end: float
@dataclass(frozen=True)
class SilenceSettings:
    threshold_db: float = -35.0; min_duration: float = .4; before_margin: float = .15; after_margin: float = .15; mode: str = "Desativado"

def detect_silences(video: Path, threshold_db: float, min_duration: float) -> list[tuple[float,float]]:
    cmd=[binary("ffmpeg"),"-i",str(video),"-af",f"silencedetect=n={threshold_db}dB:d={min_duration}","-f","null","-"]
    try:
        result=subprocess.run(cmd,capture_output=True,text=True,encoding="utf-8",errors="replace",timeout=PROCESS_TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired as exc:
        raise VideoError("A análise de silêncio excedeu o tempo limite de 2 horas.") from exc
    if result.returncode: raise VideoError(result.stderr[-1200:] or "Não foi possível analisar o áudio.")
    starts=[]; found=[]
    for line in result.stderr.splitlines():
        start=re.search(r"silence_start: ([\d.]+)",line); end=re.search(r"silence_end: ([\d.]+)",line)
        if start: starts.append(float(start.group(1)))
        if end and starts: found.append((starts.pop(0),float(end.group(1))))
    return found

def plan_cuts(silences:list[tuple[float,float]], settings:SilenceSettings) -> list[Cut]:
    if settings.mode == "Desativado": return []
    if settings.min_duration <= 0 or settings.before_margin < 0 or settings.after_margin < 0:
        raise VideoError("Duração e margens devem ser números positivos.")
    cuts=[]
    for start,end in sorted(silences):
        start, end = max(0.0, start), max(0.0, end)
        duration=end-start
        if duration < settings.min_duration: continue
        keep = 0.0 if settings.mode == "Remover silêncios" and duration >= 1 else min(.30,duration)
        cut_start=start+settings.before_margin; cut_end=end-settings.after_margin-keep
        if cut_end > cut_start:
            if cuts and cut_start <= cuts[-1].end:
                cuts[-1] = Cut(cuts[-1].start, max(cuts[-1].end, cut_end))
            else:
                cuts.append(Cut(cut_start,cut_end))
    return cuts

def map_time(value:float,cuts:list[Cut]) -> float:
    removed=0.0
    for cut in cuts:
        if value >= cut.end: removed += cut.end-cut.start
        elif value > cut.start: return cut.start-removed
        else: break
    return max(0,value-removed)

def remap_subtitles(subtitles:list[Subtitle],cuts:list[Cut]) -> list[Subtitle]:
    result=[]
    for sub in subtitles:
        start,end=map_time(sub.start,cuts),map_time(sub.end,cuts)
        if end-start >= .05:
            words=[]
            for word in sub.words:
                word_start, word_end = map_time(word.start, cuts), map_time(word.end, cuts)
                if word_end - word_start >= .01:
                    words.append(Word(word.text, word_start, word_end))
            result.append(Subtitle(start,end,sub.text,words))
    return result

def output_segments(duration: float, cuts: list[Cut]) -> list[tuple[float, float]]:
    """Blocos preservados no vídeo final, usados pelo Auto Mix de movimento."""
    points=[0.0]+[value for cut in cuts for value in (cut.start,cut.end)]+[duration]
    output=[]; cursor=0.0
    for index in range(0,len(points)-1,2):
        length=points[index+1]-points[index]
        if length>.03:
            output.append((cursor,cursor+length)); cursor += length
    return output

def apply_cuts(video:Path,cuts:list[Cut],output:Path,progress=None) -> None:
    if not cuts: raise VideoError("Não há cortes para aplicar.")
    from .video_subtitles import probe
    duration,_,_=probe(video); points=[0.0]+[v for cut in cuts for v in (cut.start,cut.end)]+[duration]
    try:
        audio_probe=subprocess.run([binary("ffprobe"),"-v","error","-select_streams","a:0","-show_entries","stream=index","-of","csv=p=0",str(video)],capture_output=True,text=True,timeout=60)
        has_audio=audio_probe.returncode == 0 and bool(audio_probe.stdout.strip())
    except subprocess.TimeoutExpired as exc:
        raise VideoError("A leitura do áudio excedeu o tempo limite.") from exc
    parts=[]; count=0
    for index in range(0,len(points)-1,2):
        a,b=points[index],points[index+1]
        if b-a>.03:
            video_filter=f"[0:v]trim=start={a}:end={b},setpts=PTS-STARTPTS[v{count}]"
            audio_filter=f";[0:a]atrim=start={a}:end={b},asetpts=PTS-STARTPTS[a{count}]" if has_audio else ""
            parts.append(video_filter+audio_filter)
            count += 1
    joined=("".join(f"[v{i}][a{i}]" for i in range(count))+f"concat=n={count}:v=1:a=1[v][a]") if has_audio else ("".join(f"[v{i}]" for i in range(count))+f"concat=n={count}:v=1:a=0[v]")
    output.parent.mkdir(parents=True,exist_ok=True)
    if progress: progress("Removendo silêncios…",30)
    filter_path = Path(tempfile.gettempdir()) / f"neiva_silence_{uuid.uuid4().hex}.txt"
    filter_path.write_text(";".join(parts+[joined]), encoding="utf-8")
    cmd=[binary("ffmpeg"),"-y","-i",str(video),"-filter_complex_script",str(filter_path),"-map","[v]"]
    if has_audio: cmd.extend(["-map","[a]"])
    cmd.extend(["-c:v","libx264","-crf","18","-preset","medium"])
    if has_audio: cmd.extend(["-c:a","aac","-b:a","192k"])
    cmd.append(str(output))
    try:
        result=subprocess.run(cmd,capture_output=True,text=True,encoding="utf-8",errors="replace",timeout=PROCESS_TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired as exc:
        output.unlink(missing_ok=True)
        raise VideoError("A remoção de silêncios excedeu o tempo limite de 2 horas.") from exc
    finally:
        filter_path.unlink(missing_ok=True)
    if result.returncode:
        output.unlink(missing_ok=True)
        raise VideoError(result.stderr[-1600:] or "Falha ao reconstruir vídeo.")
    if progress: progress("Edição automática concluída.",100)
