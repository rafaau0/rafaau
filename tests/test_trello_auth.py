from __future__ import annotations

import unittest
from unittest.mock import Mock, patch

from content_planner.trello_auth import authorize, get_identity, list_boards


class TrelloAuthTests(unittest.TestCase):
    @patch("content_planner.trello_auth.time.sleep")
    @patch("content_planner.trello_auth.time.monotonic", side_effect=[0, 1, 2])
    @patch("content_planner.trello_auth.webbrowser.open", return_value=True)
    @patch("content_planner.trello_auth.get_secret", return_value="client-license-token")
    @patch("content_planner.trello_auth.requests.get")
    @patch("content_planner.trello_auth.requests.post")
    def test_authorize_uses_https_backend_callback(
        self, post: Mock, get: Mock, _secret: Mock, browser: Mock, _clock: Mock, _sleep: Mock
    ) -> None:
        start = Mock(ok=True)
        start.json.return_value = {"connection_id": "connection-1", "authorize_url": "https://trello.com/oauth"}
        post.return_value = start
        pending = Mock()
        pending.json.return_value = {"status": "pending"}
        pending.raise_for_status.return_value = None
        complete = Mock()
        complete.json.return_value = {"status": "complete", "api_key": "public-key", "token": "user-token"}
        complete.raise_for_status.return_value = None
        get.side_effect = [pending, complete]

        self.assertEqual(authorize(), ("public-key", "user-token"))
        post.assert_called_once()
        self.assertTrue(post.call_args.args[0].startswith("https://neiva-ai-api.onrender.com/"))
        browser.assert_called_once_with("https://trello.com/oauth")

    @patch("content_planner.trello_auth.requests.get")
    def test_get_identity(self, request: Mock) -> None:
        response = Mock()
        response.json.return_value = {"id": "member-1", "fullName": "Cliente Teste", "username": "cliente"}
        request.return_value = response
        identity = get_identity("app-key", "token")
        self.assertEqual(identity.full_name, "Cliente Teste")
        response.raise_for_status.assert_called_once()

    @patch("content_planner.trello_auth.requests.get")
    def test_list_boards_is_sorted(self, request: Mock) -> None:
        response = Mock()
        response.json.return_value = [{"id": "2", "name": "Vendas"}, {"id": "1", "name": "Editorial"}]
        request.return_value = response
        boards = list_boards("app-key", "token")
        self.assertEqual([(board.name, board.board_id) for board in boards], [("Editorial", "1"), ("Vendas", "2")])


if __name__ == "__main__":
    unittest.main()
