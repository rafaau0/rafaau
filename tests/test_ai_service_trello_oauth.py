from __future__ import annotations

import unittest
from unittest.mock import Mock, patch

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from ai_service.app.main import (
    Base,
    Client,
    TrelloOAuthRequest,
    integration_decrypt,
    integration_encrypt,
    start_trello_oauth,
    trello_oauth_callback,
    trello_oauth_status,
)


class TrelloOAuthServiceTests(unittest.TestCase):
    def test_temporary_credentials_are_encrypted_and_recoverable(self) -> None:
        with patch.dict("os.environ", {"TRELLO_API_SECRET": "test-secret-value"}):
            encrypted = integration_encrypt("temporary-oauth-secret")
            self.assertNotIn("temporary-oauth-secret", encrypted)
            self.assertEqual(integration_decrypt(encrypted), "temporary-oauth-secret")

    def test_ciphertext_cannot_be_opened_with_another_secret(self) -> None:
        with patch.dict("os.environ", {"TRELLO_API_SECRET": "first-secret"}):
            encrypted = integration_encrypt("user-token")
        with patch.dict("os.environ", {"TRELLO_API_SECRET": "different-secret"}):
            with self.assertRaises(Exception):
                integration_decrypt(encrypted)

    def test_oauth_result_is_delivered_once_to_originating_client(self) -> None:
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        start_oauth = Mock()
        start_oauth.fetch_request_token.return_value = {
            "oauth_token": "request-token",
            "oauth_token_secret": "request-secret",
        }
        start_oauth.authorization_url.return_value = "https://trello.com/authorize"
        callback_oauth = Mock()
        callback_oauth.fetch_access_token.return_value = {
            "oauth_token": "access-token",
            "oauth_token_secret": "access-secret",
        }
        environment = {
            "TRELLO_API_KEY": "public-key",
            "TRELLO_API_SECRET": "server-only-secret",
            "PUBLIC_API_URL": "https://api.example.test",
        }
        with Session(engine) as session, patch.dict("os.environ", environment), patch(
            "ai_service.app.main.OAuth1Session", side_effect=[start_oauth, callback_oauth]
        ):
            client = Client(name="Cliente OAuth", token_hash="client-token-hash")
            session.add(client)
            session.commit()
            started = start_trello_oauth(client, session)
            pending = session.scalar(select(TrelloOAuthRequest))
            self.assertIsNotNone(pending)
            self.assertNotIn("request-secret", pending.request_secret_encrypted)
            self.assertEqual(started["authorize_url"], "https://trello.com/authorize")

            response = trello_oauth_callback("request-token", "verifier", session)
            self.assertEqual(response.status_code, 200)
            completed = trello_oauth_status(started["connection_id"], client, session)
            self.assertEqual(completed, {"status": "complete", "api_key": "public-key", "token": "access-token"})
            self.assertIsNone(session.scalar(select(TrelloOAuthRequest)))


if __name__ == "__main__":
    unittest.main()
