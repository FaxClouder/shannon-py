from shannon_py.streaming.events import InMemoryEventBus, StreamEvent, StreamEventType
from shannon_py.streaming.sse import SSEBroker, serialize_sse_event


def test_serialize_sse_event_uses_event_id_type_and_json_data() -> None:
    event = StreamEvent(
        workflow_id="workflow_1",
        task_id="task_1",
        type=StreamEventType.WORKFLOW_STARTED,
        payload={"status": "running"},
    )

    serialized = serialize_sse_event(event)

    assert serialized.startswith(f"id: {event.event_id}\n")
    assert "event: workflow_started\n" in serialized
    assert '"workflow_id":"workflow_1"' in serialized
    assert serialized.endswith("\n\n")


async def test_sse_broker_replays_events_after_last_event_id() -> None:
    event_bus = InMemoryEventBus()
    first = StreamEvent(
        workflow_id="workflow_1",
        task_id="task_1",
        type=StreamEventType.WORKFLOW_STARTED,
    )
    second = StreamEvent(
        workflow_id="workflow_1",
        task_id="task_1",
        type=StreamEventType.STREAM_END,
    )
    await event_bus.publish(first)
    await event_bus.publish(second)

    broker = SSEBroker(event_bus)
    chunks = [chunk async for chunk in broker.replay("workflow_1", last_event_id=first.event_id)]

    assert len(chunks) == 1
    assert f"id: {second.event_id}\n" in chunks[0]
    assert "event: stream_end\n" in chunks[0]
