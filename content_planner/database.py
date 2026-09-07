from __future__ import annotations

import sqlite3
import sys
import os
import shutil
import uuid
from datetime import date, timedelta
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

ROOT_DIR = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent.parent
if getattr(sys, "frozen", False):
    _local_data = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    DATABASE_DIR = _local_data / "NeivaPlanner" / "database"
else:
    DATABASE_DIR = ROOT_DIR / "database"
DATABASE_PATH = DATABASE_DIR / "content_planner.db"
VALID_STATUSES = {"Pendente", "Em andamento", "Concluído"}


def account_database_path() -> Path:
    """Retorna um banco isolado por conta, preservando instalações legadas."""
    try:
        from .account_sessions import current_account
        account = current_account()
    except Exception:
        account = None
    if account is None:
        return DATABASE_PATH
    return DATABASE_DIR / "accounts" / account.account_id / "content_planner.db"


@dataclass(slots=True)
class Client:
    id: int | None
    name: str
    niche: str
    instagram: str
    posting_frequency: str
    objective: str
    notes: str
    operation_id: str | None = None
    company_name: str = ""
    document: str = ""
    email: str = ""
    phone: str = ""
    address: str = ""
    contact_name: str = ""
    status: str = "Ativo"


@dataclass(slots=True)
class Contract:
    id: int | None
    client_id: int
    title: str
    description: str = ""
    value_cents: int = 0
    start_date: str = ""
    end_date: str = ""
    due_day: int | None = None
    status: str = "Rascunho"
    attachment_path: str = ""
    notes: str = ""
    operation_id: str | None = None


@dataclass(slots=True)
class Post:
    id: int | None
    client_id: int
    post_date: str
    content_type: str
    platform: str
    title: str
    description: str
    caption: str
    cta: str
    status: str
    operation_id: str | None = None
    trello_board_id: str | None = None


class Database:
    def __init__(self, db_path: Path | None = None) -> None:
        self.db_path = db_path or account_database_path()
        self.contracts_dir = self.db_path.parent / "contracts"
        self._migrate_legacy_database()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.initialize()

    def _migrate_legacy_database(self) -> None:
        """Preserva bancos de versões portáteis anteriores ao mudar para LocalAppData."""
        if self.db_path.exists() or self.db_path == DATABASE_PATH:
            return
        # Bancos por conta não recebem dados legados automaticamente: sem uma
        # confirmação de titularidade, a primeira conta poderia herdar dados de outra.
        if self.db_path.parent.parent.name == "accounts":
            return
        marker = DATABASE_DIR / ".account_migration_complete"
        candidates = [DATABASE_PATH]
        if getattr(sys, "frozen", False):
            candidates.append(ROOT_DIR / "database" / "content_planner.db")
        legacy_path = next((path for path in candidates if path.is_file()), None)
        if legacy_path and not marker.exists():
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(legacy_path, self.db_path)
            marker.touch()

    @contextmanager
    def connect(self) -> Iterable[sqlite3.Connection]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def initialize(self) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS clientes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    niche TEXT NOT NULL DEFAULT '',
                    instagram TEXT NOT NULL DEFAULT '',
                    posting_frequency TEXT NOT NULL DEFAULT '',
                    objective TEXT NOT NULL DEFAULT '',
                    notes TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS posts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    client_id INTEGER NOT NULL,
                    post_date TEXT NOT NULL,
                    content_type TEXT NOT NULL,
                    platform TEXT NOT NULL,
                    title TEXT NOT NULL,
                    description TEXT NOT NULL DEFAULT '',
                    caption TEXT NOT NULL DEFAULT '',
                    cta TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL DEFAULT 'Pendente',
                    trello_card_id TEXT DEFAULT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (client_id) REFERENCES clientes(id) ON DELETE CASCADE
                )
                """
            )
            client_columns = {row[1] for row in conn.execute("PRAGMA table_info(clientes)")}
            if "operation_id" not in client_columns:
                conn.execute("ALTER TABLE clientes ADD COLUMN operation_id TEXT DEFAULT NULL")
            client_additions = {
                "company_name": "TEXT NOT NULL DEFAULT ''",
                "document": "TEXT NOT NULL DEFAULT ''",
                "email": "TEXT NOT NULL DEFAULT ''",
                "phone": "TEXT NOT NULL DEFAULT ''",
                "address": "TEXT NOT NULL DEFAULT ''",
                "contact_name": "TEXT NOT NULL DEFAULT ''",
                "status": "TEXT NOT NULL DEFAULT 'Ativo'",
            }
            for column, definition in client_additions.items():
                if column not in client_columns:
                    conn.execute(f"ALTER TABLE clientes ADD COLUMN {column} {definition}")
            post_columns = {row[1] for row in conn.execute("PRAGMA table_info(posts)")}
            if "operation_id" not in post_columns:
                conn.execute("ALTER TABLE posts ADD COLUMN operation_id TEXT DEFAULT NULL")
            if "trello_board_id" not in post_columns:
                conn.execute("ALTER TABLE posts ADD COLUMN trello_board_id TEXT DEFAULT NULL")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_posts_client_date ON posts(client_id, post_date)")
            conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS ux_clientes_operation_id ON clientes(operation_id) WHERE operation_id IS NOT NULL")
            conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS ux_posts_operation_id ON posts(operation_id) WHERE operation_id IS NOT NULL")
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS contracts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    client_id INTEGER NOT NULL,
                    title TEXT NOT NULL,
                    description TEXT NOT NULL DEFAULT '',
                    value_cents INTEGER NOT NULL DEFAULT 0,
                    start_date TEXT NOT NULL DEFAULT '',
                    end_date TEXT NOT NULL DEFAULT '',
                    due_day INTEGER DEFAULT NULL,
                    status TEXT NOT NULL DEFAULT 'Rascunho',
                    attachment_path TEXT NOT NULL DEFAULT '',
                    notes TEXT NOT NULL DEFAULT '',
                    operation_id TEXT DEFAULT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (client_id) REFERENCES clientes(id) ON DELETE CASCADE
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_contracts_client ON contracts(client_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_contracts_status_end ON contracts(status, end_date)")
            conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS ux_contracts_operation_id ON contracts(operation_id) WHERE operation_id IS NOT NULL")
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS configuracoes (
                    chave TEXT PRIMARY KEY,
                    valor TEXT NOT NULL DEFAULT ''
                )
                """
            )

    def create_client(self, client: Client) -> int:
        self._validate_client(client)
        with self.connect() as conn:
            try:
                cur = conn.execute(
                    """
                    INSERT INTO clientes
                    (name, niche, instagram, posting_frequency, objective, notes, operation_id,
                     company_name, document, email, phone, address, contact_name, status)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        self._clean(client.name), self._clean(client.niche), self._clean(client.instagram),
                        self._clean(client.posting_frequency), self._clean(client.objective), self._clean(client.notes),
                        client.operation_id,
                        self._clean(client.company_name), self._clean(client.document), self._clean(client.email),
                        self._clean(client.phone), self._clean(client.address), self._clean(client.contact_name), client.status,
                    ),
                )
            except sqlite3.IntegrityError:
                if not client.operation_id:
                    raise
                row = conn.execute("SELECT id FROM clientes WHERE operation_id=?", (client.operation_id,)).fetchone()
                if row:
                    return int(row["id"])
                raise
            return int(cur.lastrowid)

    def update_client(self, client: Client) -> None:
        if client.id is None:
            raise ValueError("Client id is required for update.")
        self._validate_client(client)
        with self.connect() as conn:
            conn.execute(
                """
                UPDATE clientes
                SET name=?, niche=?, instagram=?, posting_frequency=?, objective=?, notes=?,
                    company_name=?, document=?, email=?, phone=?, address=?, contact_name=?, status=?,
                    updated_at=CURRENT_TIMESTAMP
                WHERE id=?
                """,
                (
                    self._clean(client.name),
                    self._clean(client.niche),
                    self._clean(client.instagram),
                    self._clean(client.posting_frequency),
                    self._clean(client.objective),
                    self._clean(client.notes),
                    self._clean(client.company_name),
                    self._clean(client.document),
                    self._clean(client.email),
                    self._clean(client.phone),
                    self._clean(client.address),
                    self._clean(client.contact_name),
                    client.status,
                    client.id,
                ),
            )

    def delete_client(self, client_id: int) -> None:
        attachments = [contract.attachment_path for contract in self.list_contracts(client_id) if contract.attachment_path]
        with self.connect() as conn:
            conn.execute("DELETE FROM clientes WHERE id=?", (client_id,))
        for attachment in attachments:
            self._delete_managed_attachment(attachment)

    def search_clients(self, term: str = "", status: str = "") -> list[Client]:
        like = f"%{term.strip()}%"
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM clientes
                WHERE (name LIKE ? OR niche LIKE ? OR instagram LIKE ? OR company_name LIKE ?
                       OR document LIKE ? OR email LIKE ? OR phone LIKE ? OR contact_name LIKE ?)
                  AND (? = '' OR status = ?)
                ORDER BY name COLLATE NOCASE
                """,
                (like, like, like, like, like, like, like, like, status, status),
            ).fetchall()
        return [self._row_to_client(row) for row in rows]

    def get_client(self, client_id: int) -> Client | None:
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM clientes WHERE id=?", (client_id,)).fetchone()
        return self._row_to_client(row) if row else None

    def create_contract(self, contract: Contract) -> int:
        self._validate_contract(contract)
        with self.connect() as conn:
            try:
                cur = conn.execute(
                    """
                    INSERT INTO contracts
                    (client_id, title, description, value_cents, start_date, end_date, due_day,
                     status, attachment_path, notes, operation_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        contract.client_id, self._clean(contract.title), self._clean(contract.description),
                        contract.value_cents, contract.start_date, contract.end_date, contract.due_day,
                        contract.status, contract.attachment_path, self._clean(contract.notes), contract.operation_id,
                    ),
                )
            except sqlite3.IntegrityError:
                if not contract.operation_id:
                    raise
                row = conn.execute("SELECT id FROM contracts WHERE operation_id=?", (contract.operation_id,)).fetchone()
                if row:
                    return int(row["id"])
                raise
            return int(cur.lastrowid)

    def update_contract(self, contract: Contract) -> None:
        if contract.id is None:
            raise ValueError("Contract id is required for update.")
        self._validate_contract(contract)
        previous = self.get_contract(contract.id)
        with self.connect() as conn:
            conn.execute(
                """
                UPDATE contracts
                SET title=?, description=?, value_cents=?, start_date=?, end_date=?, due_day=?,
                    status=?, attachment_path=?, notes=?, updated_at=CURRENT_TIMESTAMP
                WHERE id=? AND client_id=?
                """,
                (
                    self._clean(contract.title), self._clean(contract.description), contract.value_cents,
                    contract.start_date, contract.end_date, contract.due_day, contract.status,
                    contract.attachment_path, self._clean(contract.notes), contract.id, contract.client_id,
                ),
            )
        if previous and previous.attachment_path and previous.attachment_path != contract.attachment_path:
            self._delete_managed_attachment(previous.attachment_path)

    def get_contract(self, contract_id: int) -> Contract | None:
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM contracts WHERE id=?", (contract_id,)).fetchone()
        return self._row_to_contract(row) if row else None

    def list_contracts(self, client_id: int) -> list[Contract]:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM contracts WHERE client_id=? ORDER BY start_date DESC, id DESC",
                (client_id,),
            ).fetchall()
        return [self._row_to_contract(row) for row in rows]

    def delete_contract(self, contract_id: int) -> None:
        contract = self.get_contract(contract_id)
        if not contract:
            return
        with self.connect() as conn:
            conn.execute("DELETE FROM contracts WHERE id=?", (contract_id,))
        if contract.attachment_path:
            self._delete_managed_attachment(contract.attachment_path)

    def import_contract_attachment(self, source: Path, client_id: int) -> str:
        source = source.resolve()
        if not source.is_file() or source.suffix.lower() != ".pdf":
            raise ValueError("Selecione um contrato válido em PDF.")
        if source.stat().st_size > 25 * 1024 * 1024:
            raise ValueError("O PDF do contrato deve ter no máximo 25 MB.")
        target_dir = self.contracts_dir / str(client_id)
        target_dir.mkdir(parents=True, exist_ok=True)
        target = target_dir / f"{uuid.uuid4().hex}.pdf"
        shutil.copy2(source, target)
        return str(target)

    def _delete_managed_attachment(self, raw_path: str) -> None:
        try:
            path = Path(raw_path).resolve()
            managed_root = self.contracts_dir.resolve()
            if path.is_relative_to(managed_root) and path.is_file():
                path.unlink()
        except (OSError, ValueError):
            pass

    def create_post(self, post: Post) -> int:
        self._validate_post(post)
        with self.connect() as conn:
            try:
                cur = conn.execute(
                    """
                    INSERT INTO posts
                    (client_id, post_date, content_type, platform, title, description, caption, cta, status, operation_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        post.client_id, post.post_date, post.content_type, post.platform, self._clean(post.title),
                        self._clean(post.description), self._clean(post.caption), self._clean(post.cta), post.status,
                        post.operation_id,
                    ),
                )
            except sqlite3.IntegrityError:
                if not post.operation_id:
                    raise
                row = conn.execute("SELECT id FROM posts WHERE operation_id=?", (post.operation_id,)).fetchone()
                if row:
                    return int(row["id"])
                raise
            return int(cur.lastrowid)

    def update_post(self, post: Post) -> None:
        if post.id is None:
            raise ValueError("Post id is required for update.")
        self._validate_post(post)
        with self.connect() as conn:
            conn.execute(
                """
                UPDATE posts
                SET client_id=?, post_date=?, content_type=?, platform=?, title=?, description=?,
                    caption=?, cta=?, status=?, updated_at=CURRENT_TIMESTAMP
                WHERE id=?
                """,
                (
                    post.client_id,
                    post.post_date,
                    post.content_type,
                    post.platform,
                    self._clean(post.title),
                    self._clean(post.description),
                    self._clean(post.caption),
                    self._clean(post.cta),
                    post.status,
                    post.id,
                ),
            )

    def update_post_trello_card(self, post_id: int, card_id: str, board_id: str | None = None) -> None:
        with self.connect() as conn:
            conn.execute("UPDATE posts SET trello_card_id=?, trello_board_id=? WHERE id=?", (card_id, board_id, post_id))

    def delete_post(self, post_id: int) -> None:
        with self.connect() as conn:
            conn.execute("DELETE FROM posts WHERE id=?", (post_id,))

    def get_post(self, post_id: int) -> Post | None:
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM posts WHERE id=?", (post_id,)).fetchone()
        return self._row_to_post(row) if row else None

    def get_posts_for_client_month(self, client_id: int, year: int, month: int) -> list[Post]:
        prefix = f"{year:04d}-{month:02d}"
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM posts
                WHERE client_id=? AND post_date LIKE ?
                ORDER BY post_date, id
                """,
                (client_id, f"{prefix}-%"),
            ).fetchall()
        return [self._row_to_post(row) for row in rows]

    def count_posts_month(self, year: int, month: int) -> int:
        prefix = f"{year:04d}-{month:02d}-%"
        with self.connect() as conn:
            return int(conn.execute("SELECT COUNT(*) FROM posts WHERE post_date LIKE ?", (prefix,)).fetchone()[0])

    def get_posts_for_day(self, client_id: int, post_date: str) -> list[Post]:
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM posts
                WHERE client_id=? AND post_date=?
                ORDER BY id
                """,
                (client_id, post_date),
            ).fetchall()
        return [self._row_to_post(row) for row in rows]

    def get_posts_pending_trello(self, client_id: int, year: int, month: int, board_id: str | None = None) -> list[Post]:
        prefix = f"{year:04d}-{month:02d}"
        with self.connect() as conn:
            if board_id:
                rows = conn.execute(
                    """
                    SELECT * FROM posts
                    WHERE client_id=? AND post_date LIKE ?
                      AND (trello_card_id IS NULL OR trello_card_id='' OR trello_board_id IS NULL OR trello_board_id<>?)
                    ORDER BY post_date, id
                    """,
                    (client_id, f"{prefix}-%", board_id),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT * FROM posts
                    WHERE client_id=? AND post_date LIKE ? AND (trello_card_id IS NULL OR trello_card_id='')
                    ORDER BY post_date, id
                    """,
                    (client_id, f"{prefix}-%"),
                ).fetchall()
        return [self._row_to_post(row) for row in rows]

    def get_setting(self, key: str, default: str = "") -> str:
        with self.connect() as conn:
            row = conn.execute("SELECT valor FROM configuracoes WHERE chave=?", (key,)).fetchone()
        return str(row["valor"]) if row else default

    def set_setting(self, key: str, value: str) -> None:
        with self.connect() as conn:
            conn.execute(
                "INSERT INTO configuracoes (chave, valor) VALUES (?, ?) "
                "ON CONFLICT(chave) DO UPDATE SET valor=excluded.valor",
                (key, value.strip()),
            )

    def delete_setting(self, key: str) -> None:
        with self.connect() as conn:
            conn.execute("DELETE FROM configuracoes WHERE chave=?", (key,))

    def dashboard_data(self, year: int, month: int, client_id: int | None = None,
                       today: date | None = None) -> dict:
        """Métricas mensais; prioridades, agenda e contratos na data local atual."""
        today = today or date.today()
        scope = " AND client_id=?" if client_id is not None else ""
        params = (client_id,) if client_id is not None else ()
        with self.connect() as conn:
            counts = dict(conn.execute(
                "SELECT status, COUNT(*) FROM posts WHERE substr(post_date,1,7)=?" + scope + " GROUP BY status",
                (f"{year:04d}-{month:02d}", *params),
            ).fetchall())
            priorities = conn.execute(
                "SELECT * FROM posts WHERE status<>'Concluído' AND post_date<=?" + scope + " ORDER BY post_date, id",
                (today.isoformat(), *params),
            ).fetchall()
            upcoming = conn.execute(
                "SELECT * FROM posts WHERE status<>'Concluído' AND post_date>? AND post_date<=?" + scope + " ORDER BY post_date,id",
                (today.isoformat(), (today + timedelta(days=7)).isoformat(), *params),
            ).fetchall()
            contracts = conn.execute("SELECT * FROM contracts WHERE 1=1" + scope + " ORDER BY end_date,id", params).fetchall()
        clients = {c.id: c for c in self.search_clients() if client_id is None or c.id == client_id}
        current = [self._row_to_contract(r) for r in contracts if r['status'] == 'Ativo'
                   and (not r['start_date'] or r['start_date'] <= today.isoformat())
                   and (not r['end_date'] or r['end_date'] >= today.isoformat())]
        alerts = [self._row_to_contract(r) for r in contracts if r['status'] == 'Ativo' and r['end_date']
                  and r['end_date'] <= (today + timedelta(days=30)).isoformat()]
        return dict(counts=counts, clients=clients,
                    priorities=[self._row_to_post(r) for r in priorities],
                    upcoming=[self._row_to_post(r) for r in upcoming], contracts=current, alerts=alerts,
                    revenue=sum(c.value_cents for c in current if clients[c.client_id].status == 'Ativo'))

    def dashboard_stats(self) -> dict[str, int]:
        today = date.today()
        data = self.dashboard_data(today.year, today.month, today=today)
        with self.connect() as conn:
            counts = dict(conn.execute("SELECT status, COUNT(*) FROM posts GROUP BY status").fetchall())
        return {
            "clients": len(data["clients"]),
            "posts": sum(counts.values()),
            "pending": counts.get("Pendente", 0),
            "done": counts.get("Concluído", 0),
            "active_clients": sum(c.status == "Ativo" for c in data["clients"].values()),
            "active_contracts": len(data["contracts"]),
            "expiring_contracts": sum(c.end_date >= today.isoformat() for c in data["alerts"]),
            "expired_contracts": sum(c.end_date < today.isoformat() for c in data["alerts"]),
            "monthly_revenue_cents": data["revenue"],
        }

    def expiring_contracts(self, days: int = 30) -> list[tuple[Contract, Client]]:
        today = date.today()
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT contracts.*
                FROM contracts
                WHERE contracts.status='Ativo' AND contracts.end_date<>''
                  AND contracts.end_date BETWEEN ? AND ?
                ORDER BY contracts.end_date, contracts.id
                """,
                (today.isoformat(), (today + timedelta(days=max(0, min(days, 365)))).isoformat()),
            ).fetchall()
        results = []
        for row in rows:
            contract = self._row_to_contract(row)
            client = self.get_client(contract.client_id)
            if client:
                results.append((contract, client))
        return results

    @staticmethod
    def _clean(value: str) -> str:
        return value.strip()

    @staticmethod
    def _validate_client(client: Client) -> None:
        if not client.name.strip():
            raise ValueError("Nome do cliente é obrigatório.")
        if client.status not in {"Ativo", "Inativo"}:
            raise ValueError("Status do cliente inválido.")

    @staticmethod
    def _validate_contract(contract: Contract) -> None:
        if not contract.title.strip():
            raise ValueError("O título do contrato é obrigatório.")
        if contract.value_cents < 0:
            raise ValueError("O valor do contrato não pode ser negativo.")
        if contract.due_day is not None and not 1 <= contract.due_day <= 31:
            raise ValueError("O dia de vencimento deve estar entre 1 e 31.")
        if contract.status not in {"Rascunho", "Ativo", "Encerrado", "Cancelado"}:
            raise ValueError("Status do contrato inválido.")
        for raw_date in (contract.start_date, contract.end_date):
            if raw_date:
                date.fromisoformat(raw_date)
        if contract.start_date and contract.end_date and contract.end_date < contract.start_date:
            raise ValueError("A data final não pode ser anterior à data inicial.")

    @staticmethod
    def _validate_post(post: Post) -> None:
        if not post.title.strip():
            raise ValueError("Título do conteúdo é obrigatório.")
        try:
            date.fromisoformat(post.post_date)
        except ValueError as exc:
            raise ValueError("Data do conteúdo inválida.") from exc
        if post.status not in VALID_STATUSES:
            raise ValueError("Status do conteúdo inválido.")
        if not post.content_type.strip() or not post.platform.strip():
            raise ValueError("Tipo e plataforma são obrigatórios.")

    @staticmethod
    def _row_to_client(row: sqlite3.Row) -> Client:
        return Client(
            id=row["id"],
            name=row["name"],
            niche=row["niche"],
            instagram=row["instagram"],
            posting_frequency=row["posting_frequency"],
            objective=row["objective"],
            notes=row["notes"],
            operation_id=row["operation_id"] if "operation_id" in row.keys() else None,
            company_name=row["company_name"] if "company_name" in row.keys() else "",
            document=row["document"] if "document" in row.keys() else "",
            email=row["email"] if "email" in row.keys() else "",
            phone=row["phone"] if "phone" in row.keys() else "",
            address=row["address"] if "address" in row.keys() else "",
            contact_name=row["contact_name"] if "contact_name" in row.keys() else "",
            status=row["status"] if "status" in row.keys() else "Ativo",
        )

    @staticmethod
    def _row_to_contract(row: sqlite3.Row) -> Contract:
        return Contract(
            id=row["id"],
            client_id=row["client_id"],
            title=row["title"],
            description=row["description"],
            value_cents=row["value_cents"],
            start_date=row["start_date"],
            end_date=row["end_date"],
            due_day=row["due_day"],
            status=row["status"],
            attachment_path=row["attachment_path"],
            notes=row["notes"],
            operation_id=row["operation_id"],
        )

    @staticmethod
    def _row_to_post(row: sqlite3.Row) -> Post:
        return Post(
            id=row["id"],
            client_id=row["client_id"],
            post_date=row["post_date"],
            content_type=row["content_type"],
            platform=row["platform"],
            title=row["title"],
            description=row["description"],
            caption=row["caption"],
            cta=row["cta"],
            status=row["status"],
            operation_id=row["operation_id"] if "operation_id" in row.keys() else None,
            trello_board_id=row["trello_board_id"] if "trello_board_id" in row.keys() else None,
        )
