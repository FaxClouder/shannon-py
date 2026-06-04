from __future__ import annotations

from typing import Any

from shannon_py.observability.metrics import InMemoryMetricsRegistry
from shannon_py.observability.runs import RunRecorder
from shannon_py.observability.tracing import InMemoryTracer
from shannon_py.policy import InMemoryApprovalGate, PolicyDecisionStatus, PolicyEngine
from shannon_py.tools import ToolExecutor, ToolRegistry, ToolResult, ToolSpec


class ToolService:
    def __init__(
        self,
        registry: ToolRegistry,
        executor: ToolExecutor,
        policy_engine: PolicyEngine,
        approval_gate: InMemoryApprovalGate,
        metrics: InMemoryMetricsRegistry | None = None,
        run_recorder: RunRecorder | None = None,
        tracer: InMemoryTracer | None = None,
    ) -> None:
        self._registry = registry
        self._executor = executor
        self._policy_engine = policy_engine
        self._approval_gate = approval_gate
        self._metrics = metrics
        self._run_recorder = run_recorder
        self._tracer = tracer

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

        result = await self._executor.execute(tool_name, arguments)
        self._record_metric("tool_calls")
        if result.success:
            self._record_metric("tool_calls_succeeded")
        else:
            self._record_metric("tool_calls_failed")
        await self._record_run(
            "tool",
            tool_name,
            "completed" if result.success else "failed",
            result.metadata,
        )
        await self._record_trace(
            "tool.execute",
            tool_name,
            "completed" if result.success else "failed",
            result.metadata,
        )
        return result

    async def list_approvals(self):
        return await self._approval_gate.list_requests()

    def _record_metric(self, name: str) -> None:
        if self._metrics is not None:
            self._metrics.inc(name)

    async def _record_run(
        self,
        kind: str,
        subject_id: str,
        status: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        if self._run_recorder is not None:
            await self._run_recorder.record(kind, subject_id, status, metadata)

    async def _record_trace(
        self,
        name: str,
        subject_id: str,
        status: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        if self._tracer is not None:
            await self._tracer.record_span(name, subject_id, status, metadata)
