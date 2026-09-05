"""Regras de produto do plano ativo no aplicativo desktop."""
from __future__ import annotations

from dataclasses import dataclass
import requests

from .account_sessions import current_account, current_token, save_account


API_URL = "https://neiva-ai-api.onrender.com"


@dataclass(frozen=True, slots=True)
class PlanRules:
    code: str
    name: str
    max_clients: int | None
    max_monthly_posts: int | None
    max_monthly_pdfs: int | None
    trello: bool
    video: bool
    offer_flyer: bool


RULES = {
    "free": PlanRules("free", "Grátis", 1, 15, 1, False, False, False),
    "essencial": PlanRules("essencial", "Essencial", 10, None, None, True, True, True),
    "pro": PlanRules("pro", "Pro", None, None, None, True, True, True),
}


def current_plan_rules() -> PlanRules:
    account = current_account()
    # Licenças legadas mantêm todos os recursos para evitar perda de acesso.
    if account is None:
        return RULES["pro"]
    if account.plan == "free":
        return RULES["free"]
    if account.plan not in {"essencial", "pro"}:
        return RULES["free"]
    # Metadados do cofre local não autorizam recursos pagos por si sós. Uma
    # concessão paga precisa ser confirmada pela API no início da interface.
    token = current_token()
    if not token:
        return RULES["free"]
    try:
        response = requests.get(f"{API_URL}/v1/auth/session", headers={"Authorization": f"Bearer {token}"}, timeout=8)
        data = response.json() if response.ok else {}
        remote = data.get("account") if isinstance(data, dict) else None
        if not isinstance(remote, dict) or str(remote.get("id")) != account.account_id:
            return RULES["free"]
        plan = str(remote.get("plan", ""))
        if plan in {"essencial", "pro"} and data.get("license_active"):
            save_account(remote, token)
            return RULES[plan]
    except (requests.RequestException, ValueError):
        pass
    return RULES["free"]
