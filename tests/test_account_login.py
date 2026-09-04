from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from content_planner.account_login import LoginWindow


class AccountLoginTests(unittest.TestCase):
    @staticmethod
    def _window(email: str, password: str) -> SimpleNamespace:
        return SimpleNamespace(
            login_email=Mock(get=Mock(return_value=email)),
            login_password=Mock(get=Mock(return_value=password)),
            login_error=Mock(),
            login_button=Mock(),
            _show_login_error=Mock(),
            _login_request=Mock(),
            _valid_email=LoginWindow._valid_email,
        )

    def test_login_rejects_invalid_email_without_opening_app(self) -> None:
        window = self._window("email-invalido", "senha")
        LoginWindow._submit_login(window)
        window._show_login_error.assert_called_once_with("Informe um e-mail válido.")
        window._login_request.assert_not_called()

    def test_login_rejects_empty_password_without_opening_app(self) -> None:
        window = self._window("cliente@example.com", "")
        LoginWindow._submit_login(window)
        window._show_login_error.assert_called_once_with("Informe sua senha.")
        window._login_request.assert_not_called()

    def test_valid_login_is_sent_to_api_in_background(self) -> None:
        window = self._window(" CLIENTE@EXAMPLE.COM ", "senha-segura")
        thread = Mock()
        with patch("content_planner.account_login.threading.Thread", return_value=thread) as thread_factory:
            LoginWindow._submit_login(window)
        window.login_button.configure.assert_called_once_with(state="disabled", text="ENTRANDO...")
        thread_factory.assert_called_once_with(
            target=window._login_request,
            args=("cliente@example.com", "senha-segura"),
            daemon=True,
        )
        thread.start.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
