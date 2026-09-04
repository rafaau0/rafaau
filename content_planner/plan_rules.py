"""Regras de produto do plano ativo no aplicativo desktop."""
from __future__ import annotations

from dataclasses import dataclass
from .account_sessions import current_account


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
    return RULES.get(account.plan if account else None, RULES["pro"])
