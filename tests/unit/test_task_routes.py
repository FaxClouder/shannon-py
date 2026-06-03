from fastapi.testclient import TestClient

from shannon_py.api.main import create_app
from shannon_py.config import Settings


def test_submit_and_get_task_returns_mock_result() -> None:
    app = create_app(Settings(environment="test", testing=True))
    client = TestClient(app)

    submit_response = client.post(
        "/api/v1/tasks",
        json={"query": "hello", "session_id": "session_route"},
    )

    assert submit_response.status_code == 200
    submitted = submit_response.json()
    assert submitted["status"] == "queued"
    assert submitted["session_id"] == "session_route"

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

    session_response = client.get("/api/v1/sessions/session_route")

    assert session_response.status_code == 200
    session = session_response.json()
    assert [message["content"] for message in session["messages"]] == [
        "hello",
        "Mock response for: hello",
    ]

    checkpoints_response = client.get(f"/api/v1/checkpoints/{submitted['workflow_id']}")

    assert checkpoints_response.status_code == 200
    checkpoints = checkpoints_response.json()
    assert [checkpoint["status"] for checkpoint in checkpoints] == ["running", "completed"]

    latest_response = client.get(f"/api/v1/checkpoints/{submitted['workflow_id']}/latest")

    assert latest_response.status_code == 200
    assert latest_response.json()["state"]["result"]["output"] == "Mock response for: hello"


def test_get_missing_task_returns_404() -> None:
    app = create_app(Settings(environment="test", testing=True))
    client = TestClient(app)

    response = client.get("/api/v1/tasks/task_missing")

    assert response.status_code == 404
    assert response.json()["detail"] == "Task not found."


def test_get_missing_latest_checkpoint_returns_404() -> None:
    app = create_app(Settings(environment="test", testing=True))
    client = TestClient(app)

    response = client.get("/api/v1/checkpoints/workflow_missing/latest")

    assert response.status_code == 404
    assert response.json()["detail"] == "Checkpoint not found."
