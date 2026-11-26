import shutil
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Connection, Engine

from kairos.adapters.db.engine import make_engine
from kairos.adapters.db.migrate import upgrade
from kairos.config import Settings
from kairos.main import create_app


@pytest.fixture
def make_client(tmp_path_factory: pytest.TempPathFactory) -> Callable[[Path | None], TestClient]:
    """Build a client for a fresh app, optionally serving the given static directory."""

    def _make_client(static_dir: Path | None) -> TestClient:
        settings = Settings(
            data_dir=tmp_path_factory.mktemp("kairos-data"),
            static_dir=static_dir,
        )
        return TestClient(create_app(settings), base_url="http://localhost")

    return _make_client


@pytest.fixture
def client(make_client: Callable[[Path | None], TestClient]) -> TestClient:
    """A client for an app that has no static directory."""
    return make_client(None)


# --- database fixtures ---------------------------------------------------------------------


@pytest.fixture(scope="session")
def migrated_template(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """A database migrated to head once per session; every test gets its own copy."""
    path = tmp_path_factory.mktemp("kairos-template") / "kairos.db"
    engine = make_engine(path)
    upgrade(engine)
    engine.dispose()  # closes the last connection, which folds the WAL into the file
    return path


@pytest.fixture
def migrated_engine(migrated_template: Path, tmp_path: Path) -> Iterator[Engine]:
    """An engine on a private, migrated copy of the template database."""
    path = tmp_path / "kairos.db"
    shutil.copyfile(migrated_template, path)
    engine = make_engine(path)
    yield engine
    engine.dispose()


@pytest.fixture
def conn(migrated_engine: Engine) -> Iterator[Connection]:
    """A connection that rolls back at the end: tests commit explicitly when they need to."""
    with migrated_engine.connect() as connection:
        yield connection
        connection.rollback()
