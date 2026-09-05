from __future__ import annotations

import os
import threading
from dataclasses import dataclass
from typing import Any

import requests

from .database import Post


TRELLO_API_URL = "https://api.trello.com/1"


@dataclass(slots=True)
class TrelloConfig:
    api_key: str
    token: str
    board_id: str
    source_id: str = ""

    @classmethod
    def from_environment(cls, saved_values: dict[str, str] | None = None) -> "TrelloConfig":
        saved_values = saved_values or {}
        return cls(
            api_key=saved_values.get("TRELLO_API_KEY", "") or os.getenv("TRELLO_API_KEY", ""),
            token=saved_values.get("TRELLO_TOKEN", "") or os.getenv("TRELLO_TOKEN", ""),
            board_id=saved_values.get("TRELLO_BOARD_ID", "") or os.getenv("TRELLO_BOARD_ID", ""),
            source_id=saved_values.get("TRELLO_SOURCE_ID", ""),
        )

    def is_complete(self) -> bool:
        return bool(self.api_key and self.token and self.board_id)


class TrelloAPI:
    """Small Trello client kept independent from the desktop interface."""

    _locks_guard = threading.Lock()
    _card_locks: dict[str, threading.Lock] = {}

    def __init__(self, config: TrelloConfig | None = None) -> None:
        self.config = config or TrelloConfig.from_environment()

    def _auth_params(self) -> dict[str, str]:
        if not self.config.is_complete():
            raise ValueError("Configure TRELLO_API_KEY, TRELLO_TOKEN e TRELLO_BOARD_ID.")
        return {"key": self.config.api_key, "token": self.config.token}

    def create_list(self, name: str) -> str:
        payload = {**self._auth_params(), "name": name, "idBoard": self.config.board_id, "pos": "top"}
        response = requests.post(f"{TRELLO_API_URL}/lists", data=payload, timeout=20)
        response.raise_for_status()
        return str(response.json()["id"])

    def find_list(self, name: str) -> str | None:
        response = requests.get(
            f"{TRELLO_API_URL}/boards/{self.config.board_id}/lists",
            params={**self._auth_params(), "filter": "open", "fields": "id,name"},
            timeout=20,
        )
        response.raise_for_status()
        for item in response.json():
            if str(item.get("name", "")) == name:
                return str(item["id"])
        return None

    def get_or_create_list(self, name: str) -> str:
        return self.find_list(name) or self.create_list(name)

    def _post_marker(self, post: Post) -> str:
        if post.id is None:
            raise ValueError("Post sem identificador local.")
        namespace = self.config.source_id.strip()
        return f"<!-- neiva-planner-post:{namespace}:{post.id} -->" if namespace else f"<!-- neiva-planner-post:{post.id} -->"

    def find_card_for_post(self, post: Post) -> str | None:
        marker = self._post_marker(post)
        response = requests.get(
            f"{TRELLO_API_URL}/boards/{self.config.board_id}/cards",
            params={**self._auth_params(), "filter": "open", "fields": "id,desc"},
            timeout=20,
        )
        response.raise_for_status()
        for item in response.json():
            if marker in str(item.get("desc", "")):
                return str(item["id"])
        return None

    def create_card(self, list_id: str, post: Post) -> str:
        payload: dict[str, Any] = {
            **self._auth_params(),
            "idList": list_id,
            "name": f"{post.post_date} | {post.content_type} | {post.title}",
            "desc": self._build_description(post),
            "due": f"{post.post_date}T12:00:00.000Z",
            "pos": "bottom",
        }
        response = requests.post(f"{TRELLO_API_URL}/cards", data=payload, timeout=20)
        response.raise_for_status()
        return str(response.json()["id"])

    def get_or_create_card(self, list_id: str, post: Post) -> str:
        marker = self._post_marker(post)
        lock_key = f"{self.config.board_id}:{marker}"
        with self._locks_guard:
            lock = self._card_locks.setdefault(lock_key, threading.Lock())
        with lock:
            return self.find_card_for_post(post) or self.create_card(list_id, post)

    def create_cards_for_posts(self, list_name: str, posts: list[Post]) -> dict[int, str]:
        list_id = self.get_or_create_list(list_name)
        created: dict[int, str] = {}
        for post in posts:
            if post.id is None:
                continue
            created[post.id] = self.get_or_create_card(list_id, post)
        return created

    def _build_description(self, post: Post) -> str:
        return (
            f"Status: {post.status}\n"
            f"Plataforma: {post.platform}\n"
            f"Tipo: {post.content_type}\n"
            f"Data: {post.post_date}\n\n"
            f"Descrição:\n{post.description}\n\n"
            f"Legenda:\n{post.caption}\n\n"
            f"CTA:\n{post.cta}\n\n{self._post_marker(post)}"
        )
