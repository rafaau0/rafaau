from __future__ import annotations

import unittest
from unittest.mock import Mock, patch

from content_planner.trello_auth import get_identity, list_boards


class TrelloAuthTests(unittest.TestCase):
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
