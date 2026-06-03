from fastapi.testclient import TestClient

from shannon_py.api.main import create_app
from shannon_py.config import Settings


def test_submit_and_get_task_returns_mock_result() -> None:
    app = create_app(Settings(environment="test", testing=True))
    client = TestClient(app)

    submit_response = client.post("/api/v1/tasks", json={"query": "hello"})

    assert submit_response.status_code == 200
    submitted = submit_response.json()
    assert submitted["status"] == "queued"
    assert submitted["session_id"].startswith("session_")

    get_response = client.get(f"/api/v1/tasks/{submitted['task_id']}")

    assert get_response.status_code == 200
    result = get_response.json()
    assert result["status"] == "completed"
    assert result["output"] == "Mock response for: hello"
    assert result["metadata"]["provider"] == "mock"

    events_response = client.get(f"/api/v1/stream/events/{submitted['workflow_id']}")

    assert events_response.status_code == 200
    assert [event["type"] for event in events_response.json()] == [
        "workflow_started",
        "llm_output",
        "workflow_completed",
        "stream_end",
    ]


def test_get_missing_task_returns_404() -> None:
    app = create_app(Settings(environment="test", testing=True))
    client = TestClient(app)

    response = client.get("/api/v1/tasks/task_missing")

    assert response.status_code == 404
    assert response.json()["detail"] == "Task not found."
