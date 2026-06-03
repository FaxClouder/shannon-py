from shannon_py.application.tasks import (
    InMemoryTaskRepository,
    TaskRequest,
    TaskService,
    TaskStatus,
)
from shannon_py.llm.providers import MockProvider
from shannon_py.memory.session import InMemorySessionRepository
from shannon_py.orchestration.checkpoints import InMemoryCheckpointManager
from shannon_py.orchestration.simple_graph import SimpleGraph
from shannon_py.streaming.events import InMemoryEventBus, StreamEventType
from shannon_py.streaming.sse import SSEBroker


def create_task_service() -> TaskService:
    event_bus = InMemoryEventBus()
    return TaskService(
        repository=InMemoryTaskRepository(),
        simple_graph=SimpleGraph(MockProvider()),
        session_repository=InMemorySessionRepository(),
        event_bus=event_bus,
        checkpoint_manager=InMemoryCheckpointManager(),
        sse_broker=SSEBroker(event_bus),
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


async def test_task_service_turns_unsupported_mode_into_failed_result() -> None:
    service = create_task_service()

    handle = await service.submit(TaskRequest(query="run this", mode="react"))
    run_result = await service.run_task(handle.task_id)
    result = await service.get_result(handle.task_id)

    assert handle.status == TaskStatus.QUEUED
    assert run_result is not None
    assert run_result.status == TaskStatus.FAILED
    assert result is not None
    assert result.status == TaskStatus.FAILED
    assert result.error == "Unsupported task mode: react"


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
