from __future__ import annotations

import json
import os
import queue
import threading
import webbrowser
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlencode

import requests

from .secrets import get_secret


TRELLO_AUTHORIZE_URL = "https://trello.com/1/authorize"
TRELLO_API_URL = "https://api.trello.com/1"
CALLBACK_HOST = "127.0.0.1"
CALLBACK_PORT = 8765


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
    return get_secret("TRELLO_API_KEY").strip()


def _callback_page() -> bytes:
    return b"""<!doctype html><html lang='pt-BR'><head><meta charset='utf-8'>
<title>Neiva Planner - Trello</title></head><body style='font-family:Segoe UI;padding:40px'>
<h2>Conectando ao Neiva Planner...</h2><p id='status'>Aguarde enquanto concluimos a autorizacao.</p>
<script>
const data = new URLSearchParams(location.hash.slice(1));
fetch('/token', {method:'POST', headers:{'Content-Type':'application/json'},
 body:JSON.stringify({token:data.get('token') || '', error:data.get('error') || ''})})
 .then(() => { document.getElementById('status').textContent = data.get('token')
   ? 'Trello conectado. Voce pode fechar esta janela.'
   : 'A autorizacao nao foi concluida. Volte ao Neiva Planner.'; })
 .catch(() => { document.getElementById('status').textContent = 'Nao foi possivel retornar ao Neiva Planner.'; });
</script></body></html>"""


def authorize(api_key: str, timeout: int = 180) -> str:
    if not api_key:
        raise TrelloAuthError("A chave pública do aplicativo Trello não foi configurada nesta versão do Neiva Planner.")
    result: queue.Queue[dict[str, str]] = queue.Queue(maxsize=1)

    class CallbackHandler(BaseHTTPRequestHandler):
        def log_message(self, _format, *args) -> None:
            return

        def do_GET(self) -> None:
            if self.path.split("?", 1)[0] != "/callback":
                self.send_error(404)
                return
            page = _callback_page()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(page)))
            self.end_headers()
            self.wfile.write(page)

        def do_POST(self) -> None:
            if self.path != "/token":
                self.send_error(404)
                return
            try:
                size = min(int(self.headers.get("Content-Length", "0")), 8192)
                payload = json.loads(self.rfile.read(size).decode("utf-8"))
                result.put_nowait({"token": str(payload.get("token", "")), "error": str(payload.get("error", ""))})
                self.send_response(204)
                self.end_headers()
            except (ValueError, TypeError, queue.Full):
                self.send_error(400)

    try:
        server = ThreadingHTTPServer((CALLBACK_HOST, CALLBACK_PORT), CallbackHandler)
    except OSError as exc:
        raise TrelloAuthError(f"Não foi possível iniciar o retorno do login na porta {CALLBACK_PORT}: {exc}") from exc
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return_url = f"http://localhost:{CALLBACK_PORT}/callback"
    params = {
        "expiration": "never",
        "scope": "read,write",
        "response_type": "token",
        "key": api_key,
        "name": "Neiva Planner",
        "return_url": return_url,
        "callback_method": "fragment",
    }
    try:
        if not webbrowser.open(f"{TRELLO_AUTHORIZE_URL}?{urlencode(params)}"):
            raise TrelloAuthError("Não foi possível abrir o navegador para conectar ao Trello.")
        try:
            payload = result.get(timeout=timeout)
        except queue.Empty as exc:
            raise TrelloAuthError("O tempo para autorizar o Trello terminou. Tente novamente.") from exc
    finally:
        server.shutdown()
        server.server_close()
    token = payload.get("token", "").strip()
    if not token:
        raise TrelloAuthError(payload.get("error") or "A autorização do Trello foi cancelada.")
    return token


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
