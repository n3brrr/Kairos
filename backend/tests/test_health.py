from fastapi.testclient import TestClient

import kairos


def test_health_returns_ok(client: TestClient) -> None:
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok", "version": kairos.__version__}


def test_health_has_a_stable_operation_id(client: TestClient) -> None:
    schema = client.get("/openapi.json").json()
    assert schema["paths"]["/api/health"]["get"]["operationId"] == "get_health"
