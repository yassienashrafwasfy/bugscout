"""psycopg pool + tiny query helpers. JSON values go in/out as jsonb."""
from __future__ import annotations

import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from psycopg_pool import ConnectionPool

from .. import config

_pool: ConnectionPool | None = None
_lock = threading.Lock()


def init_pool(url: str | None = None) -> ConnectionPool:
    global _pool
    with _lock:
        if _pool is not None:
            _pool.close()
        _pool = ConnectionPool(url or config.DATABASE_URL, min_size=1, max_size=8, open=True,
                               kwargs={"row_factory": dict_row, "autocommit": True})
        _pool.wait(timeout=15)
        return _pool


def pool() -> ConnectionPool:
    return _pool or init_pool()


def close_pool() -> None:
    global _pool
    with _lock:
        if _pool is not None:
            _pool.close()
            _pool = None


def J(v: Any) -> Jsonb:
    return Jsonb(v)


def q(sql: str, params: Any = None) -> list[dict]:
    with pool().connection() as c:
        cur = c.execute(sql, params)
        return cur.fetchall() if cur.description else []


def q1(sql: str, params: Any = None) -> dict | None:
    rows = q(sql, params)
    return rows[0] if rows else None


@contextmanager
def tx():
    """A real transaction (the pool is autocommit; this block turns it off)."""
    with pool().connection() as c:
        c.autocommit = False
        try:
            with c.transaction():
                yield c
        finally:
            c.autocommit = True


def migrate(url: str | None = None) -> list[str]:
    """Apply migrations/*.sql once each, tracked in schema_migration."""
    applied: list[str] = []
    with psycopg.connect(url or config.DATABASE_URL, autocommit=True) as c:
        c.execute("CREATE TABLE IF NOT EXISTS schema_migration (name text PRIMARY KEY, applied_at timestamptz DEFAULT now())")
        c.execute("SELECT pg_advisory_lock(727274)")
        try:
            done = {r[0] for r in c.execute("SELECT name FROM schema_migration").fetchall()}
            for f in sorted(Path(config.MIGRATIONS_DIR).glob("*.sql")):
                if f.name in done:
                    continue
                with c.transaction():
                    c.execute(f.read_text())
                    c.execute("INSERT INTO schema_migration(name) VALUES (%s)", (f.name,))
                applied.append(f.name)
        finally:
            c.execute("SELECT pg_advisory_unlock(727274)")
    return applied
