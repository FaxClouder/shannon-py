from shannon_py.application.tasks import (
    InMemoryTaskRepository,
    TaskRequest,
    TaskService,
    TaskStatus,
)
from shannon_py.llm.providers import MockProvider
from shannon_py.memory.session import InMemorySessionRepository
from shannon_py.orchestration.checkpoints import InMemoryCheckpointManager
from shannon_py.orchestration.dag_graph import DAGGraph
from shannon_py.orchestration.react_graph import ReactGraph
from shannon_py.orchestration.research_graph import ResearchGraph
from shannon_py.orchestration.router import WorkflowRouter
from shannon_py.orchestration.simple_graph import SimpleGraph
from shannon_py.policy import PolicyEngine
from shannon_py.streaming.events import InMemoryEventBus, StreamEventType
from shannon_py.streaming.sse import SSEBroker
from shannon_py.tools import CalculatorTool, ToolExecutor, ToolRegistry


def create_task_service() -> TaskService:
    event_bus = InMemoryEventBus()
    tool_registry = ToolRegistry()
    tool_registry.register(CalculatorTool())
    tool_executor = ToolExecutor(tool_registry)
    return TaskService(
        repository=InMemoryTaskRepository(),
        simple_graph=SimpleGraph(MockProvider()),
        react_graph=ReactGraph(tool_executor),
        dag_graph=DAGGraph(SimpleGraph(MockProvider())),
        research_graph=ResearchGraph(MockProvider()),
        workflow_router=WorkflowRouter(),
        session_repository=InMemorySessionRepository(),
        event_bus=event_bus,
        checkpoint_manager=InMemoryCheckpointManager(),
        sse_broker=SSEBroker(event_bus),
        policy_engine=PolicyEngine(),
    )


async def test_task_service_completes_simple_task_with_mock_provider() -> None:
    service = create_task_service()

    handle = await service.submit(TaskRequest(query="summarize this"))
    assert handle.status == TaskStatus.QUEUED

    run_result = await service.run_task(handle.task_id)
    result = await service.get_result(handle.task_id)

    assert run_result is not None
    assert run_result.status == TaskStatus.COMPLETED
    assert result is not None
    assert result.status == TaskStatus.COMPLETED
    assert result.output == "Mock response for: summarize this"
    assert result.metadata["provider"] == "mock"


async def test_task_service_cancels_queued_task() -> None:
    service = create_task_service()

    handle = await service.submit(TaskRequest(query="cancel this"))
    cancel_result = await service.cancel(handle.task_id)
    result = await service.get_result(handle.task_id)

    assert handle.status == TaskStatus.QUEUED
    assert cancel_result is not None
    assert cancel_result.status == TaskStatus.CANCELLED
    assert result is not None
    assert result.status == TaskStatus.CANCELLED
    assert result.error == "Task cancelled."


async def test_task_service_completes_react_task_with_calculator() -> None:
    service = create_task_service()

    handle = await service.submit(TaskRequest(query="2 + 3 * 4", mode="react"))
    run_result = await service.run_task(handle.task_id)
    events = await service.list_events(handle.workflow_id)

    assert run_result is not None
    assert run_result.status == TaskStatus.COMPLETED
    assert run_result.output == "Calculator result: 14"
    assert run_result.metadata["tool_name"] == "calculator"
    assert [event.type for event in events] == [
        StreamEventType.WORKFLOW_STARTED,
        StreamEventType.TOOL_INVOKED,
        StreamEventType.TOOL_OBSERVATION,
        StreamEventType.LLM_OUTPUT,
        StreamEventType.WORKFLOW_COMPLETED,
        StreamEventType.STREAM_END,
    ]


async def test_task_service_completes_dag_task() -> None:
    service = create_task_service()

    handle = await service.submit(TaskRequest(query="first step; second step", mode="dag"))
    result = await service.run_task(handle.task_id)

    assert result is not None
    assert result.status == TaskStatus.COMPLETED
    assert result.metadata["selected_mode"] == "dag"
    assert result.metadata["step_count"] == 2
    assert "1. Mock response for: first step" in (result.output or "")


async def test_task_service_completes_research_task() -> None:
    service = create_task_service()

    handle = await service.submit(TaskRequest(query="research agent runtimes", mode="research"))
    result = await service.run_task(handle.task_id)

    assert result is not None
    assert result.status == TaskStatus.COMPLETED
    assert result.metadata["selected_mode"] == "research"
    assert result.metadata["sources"][0]["source_type"] == "mock"


async def test_task_service_auto_routes_complex_task_to_dag() -> None:
    service = create_task_service()

    handle = await service.submit(TaskRequest(query="plan one; plan two", mode="auto"))
    result = await service.run_task(handle.task_id)

    assert result is not None
    assert result.status == TaskStatus.COMPLETED
    assert result.metadata["requested_mode"] == "auto"
    assert result.metadata["selected_mode"] == "dag"


async def test_task_service_passes_session_history_to_next_task() -> None:
    service = create_task_service()

    first = await service.submit(TaskRequest(query="first", session_id="session_a"))
    await service.run_task(first.task_id)
    second = await service.submit(TaskRequest(query="second", session_id="session_a"))
    await service.run_task(second.task_id)

    result = await service.get_result(second.task_id)
    messages = await service.list_session_messages("session_a")

    assert result is not None
    assert result.metadata["session_history_count"] == 2
    assert [message.content for message in messages] == [
        "first",
        "Mock response for: first",
        "second",
        "Mock response for: second",
    ]


async def test_task_service_publishes_workflow_events() -> None:
    service = create_task_service()

    handle = await service.submit(TaskRequest(query="events"))
    await service.run_task(handle.task_id)
    events = await service.list_events(handle.workflow_id)

    assert [event.type for event in events] == [
        StreamEventType.WORKFLOW_STARTED,
        StreamEventType.LLM_OUTPUT,
        StreamEventType.WORKFLOW_COMPLETED,
        StreamEventType.STREAM_END,
    ]


async def test_task_service_saves_running_and_completed_checkpoints() -> None:
    service = create_task_service()

    handle = await service.submit(TaskRequest(query="checkpoint"))
    await service.run_task(handle.task_id)
    checkpoints = await service.list_checkpoints(handle.workflow_id)
    latest = await service.get_latest_checkpoint(handle.workflow_id)

    assert [checkpoint.status for checkpoint in checkpoints] == ["running", "completed"]
    assert latest is not None
    assert latest.status == "completed"
    assert latest.state["result"]["output"] == "Mock response for: checkpoint"
