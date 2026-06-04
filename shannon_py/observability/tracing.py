from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class TraceSpan(BaseModel):
    span_id: str = Field(default_factory=lambda: f"span_{uuid4().hex}")
    name: str
    subject_id: str
    status: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    started_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class InMemoryTracer:
    def __init__(self) -> None:
        self._spans: list[TraceSpan] = []

    async def record_span(
        self,
        name: str,
        subject_id: str,
        status: str,
        metadata: dict[str, Any] | None = None,
    ) -> TraceSpan:
        span = TraceSpan(
            name=name,
            subject_id=subject_id,
            status=status,
            metadata=metadata or {},
        )
        self._spans.append(span)
        return span

    async def list_spans(self) -> list[TraceSpan]:
        return list(self._spans)
