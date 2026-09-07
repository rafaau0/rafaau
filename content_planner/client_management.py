"""Regras puras da central local de clientes e contratos."""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP


CLIENT_STATUSES = ["Lead", "Ativo", "Recorrente", "Inativo", "Arquivado"]
CONTRACT_STATUSES = ["Rascunho", "Ativo", "Encerrado", "Cancelado"]


def parse_date_input(value: str, *, required: bool = False) -> str:
    """Aceita DD/MM/AAAA ou ISO e devolve a data ISO usada pelo SQLite."""
    cleaned = value.strip()
    if not cleaned:
        if required:
            raise ValueError("A data é obrigatória.")
        return ""
    for pattern in ("%d/%m/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(cleaned, pattern).date().isoformat()
        except ValueError:
            continue
    raise ValueError("Use uma data válida no formato DD/MM/AAAA.")


def format_date_br(value: str) -> str:
    if not value:
        return "—"
    try:
        return date.fromisoformat(value).strftime("%d/%m/%Y")
    except ValueError:
        return "—"


def parse_money_to_cents(value: str) -> int:
    cleaned = value.strip().replace("R$", "").replace(" ", "")
    if not cleaned:
        return 0
    if "," in cleaned:
        cleaned = cleaned.replace(".", "").replace(",", ".")
    try:
        amount = Decimal(cleaned).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except InvalidOperation as exc:
        raise ValueError("Informe um valor monetário válido.") from exc
    if not amount.is_finite():
        raise ValueError("Informe um valor monetário finito.")
    if amount < 0:
        raise ValueError("O valor do contrato não pode ser negativo.")
    return int(amount * 100)


def format_money(value_cents: int) -> str:
    value = Decimal(value_cents) / 100
    whole, decimal = f"{value:,.2f}".split(".")
    return f"R$ {whole.replace(',', '.')},{decimal}"


def contract_display_status(status: str, end_date: str, today: date | None = None) -> str:
    if status != "Ativo" or not end_date:
        return status
    reference = today or date.today()
    try:
        remaining = (date.fromisoformat(end_date) - reference).days
    except ValueError:
        return status
    if remaining < 0:
        return "Vencido"
    if remaining <= 30:
        return "Vence em breve"
    return status
