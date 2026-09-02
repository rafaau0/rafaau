from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from content_planner.database import Client, Database, Post


class DatabaseTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
