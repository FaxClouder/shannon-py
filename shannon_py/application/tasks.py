from __future__ import annotations

from collections.abc import AsyncIterator
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
from shannon_py.orchestration.dag_graph import DAGGraph, DAGGraphInput
from shannon_py.orchestration.react_graph import ReactGraph, ReactGraphInput
from shannon_py.orchestration.research_graph import ResearchGraph, ResearchGraphInput
from shannon_py.orchestration.router import WorkflowMode, WorkflowRouter
from shannon_py.orchestration.simple_graph import SimpleGraph, SimpleGraphInput
from shannon_py.policy import PolicyEngine
from shannon_py.streaming.events import InMemoryEventBus, StreamEvent, StreamEventType
from shannon_py.streaming.sse import SSEBroker


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
    mode: WorkflowMode = WorkflowMode.SIMPLE
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

    async def cancel(self, task_id: str, result: TaskResult) -> TaskRecord | None:
        record = self._records.get(task_id)
        if record is None:
            return None
        if record.status in {TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED}:
            return record
        record.status = TaskStatus.CANCELLED
        record.result = result
        record.updated_at = datetime.now(UTC)
        return record


class TaskService:
    def __init__(
        self,
        repository: InMemoryTaskRepository,
        simple_graph: SimpleGraph,
        react_graph: ReactGraph,
        dag_graph: DAGGraph,
        research_graph: ResearchGraph,
        workflow_router: WorkflowRouter,
        session_repository: InMemorySessionRepository,
        event_bus: InMemoryEventBus,
        checkpoint_manager: InMemoryCheckpointManager,
        sse_broker: SSEBroker,
        policy_engine: PolicyEngine,
    ) -> None:
        self._repository = repository
        self._simple_graph = simple_graph
        self._react_graph = react_graph
        self._dag_graph = dag_graph
        self._research_graph = research_graph
        self._workflow_router = workflow_router
        self._session_repository = session_repository
        self._event_bus = event_bus
        self._checkpoint_manager = checkpoint_manager
        self._sse_broker = sse_broker
        self._policy_engine = policy_engine

    async def submit(self, request: TaskRequest) -> TaskHandle:
        policy_decision = self._policy_engine.validate_task_input(request.query)
        if not policy_decision.allowed:
            request.metadata["policy_error"] = policy_decision.reason
        record = await self._repository.create(request)
        return record.to_handle()

    async def run_task(self, task_id: str) -> TaskResult | None:
        record = await self._repository.get(task_id)
        if record is None:
            return None
        if record.status == TaskStatus.CANCELLED:
            return record.result
        return await self._run(record)

    async def cancel(self, task_id: str) -> TaskResult | None:
        record = await self._repository.get(task_id)
        if record is None:
            return None
        if record.result is not None:
            return record.result

        result = TaskResult(
            task_id=record.task_id,
            workflow_id=record.workflow_id,
            session_id=record.session_id,
            status=TaskStatus.CANCELLED,
            error="Task cancelled.",
            metadata=record.request.metadata,
        )
        cancelled = await self._repository.cancel(task_id, result)
        if cancelled is None:
            return None
        await self._save_checkpoint(cancelled, TaskStatus.CANCELLED, result)
        await self._publish(cancelled, StreamEventType.WORKFLOW_FAILED, {"error": result.error})
        await self._publish(cancelled, StreamEventType.STREAM_END)
        return result

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

    def stream_sse(
        self,
        workflow_id: str,
        last_event_id: str | None = None,
        live: bool = False,
        idle_timeout_seconds: float = 30.0,
    ) -> AsyncIterator[str]:
        return self._sse_broker.replay(
            workflow_id,
            last_event_id=last_event_id,
            live=live,
            idle_timeout_seconds=idle_timeout_seconds,
        )

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
            policy_error = record.request.metadata.get("policy_error")
            if isinstance(policy_error, str):
                raise ValueError(policy_error)

            session_history = await self._session_repository.list_messages(record.session_id)
            graph_context = {
                **record.request.context,
                "session_history": [
                    message.model_dump(mode="json") for message in session_history
                ],
            }
            route = self._workflow_router.route(
                record.request.query,
                record.request.mode,
                graph_context,
            )
            graph_context["route"] = route.model_dump(mode="json")
            graph_output = await self._run_graph(record, graph_context, route.selected_mode)
            result_metadata = {
                **record.request.metadata,
                **graph_output.metadata,
                "requested_mode": record.request.mode,
                "selected_mode": route.selected_mode,
                "complexity_score": route.complexity_score,
                "route_reason": route.reason,
            }
            if route.selected_mode == WorkflowMode.SIMPLE:
                result_metadata.update(
                    {
                        "provider": graph_output.provider,
                        "model": graph_output.model,
                    }
                )

            result = TaskResult(
                task_id=record.task_id,
                workflow_id=record.workflow_id,
                session_id=record.session_id,
                status=TaskStatus.COMPLETED,
                output=graph_output.output,
                metadata=result_metadata,
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
                    metadata=result_metadata,
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

    async def _run_graph(
        self,
        record: TaskRecord,
        graph_context: dict[str, Any],
        selected_mode: WorkflowMode,
    ) -> Any:
        if selected_mode == WorkflowMode.SIMPLE:
            return await self._simple_graph.run(
                SimpleGraphInput(
                    task_id=record.task_id,
                    workflow_id=record.workflow_id,
                    session_id=record.session_id,
                    query=record.request.query,
                    context=graph_context,
                )
            )

        if selected_mode == WorkflowMode.REACT:
            graph_output = await self._react_graph.run(
                ReactGraphInput(
                    task_id=record.task_id,
                    workflow_id=record.workflow_id,
                    session_id=record.session_id,
                    query=record.request.query,
                    context=graph_context,
                )
            )
            await self._publish(
                record,
                StreamEventType.TOOL_INVOKED,
                {"tool_name": graph_output.tool_name},
            )
            event_type = (
                StreamEventType.TOOL_OBSERVATION
                if graph_output.tool_result.success
                else StreamEventType.TOOL_ERROR
            )
            await self._publish(
                record,
                event_type,
                graph_output.tool_result.model_dump(mode="json"),
            )
            return graph_output

        if selected_mode == WorkflowMode.DAG:
            return await self._dag_graph.run(
                DAGGraphInput(
                    task_id=record.task_id,
                    workflow_id=record.workflow_id,
                    session_id=record.session_id,
                    query=record.request.query,
                    context=graph_context,
                )
            )

        if selected_mode == WorkflowMode.RESEARCH:
            return await self._research_graph.run(
                ResearchGraphInput(
                    task_id=record.task_id,
                    workflow_id=record.workflow_id,
                    session_id=record.session_id,
                    query=record.request.query,
                    context=graph_context,
                )
            )

        raise ValueError(f"Unsupported task mode: {selected_mode}")

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
