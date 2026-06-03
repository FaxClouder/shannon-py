from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

from shannon_py.memory.session import (
    ConversationMessage,
    InMemorySessionRepository,
    MessageRole,
    Session,
)
from shannon_py.orchestration.checkpoints import InMemoryCheckpointManager, WorkflowCheckpoint
from shannon_py.orchestration.simple_graph import SimpleGraph, SimpleGraphInput
from shannon_py.streaming.events import InMemoryEventBus, StreamEvent, StreamEventType


class TaskStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    PAUSED = "paused"


class TaskRequest(BaseModel):
    query: str = Field(min_length=1, max_length=100_000)
    session_id: str | None = None
    mode: str = "simple"
    context: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class TaskHandle(BaseModel):
    task_id: str
    workflow_id: str
    session_id: str
    status: TaskStatus
    metadata: dict[str, Any] = Field(default_factory=dict)


class TaskResult(BaseModel):
    task_id: str
    workflow_id: str
    session_id: str
    status: TaskStatus
    output: str | None = None
    error: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class TaskRecord(BaseModel):
    task_id: str
    workflow_id: str
    session_id: str
    request: TaskRequest
    status: TaskStatus
    result: TaskResult | None = None
    created_at: datetime
    updated_at: datetime

    def to_handle(self) -> TaskHandle:
        return TaskHandle(
            task_id=self.task_id,
            workflow_id=self.workflow_id,
            session_id=self.session_id,
            status=self.status,
            metadata=self.request.metadata,
        )


class InMemoryTaskRepository:
    def __init__(self) -> None:
        self._records: dict[str, TaskRecord] = {}

    async def create(self, request: TaskRequest) -> TaskRecord:
        now = datetime.now(UTC)
        record = TaskRecord(
            task_id=f"task_{uuid4().hex}",
            workflow_id=f"workflow_{uuid4().hex}",
            session_id=request.session_id or f"session_{uuid4().hex}",
            request=request,
            status=TaskStatus.QUEUED,
            created_at=now,
            updated_at=now,
        )
        self._records[record.task_id] = record
        return record

    async def get(self, task_id: str) -> TaskRecord | None:
        return self._records.get(task_id)

    async def update_status(
        self,
        task_id: str,
        status: TaskStatus,
        result: TaskResult | None = None,
    ) -> TaskRecord:
        record = self._records[task_id]
        record.status = status
        record.updated_at = datetime.now(UTC)
        if result is not None:
            record.result = result
        return record


class TaskService:
    def __init__(
        self,
        repository: InMemoryTaskRepository,
        simple_graph: SimpleGraph,
        session_repository: InMemorySessionRepository,
        event_bus: InMemoryEventBus,
        checkpoint_manager: InMemoryCheckpointManager,
    ) -> None:
        self._repository = repository
        self._simple_graph = simple_graph
        self._session_repository = session_repository
        self._event_bus = event_bus
        self._checkpoint_manager = checkpoint_manager

    async def submit(self, request: TaskRequest) -> TaskHandle:
        record = await self._repository.create(request)
        return record.to_handle()

    async def run_task(self, task_id: str) -> TaskResult | None:
        record = await self._repository.get(task_id)
        if record is None:
            return None
        return await self._run(record)

    async def get_result(self, task_id: str) -> TaskResult | None:
        record = await self._repository.get(task_id)
        if record is None:
            return None
        if record.result is not None:
            return record.result
        return TaskResult(
            task_id=record.task_id,
            workflow_id=record.workflow_id,
            session_id=record.session_id,
            status=record.status,
            metadata=record.request.metadata,
        )

    async def list_events(self, workflow_id: str) -> list[StreamEvent]:
        return await self._event_bus.list_events(workflow_id)

    async def list_session_messages(self, session_id: str) -> list[ConversationMessage]:
        return await self._session_repository.list_messages(session_id)

    async def get_session(self, session_id: str) -> Session:
        return await self._session_repository.get_session(session_id)

    async def list_checkpoints(self, workflow_id: str) -> list[WorkflowCheckpoint]:
        return await self._checkpoint_manager.list_checkpoints(workflow_id)

    async def get_latest_checkpoint(self, workflow_id: str) -> WorkflowCheckpoint | None:
        return await self._checkpoint_manager.latest(workflow_id)

    async def _run(self, record: TaskRecord) -> TaskResult:
        await self._repository.update_status(record.task_id, TaskStatus.RUNNING)
        await self._save_checkpoint(record, TaskStatus.RUNNING)
        await self._publish(record, StreamEventType.WORKFLOW_STARTED)

        try:
            if record.request.mode != "simple":
                raise ValueError(f"Unsupported task mode: {record.request.mode}")

            session_history = await self._session_repository.list_messages(record.session_id)
            graph_output = await self._simple_graph.run(
                SimpleGraphInput(
                    task_id=record.task_id,
                    workflow_id=record.workflow_id,
                    session_id=record.session_id,
                    query=record.request.query,
                    context={
                        **record.request.context,
                        "session_history": [
                            message.model_dump(mode="json") for message in session_history
                        ],
                    },
                )
            )
            result = TaskResult(
                task_id=record.task_id,
                workflow_id=record.workflow_id,
                session_id=record.session_id,
                status=TaskStatus.COMPLETED,
                output=graph_output.output,
                metadata={
                    **record.request.metadata,
                    **graph_output.metadata,
                    "provider": graph_output.provider,
                    "model": graph_output.model,
                },
            )
            await self._repository.update_status(record.task_id, TaskStatus.COMPLETED, result)
            await self._save_checkpoint(record, TaskStatus.COMPLETED, result)
            await self._session_repository.append_message(
                record.session_id,
                ConversationMessage(
                    role=MessageRole.USER,
                    content=record.request.query,
                    task_id=record.task_id,
                ),
            )
            await self._session_repository.append_message(
                record.session_id,
                ConversationMessage(
                    role=MessageRole.ASSISTANT,
                    content=graph_output.output,
                    task_id=record.task_id,
                    metadata={"provider": graph_output.provider, "model": graph_output.model},
                ),
            )
            await self._publish(
                record,
                StreamEventType.LLM_OUTPUT,
                {"output": graph_output.output},
            )
            await self._publish(record, StreamEventType.WORKFLOW_COMPLETED)
            await self._publish(record, StreamEventType.STREAM_END)
            return result
        except Exception as exc:
            result = TaskResult(
                task_id=record.task_id,
                workflow_id=record.workflow_id,
                session_id=record.session_id,
                status=TaskStatus.FAILED,
                error=str(exc),
                metadata=record.request.metadata,
            )
            await self._repository.update_status(record.task_id, TaskStatus.FAILED, result)
            await self._save_checkpoint(record, TaskStatus.FAILED, result)
            await self._publish(record, StreamEventType.WORKFLOW_FAILED, {"error": result.error})
            await self._publish(record, StreamEventType.STREAM_END)
            return result

    async def _publish(
        self,
        record: TaskRecord,
        event_type: StreamEventType,
        payload: dict[str, Any] | None = None,
    ) -> None:
        await self._event_bus.publish(
            StreamEvent(
                workflow_id=record.workflow_id,
                task_id=record.task_id,
                type=event_type,
                payload=payload or {},
            )
        )

    async def _save_checkpoint(
        self,
        record: TaskRecord,
        status: TaskStatus,
        result: TaskResult | None = None,
    ) -> None:
        state: dict[str, Any] = {
            "query": record.request.query,
            "mode": record.request.mode,
            "context": record.request.context,
            "metadata": record.request.metadata,
        }
        if result is not None:
            state["result"] = result.model_dump(mode="json")

        await self._checkpoint_manager.save(
            WorkflowCheckpoint(
                workflow_id=record.workflow_id,
                task_id=record.task_id,
                session_id=record.session_id,
                status=status,
                state=state,
            )
        )
