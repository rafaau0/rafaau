from __future__ import annotations

import os
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

    @classmethod
    def from_environment(cls, saved_values: dict[str, str] | None = None) -> "TrelloConfig":
        saved_values = saved_values or {}
        return cls(
            api_key=os.getenv("TRELLO_API_KEY", saved_values.get("TRELLO_API_KEY", "")),
            token=os.getenv("TRELLO_TOKEN", saved_values.get("TRELLO_TOKEN", "")),
            board_id=os.getenv("TRELLO_BOARD_ID", saved_values.get("TRELLO_BOARD_ID", "")),
        )

    def is_complete(self) -> bool:
        return bool(self.api_key and self.token and self.board_id)


class TrelloAPI:
    """Small Trello client kept independent from the desktop interface."""

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

    def create_cards_for_posts(self, list_name: str, posts: list[Post]) -> dict[int, str]:
        list_id = self.create_list(list_name)
        created: dict[int, str] = {}
        for post in posts:
            if post.id is None:
                continue
            created[post.id] = self.create_card(list_id, post)
        return created

    @staticmethod
    def _build_description(post: Post) -> str:
        return (
            f"Status: {post.status}\n"
            f"Plataforma: {post.platform}\n"
            f"Tipo: {post.content_type}\n"
            f"Data: {post.post_date}\n\n"
            f"Descrição:\n{post.description}\n\n"
            f"Legenda:\n{post.caption}\n\n"
            f"CTA:\n{post.cta}"
        )
