from collections.abc import Callable
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

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
