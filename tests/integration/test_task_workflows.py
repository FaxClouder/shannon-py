from fastapi.testclient import TestClient

from shannon_py.api.main import create_app
from shannon_py.config import Settings


def test_simple_task_workflow_submit_query_and_session() -> None:
    client = TestClient(create_app(Settings(environment="test", testing=True)))

    submitted = client.post(
        "/api/v1/tasks",
        json={"query": "integration simple", "session_id": "session_integration"},
    ).json()

    result = client.get(f"/api/v1/tasks/{submitted['task_id']}").json()
    session = client.get("/api/v1/sessions/session_integration").json()

    assert result["status"] == "completed"
    assert result["output"] == "Mock response for: integration simple"
    assert [message["role"] for message in session["messages"]] == ["user", "assistant"]


def test_react_calculator_workflow_records_tool_events() -> None:
    client = TestClient(create_app(Settings(environment="test", testing=True)))

    submitted = client.post(
        "/api/v1/tasks",
        json={"query": "8 + 5", "mode": "react"},
    ).json()

    result = client.get(f"/api/v1/tasks/{submitted['task_id']}").json()
    events = client.get(f"/api/v1/stream/events/{submitted['workflow_id']}").json()
    sse = client.get(
        "/api/v1/stream/sse",
        params={"workflow_id": submitted["workflow_id"], "live": False},
    )

    assert result["output"] == "Calculator result: 13"
    assert "tool_invoked" in [event["type"] for event in events]
    assert "event: tool_observation\n" in sse.text
