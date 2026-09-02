"""Detecção e remoção segura de silêncios com remapeamento de legendas."""
from __future__ import annotations
import re, subprocess
from dataclasses import dataclass
from pathlib import Path
from .ffmpeg_tools import binary
from .video_subtitles import Subtitle, VideoError

@dataclass(frozen=True)
class Cut: start: float; end: float
@dataclass(frozen=True)
class SilenceSettings:
    threshold_db: float = -35.0; min_duration: float = .4; before_margin: float = .15; after_margin: float = .15; mode: str = "Desativado"

def detect_silences(video: Path, threshold_db: float, min_duration: float) -> list[tuple[float,float]]:
    cmd=[binary("ffmpeg"),"-i",str(video),"-af",f"silencedetect=n={threshold_db}dB:d={min_duration}","-f","null","-"]
    result=subprocess.run(cmd,capture_output=True,text=True,encoding="utf-8",errors="replace")
    if result.returncode: raise VideoError(result.stderr[-1200:] or "Não foi possível analisar o áudio.")
    starts=[]; found=[]
    for line in result.stderr.splitlines():
        start=re.search(r"silence_start: ([\d.]+)",line); end=re.search(r"silence_end: ([\d.]+)",line)
        if start: starts.append(float(start.group(1)))
        if end and starts: found.append((starts.pop(0),float(end.group(1))))
    return found

def plan_cuts(silences:list[tuple[float,float]], settings:SilenceSettings) -> list[Cut]:
    if settings.mode == "Desativado": return []
    cuts=[]
    for start,end in silences:
        duration=end-start
        if duration < settings.min_duration: continue
        keep = 0.0 if settings.mode == "Remover silêncios" and duration >= 1 else min(.30,duration)
        cut_start=start+settings.before_margin; cut_end=end-settings.after_margin-keep
        if cut_end > cut_start: cuts.append(Cut(cut_start,cut_end))
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
        if end-start >= .05: result.append(Subtitle(start,end,sub.text))
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
    parts=[]; count=0
    for index in range(0,len(points)-1,2):
        a,b=points[index],points[index+1]
        if b-a>.03:
            parts.append(f"[0:v]trim=start={a}:end={b},setpts=PTS-STARTPTS[v{count}];[0:a]atrim=start={a}:end={b},asetpts=PTS-STARTPTS[a{count}]")
            count += 1
    joined="".join(f"[v{i}][a{i}]" for i in range(count))+f"concat=n={count}:v=1:a=1[v][a]"
    output.parent.mkdir(parents=True,exist_ok=True)
    if progress: progress("Removendo silêncios…",30)
    cmd=[binary("ffmpeg"),"-y","-i",str(video),"-filter_complex",";".join(parts+[joined]),"-map","[v]","-map","[a]","-c:v","libx264","-crf","18","-preset","medium","-c:a","aac","-b:a","192k",str(output)]
    result=subprocess.run(cmd,capture_output=True,text=True,encoding="utf-8",errors="replace")
    if result.returncode: raise VideoError(result.stderr[-1600:] or "Falha ao reconstruir vídeo.")
    if progress: progress("Edição automática concluída.",100)
