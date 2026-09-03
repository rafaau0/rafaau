"""API privada: a chave OpenAI permanece exclusivamente no servidor."""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
from datetime import datetime, timezone

import requests
from fastapi import Depends, FastAPI, Header, HTTPException, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import Boolean, DateTime, Integer, String, UniqueConstraint, create_engine, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker


DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./neiva_ai.db")
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+psycopg://", 1)
elif DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg://", 1)

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


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


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def db_session():
    with SessionLocal() as session:
        yield session


def require_admin(authorization: str | None = Header(default=None)) -> None:
    expected = os.getenv("NEIVA_ADMIN_TOKEN", "")
    supplied = authorization.removeprefix("Bearer ").strip() if authorization else ""
    if not expected or not hmac.compare_digest(supplied, expected):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Não autorizado.")


def current_client(
    authorization: str | None = Header(default=None), session: Session = Depends(db_session)
) -> Client:
    token = authorization.removeprefix("Bearer ").strip() if authorization else ""
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Chave de acesso ausente.")
    client = session.scalar(select(Client).where(Client.token_hash == token_hash(token)))
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


@app.on_event("startup")
def initialize_database() -> None:
    Base.metadata.create_all(engine)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/v1/cuts")
def create_cuts(payload: CutsRequest, client: Client = Depends(current_client), session: Session = Depends(db_session)) -> dict:
    consume_quota(session, client)
    try:
        return {"cuts": ask_openai(payload)}
    except HTTPException:
        raise
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.post("/v1/admin/clients", dependencies=[Depends(require_admin)])
def create_client(payload: CreateClientRequest, session: Session = Depends(db_session)) -> dict:
    if session.scalar(select(Client).where(Client.name == payload.name)):
        raise HTTPException(status_code=409, detail="Já existe um cliente com esse nome.")
    raw_token = f"neiva_{secrets.token_urlsafe(32)}"
    client = Client(name=payload.name, token_hash=token_hash(raw_token), monthly_limit=payload.monthly_limit)
    session.add(client)
    session.commit()
    return {"id": client.id, "name": client.name, "monthly_limit": client.monthly_limit, "access_token": raw_token}
