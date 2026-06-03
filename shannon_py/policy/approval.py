from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class ApprovalStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class ApprovalRequest(BaseModel):
    approval_id: str = Field(default_factory=lambda: f"approval_{uuid4().hex}")
    subject_type: str
    subject_name: str
    status: ApprovalStatus = ApprovalStatus.PENDING
    reason: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    decided_at: datetime | None = None


class InMemoryApprovalGate:
    def __init__(self) -> None:
        self._requests: dict[str, ApprovalRequest] = {}

    async def request_approval(
        self,
        subject_type: str,
        subject_name: str,
        reason: str,
        metadata: dict[str, Any] | None = None,
    ) -> ApprovalRequest:
        approval = ApprovalRequest(
            subject_type=subject_type,
            subject_name=subject_name,
            reason=reason,
            metadata=metadata or {},
        )
        self._requests[approval.approval_id] = approval
        return approval

    async def decide(self, approval_id: str, approved: bool) -> ApprovalRequest | None:
        approval = self._requests.get(approval_id)
        if approval is None:
            return None
        approval.status = ApprovalStatus.APPROVED if approved else ApprovalStatus.REJECTED
        approval.decided_at = datetime.now(UTC)
        return approval

    async def list_requests(self) -> list[ApprovalRequest]:
        return list(self._requests.values())
