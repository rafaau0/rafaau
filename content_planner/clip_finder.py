"""Seleção local de trechos promissores a partir de uma transcrição."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable

from .video_subtitles import Subtitle


@dataclass(frozen=True)
class ClipSuggestion:
    start: float
    end: float
    title: str
    summary: str
    score: int


_HOOKS = ("ninguém", "segredo", "erro", "verdade", "como", "por que", "porque", "resultado", "aprendi", "mudou", "dica", "atenção", "importante", "melhor", "pior", "problema", "solução", "vender", "crescer")


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _title(text: str) -> str:
    first = _clean(re.split(r"[.!?]", text, maxsplit=1)[0]).strip(" -,:;")
    words = first.split()
    if not words:
        return "Trecho em destaque"
    value = " ".join(words[:11]).strip(" -,:;")
    return value[:1].upper() + value[1:] + ("…" if len(words) > 11 else "")


def _score(text: str, seconds: float) -> int:
    lowered = text.lower()
    hooks = sum(1 for word in _HOOKS if re.search(rf"\b{re.escape(word)}\b", lowered))
    score = 42 + min(26, hooks * 6)
    if "?" in text: score += 8
    if "!" in text: score += 5
    if 25 <= seconds <= 65: score += 12
    elif 18 <= seconds <= 85: score += 6
    if 35 <= len(text.split()) <= 155: score += 7
    return min(99, score)


def find_suggestions(subtitles: Iterable[Subtitle], limit: int = 8) -> list[ClipSuggestion]:
    """Agrupa fala contínua em cortes curtos e os classifica por potencial de gancho."""
    entries = [item for item in subtitles if _clean(item.text)]
    candidates: list[ClipSuggestion] = []
    for start_index in range(len(entries)):
        group: list[Subtitle] = []
        for item in entries[start_index:]:
            if group and item.start - group[-1].end > 3.5: break
            group.append(item)
            duration = item.end - group[0].start
            if duration < 22: continue
            text = _clean(" ".join(part.text for part in group))
            candidates.append(ClipSuggestion(group[0].start, item.end, _title(text), text, _score(text, duration)))
            if duration >= 65: break
    candidates.sort(key=lambda item: item.score, reverse=True)
    selected: list[ClipSuggestion] = []
    for candidate in candidates:
        if any(max(0, min(candidate.end, existing.end) - max(candidate.start, existing.start)) > 12 for existing in selected): continue
        selected.append(candidate)
        if len(selected) == limit: break
    return sorted(selected, key=lambda item: item.start)
