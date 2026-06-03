from shannon_py.application.tasks import (
    InMemoryTaskRepository,
    TaskRequest,
    TaskService,
    TaskStatus,
)
from shannon_py.llm.providers import MockProvider
from shannon_py.orchestration.simple_graph import SimpleGraph


async def test_task_service_completes_simple_task_with_mock_provider() -> None:
    service = TaskService(
        repository=InMemoryTaskRepository(),
        simple_graph=SimpleGraph(MockProvider()),
    )

    handle = await service.submit(TaskRequest(query="summarize this"))
    result = await service.get_result(handle.task_id)

    assert handle.status == TaskStatus.COMPLETED
    assert result is not None
    assert result.status == TaskStatus.COMPLETED
    assert result.output == "Mock response for: summarize this"
    assert result.metadata["provider"] == "mock"


async def test_task_service_turns_unsupported_mode_into_failed_result() -> None:
    service = TaskService(
        repository=InMemoryTaskRepository(),
        simple_graph=SimpleGraph(MockProvider()),
    )

    handle = await service.submit(TaskRequest(query="run this", mode="react"))
    result = await service.get_result(handle.task_id)

    assert handle.status == TaskStatus.FAILED
    assert result is not None
    assert result.status == TaskStatus.FAILED
    assert result.error == "Unsupported task mode: react"
