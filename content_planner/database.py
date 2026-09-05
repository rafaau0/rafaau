from __future__ import annotations

import sqlite3
import sys
import os
import shutil
from datetime import date
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
                    INSERT INTO clientes (name, niche, instagram, posting_frequency, objective, notes, operation_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        self._clean(client.name), self._clean(client.niche), self._clean(client.instagram),
                        self._clean(client.posting_frequency), self._clean(client.objective), self._clean(client.notes),
                        client.operation_id,
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
                    client.id,
                ),
            )

    def delete_client(self, client_id: int) -> None:
        with self.connect() as conn:
            conn.execute("DELETE FROM clientes WHERE id=?", (client_id,))

    def search_clients(self, term: str = "") -> list[Client]:
        like = f"%{term.strip()}%"
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM clientes
                WHERE name LIKE ? OR niche LIKE ? OR instagram LIKE ?
                ORDER BY name COLLATE NOCASE
                """,
                (like, like, like),
            ).fetchall()
        return [self._row_to_client(row) for row in rows]

    def get_client(self, client_id: int) -> Client | None:
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM clientes WHERE id=?", (client_id,)).fetchone()
        return self._row_to_client(row) if row else None

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

    def dashboard_stats(self) -> dict[str, int]:
        with self.connect() as conn:
            clients = conn.execute("SELECT COUNT(*) FROM clientes").fetchone()[0]
            posts = conn.execute("SELECT COUNT(*) FROM posts").fetchone()[0]
            pending = conn.execute("SELECT COUNT(*) FROM posts WHERE status='Pendente'").fetchone()[0]
            done = conn.execute("SELECT COUNT(*) FROM posts WHERE status='Concluído'").fetchone()[0]
        return {"clients": clients, "posts": posts, "pending": pending, "done": done}

    @staticmethod
    def _clean(value: str) -> str:
        return value.strip()

    @staticmethod
    def _validate_client(client: Client) -> None:
        if not client.name.strip():
            raise ValueError("Nome do cliente é obrigatório.")

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
