from __future__ import annotations

import json
from collections.abc import AsyncIterator

from shannon_py.streaming.events import InMemoryEventBus, StreamEvent


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
    ) -> AsyncIterator[str]:
        events = await self._event_bus.list_events(workflow_id, after_event_id=last_event_id)
        for event in events:
            yield serialize_sse_event(event)
