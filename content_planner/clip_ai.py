"""Análise contextual de cortes pela API da OpenAI."""
from __future__ import annotations

import json
from dataclasses import dataclass

import requests

from .clip_finder import ClipSuggestion
from .video_subtitles import Subtitle


class ClipAIError(RuntimeError):
    pass


_SCHEMA = {
    "type": "object",
    "properties": {
        "cuts": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "start": {"type": "number"}, "end": {"type": "number"},
                    "title": {"type": "string"}, "summary": {"type": "string"},
                    "score": {"type": "integer"},
                },
                "required": ["start", "end", "title", "summary", "score"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["cuts"], "additionalProperties": False,
}


def analyze_cuts(subtitles: list[Subtitle], api_key: str, limit: int = 8) -> list[ClipSuggestion]:
    if not api_key:
        raise ClipAIError("Informe a chave OPENAI_API_KEY em Configurações para usar a análise por IA.")
    transcript = "\n".join(f"[{item.start:.2f} - {item.end:.2f}] {item.text}" for item in subtitles)
    if not transcript.strip():
        return []
    requested_limit = max(0, int(limit))
    if requested_limit == 0:
        return []
    instructions = """Você é um editor especializado em cortes virais em português do Brasil.
Analise a transcrição com timestamps e selecione os melhores trechos de 20 a 90 segundos.
Prefira uma ideia completa, gancho forte, ensino útil, história, opinião marcante ou conclusão.
Use SOMENTE timestamps existentes ou contidos no intervalo da transcrição. Não invente falas.
Retorne no máximo o número de cortes pedido, com título curto e atraente, resumo fiel e score de 0 a 100."""
    payload = {
        "model": "gpt-5-mini", "store": False, "instructions": instructions,
        "input": f"Sugira no máximo {limit} cortes para esta transcrição:\n\n{transcript}",
        "text": {"format": {"type": "json_schema", "name": "cortes_sugeridos", "strict": True, "schema": _SCHEMA}},
    }
    try:
        response = requests.post("https://api.openai.com/v1/responses", headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}, json=payload, timeout=90)
    except requests.RequestException as exc:
        raise ClipAIError(f"Não foi possível conectar à OpenAI: {exc}") from exc
    if not response.ok:
        try: message = response.json().get("error", {}).get("message", response.text)
        except ValueError: message = response.text
        raise ClipAIError(f"OpenAI: {message}")
    try:
        data = response.json()
        text = data.get("output_text") or next(part["text"] for output in data["output"] for part in output.get("content", []) if part.get("type") == "output_text")
        cuts = json.loads(text)["cuts"]
        lower, upper = min(item.start for item in subtitles), max(item.end for item in subtitles)
        validated: list[ClipSuggestion] = []
        for item in sorted(cuts, key=lambda value: float(value["start"])):
            start = max(lower, float(item["start"]))
            end = min(upper, float(item["end"]))
            if end <= start or not 20 <= end - start <= 90:
                continue
            candidate = ClipSuggestion(start, end, str(item["title"]).strip(), str(item["summary"]).strip(), max(0, min(100, int(item["score"]))))
            if not candidate.title or any(candidate.start < saved.end and candidate.end > saved.start for saved in validated):
                continue
            validated.append(candidate)
            if len(validated) >= requested_limit:
                break
        return validated
    except (KeyError, TypeError, ValueError, StopIteration, json.JSONDecodeError) as exc:
        raise ClipAIError("A resposta da IA não teve o formato esperado. Tente novamente.") from exc
