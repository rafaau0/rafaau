"""Worker local chamado pelo painel do DaVinci para gerar legendas SRT."""
from __future__ import annotations

import json
import logging
from pathlib import Path

from .video_subtitles import Subtitle, Word, transcribe_interval, write_captions


def _map_time(value: float, kept: list[tuple[float, float]]) -> float | None:
    output_cursor = 0.0
    for start, end in kept:
        if start <= value <= end:
            return output_cursor + min(end - start, max(0.0, value - start))
        output_cursor += end - start
    return None


def remap_captions(
    subtitles: list[Subtitle], kept: list[tuple[float, float]], chars_per_caption: int
) -> list[Subtitle]:
    mapped_words: list[Word] = []
    fallback: list[Subtitle] = []
    for subtitle in subtitles:
        if subtitle.words:
            for word in subtitle.words:
                midpoint = (word.start + word.end) / 2
                if not any(start <= midpoint <= end for start, end in kept):
                    continue
                start = _map_time(word.start, kept)
                end = _map_time(word.end, kept)
                if start is None:
                    start = _map_time(midpoint, kept)
                if end is None:
                    end = _map_time(midpoint, kept)
                if start is not None and end is not None:
                    mapped_words.append(Word(word.text.strip(), start, max(start + 0.01, end)))
            continue
        for keep_start, keep_end in kept:
            overlap_start = max(subtitle.start, keep_start)
            overlap_end = min(subtitle.end, keep_end)
            if overlap_end - overlap_start < 0.05:
                continue
            start = _map_time(overlap_start, kept)
            end = _map_time(overlap_end, kept)
            if start is not None and end is not None:
                fallback.append(Subtitle(start, end, subtitle.text.strip()))

    result: list[Subtitle] = []
    current: list[Word] = []
    for word in mapped_words:
        proposed = " ".join(item.text for item in [*current, word]).strip()
        has_large_gap = bool(current and word.start - current[-1].end > 1.2)
        if current and (len(proposed) > chars_per_caption or has_large_gap):
            result.append(Subtitle(current[0].start, current[-1].end, " ".join(item.text for item in current), current))
            current = []
        current.append(word)
    if current:
        result.append(Subtitle(current[0].start, current[-1].end, " ".join(item.text for item in current), current))
    return sorted(result + fallback, key=lambda caption: caption.start)


def _write_result(path: Path, payload: dict) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def run_request(request_path: Path) -> int:
    result_path = request_path.with_suffix(".result.json")
    try:
        request = json.loads(request_path.read_text(encoding="utf-8"))
        input_path = Path(request["input_path"])
        output_path = Path(request["output_path"])
        source_start = float(request["source_start_seconds"])
        duration = float(request["duration_seconds"])
        kept = [(float(start), float(end)) for start, end in request["kept_intervals"]]
        chars = int(request.get("chars_per_caption", 42))
        model = str(request.get("model", "small"))
        if not input_path.is_file():
            raise ValueError("O arquivo original do vídeo não foi encontrado.")
        if output_path.suffix.casefold() != ".srt":
            raise ValueError("O destino da legenda precisa ser um arquivo SRT.")
        if duration <= 0 or not kept or not 1 <= chars <= 60:
            raise ValueError("Os parâmetros recebidos para transcrição são inválidos.")

        subtitles = transcribe_interval(input_path, model, 12, source_start, duration)
        captions = remap_captions(subtitles, kept, chars)
        if not captions:
            raise RuntimeError("Nenhuma fala foi reconhecida nesse vídeo.")
        write_captions(captions, output_path)
        _write_result(result_path, {"ok": True, "captions": len(captions), "output_path": str(output_path)})
        return 0
    except Exception as exc:
        logging.exception("Falha ao gerar legenda para o DaVinci")
        _write_result(result_path, {"ok": False, "error": str(exc)})
        return 1

