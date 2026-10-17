from fastapi.testclient import TestClient


def test_health_returns_ok_and_db_up(client: TestClient) -> None:
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["database"] == "up"
    assert body["version"]
    assert response.headers["X-Request-ID"]
