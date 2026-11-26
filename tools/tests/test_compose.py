from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def compose() -> dict:
    return yaml.safe_load((ROOT / "compose.yaml").read_text(encoding="utf-8"))


def test_host_port_is_published_on_loopback_only(compose):
    assert compose["services"]["kairos"]["ports"] == ["127.0.0.1:8000:8000"]


def test_data_lives_in_a_named_volume(compose):
    assert "kairos-data:/data" in compose["services"]["kairos"]["volumes"]
    assert "kairos-data" in compose["volumes"]


def test_container_is_read_only_and_drops_privileges(compose):
    svc = compose["services"]["kairos"]
    assert svc["read_only"] is True and svc["cap_drop"] == ["ALL"]
    assert "no-new-privileges:true" in svc["security_opt"]
