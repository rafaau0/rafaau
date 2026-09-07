from __future__ import annotations

import tempfile
import unittest
import sqlite3
from datetime import date, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from content_planner.client_management import contract_display_status, format_date_br, format_money, parse_date_input, parse_money_to_cents
from content_planner.database import DATABASE_DIR, Client, Contract, Database, Post, account_database_path


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

        self.assertEqual(
            self.database.dashboard_stats(),
            {
                "clients": 1,
                "posts": 1,
                "pending": 0,
                "done": 1,
                "active_clients": 1,
                "active_contracts": 0,
                "expiring_contracts": 0,
                "expired_contracts": 0,
                "monthly_revenue_cents": 0,
            },
        )
        self.assertEqual([post.id for post in self.database.get_posts_pending_trello(self.client_id, 2026, 8)], [post_id])

        self.database.update_post_trello_card(post_id, "card-123")
        self.assertEqual(self.database.get_posts_pending_trello(self.client_id, 2026, 8), [])
        self.assertEqual([post.id for post in self.database.get_posts_pending_trello(self.client_id, 2026, 8, "other-board")], [post_id])
        self.database.update_post_trello_card(post_id, "card-123", "other-board")
        self.assertEqual(self.database.get_posts_pending_trello(self.client_id, 2026, 8, "other-board"), [])

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

    def test_client_profile_contract_and_attachment_lifecycle(self) -> None:
        client = self.database.get_client(self.client_id)
        self.assertIsNotNone(client)
        client.company_name = "Empresa Teste Ltda"
        client.document = "00.000.000/0001-00"
        client.email = "contato@example.com"
        client.phone = "(11) 99999-0000"
        client.contact_name = "Responsável"
        self.database.update_client(client)

        source = Path(self.temp_dir.name) / "contrato.pdf"
        source.write_bytes(b"%PDF-1.4\n% test")
        attachment = self.database.import_contract_attachment(source, self.client_id)
        start = date.today().isoformat()
        end = (date.today() + timedelta(days=20)).isoformat()
        contract_id = self.database.create_contract(
            Contract(
                None,
                self.client_id,
                "Gestão de conteúdo",
                value_cents=250_000,
                start_date=start,
                end_date=end,
                due_day=10,
                status="Ativo",
                attachment_path=attachment,
            )
        )
        self.database.create_contract(
            Contract(
                None,
                self.client_id,
                "Contrato vencido",
                value_cents=90_000,
                start_date=(date.today() - timedelta(days=40)).isoformat(),
                end_date=(date.today() - timedelta(days=1)).isoformat(),
                status="Ativo",
            )
        )

        saved = self.database.get_contract(contract_id)
        self.assertEqual(saved.title, "Gestão de conteúdo")
        self.assertTrue(Path(saved.attachment_path).is_file())
        self.assertEqual(self.database.search_clients("empresa")[0].id, self.client_id)
        stats = self.database.dashboard_stats()
        self.assertEqual(stats["active_contracts"], 1)
        self.assertEqual(stats["expiring_contracts"], 1)
        self.assertEqual(stats["expired_contracts"], 1)
        self.assertEqual(stats["monthly_revenue_cents"], 250_000)
        self.assertEqual(self.database.expiring_contracts()[0][1].email, "contato@example.com")

        self.database.delete_contract(contract_id)
        self.assertIsNone(self.database.get_contract(contract_id))
        self.assertFalse(Path(attachment).exists())

        second_attachment = self.database.import_contract_attachment(source, self.client_id)
        self.database.create_contract(
            Contract(None, self.client_id, "Contrato final", attachment_path=second_attachment)
        )
        self.database.delete_client(self.client_id)
        self.assertFalse(Path(second_attachment).exists())
        self.assertEqual(self.database.list_contracts(self.client_id), [])

    def test_existing_database_receives_additive_client_and_contract_schema(self) -> None:
        path = Path(self.temp_dir.name) / "legacy.db"
        connection = sqlite3.connect(path)
        try:
            connection.execute(
                """
                CREATE TABLE clientes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL,
                    niche TEXT NOT NULL DEFAULT '', instagram TEXT NOT NULL DEFAULT '',
                    posting_frequency TEXT NOT NULL DEFAULT '', objective TEXT NOT NULL DEFAULT '',
                    notes TEXT NOT NULL DEFAULT '', created_at TEXT, updated_at TEXT
                )
                """
            )
            connection.execute("INSERT INTO clientes (name) VALUES ('Legado')")
            connection.commit()
        finally:
            connection.close()

        migrated = Database(path)
        legacy = migrated.get_client(1)
        self.assertEqual(legacy.status, "Ativo")
        self.assertEqual(legacy.email, "")
        self.assertEqual(migrated.list_contracts(1), [])

    def test_client_management_formatters_validate_brazilian_input(self) -> None:
        self.assertEqual(parse_date_input("06/09/2026"), "2026-09-06")
        self.assertEqual(format_date_br("2026-09-06"), "06/09/2026")
        self.assertEqual(parse_money_to_cents("R$ 1.234,56"), 123_456)
        self.assertEqual(format_money(123_456), "R$ 1.234,56")
        self.assertEqual(contract_display_status("Ativo", (date.today() + timedelta(days=5)).isoformat()), "Vence em breve")


if __name__ == "__main__":
    unittest.main()
