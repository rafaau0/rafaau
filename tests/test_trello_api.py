from __future__ import annotations

import unittest
from unittest.mock import Mock, patch

from content_planner.database import Post
from content_planner.trello_api import TrelloAPI, TrelloConfig


class TrelloAPITests(unittest.TestCase):
    def setUp(self) -> None:
        self.api = TrelloAPI(TrelloConfig("key", "token", "board"))
        self.post = Post(7, 1, "2026-09-03", "Reel", "Instagram", "Titulo", "", "", "", "Pendente")

    @patch("content_planner.trello_api.requests.get")
    def test_finds_existing_card_by_local_marker(self, request: Mock) -> None:
        response = Mock()
        response.json.return_value = [{"id": "card-1", "desc": "texto <!-- neiva-planner-post:7 -->"}]
        request.return_value = response
        self.assertEqual(self.api.find_card_for_post(self.post), "card-1")

    @patch("content_planner.trello_api.requests.get")
    def test_reuses_existing_list(self, request: Mock) -> None:
        response = Mock()
        response.json.return_value = [{"id": "list-1", "name": "Cliente - Setembro 2026"}]
        request.return_value = response
        self.assertEqual(self.api.get_or_create_list("Cliente - Setembro 2026"), "list-1")

    def test_card_description_has_stable_marker(self) -> None:
        self.assertIn("<!-- neiva-planner-post:7 -->", self.api._build_description(self.post))


if __name__ == "__main__":
    unittest.main()
