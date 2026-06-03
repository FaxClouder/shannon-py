from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

from shannon_py.orchestration.simple_graph import SimpleGraph, SimpleGraphInput


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
    ) -> None:
        self._repository = repository
        self._simple_graph = simple_graph

    async def submit(self, request: TaskRequest) -> TaskHandle:
        record = await self._repository.create(request)
        await self._run(record)
        updated = await self._repository.get(record.task_id)
        if updated is None:
            raise RuntimeError(f"Task disappeared after execution: {record.task_id}")
        return updated.to_handle()

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

    async def _run(self, record: TaskRecord) -> None:
        await self._repository.update_status(record.task_id, TaskStatus.RUNNING)

        try:
            if record.request.mode != "simple":
                raise ValueError(f"Unsupported task mode: {record.request.mode}")

            graph_output = await self._simple_graph.run(
                SimpleGraphInput(
                    task_id=record.task_id,
                    workflow_id=record.workflow_id,
                    session_id=record.session_id,
                    query=record.request.query,
                    context=record.request.context,
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
                    "provider": graph_output.provider,
                    "model": graph_output.model,
                },
            )
            await self._repository.update_status(record.task_id, TaskStatus.COMPLETED, result)
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
