"""A small SQL boundary with local SQLite and optional PostgreSQL support."""

from contextlib import contextmanager
from pathlib import Path
import sqlite3
from typing import Any, Iterator, Mapping


class Session:
    def __init__(self, connection: Any, dialect: str):
        self.connection = connection
        self.dialect = dialect

    def execute(self, sql: str, params: Mapping[str, Any] | None = None):
        if self.dialect == "postgresql":
            from sqlalchemy import text
            return self.connection.execute(text(sql), dict(params or {}))
        return self.connection.execute(sql, dict(params or {}))

    def one(self, sql: str, params: Mapping[str, Any] | None = None) -> dict | None:
        result = self.execute(sql, params)
        row = result.mappings().first() if self.dialect == "postgresql" else result.fetchone()
        return dict(row) if row is not None else None

    def all(self, sql: str, params: Mapping[str, Any] | None = None) -> list[dict]:
        result = self.execute(sql, params)
        rows = result.mappings().all() if self.dialect == "postgresql" else result.fetchall()
        return [dict(row) for row in rows]

    def lock(self, sql: str) -> str:
        return sql + " FOR UPDATE" if self.dialect == "postgresql" else sql


class Database:
    def __init__(self, url: str = "sqlite:///.relaydesk/relaydesk.db"):
        self.url = url
        self.engine = None
        if url.startswith("sqlite:///"):
            self.dialect = "sqlite"
            self.path = Path(url.removeprefix("sqlite:///"))
            self.path.parent.mkdir(parents=True, exist_ok=True)
        elif url.startswith(("postgresql://", "postgresql+psycopg://")):
            from sqlalchemy import create_engine
            self.dialect = "postgresql"
            normalized = url.replace("postgresql://", "postgresql+psycopg://", 1)
            self.engine = create_engine(normalized, pool_pre_ping=True)
        else:
            raise ValueError("Use sqlite:///path or postgresql+psycopg:// connection URLs.")

    @contextmanager
    def transaction(self) -> Iterator[Session]:
        if self.engine is not None:
            with self.engine.begin() as connection:
                yield Session(connection, self.dialect)
            return
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA busy_timeout=10000")
        try:
            connection.execute("BEGIN IMMEDIATE")
            yield Session(connection, self.dialect)
            connection.commit()
        except BaseException:
            connection.rollback()
            raise
        finally:
            connection.close()

    def initialize(self) -> None:
        statements = Path(__file__).with_name("schema.sql").read_text().split(";")
        with self.transaction() as session:
            for statement in statements:
                if statement.strip():
                    session.execute(statement)

    def close(self) -> None:
        if self.engine is not None:
            self.engine.dispose()
