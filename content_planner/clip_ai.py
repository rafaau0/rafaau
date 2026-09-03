"""Análise contextual de cortes pela API privada do Neiva."""
from __future__ import annotations

import json

import requests

from .clip_finder import ClipSuggestion
from .video_subtitles import Subtitle


class ClipAIError(RuntimeError):
    pass


def analyze_cuts(subtitles: list[Subtitle], api_url: str, access_token: str, limit: int = 8) -> list[ClipSuggestion]:
    """Envia apenas a transcrição para a API hospedada pelo Neiva."""
    if not api_url or not access_token:
        raise ClipAIError("Configure a URL e a chave de acesso da IA Neiva em Configurações.")
    if not any(item.text.strip() for item in subtitles):
        return []
    requested_limit = max(0, int(limit))
    if requested_limit == 0:
        return []
    payload = {"subtitles": [{"start": item.start, "end": item.end, "text": item.text} for item in subtitles], "limit": requested_limit}
    try:
        response = requests.post(f"{api_url.rstrip('/')}/v1/cuts", headers={"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}, json=payload, timeout=105)
    except requests.RequestException as exc:
        raise ClipAIError(f"Não foi possível conectar à IA Neiva: {exc}") from exc
    if not response.ok:
        try: message = response.json().get("detail", response.json().get("error", response.text))
        except ValueError: message = response.text
        raise ClipAIError(f"IA Neiva: {message}")
    try:
        cuts = response.json()["cuts"]
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
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise ClipAIError("A resposta da IA não teve o formato esperado. Tente novamente.") from exc
