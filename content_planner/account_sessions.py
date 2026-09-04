"""Gerenciamento local de contas autenticadas no cofre do Windows."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, asdict

from .secrets import get_secret, set_secret


INDEX_KEY = "NEIVA_SAVED_ACCOUNTS"
ACTIVE_KEY = "NEIVA_ACTIVE_ACCOUNT"


@dataclass(frozen=True, slots=True)
class SavedAccount:
    account_id: str
    name: str
    email: str
    plan: str | None = None


def _safe_id(account_id: object, email: str) -> str:
    value = str(account_id or "").strip()
    if value.isdigit():
        return value
    return hashlib.sha256(email.strip().lower().encode("utf-8")).hexdigest()[:20]


def _token_key(account_id: str) -> str:
    return f"NEIVA_ACCOUNT_TOKEN_{account_id}"


def saved_accounts() -> list[SavedAccount]:
    try:
        items = json.loads(get_secret(INDEX_KEY) or "[]")
        return [SavedAccount(**item) for item in items if isinstance(item, dict)]
    except (TypeError, ValueError):
        return []


def current_account() -> SavedAccount | None:
    active_id = get_secret(ACTIVE_KEY)
    return next((account for account in saved_accounts() if account.account_id == active_id), None)


def current_token() -> str:
    account = current_account()
    if account:
        token = get_secret(_token_key(account.account_id))
        if token:
            return token
    return get_secret("NEIVA_AI_CLIENT_TOKEN")


def save_account(account_data: dict, token: str) -> SavedAccount:
    email = str(account_data.get("email", "")).strip().lower()
    account = SavedAccount(
        account_id=_safe_id(account_data.get("id"), email),
        name=str(account_data.get("name", "")).strip() or email,
        email=email,
        plan=str(account_data["plan"]) if account_data.get("plan") else None,
    )
    accounts = [item for item in saved_accounts() if item.account_id != account.account_id]
    accounts.append(account)
    set_secret(INDEX_KEY, json.dumps([asdict(item) for item in accounts], ensure_ascii=False))
    set_secret(_token_key(account.account_id), token)
    activate_account(account.account_id)
    return account


def activate_account(account_id: str) -> SavedAccount:
    account = next((item for item in saved_accounts() if item.account_id == str(account_id)), None)
    if account is None:
        raise ValueError("Conta salva não encontrada.")
    token = get_secret(_token_key(account.account_id))
    if not token:
        raise ValueError("A sessão desta conta expirou. Entre novamente.")
    set_secret(ACTIVE_KEY, account.account_id)
    # Mantém compatibilidade com os módulos que já consomem a licença atual.
    set_secret("NEIVA_AI_CLIENT_TOKEN", token)
    set_secret("NEIVA_ACCOUNT_EMAIL", account.email)
    return account


def remove_account(account_id: str) -> None:
    account_id = str(account_id)
    remaining = [item for item in saved_accounts() if item.account_id != account_id]
    set_secret(_token_key(account_id), "")
    set_secret(INDEX_KEY, json.dumps([asdict(item) for item in remaining], ensure_ascii=False))
    if get_secret(ACTIVE_KEY) == account_id:
        set_secret(ACTIVE_KEY, "")
        set_secret("NEIVA_AI_CLIENT_TOKEN", "")
        set_secret("NEIVA_ACCOUNT_EMAIL", "")
        if remaining:
            activate_account(remaining[0].account_id)

