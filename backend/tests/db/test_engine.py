from pathlib import Path

import pytest
from sqlalchemy.exc import OperationalError

from kairos.adapters.db.engine import make_engine


def test_file_engine_uses_wal_foreign_keys_and_a_busy_timeout(tmp_path: Path):
    engine = make_engine(tmp_path / "k.db")
    with engine.connect() as connection:
        assert connection.exec_driver_sql("PRAGMA journal_mode").scalar() == "wal"
        assert connection.exec_driver_sql("PRAGMA foreign_keys").scalar() == 1
        assert connection.exec_driver_sql("PRAGMA busy_timeout").scalar() == 5000
    engine.dispose()


def test_memory_engine_enforces_foreign_keys_and_is_shared_across_connections():
    engine = make_engine(None)
    with engine.begin() as connection:
        assert connection.exec_driver_sql("PRAGMA foreign_keys").scalar() == 1
        connection.exec_driver_sql("CREATE TABLE t (x INTEGER)")
    with engine.connect() as connection:
        assert connection.exec_driver_sql("SELECT count(*) FROM t").scalar() == 0
    engine.dispose()


def test_a_transaction_takes_the_write_lock_when_it_begins(tmp_path: Path):
    path = tmp_path / "k.db"
    first = make_engine(path, busy_timeout_ms=100)
    second = make_engine(path, busy_timeout_ms=100)
    with first.begin() as connection:
        connection.exec_driver_sql("SELECT 1")  # only reads, yet the lock is already taken
        with pytest.raises(OperationalError, match="locked"), second.begin():
            pass
    with second.begin() as connection:  # released at commit
        connection.exec_driver_sql("SELECT 1")
    first.dispose()
    second.dispose()


def test_a_rolled_back_transaction_leaves_no_trace(tmp_path: Path):
    engine = make_engine(tmp_path / "k.db")
    with engine.begin() as connection:
        connection.exec_driver_sql("CREATE TABLE t (x INTEGER)")
    with engine.connect() as connection:
        connection.exec_driver_sql("INSERT INTO t VALUES (1)")
        connection.rollback()
    with engine.connect() as connection:
        assert connection.exec_driver_sql("SELECT count(*) FROM t").scalar() == 0
    engine.dispose()


def test_read_only_engine_reads_but_cannot_write(tmp_path: Path):
    path = tmp_path / "k.db"
    writer = make_engine(path)
    with writer.begin() as connection:
        connection.exec_driver_sql("CREATE TABLE t (x INTEGER)")
    writer.dispose()
    reader = make_engine(path, read_only=True)
    with reader.connect() as connection:
        assert connection.exec_driver_sql("SELECT count(*) FROM t").scalar() == 0
    with pytest.raises(OperationalError, match="readonly"), reader.begin() as connection:
        connection.exec_driver_sql("INSERT INTO t VALUES (1)")
    reader.dispose()
