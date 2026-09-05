from __future__ import annotations

import unittest
from unittest.mock import Mock, patch

from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from ai_service.app.main import (
    Account,
    AccountLoginRequest,
    Base,
    CheckoutOrder,
    CheckoutRequest,
    Client,
    DeviceToken,
    MonthlyUsage,
    Subscription,
    app_logout,
    asaas_webhook,
    consume_quota,
    create_checkout,
    current_client,
    refund_quota,
    sign_in_account,
    token_hash,
)


class SecurityAndBillingRegressionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)

    def test_logout_revokes_the_presented_device_token(self) -> None:
        with Session(self.engine) as session:
            client = Client(name="Logout", token_hash=token_hash("legacy"))
            session.add(client)
            session.flush()
            session.add(DeviceToken(client_id=client.id, token_hash=token_hash("device"), device_id="device-identifier-123"))
            session.commit()

            result = app_logout(HTTPAuthorizationCredentials(scheme="Bearer", credentials="device"), session)

            self.assertEqual(result, {"ok": True})
            self.assertIsNone(session.scalar(select(DeviceToken)))

    def test_inactive_account_cannot_use_an_existing_device_token(self) -> None:
        with Session(self.engine) as session:
            account = Account(name="Bloqueada", email="blocked@example.com", password_hash="hash", active=False)
            session.add(account)
            session.flush()
            client = Client(name="Blocked client", token_hash=token_hash("legacy"), account_id=account.id)
            session.add(client)
            session.flush()
            session.add(DeviceToken(client_id=client.id, token_hash=token_hash("device"), device_id="device-identifier-123"))
            session.commit()

            with self.assertRaises(HTTPException) as raised:
                current_client(HTTPAuthorizationCredentials(scheme="Bearer", credentials="device"), session)

            self.assertEqual(raised.exception.status_code, 401)

    def test_repeated_invalid_passwords_are_temporarily_limited(self) -> None:
        payload = AccountLoginRequest(email="target@example.com", password="wrong-password")
        with Session(self.engine) as session:
            for _ in range(8):
                with self.assertRaises(HTTPException) as raised:
                    sign_in_account(payload, session, "203.0.113.10", None)
                self.assertEqual(raised.exception.status_code, 401)
            with self.assertRaises(HTTPException) as limited:
                sign_in_account(payload, session, "203.0.113.10", None)
            self.assertEqual(limited.exception.status_code, 429)

    def test_failed_ai_reservation_can_be_refunded_without_losing_quota(self) -> None:
        with Session(self.engine) as session:
            client = Client(name="Quota", token_hash="hash", plan_code="essencial", monthly_limit=1)
            session.add(client)
            session.commit()

            reservation = consume_quota(session, client)
            with self.assertRaises(HTTPException) as raised:
                consume_quota(session, client)
            self.assertEqual(raised.exception.status_code, 429)

            refund_quota(session, reservation)
            consume_quota(session, client)
            usage = session.scalar(select(MonthlyUsage))
            self.assertEqual(usage.requests_count, 1)

    def test_older_payment_event_does_not_reactivate_and_renewal_does(self) -> None:
        with Session(self.engine) as session, patch.dict("os.environ", {"ASAAS_WEBHOOK_TOKEN": "webhook-secret"}):
            client = Client(name="Subscriber", token_hash="hash", plan_code="pro", monthly_limit=80)
            session.add(client)
            session.flush()
            session.add(Subscription(client_id=client.id, provider_subscription_id="sub-1", plan_code="pro", status="active"))
            session.commit()

            def notify(event_id: str, event: str, event_date: str) -> None:
                asaas_webhook(
                    {
                        "id": event_id,
                        "event": event,
                        "payment": {"subscription": "sub-1", "dateCreated": event_date, "dueDate": event_date},
                    },
                    "webhook-secret",
                    session,
                )

            notify("overdue", "PAYMENT_OVERDUE", "2026-05-10")
            self.assertFalse(client.active)
            notify("old-confirmation", "PAYMENT_CONFIRMED", "2026-05-01")
            self.assertFalse(client.active)
            notify("renewal", "PAYMENT_CONFIRMED", "2026-06-01")
            self.assertTrue(client.active)
            self.assertEqual(session.scalar(select(Subscription)).status, "active")

    def test_checkout_reuses_the_same_provider_session_for_an_idempotency_key(self) -> None:
        response = Mock(ok=True, status_code=200)
        response.json.return_value = {"id": "checkout-123"}
        environment = {
            "ASAAS_API_KEY": "asaas-key",
            "ASAAS_BASE_URL": "https://sandbox.asaas.com/api/v3",
            "ASAAS_WEBHOOK_TOKEN": "webhook-secret",
            "SITE_URL": "https://example.test",
        }
        with Session(self.engine) as session, patch.dict("os.environ", environment), patch(
            "ai_service.app.main.requests.post", return_value=response
        ) as post:
            account = Account(name="Buyer", email="buyer@example.com", password_hash="hash")
            session.add(account)
            session.commit()

            first = create_checkout(CheckoutRequest(plan_code="essencial"), account, session, "checkout-attempt-0001")
            second = create_checkout(CheckoutRequest(plan_code="essencial"), account, session, "checkout-attempt-0001")

            self.assertEqual(first, second)
            self.assertEqual(post.call_count, 1)
            self.assertEqual(session.scalars(select(CheckoutOrder)).all().__len__(), 1)


if __name__ == "__main__":
    unittest.main()
