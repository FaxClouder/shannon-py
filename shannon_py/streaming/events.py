from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class StreamEventType(StrEnum):
    WORKFLOW_STARTED = "workflow_started"
    WORKFLOW_COMPLETED = "workflow_completed"
    WORKFLOW_FAILED = "workflow_failed"
    LLM_OUTPUT = "llm_output"
    STREAM_END = "stream_end"


class StreamEvent(BaseModel):
    event_id: str = Field(default_factory=lambda: f"event_{uuid4().hex}")
    workflow_id: str
    task_id: str
    type: StreamEventType
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class InMemoryEventBus:
    def __init__(self) -> None:
        self._events_by_workflow: dict[str, list[StreamEvent]] = {}

    async def publish(self, event: StreamEvent) -> None:
        self._events_by_workflow.setdefault(event.workflow_id, []).append(event)

    async def list_events(
        self,
        workflow_id: str,
        after_event_id: str | None = None,
    ) -> list[StreamEvent]:
        events = self._events_by_workflow.get(workflow_id, [])
        if after_event_id is None:
            return list(events)

        for index, event in enumerate(events):
            if event.event_id == after_event_id:
                return list(events[index + 1 :])
        return list(events)
