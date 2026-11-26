from collections.abc import Callable
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


def test_spa_fallback_serves_index_for_deep_links(
    make_client: Callable[[Path | None], TestClient], tmp_path: Path
) -> None:
    (tmp_path / "index.html").write_text("<html>kairos</html>")
    r = make_client(tmp_path).get("/boards/1")
    assert r.status_code == 200 and "kairos" in r.text


def test_unknown_api_path_is_a_json_404(
    make_client: Callable[[Path | None], TestClient], tmp_path: Path
) -> None:
    (tmp_path / "index.html").write_text("<html>kairos</html>")
    r = make_client(tmp_path).get("/api/nope")
    assert r.status_code == 404 and r.headers["content-type"].startswith("application/json")


def test_app_starts_without_a_static_dir(client: TestClient) -> None:
    assert client.get("/api/health").status_code == 200
    assert client.get("/").status_code == 404


@pytest.fixture
def static_dir(tmp_path: Path) -> Path:
    """A built-SPA lookalike: an index, a root-level file and an assets folder."""
    root = tmp_path / "static"
    (root / "assets").mkdir(parents=True)
    (root / "index.html").write_text("<html>kairos</html>")
    (root / "manifest.webmanifest").write_text('{"name": "Kairos"}')
    (root / "assets" / "app.js").write_text("console.log('kairos');")
    return root


def test_app_starts_when_the_static_dir_does_not_exist(
    make_client: Callable[[Path | None], TestClient], tmp_path: Path
) -> None:
    client = make_client(tmp_path / "missing")
    assert client.get("/api/health").status_code == 200
    assert client.get("/boards/1").status_code == 404


def test_a_static_dir_without_an_index_is_not_served(
    make_client: Callable[[Path | None], TestClient], tmp_path: Path
) -> None:
    (tmp_path / "manifest.webmanifest").write_text("{}")
    client = make_client(tmp_path)
    assert client.get("/api/health").status_code == 200
    assert client.get("/manifest.webmanifest").status_code == 404


def test_the_root_serves_the_index(
    make_client: Callable[[Path | None], TestClient], static_dir: Path
) -> None:
    r = make_client(static_dir).get("/")
    assert r.status_code == 200 and "kairos" in r.text


def test_a_real_file_is_served_instead_of_the_index(
    make_client: Callable[[Path | None], TestClient], static_dir: Path
) -> None:
    r = make_client(static_dir).get("/manifest.webmanifest")
    assert r.status_code == 200 and r.json() == {"name": "Kairos"}


def test_assets_are_served_and_a_missing_asset_is_a_404_not_the_index(
    make_client: Callable[[Path | None], TestClient], static_dir: Path
) -> None:
    client = make_client(static_dir)
    assert client.get("/assets/app.js").text == "console.log('kairos');"
    assert client.get("/assets/missing.js").status_code == 404


@pytest.mark.parametrize("path", ["/api", "/api/", "/api/tasks/1", "/mcp", "/mcp/", "/mcp/sse"])
def test_the_catch_all_never_shadows_api_or_mcp(
    make_client: Callable[[Path | None], TestClient], static_dir: Path, path: str
) -> None:
    r = make_client(static_dir).get(path)
    assert r.status_code == 404 and "kairos" not in r.text


def test_paths_outside_the_static_dir_are_never_served(
    make_client: Callable[[Path | None], TestClient], static_dir: Path
) -> None:
    (static_dir.parent / "secret.txt").write_text("top secret")
    r = make_client(static_dir).get("/%2e%2e/secret.txt")
    assert "top secret" not in r.text


def test_a_missing_assets_dir_is_a_404_not_a_crash(
    make_client: Callable[[Path | None], TestClient], tmp_path: Path
) -> None:
    (tmp_path / "index.html").write_text("<html>kairos</html>")
    assert make_client(tmp_path).get("/assets/app.js").status_code == 404


def test_a_path_the_filesystem_rejects_falls_back_to_the_index(
    make_client: Callable[[Path | None], TestClient],
    static_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = make_client(static_dir)

    def reject(self: Path, strict: bool = False) -> Path:
        raise ValueError("embedded null byte")

    # POSIX raises this for a NUL byte in a path; Windows does not, so force it.
    monkeypatch.setattr(Path, "resolve", reject)
    r = client.get("/a%00b")
    assert r.status_code == 200 and "kairos" in r.text
