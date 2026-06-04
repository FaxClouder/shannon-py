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
    events = events_response.json()
    assert [event["type"] for event in events] == [
        "workflow_started",
        "llm_output",
        "workflow_completed",
        "stream_end",
    ]

    sse_response = client.get(
        f"/api/v1/stream/sse?workflow_id={submitted['workflow_id']}&live=false"
    )

    assert sse_response.status_code == 200
    assert sse_response.headers["content-type"].startswith("text/event-stream")
    assert "event: workflow_started\n" in sse_response.text
    assert "event: stream_end\n" in sse_response.text

    resumed_sse_response = client.get(
        "/api/v1/stream/sse",
        params={
            "workflow_id": submitted["workflow_id"],
            "last_event_id": events[0]["event_id"],
            "live": False,
        },
    )

    assert resumed_sse_response.status_code == 200
    assert "event: workflow_started\n" not in resumed_sse_response.text
    assert "event: llm_output\n" in resumed_sse_response.text

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


def test_cancel_missing_task_returns_404() -> None:
    app = create_app(Settings(environment="test", testing=True))
    client = TestClient(app)

    response = client.post("/api/v1/tasks/task_missing/cancel")

    assert response.status_code == 404
    assert response.json()["detail"] == "Task not found."


def test_invalid_task_mode_returns_validation_error() -> None:
    app = create_app(Settings(environment="test", testing=True))
    client = TestClient(app)

    response = client.post("/api/v1/tasks", json={"query": "bad mode", "mode": "swarm"})

    assert response.status_code == 422


def test_get_missing_latest_checkpoint_returns_404() -> None:
    app = create_app(Settings(environment="test", testing=True))
    client = TestClient(app)

    response = client.get("/api/v1/checkpoints/workflow_missing/latest")

    assert response.status_code == 404
    assert response.json()["detail"] == "Checkpoint not found."


def test_tool_routes_list_and_execute_calculator() -> None:
    app = create_app(Settings(environment="test", testing=True))
    client = TestClient(app)

    list_response = client.get("/api/v1/tools")

    assert list_response.status_code == 200
    assert [tool["name"] for tool in list_response.json()] == ["calculator", "python_exec"]

    execute_response = client.post(
        "/api/v1/tools/calculator/execute",
        json={"arguments": {"expression": "10 / 4"}},
    )

    assert execute_response.status_code == 200
    result = execute_response.json()
    assert result["success"] is True
    assert result["content"] == "2.5"

    python_response = client.post(
        "/api/v1/tools/python_exec/execute",
        json={"arguments": {"session_id": "session_api_tool", "code": "print('ok')"}},
    )

    assert python_response.status_code == 200
    python_result = python_response.json()
    assert python_result["success"] is False
    assert python_result["error"] == "Tool requires approval: python_exec"
    assert python_result["metadata"]["approval_status"] == "pending"

    approvals_response = client.get("/api/v1/approvals")

    assert approvals_response.status_code == 200
    assert approvals_response.json()[0]["subject_name"] == "python_exec"

    approved_python_response = client.post(
        "/api/v1/tools/python_exec/execute",
        json={
            "arguments": {"session_id": "session_api_tool", "code": "print('ok')"},
            "approved": True,
        },
    )

    assert approved_python_response.status_code == 200
    approved_python_result = approved_python_response.json()
    assert approved_python_result["success"] is True
    assert approved_python_result["content"] == "ok\n"


def test_approved_python_exec_runs() -> None:
    app = create_app(Settings(environment="test", testing=True))
    client = TestClient(app)

    python_response = client.post(
        "/api/v1/tools/python_exec/execute",
        json={
            "arguments": {"session_id": "session_api_tool", "code": "print('ok')"},
            "approved": True,
        },
    )

    assert python_response.status_code == 200
    python_result = python_response.json()
    assert python_result["success"] is True
    assert python_result["content"] == "ok\n"


def test_react_task_uses_calculator_tool() -> None:
    app = create_app(Settings(environment="test", testing=True))
    client = TestClient(app)

    submit_response = client.post(
        "/api/v1/tasks",
        json={"query": "6 * 7", "mode": "react"},
    )

    assert submit_response.status_code == 200
    submitted = submit_response.json()

    result_response = client.get(f"/api/v1/tasks/{submitted['task_id']}")

    assert result_response.status_code == 200
    result = result_response.json()
    assert result["status"] == "completed"
    assert result["output"] == "Calculator result: 42"
    assert result["metadata"]["tool_name"] == "calculator"


def test_dag_and_research_task_modes_are_supported() -> None:
    app = create_app(Settings(environment="test", testing=True))
    client = TestClient(app)

    dag = client.post("/api/v1/tasks", json={"query": "a; b", "mode": "dag"}).json()
    research = client.post(
        "/api/v1/tasks",
        json={"query": "research this", "mode": "research"},
    ).json()

    dag_result = client.get(f"/api/v1/tasks/{dag['task_id']}").json()
    research_result = client.get(f"/api/v1/tasks/{research['task_id']}").json()

    assert dag_result["metadata"]["selected_mode"] == "dag"
    assert dag_result["metadata"]["step_count"] == 2
    assert research_result["metadata"]["selected_mode"] == "research"
    assert research_result["metadata"]["sources"][0]["source_type"] == "mock"


def test_metrics_and_run_records_are_exposed() -> None:
    app = create_app(Settings(environment="test", testing=True))
    client = TestClient(app)

    client.post("/api/v1/tasks", json={"query": "metrics test"})
    client.post("/api/v1/tools/calculator/execute", json={"arguments": {"expression": "1+1"}})

    metrics_response = client.get("/metrics")
    runs_response = client.get("/api/v1/runs")
    traces_response = client.get("/api/v1/traces")

    assert metrics_response.status_code == 200
    assert "tasks_submitted" in metrics_response.text
    assert "tool_calls" in metrics_response.text
    assert runs_response.status_code == 200
    assert len(runs_response.json()) >= 1
    assert traces_response.status_code == 200
    assert len(traces_response.json()) >= 1


def test_openai_compatible_chat_completions_returns_mock_response() -> None:
    app = create_app(Settings(environment="test", testing=True))
    client = TestClient(app)

    response = client.post(
        "/v1/chat/completions",
        json={
            "model": "mock-default",
            "messages": [
                {"role": "user", "content": "Say hello"},
            ],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["object"] == "chat.completion"
    assert payload["choices"][0]["message"]["role"] == "assistant"
    assert "Mock response for:" in payload["choices"][0]["message"]["content"]
