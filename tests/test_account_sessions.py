import unittest
from unittest.mock import patch

from content_planner import account_sessions


class AccountSessionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.store: dict[str, str] = {}
        self.get_patch = patch.object(account_sessions, "get_secret", side_effect=lambda key, legacy_value="": self.store.get(key, legacy_value))
        self.set_patch = patch.object(account_sessions, "set_secret", side_effect=lambda key, value: self.store.__setitem__(key, value))
        self.get_patch.start()
        self.set_patch.start()

    def tearDown(self) -> None:
        self.get_patch.stop()
        self.set_patch.stop()

    def test_multiple_accounts_can_be_saved_and_switched(self) -> None:
        first = account_sessions.save_account({"id": 1, "name": "Ana", "email": "ana@example.com", "plan": "pro"}, "token-a")
        second = account_sessions.save_account({"id": 2, "name": "Bia", "email": "bia@example.com"}, "token-b")
        self.assertEqual(len(account_sessions.saved_accounts()), 2)
        self.assertEqual(account_sessions.current_account(), second)
        account_sessions.activate_account(first.account_id)
        self.assertEqual(account_sessions.current_token(), "token-a")
        self.assertEqual(self.store["NEIVA_ACCOUNT_EMAIL"], "ana@example.com")

    def test_logout_preserves_and_activates_another_account(self) -> None:
        first = account_sessions.save_account({"id": 1, "name": "Ana", "email": "ana@example.com"}, "token-a")
        second = account_sessions.save_account({"id": 2, "name": "Bia", "email": "bia@example.com"}, "token-b")
        account_sessions.remove_account(second.account_id)
        self.assertEqual(account_sessions.current_account(), first)
        self.assertEqual(account_sessions.current_token(), "token-a")


if __name__ == "__main__":
    unittest.main()
