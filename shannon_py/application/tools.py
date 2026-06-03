from __future__ import annotations

from typing import Any

from shannon_py.policy import InMemoryApprovalGate, PolicyDecisionStatus, PolicyEngine
from shannon_py.tools import ToolExecutor, ToolRegistry, ToolResult, ToolSpec


class ToolService:
    def __init__(
        self,
        registry: ToolRegistry,
        executor: ToolExecutor,
        policy_engine: PolicyEngine,
        approval_gate: InMemoryApprovalGate,
    ) -> None:
        self._registry = registry
        self._executor = executor
        self._policy_engine = policy_engine
        self._approval_gate = approval_gate

    async def list_tools(self) -> list[ToolSpec]:
        return self._registry.list_specs()

    async def execute(self, tool_name: str, arguments: dict[str, Any]) -> ToolResult:
        tool = self._registry.get(tool_name)
        if tool is None:
            return await self._executor.execute(tool_name, arguments)

        approved = arguments.pop("approved", False) is True
        decision = self._policy_engine.evaluate_tool_execution(tool.spec, approved=approved)
        if decision.status == PolicyDecisionStatus.APPROVAL_REQUIRED:
            approval = await self._approval_gate.request_approval(
                subject_type="tool",
                subject_name=tool_name,
                reason=decision.reason,
                metadata={"arguments": arguments},
            )
            return ToolResult(
                success=False,
                content="",
                error=decision.reason,
                metadata={
                    "tool_name": tool_name,
                    "approval_id": approval.approval_id,
                    "approval_status": approval.status,
                },
            )
        if not decision.allowed:
            return ToolResult(
                success=False,
                content="",
                error=decision.reason,
                metadata={"tool_name": tool_name},
            )

        return await self._executor.execute(tool_name, arguments)

    async def list_approvals(self):
        return await self._approval_gate.list_requests()
