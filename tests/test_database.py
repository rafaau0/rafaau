from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from content_planner.database import DATABASE_DIR, Client, Database, Post, account_database_path


class DatabaseTests(unittest.TestCase):
    def test_default_database_is_isolated_by_account(self) -> None:
        with patch("content_planner.account_sessions.current_account", return_value=SimpleNamespace(account_id="42")):
            self.assertEqual(account_database_path(), DATABASE_DIR / "accounts" / "42" / "content_planner.db")

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.database = Database(Path(self.temp_dir.name) / "planner.db")
        self.client_id = self.database.create_client(Client(None, "Cliente Teste", "Varejo", "@teste", "3x", "Vender", ""))

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_dashboard_and_trello_pending_posts(self) -> None:
        post_id = self.database.create_post(
            Post(None, self.client_id, "2026-08-31", "Feed", "Instagram", "Oferta", "", "", "", "Concluído")
        )

        self.assertEqual(self.database.dashboard_stats(), {"clients": 1, "posts": 1, "pending": 0, "done": 1})
        self.assertEqual([post.id for post in self.database.get_posts_pending_trello(self.client_id, 2026, 8)], [post_id])

        self.database.update_post_trello_card(post_id, "card-123")
        self.assertEqual(self.database.get_posts_pending_trello(self.client_id, 2026, 8), [])

    def test_settings_are_persisted(self) -> None:
        self.database.set_setting("TRELLO_BOARD_ID", "board-123")
        self.assertEqual(self.database.get_setting("TRELLO_BOARD_ID"), "board-123")
        self.assertEqual(self.database.get_setting("UNKNOWN", "fallback"), "fallback")

    def test_repeated_create_operation_returns_the_original_record(self) -> None:
        operation = "same-ui-submit"
        payload = Client(None, "Outro cliente", "", "", "", "", "", operation)
        first = self.database.create_client(payload)
        second = self.database.create_client(payload)
        self.assertEqual(first, second)
        self.assertEqual(len([item for item in self.database.search_clients() if item.operation_id == operation]), 1)


if __name__ == "__main__":
    unittest.main()
