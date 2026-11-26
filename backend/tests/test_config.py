from pathlib import Path

import pytest

from kairos.config import Settings

ENV_VARS = ("KAIROS_DATA_DIR", "KAIROS_STATIC_DIR", "KAIROS_ALLOWED_HOSTS")


@pytest.fixture(autouse=True)
def clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ENV_VARS:
        monkeypatch.delenv(name, raising=False)


def test_defaults() -> None:
    settings = Settings()
    assert settings.data_dir == Path("/data")
    assert settings.static_dir is None
    assert settings.allowed_hosts == ["localhost", "127.0.0.1"]


def test_settings_are_read_from_kairos_prefixed_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KAIROS_DATA_DIR", "/srv/kairos")
    monkeypatch.setenv("KAIROS_STATIC_DIR", "/srv/static")
    monkeypatch.setenv("KAIROS_ALLOWED_HOSTS", '["localhost", "kairos.test"]')
    settings = Settings()
    assert settings.data_dir == Path("/srv/kairos")
    assert settings.static_dir == Path("/srv/static")
    assert settings.allowed_hosts == ["localhost", "kairos.test"]


def test_database_lives_inside_the_data_directory():
    assert Settings(data_dir=Path("/data")).database_path == Path("/data/kairos.db")
