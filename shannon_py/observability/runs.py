from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class RunRecord(BaseModel):
    run_id: str = Field(default_factory=lambda: f"run_{uuid4().hex}")
    kind: str
    subject_id: str
    status: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class RunRecorder:
    def __init__(self) -> None:
        self._runs: list[RunRecord] = []

    async def record(
        self,
        kind: str,
        subject_id: str,
        status: str,
        metadata: dict[str, Any] | None = None,
    ) -> RunRecord:
        run = RunRecord(
            kind=kind,
            subject_id=subject_id,
            status=status,
            metadata=metadata or {},
        )
        self._runs.append(run)
        return run

    async def list_runs(self) -> list[RunRecord]:
        return list(self._runs)
