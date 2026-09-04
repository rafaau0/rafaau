from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from ai_service.app.main import Account, Base, Client, ensure_free_client, start_trello_oauth
from content_planner.plan_rules import current_plan_rules


class PlanTests(unittest.TestCase):
    def test_desktop_free_plan_limits_paid_features(self) -> None:
        with patch("content_planner.plan_rules.current_account", return_value=SimpleNamespace(plan="free")):
            rules = current_plan_rules()
        self.assertEqual(rules.max_clients, 1)
        self.assertEqual(rules.max_monthly_posts, 15)
        self.assertEqual(rules.max_monthly_pdfs, 1)
        self.assertFalse(rules.video)
        self.assertFalse(rules.trello)
        self.assertFalse(rules.offer_flyer)

    def test_new_account_receives_free_license(self) -> None:
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        with Session(engine) as session:
            account = Account(name="Conta Grátis", email="free@example.com", password_hash="hash")
            session.add(account)
            session.flush()
            client = ensure_free_client(session, account)
            self.assertEqual(client.plan_code, "free")
            self.assertEqual(client.monthly_limit, 0)
            self.assertEqual(client.device_limit, 1)

    def test_free_plan_cannot_start_trello_oauth(self) -> None:
        client = Client(name="Grátis", token_hash="hash", plan_code="free")
        with self.assertRaises(HTTPException) as raised:
            start_trello_oauth(client, None)
        self.assertEqual(raised.exception.status_code, 403)


if __name__ == "__main__":
    unittest.main()
