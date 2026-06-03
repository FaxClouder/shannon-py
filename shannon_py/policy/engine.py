from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel

from shannon_py.tools import ToolSpec


class PolicyDecisionStatus(StrEnum):
    ALLOWED = "allowed"
    DENIED = "denied"
    APPROVAL_REQUIRED = "approval_required"


class PolicyDecision(BaseModel):
    status: PolicyDecisionStatus
    reason: str

    @property
    def allowed(self) -> bool:
        return self.status == PolicyDecisionStatus.ALLOWED


class PolicyEngine:
    def __init__(self, max_input_chars: int = 100_000) -> None:
        self._max_input_chars = max_input_chars

    def validate_task_input(self, query: str) -> PolicyDecision:
        if len(query) > self._max_input_chars:
            return PolicyDecision(
                status=PolicyDecisionStatus.DENIED,
                reason=f"Input exceeds {self._max_input_chars} characters.",
            )
        return PolicyDecision(status=PolicyDecisionStatus.ALLOWED, reason="Task input allowed.")

    def evaluate_tool_execution(
        self,
        tool_spec: ToolSpec,
        approved: bool = False,
    ) -> PolicyDecision:
        if tool_spec.dangerous and not approved:
            return PolicyDecision(
                status=PolicyDecisionStatus.APPROVAL_REQUIRED,
                reason=f"Tool requires approval: {tool_spec.name}",
            )
        return PolicyDecision(status=PolicyDecisionStatus.ALLOWED, reason="Tool execution allowed.")
