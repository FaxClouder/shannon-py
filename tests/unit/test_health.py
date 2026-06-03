from fastapi.testclient import TestClient

from shannon_py.api.main import create_app
from shannon_py.config import Settings


def test_health_route_returns_service_status() -> None:
    app = create_app(Settings(app_name="Test Shannon", environment="test", testing=True))
    client = TestClient(app)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "Test Shannon",
        "environment": "test",
        "version": "0.1.0",
    }
