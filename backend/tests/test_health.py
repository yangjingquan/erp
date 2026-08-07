from fastapi.testclient import TestClient

from app.main import app


def test_health_uses_unified_response_shape():
    response = TestClient(app).get("/api/health")

    assert response.status_code == 200
    assert set(response.json()) == {"code", "msg", "data"}
