from __future__ import annotations

import json
from collections.abc import AsyncIterator

from shannon_py.streaming.events import InMemoryEventBus, StreamEvent, StreamEventType


def serialize_sse_event(event: StreamEvent) -> str:
    data = event.model_dump(mode="json")
    return (
        f"id: {event.event_id}\n"
        f"event: {event.type}\n"
        f"data: {json.dumps(data, ensure_ascii=False, separators=(',', ':'))}\n\n"
    )


class SSEBroker:
    def __init__(self, event_bus: InMemoryEventBus) -> None:
        self._event_bus = event_bus

    async def replay(
        self,
        workflow_id: str,
        last_event_id: str | None = None,
        live: bool = False,
        idle_timeout_seconds: float = 30.0,
    ) -> AsyncIterator[str]:
        events = await self._event_bus.list_events(workflow_id, after_event_id=last_event_id)
        for event in events:
            yield serialize_sse_event(event)
            last_event_id = event.event_id
            if event.type == StreamEventType.STREAM_END:
                return

        if not live:
            return

        while True:
            event = await self._event_bus.wait_for_next_event(
                workflow_id,
                after_event_id=last_event_id,
                timeout_seconds=idle_timeout_seconds,
            )
            if event is None:
                return

            yield serialize_sse_event(event)
            last_event_id = event.event_id
            if event.type == StreamEventType.STREAM_END:
                return
