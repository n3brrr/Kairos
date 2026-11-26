from datetime import UTC
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import text

from kairos.adapters.db.engine import make_engine
from kairos.adapters.runtime import system_clock, uuid_ids
from kairos.config import Settings
from kairos.features.registry.service import RegistryService
from kairos.features.tasks.queries import TaskQueries
from kairos.features.tasks.service import TaskService
from kairos.main import create_app


def _client(data_dir: Path) -> tuple[TestClient, Settings]:
    settings = Settings(data_dir=data_dir)
    return TestClient(create_app(settings), base_url="http://localhost"), settings


def _revision(settings: Settings) -> str:
    engine = make_engine(settings.database_path, read_only=True)
    with engine.connect() as conn:
        revision = conn.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
    engine.dispose()
    return str(revision)


def test_starting_the_app_creates_the_data_directory_and_migrates_the_database(tmp_path: Path):
    client, settings = _client(tmp_path / "not-there-yet")
    with client:
        assert client.get("/api/health").status_code == 200
        assert settings.database_path.is_file()
    assert _revision(settings) == "0001"


def test_the_services_are_ready_on_the_app_state(tmp_path: Path):
    app = create_app(Settings(data_dir=tmp_path))
    with TestClient(app, base_url="http://localhost"):
        assert isinstance(app.state.tasks, TaskService)
        assert isinstance(app.state.registry, RegistryService)
        assert isinstance(app.state.queries, TaskQueries)


def test_starting_twice_keeps_the_data_and_does_not_fail(tmp_path: Path):
    client, settings = _client(tmp_path)
    with client:
        pass
    engine = make_engine(settings.database_path)
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO agents VALUES ('a1', 'agent', '[]', '[]', 3)"))
    engine.dispose()
    again, _ = _client(tmp_path)
    with again:
        assert again.get("/api/health").status_code == 200
    engine = make_engine(settings.database_path, read_only=True)
    with engine.connect() as conn:
        assert conn.execute(text("SELECT count(*) FROM agents")).scalar_one() == 1
    engine.dispose()


def test_the_default_clock_is_utc_and_the_default_ids_are_unique():
    assert system_clock().tzinfo is not None
    assert system_clock().utcoffset() == UTC.utcoffset(None)
    ids = {uuid_ids() for _ in range(100)}
    assert len(ids) == 100
    assert all(len(i) == 32 for i in ids)
