from collections.abc import Callable
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


def test_foreign_host_is_rejected(client: TestClient) -> None:
    assert client.get("/api/health", headers={"Host": "evil.example"}).status_code == 400


@pytest.mark.parametrize("path", ["/api/health", "/api/nope", "/", "/boards/1"])
def test_foreign_host_is_rejected_on_every_route(
    make_client: Callable[[Path | None], TestClient], tmp_path: Path, path: str
) -> None:
    (tmp_path / "index.html").write_text("<html>kairos</html>")
    r = make_client(tmp_path).get(path, headers={"Host": "evil.example"})
    assert r.status_code == 400


@pytest.mark.parametrize("host", ["localhost", "localhost:8000", "127.0.0.1", "127.0.0.1:8000"])
def test_loopback_hosts_are_accepted_with_or_without_a_port(client: TestClient, host: str) -> None:
    assert client.get("/api/health", headers={"Host": host}).status_code == 200
