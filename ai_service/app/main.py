"""API privada: a chave OpenAI permanece exclusivamente no servidor."""
from __future__ import annotations

import hashlib
import hmac
import html
import json
import logging
import os
import re
import secrets
from base64 import urlsafe_b64decode, urlsafe_b64encode
from datetime import datetime, timedelta, timezone

import requests
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from fastapi import Depends, FastAPI, Header, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field, field_validator
from requests_oauthlib import OAuth1Session
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, UniqueConstraint, create_engine, inspect, select, text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker


logger = logging.getLogger(__name__)


DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./neiva_ai.db")
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+psycopg://", 1)
elif DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg://", 1)

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
bearer_scheme = HTTPBearer(auto_error=False)


class Base(DeclarativeBase):
    pass


class Account(Base):
    """Conta do comprador. A senha nunca e armazenada em texto puro."""
    __tablename__ = "accounts"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(254), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(512))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class Client(Base):
    __tablename__ = "clients"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    monthly_limit: Mapped[int] = mapped_column(Integer, default=30)
    account_id: Mapped[int | None] = mapped_column(ForeignKey("accounts.id"), nullable=True, index=True)
    device_limit: Mapped[int] = mapped_column(Integer, default=2)
    plan_code: Mapped[str] = mapped_column(String(30), default="legacy")
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class MonthlyUsage(Base):
    __tablename__ = "monthly_usage"
    __table_args__ = (UniqueConstraint("client_id", "period", name="uq_usage_client_period"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    client_id: Mapped[int] = mapped_column(Integer, index=True)
    period: Mapped[str] = mapped_column(String(7))
    requests_count: Mapped[int] = mapped_column(Integer, default=0)


class ActivationCode(Base):
    __tablename__ = "activation_codes"
    id: Mapped[int] = mapped_column(primary_key=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id"), unique=True, index=True)
    code_hash: Mapped[str] = mapped_column(String(64), unique=True)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class DeviceToken(Base):
    __tablename__ = "device_tokens"
    id: Mapped[int] = mapped_column(primary_key=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    device_id: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class Subscription(Base):
    __tablename__ = "subscriptions"
    id: Mapped[int] = mapped_column(primary_key=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id"), index=True)
    provider: Mapped[str] = mapped_column(String(30), default="asaas")
    provider_subscription_id: Mapped[str] = mapped_column(String(120), unique=True)
    plan_code: Mapped[str] = mapped_column(String(30))
    status: Mapped[str] = mapped_column(String(30), default="pending")
    current_period_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_event_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_event_rank: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class ProcessedWebhook(Base):
    __tablename__ = "processed_webhooks"
    id: Mapped[int] = mapped_column(primary_key=True)
    provider: Mapped[str] = mapped_column(String(30))
    event_id: Mapped[str] = mapped_column(String(160), unique=True)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class AccountSession(Base):
    """Sessao curta usada apenas no site para iniciar o checkout autenticado."""
    __tablename__ = "account_sessions"
    id: Mapped[int] = mapped_column(primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class LoginThrottle(Base):
    """Contador distribuído de falhas sem persistir e-mail ou endereço de rede."""
    __tablename__ = "login_throttles"
    id: Mapped[int] = mapped_column(primary_key=True)
    identity_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    window_started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class CheckoutOrder(Base):
    """Pedido criado antes do Checkout e conciliado pelo webhook do Asaas."""
    __tablename__ = "checkout_orders"
    id: Mapped[int] = mapped_column(primary_key=True)
    public_id: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    claim_token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(120), unique=True, nullable=True, index=True)
    customer_name: Mapped[str] = mapped_column(String(120))
    customer_email: Mapped[str] = mapped_column(String(254), index=True)
    account_id: Mapped[int | None] = mapped_column(ForeignKey("accounts.id"), nullable=True, index=True)
    plan_code: Mapped[str] = mapped_column(String(30))
    checkout_id: Mapped[str | None] = mapped_column(String(120), unique=True, nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="pending")
    client_id: Mapped[int | None] = mapped_column(ForeignKey("clients.id"), nullable=True, index=True)
    # O cÃ³digo fica armazenado somente atÃ© a primeira ativaÃ§Ã£o no aplicativo.
    activation_code: Mapped[str | None] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class TrelloOAuthRequest(Base):
    """Autorização curta, vinculada à licença que iniciou a conexão."""
    __tablename__ = "trello_oauth_requests"
    id: Mapped[int] = mapped_column(primary_key=True)
    public_id: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id"), index=True)
    request_token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    request_secret_encrypted: Mapped[str] = mapped_column(String(1000))
    access_token_encrypted: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="pending")
    error: Mapped[str | None] = mapped_column(String(500), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class SubtitleInput(BaseModel):
    start: float = Field(ge=0)
    end: float = Field(gt=0)
    text: str = Field(min_length=1, max_length=1500)

    @field_validator("end")
    @classmethod
    def end_after_start(cls, value: float, info) -> float:
        if value <= info.data.get("start", -1):
            raise ValueError("end deve ser maior que start")
        return value


class CutsRequest(BaseModel):
    subtitles: list[SubtitleInput] = Field(min_length=1, max_length=1200)
    limit: int = Field(default=8, ge=1, le=12)


class CreateClientRequest(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    monthly_limit: int = Field(default=30, ge=1, le=10000)


class ActivateRequest(BaseModel):
    activation_code: str = Field(min_length=12, max_length=200)


class RegisterSubscriptionRequest(BaseModel):
    client_id: int = Field(gt=0)
    provider_subscription_id: str = Field(min_length=3, max_length=120)
    plan_code: str


class CheckoutRequest(BaseModel):
    plan_code: str


class AccountRegisterRequest(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    email: str = Field(min_length=5, max_length=254)
    password: str = Field(min_length=8, max_length=128)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        value = " ".join(value.split())
        if len(value) < 2:
            raise ValueError("Informe um nome valido.")
        return value

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        return normalize_email(value)

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        if not value.strip() or len(value.strip()) < 8:
            raise ValueError("A senha deve ter pelo menos 8 caracteres nao vazios.")
        return value


class AccountLoginRequest(BaseModel):
    email: str = Field(min_length=5, max_length=254)
    password: str = Field(min_length=1, max_length=128)

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        return normalize_email(value)


class AppLoginRequest(AccountLoginRequest):
    device_id: str = Field(min_length=16, max_length=120)


PLANS = {
    "free": {"name": "Neiva Grátis", "monthly_price": 0, "ai_credits": 0, "devices": 1, "clients": 1},
    "essencial": {"name": "Neiva Essencial", "monthly_price": 49.90, "ai_credits": 20, "devices": 2, "clients": 10},
    "pro": {"name": "Neiva Pro", "monthly_price": 89.90, "ai_credits": 80, "devices": 3, "clients": None},
}


def normalize_email(value: str) -> str:
    email = value.strip().lower()
    if any(char.isspace() for char in email):
        raise ValueError("Informe um e-mail valido.")
    if email.count("@") != 1 or email.startswith("@") or email.endswith("@"):
        raise ValueError("Informe um e-mail valido.")
    local, domain = email.split("@")
    if not local or "." not in domain or domain.startswith(".") or domain.endswith(".") or not re.fullmatch(r"[a-z0-9.!#$%&'*+/=?^_`{|}~-]+", local) or not re.fullmatch(r"[a-z0-9.-]+", domain):
        raise ValueError("Informe um e-mail valido.")
    return email


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def login_identity(email: str, forwarded_for: str | None, real_ip: str | None) -> str:
    origin = (forwarded_for.split(",", 1)[0].strip() if isinstance(forwarded_for, str) else "")
    origin = origin or (real_ip.strip() if isinstance(real_ip, str) else "") or "unknown"
    return token_hash(f"{email.strip().lower()}|{origin[:120]}")


def check_login_limit(session: Session, identity: str) -> None:
    throttle = session.scalar(select(LoginThrottle).where(LoginThrottle.identity_hash == identity))
    if not throttle or not throttle.locked_until:
        return
    locked_until = throttle.locked_until
    if locked_until.tzinfo is None:
        locked_until = locked_until.replace(tzinfo=timezone.utc)
    if locked_until > datetime.now(timezone.utc):
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Muitas tentativas. Aguarde alguns minutos antes de tentar novamente.")


def record_login_failure(session: Session, identity: str) -> None:
    now = datetime.now(timezone.utc)
    throttle = session.scalar(select(LoginThrottle).where(LoginThrottle.identity_hash == identity).with_for_update())
    if throttle is None:
        throttle = LoginThrottle(identity_hash=identity, attempts=0, window_started_at=now)
        session.add(throttle)
    window_started = throttle.window_started_at
    if window_started.tzinfo is None:
        window_started = window_started.replace(tzinfo=timezone.utc)
    if window_started < now - timedelta(minutes=15):
        throttle.attempts = 0
        throttle.window_started_at = now
        throttle.locked_until = None
    throttle.attempts += 1
    if throttle.attempts >= 8:
        throttle.locked_until = now + timedelta(minutes=15)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        # Uma requisição concorrente criou o contador; registre esta tentativa nela.
        record_login_failure(session, identity)


def clear_login_failures(session: Session, identity: str) -> None:
    throttle = session.scalar(select(LoginThrottle).where(LoginThrottle.identity_hash == identity))
    if throttle:
        session.delete(throttle)


def integration_encrypt(value: str) -> str:
    secret = os.getenv("TRELLO_API_SECRET", "")
    if not secret:
        raise RuntimeError("Integração Trello não configurada.")
    key = hashlib.sha256(("neiva-trello:" + secret).encode("utf-8")).digest()
    nonce = secrets.token_bytes(12)
    encrypted = AESGCM(key).encrypt(nonce, value.encode("utf-8"), b"trello-oauth-v1")
    return urlsafe_b64encode(nonce + encrypted).decode("ascii")


def integration_decrypt(value: str) -> str:
    secret = os.getenv("TRELLO_API_SECRET", "")
    if not secret:
        raise RuntimeError("Integração Trello não configurada.")
    raw = urlsafe_b64decode(value.encode("ascii"))
    key = hashlib.sha256(("neiva-trello:" + secret).encode("utf-8")).digest()
    return AESGCM(key).decrypt(raw[:12], raw[12:], b"trello-oauth-v1").decode("utf-8")


def password_hash(password: str) -> str:
    """PBKDF2 com sal individual; nao depende de pacote extra no Render."""
    iterations = 600_000
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return "pbkdf2_sha256${}${}${}".format(
        iterations,
        urlsafe_b64encode(salt).decode("ascii"),
        urlsafe_b64encode(digest).decode("ascii"),
    )


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, raw_iterations, raw_salt, raw_digest = encoded.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        expected = urlsafe_b64decode(raw_digest.encode("ascii"))
        salt = urlsafe_b64decode(raw_salt.encode("ascii"))
        actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, int(raw_iterations))
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


def new_account_session(session: Session, account: Account) -> str:
    session.execute(text("DELETE FROM account_sessions WHERE expires_at < :now"), {"now": datetime.now(timezone.utc)})
    raw_token = f"neiva_web_{secrets.token_urlsafe(32)}"
    session.add(AccountSession(
        account_id=account.id,
        token_hash=token_hash(raw_token),
        expires_at=datetime.now(timezone.utc) + timedelta(hours=2),
    ))
    return raw_token


def new_activation_code() -> str:
    return f"NEIVA-{secrets.token_urlsafe(12).upper()}"


def activate_paid_order(session: Session, order: CheckoutOrder) -> None:
    """Cria uma Ãºnica licenÃ§a para um pedido confirmado pelo Asaas."""
    if order.client_id is not None:
        client = session.get(Client, order.client_id)
        if client:
            plan = PLANS[order.plan_code]
            client.monthly_limit = plan["ai_credits"]
            client.device_limit = plan["devices"]
            client.plan_code = order.plan_code
            client.active = True
        order.status = "paid"
        return
    plan = PLANS[order.plan_code]
    existing_client = session.scalar(select(Client).where(Client.account_id == order.account_id)) if order.account_id else None
    if existing_client:
        existing_client.monthly_limit = plan["ai_credits"]
        existing_client.device_limit = plan["devices"]
        existing_client.plan_code = order.plan_code
        existing_client.active = True
        order.client_id = existing_client.id
        order.status = "paid"
        return
    # Pedidos antigos continuam recebendo codigo de ativacao. Pedidos feitos
    # por uma conta nova passam a usar login e nao precisam de codigo.
    activation_code = new_activation_code() if order.account_id is None else None
    client = Client(
        name=f"{order.customer_name} [{order.public_id[:8]}]",
        token_hash=token_hash(f"neiva_{secrets.token_urlsafe(32)}"),
        monthly_limit=plan["ai_credits"],
        account_id=order.account_id,
        device_limit=plan["devices"],
        plan_code=order.plan_code,
        active=True,
    )
    session.add(client)
    session.flush()
    if activation_code:
        session.add(ActivationCode(client_id=client.id, code_hash=token_hash(activation_code)))
    order.client_id = client.id
    order.activation_code = activation_code
    order.status = "paid"


def db_session():
    with SessionLocal() as session:
        yield session


def require_admin(credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme)) -> None:
    expected = os.getenv("NEIVA_ADMIN_TOKEN", "")
    supplied = credentials.credentials if credentials else ""
    if not expected or not hmac.compare_digest(supplied, expected):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Não autorizado.")


def current_client(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme), session: Session = Depends(db_session)
) -> Client:
    token = credentials.credentials if credentials else ""
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Chave de acesso ausente.")
    client = session.scalar(select(Client).where(Client.token_hash == token_hash(token)))
    device_token = None
    if client is None:
        device_token = session.scalar(select(DeviceToken).where(DeviceToken.token_hash == token_hash(token)))
        client = session.get(Client, device_token.client_id) if device_token else None
    if not client or not client.active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Chave de acesso inválida.")
    if client.account_id:
        account = session.get(Account, client.account_id)
        if not account or not account.active:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Conta indisponivel.")
    if device_token:
        reference = device_token.last_seen_at or device_token.created_at
        if reference.tzinfo is None:
            reference = reference.replace(tzinfo=timezone.utc)
        if reference < datetime.now(timezone.utc) - timedelta(days=90):
            session.delete(device_token)
            session.commit()
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Sua sessao expirou. Entre novamente.")
        device_token.last_seen_at = datetime.now(timezone.utc)
        session.commit()
    if client.plan_code in {"essencial", "pro"}:
        subscription = session.scalar(select(Subscription).where(Subscription.client_id == client.id).order_by(Subscription.id.desc()))
        if subscription:
            period_end = subscription.current_period_end
            if period_end and period_end.tzinfo is None:
                period_end = period_end.replace(tzinfo=timezone.utc)
            if subscription.status not in {"active", "pending_cancellation"} or (period_end and period_end < datetime.now(timezone.utc)):
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sua assinatura nao esta ativa.")
    return client


def current_account(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme), session: Session = Depends(db_session)
) -> Account:
    raw_token = credentials.credentials if credentials else ""
    if not raw_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Entre na sua conta para continuar.")
    account_session = session.scalar(select(AccountSession).where(AccountSession.token_hash == token_hash(raw_token)))
    if not account_session or account_session.expires_at.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Sua sessao expirou. Entre novamente.")
    account = session.get(Account, account_session.account_id)
    if not account or not account.active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Conta indisponivel.")
    return account


def consume_quota(session: Session, client: Client) -> tuple[int, str]:
    if client.plan_code == "free":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="A análise com IA está disponível nos planos Essencial e Pro.")
    period = datetime.now(timezone.utc).strftime("%Y-%m")
    result = session.execute(
        update(MonthlyUsage)
        .where(MonthlyUsage.client_id == client.id, MonthlyUsage.period == period, MonthlyUsage.requests_count < client.monthly_limit)
        .values(requests_count=MonthlyUsage.requests_count + 1)
    )
    if result.rowcount == 0:
        exists = session.scalar(select(MonthlyUsage.id).where(MonthlyUsage.client_id == client.id, MonthlyUsage.period == period))
        if exists is None:
            try:
                usage = MonthlyUsage(client_id=client.id, period=period, requests_count=1)
                session.add(usage)
                session.commit()
                return client.id, period
            except IntegrityError:
                session.rollback()
                return consume_quota(session, client)
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Limite mensal de análises atingido.")
    session.commit()
    return client.id, period


def refund_quota(session: Session, reservation: tuple[int, str]) -> None:
    client_id, period = reservation
    session.execute(
        update(MonthlyUsage)
        .where(MonthlyUsage.client_id == client_id, MonthlyUsage.period == period, MonthlyUsage.requests_count > 0)
        .values(requests_count=MonthlyUsage.requests_count - 1)
    )
    session.commit()


SCHEMA = {
    "type": "object", "properties": {"cuts": {"type": "array", "items": {
        "type": "object", "properties": {
            "start": {"type": "number"}, "end": {"type": "number"}, "title": {"type": "string"},
            "summary": {"type": "string"}, "score": {"type": "integer"},
        }, "required": ["start", "end", "title", "summary", "score"], "additionalProperties": False,
    }}}, "required": ["cuts"], "additionalProperties": False,
}

INSTRUCTIONS = """Você é um editor especializado em cortes virais em português do Brasil.
Analise a transcrição com timestamps e escolha trechos de 20 a 90 segundos.
Prefira gancho forte, ideia completa, ensino útil, história ou opinião marcante.
Use somente timestamps existentes e não invente falas."""


def ask_openai(payload: CutsRequest) -> list[dict]:
    api_key = os.getenv("OPENAI_API_KEY", "")
    model = os.getenv("OPENAI_MODEL", "gpt-5-mini")
    if not api_key:
        raise RuntimeError("Serviço de IA ainda não configurado.")
    transcript = "\n".join(f"[{x.start:.2f} - {x.end:.2f}] {x.text}" for x in payload.subtitles)
    if len(transcript.encode("utf-8")) > 220_000:
        raise HTTPException(status_code=413, detail="A transcrição é grande demais para análise.")
    body = {
        "model": model, "store": False, "instructions": INSTRUCTIONS,
        "input": f"Sugira no máximo {payload.limit} cortes para esta transcrição:\n\n{transcript}",
        "text": {"format": {"type": "json_schema", "name": "cortes_sugeridos", "strict": True, "schema": SCHEMA}},
    }
    try:
        response = requests.post(
            "https://api.openai.com/v1/responses", headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json=body, timeout=90,
        )
    except requests.RequestException as exc:
        raise RuntimeError("Não foi possível conectar ao provedor de IA.") from exc
    if not response.ok:
        raise RuntimeError("O provedor de IA recusou a análise. Tente novamente em alguns instantes.")
    try:
        data = response.json()
        if not isinstance(data, dict):
            raise TypeError("Resposta externa não é um objeto.")
        output = data.get("output_text") or next(part["text"] for item in data["output"] for part in item.get("content", []) if part.get("type") == "output_text")
        raw_cuts = json.loads(output)["cuts"]
        lower = min(item.start for item in payload.subtitles)
        upper = max(item.end for item in payload.subtitles)
        validated: list[dict] = []
        for item in sorted(raw_cuts, key=lambda value: float(value["start"])):
            start = max(lower, float(item["start"]))
            end = min(upper, float(item["end"]))
            title = str(item["title"]).strip()
            summary = str(item["summary"]).strip()
            if not title or not summary or end <= start or not 20 <= end - start <= 90:
                continue
            if any(start < saved["end"] and end > saved["start"] for saved in validated):
                continue
            validated.append({"start": start, "end": end, "title": title, "summary": summary, "score": max(0, min(100, int(item["score"])))})
            if len(validated) >= payload.limit:
                break
        return validated
    except (KeyError, TypeError, ValueError, StopIteration, json.JSONDecodeError) as exc:
        raise RuntimeError("O provedor retornou uma resposta inválida.") from exc


app = FastAPI(title="Neiva AI API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "https://neiva-planner-site.rafaau0.workers.dev",
        "https://rafaau.site",
        "https://www.rafaau.site",
    ],
    # Somente o ambiente de testes define esta variável. Assim, links de
    # prévia da Cloudflare podem acessar a API de staging sem abrir a API
    # de produção para origens temporárias.
    allow_origin_regex=os.getenv("CORS_ORIGIN_REGEX") or None,
    allow_methods=["POST", "GET"],
    allow_headers=["*"],
)


@app.on_event("startup")
def initialize_database() -> None:
    Base.metadata.create_all(engine)
    # create_all nao adiciona colunas em tabelas que ja existiam no PostgreSQL.
    # Estas alteracoes sao aditivas e preservam todas as licencas anteriores.
    additions = {
        "clients": {"account_id": "INTEGER", "device_limit": "INTEGER DEFAULT 2", "plan_code": "VARCHAR(30) DEFAULT 'legacy'"},
        "device_tokens": {"device_id": "VARCHAR(120)", "last_seen_at": "TIMESTAMP"},
        "checkout_orders": {"account_id": "INTEGER", "idempotency_key": "VARCHAR(120)"},
        "subscriptions": {"last_event_at": "TIMESTAMP", "last_event_rank": "INTEGER DEFAULT 0"},
    }
    inspector = inspect(engine)
    with engine.begin() as connection:
        for table_name, columns in additions.items():
            existing = {column["name"] for column in inspector.get_columns(table_name)}
            for column_name, definition in columns.items():
                if column_name not in existing:
                    connection.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {definition}"))
        connection.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ix_checkout_orders_idempotency_key ON checkout_orders (idempotency_key)"))


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


def account_response(account: Account, client: Client | None = None) -> dict:
    return {
        "id": account.id,
        "name": account.name,
        "email": account.email,
        "license_active": bool(client and client.active),
        "plan": None if client is None else (client.plan_code if client.plan_code != "legacy" else next((code for code, details in PLANS.items() if details["ai_credits"] == client.monthly_limit), "pro")),
    }


def ensure_free_client(session: Session, account: Account) -> Client:
    client = session.scalar(select(Client).where(Client.account_id == account.id))
    if client:
        return client
    plan = PLANS["free"]
    client = Client(
        name=f"{account.name} [free-{account.id}]",
        token_hash=token_hash(f"neiva_{secrets.token_urlsafe(32)}"),
        monthly_limit=plan["ai_credits"], account_id=account.id,
        device_limit=plan["devices"], plan_code="free", active=True,
    )
    session.add(client)
    session.flush()
    return client


@app.post("/v1/auth/register", status_code=status.HTTP_201_CREATED)
def register_account(payload: AccountRegisterRequest, session: Session = Depends(db_session)) -> dict:
    if session.scalar(select(Account).where(Account.email == payload.email)):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Ja existe uma conta com este e-mail. Entre para continuar.")
    account = Account(name=payload.name, email=payload.email, password_hash=password_hash(payload.password))
    session.add(account)
    session.flush()
    client = ensure_free_client(session, account)
    access_token = new_account_session(session, account)
    session.commit()
    return {"account": account_response(account, client), "access_token": access_token, "token_type": "bearer"}


@app.post("/v1/auth/sign-in")
def sign_in_account(
    payload: AccountLoginRequest,
    session: Session = Depends(db_session),
    x_forwarded_for: str | None = Header(default=None, alias="X-Forwarded-For"),
    x_real_ip: str | None = Header(default=None, alias="X-Real-IP"),
) -> dict:
    identity = login_identity(payload.email, x_forwarded_for, x_real_ip)
    check_login_limit(session, identity)
    account = session.scalar(select(Account).where(Account.email == payload.email))
    if not account or not account.active or not verify_password(payload.password, account.password_hash):
        record_login_failure(session, identity)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="E-mail ou senha incorretos.")
    clear_login_failures(session, identity)
    client = ensure_free_client(session, account)
    access_token = new_account_session(session, account)
    session.commit()
    return {"account": account_response(account, client), "access_token": access_token, "token_type": "bearer"}


@app.post("/v1/auth/app-login")
def app_login(
    payload: AppLoginRequest,
    session: Session = Depends(db_session),
    x_forwarded_for: str | None = Header(default=None, alias="X-Forwarded-For"),
    x_real_ip: str | None = Header(default=None, alias="X-Real-IP"),
) -> dict:
    identity = login_identity(payload.email, x_forwarded_for, x_real_ip)
    check_login_limit(session, identity)
    account = session.scalar(select(Account).where(Account.email == payload.email))
    if not account or not account.active or not verify_password(payload.password, account.password_hash):
        record_login_failure(session, identity)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="E-mail ou senha incorretos.")
    clear_login_failures(session, identity)
    client = ensure_free_client(session, account)
    if not client.active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sua licença está suspensa. Regularize a assinatura para entrar.")
    device = session.scalar(select(DeviceToken).where(DeviceToken.client_id == client.id, DeviceToken.device_id == payload.device_id))
    if device is None:
        cutoff = datetime.now(timezone.utc) - timedelta(days=90)
        devices = session.scalars(select(DeviceToken).where(DeviceToken.client_id == client.id, DeviceToken.device_id.is_not(None))).all()
        active_devices = []
        for saved_device in devices:
            reference = saved_device.last_seen_at or saved_device.created_at
            if reference.tzinfo is None:
                reference = reference.replace(tzinfo=timezone.utc)
            if reference < cutoff:
                session.delete(saved_device)
            else:
                active_devices.append(saved_device)
        if len(active_devices) >= client.device_limit:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"Seu plano permite ate {client.device_limit} dispositivos. Saia de um deles para entrar neste.")
        device = DeviceToken(client_id=client.id, token_hash="", device_id=payload.device_id)
        session.add(device)
    raw_token = f"neiva_{secrets.token_urlsafe(32)}"
    device.token_hash = token_hash(raw_token)
    device.last_seen_at = datetime.now(timezone.utc)
    session.commit()
    return {"access_token": raw_token, "account": account_response(account, client), "token_type": "bearer"}


@app.post("/v1/auth/logout")
def app_logout(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    session: Session = Depends(db_session),
) -> dict[str, bool]:
    """Revoga o token apresentado mesmo se a conta/licença já estiver desativada."""
    raw_token = credentials.credentials if credentials else ""
    if not raw_token:
        return {"ok": True}
    device = session.scalar(select(DeviceToken).where(DeviceToken.token_hash == token_hash(raw_token)))
    if device:
        session.delete(device)
        session.commit()
    return {"ok": True}


@app.get("/v1/auth/session")
def app_session(client: Client = Depends(current_client), session: Session = Depends(db_session)) -> dict:
    account = session.get(Account, client.account_id) if client.account_id else None
    if account is None:
        return {"license_active": True, "legacy_license": True}
    return {"account": account_response(account, client), "license_active": True, "legacy_license": False}


TRELLO_REQUEST_TOKEN_URL = "https://trello.com/1/OAuthGetRequestToken"
TRELLO_AUTHORIZE_URL = "https://trello.com/1/OAuthAuthorizeToken"
TRELLO_ACCESS_TOKEN_URL = "https://trello.com/1/OAuthGetAccessToken"


def trello_credentials() -> tuple[str, str]:
    api_key = os.getenv("TRELLO_API_KEY", "").strip()
    api_secret = os.getenv("TRELLO_API_SECRET", "").strip()
    if not api_key or not api_secret:
        raise HTTPException(status_code=503, detail="Integração Trello ainda não configurada.")
    return api_key, api_secret


def _oauth_expired(value: datetime) -> bool:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value < datetime.now(timezone.utc)


@app.post("/v1/integrations/trello/start")
def start_trello_oauth(client: Client = Depends(current_client), session: Session = Depends(db_session)) -> dict[str, str]:
    """Inicia OAuth 1.0; o segredo do aplicativo nunca é enviado ao desktop."""
    if client.plan_code == "free":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="A integração com Trello está disponível nos planos Essencial e Pro.")
    api_key, api_secret = trello_credentials()
    public_id = secrets.token_urlsafe(24)
    public_api_url = os.getenv("PUBLIC_API_URL", "https://neiva-ai-api.onrender.com").rstrip("/")
    callback_url = f"{public_api_url}/v1/integrations/trello/callback"
    oauth = OAuth1Session(api_key, client_secret=api_secret, callback_uri=callback_url)
    try:
        request_token = oauth.fetch_request_token(TRELLO_REQUEST_TOKEN_URL, timeout=20)
        oauth_token = request_token["oauth_token"]
        oauth_secret = request_token["oauth_token_secret"]
    except (requests.RequestException, KeyError, ValueError) as exc:
        logger.warning("Falha ao iniciar OAuth Trello: %s", type(exc).__name__)
        raise HTTPException(status_code=502, detail="O Trello não iniciou a autorização.") from exc
    session.add(TrelloOAuthRequest(
        public_id=public_id,
        client_id=client.id,
        request_token_hash=token_hash(oauth_token),
        request_secret_encrypted=integration_encrypt(oauth_secret),
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),
    ))
    session.commit()
    authorize_url = oauth.authorization_url(
        TRELLO_AUTHORIZE_URL,
        name="Neiva Planner",
        scope="read,write",
        expiration="never",
    )
    return {"connection_id": public_id, "authorize_url": authorize_url}


@app.get("/v1/integrations/trello/callback", response_class=HTMLResponse, include_in_schema=False)
def trello_oauth_callback(
    oauth_token: str = "",
    oauth_verifier: str = "",
    session: Session = Depends(db_session),
) -> HTMLResponse:
    pending = session.scalar(
        select(TrelloOAuthRequest).where(TrelloOAuthRequest.request_token_hash == token_hash(oauth_token))
    ) if oauth_token else None
    if not pending or pending.status != "pending" or _oauth_expired(pending.expires_at):
        return HTMLResponse(
            "<main><h1>Neiva Planner</h1><p>Esta autorização expirou. Volte ao aplicativo e tente novamente.</p></main>",
            status_code=400,
            headers={"Referrer-Policy": "no-referrer", "Cache-Control": "no-store"},
        )
    if not oauth_verifier:
        pending.status = "failed"
        pending.error = "Autorização cancelada no Trello."
        session.commit()
        return HTMLResponse(
            "<main><h1>Neiva Planner</h1><p>Autorização cancelada. Você pode fechar esta janela.</p></main>",
            status_code=400,
            headers={"Referrer-Policy": "no-referrer", "Cache-Control": "no-store"},
        )
    api_key, api_secret = trello_credentials()
    oauth = OAuth1Session(
        api_key,
        client_secret=api_secret,
        resource_owner_key=oauth_token,
        resource_owner_secret=integration_decrypt(pending.request_secret_encrypted),
        verifier=oauth_verifier,
    )
    try:
        access = oauth.fetch_access_token(TRELLO_ACCESS_TOKEN_URL, timeout=20)
        access_token = access["oauth_token"]
    except (requests.RequestException, KeyError, ValueError) as exc:
        pending.status = "failed"
        pending.error = "O Trello não concluiu a autorização."
        session.commit()
        logger.warning("Falha ao concluir OAuth Trello: %s", type(exc).__name__)
        return HTMLResponse(
            "<main><h1>Neiva Planner</h1><p>Não foi possível concluir. Volte ao aplicativo e tente novamente.</p></main>",
            status_code=502,
            headers={"Referrer-Policy": "no-referrer", "Cache-Control": "no-store"},
        )
    pending.access_token_encrypted = integration_encrypt(access_token)
    pending.request_secret_encrypted = "consumido"
    pending.status = "complete"
    session.commit()
    return HTMLResponse(
        "<main><h1>Neiva Planner</h1><p>Trello conectado com sucesso. Você pode fechar esta janela.</p></main>",
        headers={"Referrer-Policy": "no-referrer", "Cache-Control": "no-store"},
    )


@app.get("/v1/integrations/trello/status/{connection_id}")
def trello_oauth_status(
    connection_id: str,
    client: Client = Depends(current_client),
    session: Session = Depends(db_session),
) -> dict:
    pending = session.scalar(select(TrelloOAuthRequest).where(
        TrelloOAuthRequest.public_id == connection_id,
        TrelloOAuthRequest.client_id == client.id,
    ))
    if not pending:
        raise HTTPException(status_code=404, detail="Autorização não encontrada.")
    if _oauth_expired(pending.expires_at):
        session.delete(pending)
        session.commit()
        return {"status": "expired"}
    if pending.status == "failed":
        message = pending.error or "Autorização não concluída."
        session.delete(pending)
        session.commit()
        return {"status": "failed", "message": message}
    if pending.status != "complete" or not pending.access_token_encrypted:
        return {"status": "pending"}
    api_key, _api_secret = trello_credentials()
    access_token = integration_decrypt(pending.access_token_encrypted)
    session.delete(pending)
    session.commit()
    return {"status": "complete", "api_key": api_key, "token": access_token}


@app.get("/v1/billing/return", response_class=HTMLResponse, include_in_schema=False)
def checkout_return(
    checkout: str = "", order: str = "", claim: str = "", session: Session = Depends(db_session)
) -> HTMLResponse:
    """Página pública temporária para retornos do Checkout antes do site ser publicado."""
    messages = {
        "success": "Pagamento enviado com sucesso. Você receberá a confirmação da sua licença após a aprovação.",
        "cancel": "Checkout cancelado. Você pode voltar ao Neiva Planner e tentar novamente quando quiser.",
        "expired": "Este checkout expirou. Volte ao Neiva Planner para gerar um novo link.",
    }
    message = messages.get(checkout, "Retorno de checkout recebido.")
    if checkout == "success" and order and claim:
        checkout_order = session.scalar(select(CheckoutOrder).where(CheckoutOrder.public_id == order))
        if checkout_order and hmac.compare_digest(checkout_order.claim_token_hash, token_hash(claim)):
            if checkout_order.status == "paid":
                message = f"LicenÃ§a liberada. Seu cÃ³digo de ativaÃ§Ã£o Ã©: {checkout_order.activation_code}"
            else:
                message = "Pagamento recebido. Aguarde alguns segundos e atualize esta pÃ¡gina para ver seu cÃ³digo de ativaÃ§Ã£o."
    page = f"<main><h1>Neiva Planner</h1><p>{html.escape(message)}</p></main>"
    return HTMLResponse(page, headers={"Referrer-Policy": "no-referrer"})


@app.get("/v1/billing/orders/{public_id}")
def checkout_order_status(public_id: str, claim: str, session: Session = Depends(db_session)) -> dict:
    """Consulta limitada ao navegador que iniciou o checkout; nunca expÃµe dados de pagamento."""
    checkout_order = session.scalar(select(CheckoutOrder).where(CheckoutOrder.public_id == public_id))
    if not checkout_order or not hmac.compare_digest(checkout_order.claim_token_hash, token_hash(claim)):
        raise HTTPException(status_code=404, detail="Pedido nÃ£o encontrado.")
    return {
        "status": checkout_order.status,
        "license_active": checkout_order.status == "paid",
    }


@app.get("/v1/billing/plans")
def list_plans() -> dict:
    """Planos públicos; preços ficam centralizados no servidor."""
    return {"plans": [{"code": code, **details} for code, details in PLANS.items()]}


@app.post("/v1/billing/checkout")
def create_checkout(
    payload: CheckoutRequest,
    account: Account = Depends(current_account),
    session: Session = Depends(db_session),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict[str, str]:
    """Cria uma sessão de checkout recorrente hospedada pelo Asaas."""
    plan = PLANS.get(payload.plan_code)
    api_key = os.getenv("ASAAS_API_KEY", "")
    base_url = os.getenv("ASAAS_BASE_URL", "").rstrip("/")
    if not plan or payload.plan_code == "free":
        raise HTTPException(status_code=400, detail="O plano Grátis não exige checkout.")
    if not api_key or not base_url:
        raise HTTPException(status_code=503, detail="Checkout ainda não configurado.")
    key = (idempotency_key or "").strip()
    if not 16 <= len(key) <= 120:
        raise HTTPException(status_code=400, detail="Chave de idempotência ausente ou inválida.")
    claim_secret = os.getenv("CHECKOUT_CLAIM_SECRET", "") or os.getenv("ASAAS_WEBHOOK_TOKEN", "") or api_key
    claim_token = urlsafe_b64encode(hmac.new(claim_secret.encode("utf-8"), f"{account.id}:{key}".encode("utf-8"), hashlib.sha256).digest()).decode("ascii").rstrip("=")
    existing_order = session.scalar(select(CheckoutOrder).where(CheckoutOrder.idempotency_key == key, CheckoutOrder.account_id == account.id))
    checkout_host = "https://sandbox.asaas.com" if "sandbox" in base_url else "https://asaas.com"
    if existing_order:
        if existing_order.plan_code != payload.plan_code:
            raise HTTPException(status_code=409, detail="Esta tentativa já foi usada para outro plano.")
        if not existing_order.checkout_id:
            raise HTTPException(status_code=409, detail="Checkout ainda está sendo criado. Tente novamente em instantes.")
        return {
            "checkout_url": f"{checkout_host}/checkoutSession/show?id={existing_order.checkout_id}",
            "order_id": existing_order.public_id,
            "claim_token": claim_token,
        }
    checkout_order = CheckoutOrder(
        public_id=secrets.token_urlsafe(18),
        claim_token_hash=token_hash(claim_token),
        idempotency_key=key,
        customer_name=account.name,
        customer_email=account.email,
        account_id=account.id,
        plan_code=payload.plan_code,
    )
    session.add(checkout_order)
    try:
        session.flush()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(status_code=409, detail="Checkout duplicado em processamento. Tente novamente em instantes.") from exc
    tomorrow = (datetime.now(timezone.utc) + timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S")
    callback_base = os.getenv("SITE_URL", "").rstrip("/")
    if not callback_base or "localhost" in callback_base.lower() or "127.0.0.1" in callback_base:
        callback_base = "https://neiva-ai-api.onrender.com/v1/billing/return"
        callback_urls = {
            "successUrl": f"{callback_base}?checkout=success&order={checkout_order.public_id}&claim={claim_token}",
            "cancelUrl": f"{callback_base}?checkout=cancel&order={checkout_order.public_id}",
            "expiredUrl": f"{callback_base}?checkout=expired&order={checkout_order.public_id}",
        }
    else:
        callback_urls = {
            "successUrl": f"{callback_base}/?checkout=success&order={checkout_order.public_id}",
            "cancelUrl": f"{callback_base}/?checkout=cancel&order={checkout_order.public_id}",
            "expiredUrl": f"{callback_base}/?checkout=expired&order={checkout_order.public_id}",
        }
    # Assinatura recorrente no Checkout Asaas usa cartão; Pix recorrente é um
    # fluxo separado de Pix Automático e será integrado como forma adicional.
    body = {"billingTypes": ["CREDIT_CARD"], "chargeTypes": ["RECURRENT"], "minutesToExpire": 60,
            "callback": callback_urls,
            "items": [{"name": plan["name"], "description": "Assinatura Neiva Planner", "quantity": 1, "value": plan["monthly_price"]}],
            "subscription": {"cycle": "MONTHLY", "nextDueDate": tomorrow},
            "externalReference": checkout_order.public_id}
    try:
        response = requests.post(f"{base_url}/checkouts", headers={"access_token": api_key, "Content-Type": "application/json", "User-Agent": "NeivaPlanner/1.0", "Idempotency-Key": key}, json=body, timeout=30)
    except requests.RequestException as exc:
        raise HTTPException(status_code=503, detail="Não foi possível abrir o checkout.") from exc
    if not response.ok:
        # O Asaas não devolve segredos neste campo. Registrar somente a
        # descrição ajuda a corrigir a configuração do Sandbox sem expor a
        # chave de API nem os cabeçalhos da requisição.
        message = "O Asaas recusou esta solicitação."
        try:
            error_data = response.json()
            errors = error_data.get("errors", []) if isinstance(error_data, dict) else []
            descriptions = [
                str(item.get("description", "")).strip()
                for item in errors
                if isinstance(item, dict) and item.get("description")
            ]
            if descriptions:
                message = " ".join(descriptions)[:500]
        except (ValueError, TypeError):
            pass
        logger.warning("Asaas checkout recusado: status=%s motivo=%s", response.status_code, message)
        raise HTTPException(status_code=502, detail=f"Asaas Sandbox: {message}")
    try:
        response_data = response.json()
        checkout_id = response_data.get("id") if isinstance(response_data, dict) else None
    except (ValueError, TypeError):
        checkout_id = None
    if not checkout_id:
        raise HTTPException(status_code=502, detail="O Asaas não retornou um checkout.")
    checkout_order.checkout_id = checkout_id
    checkout_order.status = "checkout_created"
    session.commit()
    return {
        "checkout_url": f"{checkout_host}/checkoutSession/show?id={checkout_id}",
        "order_id": checkout_order.public_id,
        "claim_token": claim_token,
    }


@app.post("/v1/cuts")
def create_cuts(payload: CutsRequest, client: Client = Depends(current_client), session: Session = Depends(db_session)) -> dict:
    transcript_size = len("\n".join(item.text for item in payload.subtitles).encode("utf-8"))
    if transcript_size > 220_000:
        raise HTTPException(status_code=413, detail="A transcrição é grande demais para análise.")
    if not os.getenv("OPENAI_API_KEY", ""):
        raise HTTPException(status_code=503, detail="Serviço de IA ainda não configurado.")
    reservation = consume_quota(session, client)
    try:
        return {"cuts": ask_openai(payload)}
    except HTTPException:
        refund_quota(session, reservation)
        raise
    except RuntimeError as exc:
        refund_quota(session, reservation)
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.post("/v1/activate")
def activate(payload: ActivateRequest, session: Session = Depends(db_session)) -> dict:
    activation = session.scalar(select(ActivationCode).where(ActivationCode.code_hash == token_hash(payload.activation_code)))
    if not activation or activation.used_at is not None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Código de ativação inválido ou já utilizado.")
    client = session.get(Client, activation.client_id)
    if not client or not client.active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Esta licença não está ativa.")
    raw_token = f"neiva_{secrets.token_urlsafe(32)}"
    session.add(DeviceToken(client_id=client.id, token_hash=token_hash(raw_token)))
    checkout_order = session.scalar(select(CheckoutOrder).where(CheckoutOrder.activation_code == payload.activation_code))
    if checkout_order:
        checkout_order.activation_code = None
    activation.used_at = datetime.now(timezone.utc)
    session.commit()
    return {"access_token": raw_token}


@app.post("/v1/webhooks/asaas")
def asaas_webhook(
    payload: dict,
    asaas_access_token: str | None = Header(default=None),
    session: Session = Depends(db_session),
) -> dict[str, bool]:
    """Recebe notificações do Asaas e processa cada evento somente uma vez."""
    expected = os.getenv("ASAAS_WEBHOOK_TOKEN", "")
    if not expected or not asaas_access_token or not hmac.compare_digest(asaas_access_token, expected):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Webhook não autorizado.")
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Payload de webhook inválido.")
    event_id = str(payload.get("id", "")).strip()
    if not event_id:
        raise HTTPException(status_code=400, detail="Evento sem identificador.")
    if session.scalar(select(ProcessedWebhook).where(ProcessedWebhook.event_id == event_id)):
        return {"ok": True}
    event = str(payload.get("event", "")).strip()
    checkout = payload.get("checkout") or {}
    if not isinstance(checkout, dict):
        raise HTTPException(status_code=400, detail="Checkout inválido no webhook.")
    checkout_id = str(checkout.get("id", "")).strip()
    checkout_order = session.scalar(select(CheckoutOrder).where(CheckoutOrder.checkout_id == checkout_id)) if checkout_id else None
    if checkout_order:
        if event == "CHECKOUT_PAID":
            activate_paid_order(session, checkout_order)
        elif event == "CHECKOUT_CANCELED" and checkout_order.status != "paid":
            checkout_order.status = "cancelled"
        elif event == "CHECKOUT_EXPIRED" and checkout_order.status != "paid":
            checkout_order.status = "expired"

    payment = payload.get("payment") or {}
    subscription_payload = payload.get("subscription") or {}
    if not isinstance(payment, dict) or not isinstance(subscription_payload, dict):
        raise HTTPException(status_code=400, detail="Pagamento ou assinatura inválidos no webhook.")
    raw_subscription = payment.get("subscription") or subscription_payload.get("id") or ""
    if isinstance(raw_subscription, dict):
        raw_subscription = raw_subscription.get("id", "")
    provider_subscription_id = str(raw_subscription).strip()
    external_reference = str(payment.get("externalReference", "")).strip()
    if checkout_order is None and external_reference:
        checkout_order = session.scalar(select(CheckoutOrder).where(CheckoutOrder.public_id == external_reference))
    # O Asaas pode enviar PAYMENT_CONFIRMED antes (ou sem) CHECKOUT_PAID.
    # Ambos representam pagamento aprovado e precisam liberar a mesma licenca.
    if checkout_order and event in {"CHECKOUT_PAID", "PAYMENT_CONFIRMED", "PAYMENT_RECEIVED"}:
        activate_paid_order(session, checkout_order)
    subscription = session.scalar(select(Subscription).where(Subscription.provider_subscription_id == provider_subscription_id)) if provider_subscription_id else None
    if subscription is None and checkout_order and checkout_order.client_id and provider_subscription_id:
        subscription = Subscription(
            client_id=checkout_order.client_id,
            provider_subscription_id=provider_subscription_id,
            plan_code=checkout_order.plan_code,
        )
        session.add(subscription)
        session.flush()
    if subscription:
        client = session.get(Client, subscription.client_id)
        def provider_date() -> datetime:
            for source in (payment, subscription_payload, payload):
                for key in ("confirmedDate", "paymentDate", "dateCreated", "dueDate"):
                    raw = source.get(key) if isinstance(source, dict) else None
                    if raw:
                        try:
                            parsed = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
                            return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
                        except ValueError:
                            continue
            return datetime.now(timezone.utc)

        event_at = provider_date()
        ranks = {
            "CHECKOUT_PAID": 10, "PAYMENT_CONFIRMED": 10, "PAYMENT_RECEIVED": 10, "PAYMENT_OVERDUE": 20,
            "SUBSCRIPTION_INACTIVATED": 30, "SUBSCRIPTION_DELETED": 30,
            "PAYMENT_REFUNDED": 40, "PAYMENT_CHARGEBACK_REQUESTED": 40,
        }
        event_rank = ranks.get(event, 0)
        previous_at = subscription.last_event_at
        if previous_at and previous_at.tzinfo is None:
            previous_at = previous_at.replace(tzinfo=timezone.utc)
        apply_event = not previous_at or event_at > previous_at or (event_at == previous_at and event_rank >= subscription.last_event_rank)
        if apply_event and event in {"CHECKOUT_PAID", "PAYMENT_CONFIRMED", "PAYMENT_RECEIVED"}:
            subscription.status = "active"
            due_raw = payment.get("dueDate")
            try:
                due = datetime.fromisoformat(str(due_raw)).replace(tzinfo=timezone.utc) if due_raw else event_at
            except ValueError:
                due = event_at
            subscription.current_period_end = max(event_at, due) + timedelta(days=31)
            if client:
                plan = PLANS.get(subscription.plan_code)
                if plan:
                    client.plan_code = subscription.plan_code
                    client.monthly_limit = plan["ai_credits"]
                    client.device_limit = plan["devices"]
                client.active = True
        elif apply_event and event == "PAYMENT_OVERDUE":
            subscription.status = "past_due"
            if client:
                client.active = False
        elif apply_event and event in {"SUBSCRIPTION_INACTIVATED", "SUBSCRIPTION_DELETED"}:
            period_end = subscription.current_period_end
            if period_end and period_end.tzinfo is None:
                period_end = period_end.replace(tzinfo=timezone.utc)
            subscription.status = "pending_cancellation" if period_end and period_end > datetime.now(timezone.utc) else "cancelled"
            if client and subscription.status == "cancelled":
                client.active = False
        elif apply_event and event in {"PAYMENT_REFUNDED", "PAYMENT_CHARGEBACK_REQUESTED"}:
            subscription.status = "suspended"
            if client:
                client.active = False
        if apply_event and event_rank:
            subscription.last_event_at = event_at
            subscription.last_event_rank = event_rank
    session.add(ProcessedWebhook(provider="asaas", event_id=event_id))
    session.commit()
    return {"ok": True}


@app.post("/v1/admin/billing/subscriptions", dependencies=[Depends(require_admin)])
def register_subscription(payload: RegisterSubscriptionRequest, session: Session = Depends(db_session)) -> dict:
    """Registra a assinatura criada no Asaas; o webhook define a ativação real."""
    if payload.plan_code not in PLANS:
        raise HTTPException(status_code=422, detail="Plano inválido.")
    if not session.get(Client, payload.client_id):
        raise HTTPException(status_code=404, detail="Cliente não encontrado.")
    if session.scalar(select(Subscription).where(Subscription.provider_subscription_id == payload.provider_subscription_id)):
        raise HTTPException(status_code=409, detail="Assinatura já registrada.")
    subscription = Subscription(client_id=payload.client_id, provider_subscription_id=payload.provider_subscription_id, plan_code=payload.plan_code)
    session.add(subscription)
    session.commit()
    return {"id": subscription.id, "status": subscription.status, "plan": subscription.plan_code}


@app.post("/v1/admin/clients", dependencies=[Depends(require_admin)])
def create_client(payload: CreateClientRequest, session: Session = Depends(db_session)) -> dict:
    if session.scalar(select(Client).where(Client.name == payload.name)):
        raise HTTPException(status_code=409, detail="Já existe um cliente com esse nome.")
    raw_token = f"neiva_{secrets.token_urlsafe(32)}"
    activation_code = f"NEIVA-{secrets.token_urlsafe(12).upper()}"
    client = Client(name=payload.name, token_hash=token_hash(raw_token), monthly_limit=payload.monthly_limit)
    session.add(client)
    session.flush()
    session.add(ActivationCode(client_id=client.id, code_hash=token_hash(activation_code)))
    session.commit()
    return {"id": client.id, "name": client.name, "monthly_limit": client.monthly_limit, "activation_code": activation_code}
