from __future__ import annotations

import asyncio
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
    TOOL_INVOKED = "tool_invoked"
    TOOL_OBSERVATION = "tool_observation"
    TOOL_ERROR = "tool_error"
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
        self._condition = asyncio.Condition()

    async def publish(self, event: StreamEvent) -> None:
        async with self._condition:
            self._events_by_workflow.setdefault(event.workflow_id, []).append(event)
            self._condition.notify_all()

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

    async def wait_for_next_event(
        self,
        workflow_id: str,
        after_event_id: str | None = None,
        timeout_seconds: float = 30.0,
    ) -> StreamEvent | None:
        async with self._condition:
            try:
                await asyncio.wait_for(
                    self._condition.wait_for(
                        lambda: bool(self._next_events(workflow_id, after_event_id))
                    ),
                    timeout=timeout_seconds,
                )
            except TimeoutError:
                return None

            events = self._next_events(workflow_id, after_event_id)
            if not events:
                return None
            return events[0]

    def _next_events(
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
