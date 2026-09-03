"""API privada: a chave OpenAI permanece exclusivamente no servidor."""
from __future__ import annotations

import hashlib
import hmac
import html
import json
import logging
import os
import secrets
from datetime import datetime, timedelta, timezone

import requests
from fastapi import Depends, FastAPI, Header, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, UniqueConstraint, create_engine, select
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


class Client(Base):
    __tablename__ = "clients"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    monthly_limit: Mapped[int] = mapped_column(Integer, default=30)
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
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class ProcessedWebhook(Base):
    __tablename__ = "processed_webhooks"
    id: Mapped[int] = mapped_column(primary_key=True)
    provider: Mapped[str] = mapped_column(String(30))
    event_id: Mapped[str] = mapped_column(String(160), unique=True)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class CheckoutOrder(Base):
    """Pedido criado antes do Checkout e conciliado pelo webhook do Asaas."""
    __tablename__ = "checkout_orders"
    id: Mapped[int] = mapped_column(primary_key=True)
    public_id: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    claim_token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    customer_name: Mapped[str] = mapped_column(String(120))
    customer_email: Mapped[str] = mapped_column(String(254), index=True)
    plan_code: Mapped[str] = mapped_column(String(30))
    checkout_id: Mapped[str | None] = mapped_column(String(120), unique=True, nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="pending")
    client_id: Mapped[int | None] = mapped_column(ForeignKey("clients.id"), nullable=True, index=True)
    # O cÃ³digo fica armazenado somente atÃ© a primeira ativaÃ§Ã£o no aplicativo.
    activation_code: Mapped[str | None] = mapped_column(String(200), nullable=True)
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
    customer_name: str = Field(min_length=2, max_length=120)
    customer_email: str = Field(min_length=5, max_length=254)

    @field_validator("customer_name")
    @classmethod
    def normalize_customer_name(cls, value: str) -> str:
        return " ".join(value.split())

    @field_validator("customer_email")
    @classmethod
    def validate_customer_email(cls, value: str) -> str:
        email = value.strip().lower()
        if email.count("@") != 1 or email.startswith("@") or email.endswith("@"):
            raise ValueError("Informe um e-mail vÃ¡lido.")
        return email


PLANS = {
    "essencial": {"name": "Neiva Essencial", "monthly_price": 49.90, "ai_credits": 20, "devices": 2},
    "pro": {"name": "Neiva Pro", "monthly_price": 89.90, "ai_credits": 80, "devices": 2},
}


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def new_activation_code() -> str:
    return f"NEIVA-{secrets.token_urlsafe(12).upper()}"


def activate_paid_order(session: Session, order: CheckoutOrder) -> None:
    """Cria uma Ãºnica licenÃ§a para um pedido confirmado pelo Asaas."""
    if order.client_id is not None:
        order.status = "paid"
        return
    plan = PLANS[order.plan_code]
    activation_code = new_activation_code()
    client = Client(
        name=f"{order.customer_name} [{order.public_id[:8]}]",
        token_hash=token_hash(f"neiva_{secrets.token_urlsafe(32)}"),
        monthly_limit=plan["ai_credits"],
        active=True,
    )
    session.add(client)
    session.flush()
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
    if client is None:
        device_token = session.scalar(select(DeviceToken).where(DeviceToken.token_hash == token_hash(token)))
        client = session.get(Client, device_token.client_id) if device_token else None
    if not client or not client.active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Chave de acesso inválida.")
    return client


def consume_quota(session: Session, client: Client) -> None:
    period = datetime.now(timezone.utc).strftime("%Y-%m")
    usage = session.scalar(select(MonthlyUsage).where(MonthlyUsage.client_id == client.id, MonthlyUsage.period == period))
    if usage is None:
        usage = MonthlyUsage(client_id=client.id, period=period, requests_count=0)
        session.add(usage)
        session.flush()
    if usage.requests_count >= client.monthly_limit:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Limite mensal de análises atingido.")
    usage.requests_count += 1
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
    data = response.json()
    try:
        output = data.get("output_text") or next(part["text"] for item in data["output"] for part in item.get("content", []) if part.get("type") == "output_text")
        return json.loads(output)["cuts"]
    except (KeyError, TypeError, ValueError, StopIteration, json.JSONDecodeError) as exc:
        raise RuntimeError("O provedor retornou uma resposta inválida.") from exc


app = FastAPI(title="Neiva AI API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "https://neiva-planner-site.rafaau0.workers.dev",
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


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


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
            if checkout_order.status == "paid" and checkout_order.activation_code:
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
        "activation_code": checkout_order.activation_code if checkout_order.status == "paid" else None,
    }


@app.get("/v1/billing/plans")
def list_plans() -> dict:
    """Planos públicos; preços ficam centralizados no servidor."""
    return {"plans": [{"code": code, **details} for code, details in PLANS.items()]}


@app.post("/v1/billing/checkout")
def create_checkout(payload: CheckoutRequest, session: Session = Depends(db_session)) -> dict[str, str]:
    """Cria uma sessão de checkout recorrente hospedada pelo Asaas."""
    plan = PLANS.get(payload.plan_code)
    api_key = os.getenv("ASAAS_API_KEY", "")
    base_url = os.getenv("ASAAS_BASE_URL", "").rstrip("/")
    if not plan or not api_key or not base_url:
        raise HTTPException(status_code=503, detail="Checkout ainda não configurado.")
    claim_token = secrets.token_urlsafe(32)
    checkout_order = CheckoutOrder(
        public_id=secrets.token_urlsafe(18),
        claim_token_hash=token_hash(claim_token),
        customer_name=payload.customer_name,
        customer_email=payload.customer_email,
        plan_code=payload.plan_code,
    )
    session.add(checkout_order)
    session.flush()
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
        response = requests.post(f"{base_url}/checkouts", headers={"access_token": api_key, "Content-Type": "application/json", "User-Agent": "NeivaPlanner/1.0"}, json=body, timeout=30)
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
    checkout_id = response.json().get("id")
    if not checkout_id:
        raise HTTPException(status_code=502, detail="O Asaas não retornou um checkout.")
    checkout_order.checkout_id = checkout_id
    checkout_order.status = "checkout_created"
    session.commit()
    checkout_host = "https://sandbox.asaas.com" if "sandbox" in base_url else "https://asaas.com"
    return {
        "checkout_url": f"{checkout_host}/checkoutSession/show?id={checkout_id}",
        "order_id": checkout_order.public_id,
        "claim_token": claim_token,
    }


@app.post("/v1/cuts")
def create_cuts(payload: CutsRequest, client: Client = Depends(current_client), session: Session = Depends(db_session)) -> dict:
    consume_quota(session, client)
    try:
        return {"cuts": ask_openai(payload)}
    except HTTPException:
        raise
    except RuntimeError as exc:
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
    event_id = str(payload.get("id", "")).strip()
    if not event_id:
        raise HTTPException(status_code=400, detail="Evento sem identificador.")
    if session.scalar(select(ProcessedWebhook).where(ProcessedWebhook.event_id == event_id)):
        return {"ok": True}
    event = str(payload.get("event", "")).strip()
    checkout = payload.get("checkout") or {}
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
    provider_subscription_id = str(payment.get("subscription", "")).strip()
    external_reference = str(payment.get("externalReference", "")).strip()
    if checkout_order is None and external_reference:
        checkout_order = session.scalar(select(CheckoutOrder).where(CheckoutOrder.public_id == external_reference))
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
        if event in {"PAYMENT_CONFIRMED", "PAYMENT_RECEIVED"}:
            subscription.status = "active"
            subscription.current_period_end = datetime.now(timezone.utc) + timedelta(days=31)
            if client:
                client.active = True
        elif event == "PAYMENT_OVERDUE":
            subscription.status = "past_due"
        elif event in {"PAYMENT_REFUNDED", "PAYMENT_CHARGEBACK_REQUESTED"}:
            subscription.status = "suspended"
            if client:
                client.active = False
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
