from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class WorkflowCheckpoint(BaseModel):
    checkpoint_id: str = Field(default_factory=lambda: f"checkpoint_{uuid4().hex}")
    workflow_id: str
    task_id: str
    session_id: str
    status: str
    state: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class InMemoryCheckpointManager:
    def __init__(self) -> None:
        self._checkpoints_by_workflow: dict[str, list[WorkflowCheckpoint]] = {}

    async def save(self, checkpoint: WorkflowCheckpoint) -> WorkflowCheckpoint:
        self._checkpoints_by_workflow.setdefault(checkpoint.workflow_id, []).append(checkpoint)
        return checkpoint

    async def list_checkpoints(self, workflow_id: str) -> list[WorkflowCheckpoint]:
        return list(self._checkpoints_by_workflow.get(workflow_id, []))

    async def latest(self, workflow_id: str) -> WorkflowCheckpoint | None:
        checkpoints = self._checkpoints_by_workflow.get(workflow_id, [])
        if not checkpoints:
            return None
        return checkpoints[-1]
