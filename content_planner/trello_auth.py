from __future__ import annotations

import json
import os
import time
import webbrowser
from dataclasses import dataclass
from pathlib import Path

import requests

from .account_login import API_URL
from .account_sessions import account_secret_key
from .secrets import get_secret


TRELLO_API_URL = "https://api.trello.com/1"


class TrelloAuthError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class TrelloIdentity:
    member_id: str
    full_name: str
    username: str


@dataclass(frozen=True, slots=True)
class TrelloBoard:
    board_id: str
    name: str


def _packaged_root() -> Path:
    import sys

    return Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))


def get_app_key() -> str:
    """Obtém a chave pública do aplicativo, sem exigir configuração do cliente."""
    environment = os.getenv("TRELLO_APP_KEY", "").strip()
    if environment:
        return environment
    config_path = _packaged_root() / "assets" / "trello_app.json"
    if config_path.is_file():
        try:
            return str(json.loads(config_path.read_text(encoding="utf-8")).get("api_key", "")).strip()
        except (OSError, ValueError, TypeError):
            pass
    # Compatibilidade com instalações que já tinham a chave configurada manualmente.
    return get_secret(account_secret_key("TRELLO_API_KEY")).strip()


def authorize(timeout: int = 300) -> tuple[str, str]:
    """Autoriza pelo callback HTTPS da API e entrega a credencial uma única vez."""
    client_token = get_secret("NEIVA_AI_CLIENT_TOKEN")
    if not client_token:
        raise TrelloAuthError("Entre na sua conta rafaau antes de conectar o Trello.")
    headers = {"Authorization": f"Bearer {client_token}"}
    try:
        response = requests.post(f"{API_URL}/v1/integrations/trello/start", headers=headers, timeout=30)
        if not response.ok:
            try:
                message = response.json().get("detail", response.text)
            except ValueError:
                message = response.text
            raise TrelloAuthError(message or "Não foi possível iniciar a conexão com o Trello.")
        payload = response.json()
        connection_id = str(payload["connection_id"])
        authorize_url = str(payload["authorize_url"])
        if not webbrowser.open(authorize_url):
            raise TrelloAuthError("Não foi possível abrir o navegador para conectar ao Trello.")
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            time.sleep(2)
            status_response = requests.get(
                f"{API_URL}/v1/integrations/trello/status/{connection_id}",
                headers=headers,
                timeout=20,
            )
            status_response.raise_for_status()
            result = status_response.json()
            if result.get("status") == "complete":
                return str(result["api_key"]), str(result["token"])
            if result.get("status") in {"failed", "expired"}:
                raise TrelloAuthError(str(result.get("message") or "A autorização do Trello não foi concluída."))
        raise TrelloAuthError("O tempo para autorizar o Trello terminou. Tente novamente.")
    except TrelloAuthError:
        raise
    except (requests.RequestException, KeyError, TypeError, ValueError) as exc:
        raise TrelloAuthError("Não foi possível concluir a conexão segura com o Trello.") from exc


def get_identity(api_key: str, token: str) -> TrelloIdentity:
    try:
        response = requests.get(
            f"{TRELLO_API_URL}/members/me",
            params={"key": api_key, "token": token, "fields": "fullName,username"},
            timeout=20,
        )
        response.raise_for_status()
        data = response.json()
        return TrelloIdentity(str(data["id"]), str(data.get("fullName", "")), str(data.get("username", "")))
    except (requests.RequestException, KeyError, TypeError, ValueError) as exc:
        raise TrelloAuthError("Não foi possível validar a conta do Trello.") from exc


def list_boards(api_key: str, token: str) -> list[TrelloBoard]:
    try:
        response = requests.get(
            f"{TRELLO_API_URL}/members/me/boards",
            params={"key": api_key, "token": token, "fields": "name", "filter": "open"},
            timeout=20,
        )
        response.raise_for_status()
        boards = response.json()
        return sorted((TrelloBoard(str(item["id"]), str(item["name"])) for item in boards), key=lambda item: item.name.casefold())
    except (requests.RequestException, KeyError, TypeError, ValueError) as exc:
        raise TrelloAuthError("Não foi possível carregar os quadros do Trello.") from exc
