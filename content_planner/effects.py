"""Geração de legendas ASS animadas e word-by-word para AutoClip Etapa 3."""
from __future__ import annotations
from pathlib import Path

def _ass_time(value: float) -> str:
    h=int(value//3600); m=int(value%3600//60); s=value%60
    return f"{h}:{m:02}:{s:05.2f}"

def _escape(text:str)->str: return text.replace("\\","\\\\").replace("{","\\{").replace("}","\\}")

def write_ass(subtitles, path:Path, font:str, size:int, position:str, preset:str, animation:str, keywords:set[str], highlight:str="#FFFF00") -> None:
    alignment={"Superior":8,"Centro":5,"Inferior":2}.get(position,5)
    # ASS uses BGR colors; yellow is &H0000FFFF.
    colors={"Viral":"&H0000FFFF","Clean":"&H00FFFFFF","Impacto":"&H0000FFFF","Meme":"&H0000FFFF"}
    primary=colors.get(preset,"&H0000FFFF"); outline="&H00000000"
    header=f"""[Script Info]\nScriptType: v4.00+\nPlayResX: 1080\nPlayResY: 1920\n\n[V4+ Styles]\nFormat: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV,Encoding\nStyle: Default,{font},{size},{primary},&H00FFFFFF,{outline},&H80000000,-1,0,0,0,100,100,0,0,1,3,1,{alignment},50,50,150,1\n\n[Events]\nFormat: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text\n"""
    animation_tags={"Pop":"{\\fscx80\\fscy80\\t(0,120,\\fscx100\\fscy100)}","Bounce":"{\\fscx115\\fscy115\\t(0,180,\\fscx100\\fscy100)}","Fade":"{\\fad(120,120)}","Scale":"{\\fscx70\\fscy70\\t(0,160,\\fscx100\\fscy100)}","Slide":"{\\move(540,1150,540,960,0,180)}","Typewriter":"{\\fad(30,30)}","Word Highlight":""}
    lines=[header]
    mixed_animations=("Pop","Fade","Scale","Bounce","Slide","Typewriter")
    for index, sub in enumerate(subtitles):
        current_animation=mixed_animations[index % len(mixed_animations)] if animation == "Auto Mix" else animation
        words=getattr(sub,"words",[]) or []
        if words and (current_animation=="Word Highlight" or preset in {"Viral","Impacto","Meme"}):
            chunks=[]
            for word in words:
                centiseconds=max(1,round((word.end-word.start)*100)); text=_escape(word.text)
                if word.text.strip(".,!?;:").lower() in keywords: text=f"{{\\c{primary}\\fscx115\\fscy115}}{text}{{\\r}}"
                chunks.append(f"{{\\k{centiseconds}}}{text}")
            text=" ".join(chunks)
        else:
            text=_escape(sub.text)
            for key in keywords:
                text=text.replace(key, f"{{\\c{primary}\\fscx115\\fscy115}}{key}{{\\r}}")
            text=animation_tags.get(current_animation,"")+text
        lines.append(f"Dialogue: 0,{_ass_time(sub.start)},{_ass_time(sub.end)},Default,,0,0,0,,{text}\n")
    path.write_text("".join(lines),encoding="utf-8-sig")
