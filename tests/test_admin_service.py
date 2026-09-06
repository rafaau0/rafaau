from __future__ import annotations

import unittest
from http.cookies import SimpleCookie
from unittest.mock import patch

from fastapi import HTTPException, Request, Response
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from ai_service.app.main import (
    ADMIN_COOKIE_NAME,
    Account,
    AdminAuditLog,
    AdminIdentity,
    AdminLoginRequest,
    AdminSession,
    AdminUser,
    AdminClientUpdateRequest,
    Base,
    Client,
    DeviceToken,
    admin_csrf_token,
    admin_customer_detail,
    admin_sign_in,
    bootstrap_admin,
    current_admin,
    current_admin_write,
    password_hash,
    revoke_admin_device,
    token_hash,
    update_admin_customer,
    verify_password,
)


class AdminServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.environment = {"ADMIN_SESSION_SECRET": "admin-session-test-secret", "ADMIN_COOKIE_SECURE": "false"}

    def test_admin_login_uses_httponly_cookie_and_csrf(self) -> None:
        with Session(self.engine) as session, patch.dict("os.environ", self.environment):
            user = AdminUser(email="owner@example.com", password_hash=password_hash("strong-admin-password"))
            session.add(user)
            session.commit()
            response = Response()

            result = admin_sign_in(
                AdminLoginRequest(email="owner@example.com", password="strong-admin-password"),
                response,
                session,
                "203.0.113.50",
                None,
            )

            cookie = SimpleCookie()
            cookie.load(response.headers["set-cookie"])
            raw_token = cookie[ADMIN_COOKIE_NAME].value
            self.assertTrue(cookie[ADMIN_COOKIE_NAME]["httponly"])
            self.assertEqual(result["csrf_token"], admin_csrf_token(raw_token))
            self.assertIsNotNone(session.scalar(select(AdminSession).where(AdminSession.token_hash == token_hash(raw_token))))

    def test_explicit_password_reset_revokes_existing_admin_sessions(self) -> None:
        with Session(self.engine) as session:
            user = AdminUser(email="owner@example.com", password_hash=password_hash("old-strong-password"))
            session.add(user)
            session.flush()
            from datetime import datetime, timedelta, timezone
            session.add(AdminSession(
                admin_user_id=user.id,
                token_hash=token_hash("existing-session"),
                expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
            ))
            session.commit()

            self.assertEqual(bootstrap_admin(session, user.email, "new-strong-password", True), "reset")
            self.assertTrue(verify_password("new-strong-password", user.password_hash))
            self.assertFalse(verify_password("old-strong-password", user.password_hash))
            self.assertIsNone(session.scalar(select(AdminSession)))
            self.assertEqual(session.scalar(select(AdminAuditLog)).action, "admin.password_reset")

    def test_session_and_csrf_are_required(self) -> None:
        with Session(self.engine) as session, patch.dict("os.environ", self.environment):
            user = AdminUser(email="owner@example.com", password_hash="hash")
            session.add(user)
            session.flush()
            raw_token = "admin-raw-token"
            from datetime import datetime, timedelta, timezone
            session.add(AdminSession(
                admin_user_id=user.id,
                token_hash=token_hash(raw_token),
                expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
            ))
            session.commit()
            request = Request({"type": "http", "headers": [(b"cookie", f"{ADMIN_COOKIE_NAME}={raw_token}".encode())]})
            identity = current_admin(request, session)
            self.assertEqual(identity.user.email, "owner@example.com")
            with self.assertRaises(HTTPException) as raised:
                current_admin_write(None, identity)
            self.assertEqual(raised.exception.status_code, 403)
            self.assertEqual(current_admin_write(admin_csrf_token(raw_token), identity), identity)

    def test_customer_changes_and_device_revocation_are_audited(self) -> None:
        with Session(self.engine) as session:
            admin_user = AdminUser(email="owner@example.com", password_hash="hash")
            account = Account(name="Cliente", email="cliente@example.com", password_hash="hash")
            session.add_all([admin_user, account])
            session.flush()
            client = Client(name="Cliente [free]", token_hash="token", account_id=account.id, plan_code="free")
            session.add(client)
            session.flush()
            device = DeviceToken(client_id=client.id, token_hash="device-token", device_id="device-identifier-123")
            session.add(device)
            session.commit()
            identity = AdminIdentity(admin_user, "raw")

            updated = update_admin_customer(
                client.id,
                AdminClientUpdateRequest(plan_code="pro", active=False, account_active=False, reason="Atendimento solicitado pelo titular"),
                identity,
                session,
            )
            self.assertEqual(updated["plan_code"], "pro")
            self.assertFalse(updated["active"])
            self.assertEqual(updated["monthly_limit"], 80)
            self.assertFalse(account.active)

            detail = admin_customer_detail(client.id, identity, session)
            self.assertNotIn("token_hash", detail)
            self.assertNotIn("password_hash", detail)
            self.assertEqual(detail["devices"][0]["label"], "Dispositivo ••••er-123")

            self.assertEqual(
                revoke_admin_device(client.id, device.id, "Troca de computador autorizada", identity, session),
                {"ok": True},
            )
            self.assertIsNone(session.get(DeviceToken, device.id))
            actions = [entry.action for entry in session.scalars(select(AdminAuditLog).order_by(AdminAuditLog.id)).all()]
            self.assertEqual(actions, ["customer.updated", "device.revoked"])


if __name__ == "__main__":
    unittest.main()
