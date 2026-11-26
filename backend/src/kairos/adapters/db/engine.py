"""The SQLite engine: WAL, foreign keys and a write lock taken when a transaction begins."""

import sqlite3
from pathlib import Path

from sqlalchemy import Connection, Engine, create_engine, event
from sqlalchemy.pool import ConnectionPoolEntry, StaticPool


def make_engine(
    path: Path | None, *, read_only: bool = False, busy_timeout_ms: int = 5000
) -> Engine:
    """Build the engine for the database file at `path`, or a shared in-memory one for `None`.

    Every transaction starts with `BEGIN IMMEDIATE` (ADR-0002), so two writers queue instead of
    failing half-way. A `read_only` engine only reads: it never sets the journal mode and begins
    plain transactions.
    """
    if path is None:
        engine = create_engine(
            "sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False}
        )
    else:
        engine = create_engine(f"sqlite:///{path}", connect_args={"check_same_thread": False})

    def on_connect(dbapi_connection: sqlite3.Connection, _record: ConnectionPoolEntry) -> None:
        # Take transaction control away from the driver: the "begin" hook below owns it.
        dbapi_connection.isolation_level = None
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute(f"PRAGMA busy_timeout={int(busy_timeout_ms)}")
        if read_only:
            cursor.execute("PRAGMA query_only=ON")
        elif path is not None:
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.close()

    def on_begin(connection: Connection) -> None:
        connection.exec_driver_sql("BEGIN" if read_only else "BEGIN IMMEDIATE")

    event.listen(engine, "connect", on_connect)
    event.listen(engine, "begin", on_begin)
    return engine
