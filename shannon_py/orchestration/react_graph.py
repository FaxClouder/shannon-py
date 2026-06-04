from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from shannon_py.agent import AgentRole, AgentRuntime, AgentSpec
from shannon_py.tools.core import ToolExecutor, ToolResult


class ReactGraphInput(BaseModel):
    task_id: str
    workflow_id: str
    session_id: str
    query: str = Field(min_length=1)
    context: dict[str, Any] = Field(default_factory=dict)


class ReactGraphOutput(BaseModel):
    output: str
    tool_name: str
    tool_result: ToolResult
    metadata: dict[str, Any] = Field(default_factory=dict)


class ReactGraph:
    def __init__(
        self,
        tool_executor: ToolExecutor,
        runtime: AgentRuntime | None = None,
    ) -> None:
        self._tool_executor = tool_executor
        self._runtime = runtime or AgentRuntime(tool_executor=tool_executor)

    async def run(self, graph_input: ReactGraphInput) -> ReactGraphOutput:
        expression = _extract_calculator_expression(graph_input.query, graph_input.context)
        result = await self._runtime.run_react(
            AgentSpec(role=AgentRole.ASSISTANT, name="react"),
            graph_input.workflow_id,
            graph_input.task_id,
            graph_input.session_id,
            graph_input.query,
            graph_input.context,
            tool_name="calculator",
            tool_arguments={"expression": expression},
        )

        return ReactGraphOutput(
            output=result.output or "",
            tool_name=result.metadata.get("tool_name", "calculator"),
            tool_result=ToolResult(
                success=bool(result.metadata.get("tool_success", False)),
                content=result.output or "",
                metadata=result.metadata,
                error=result.error,
            ),
            metadata=result.metadata,
        )


def _extract_calculator_expression(query: str, context: dict[str, Any]) -> str:
    tool_args = context.get("tool_args")
    if isinstance(tool_args, dict):
        calculator_args = tool_args.get("calculator")
        if isinstance(calculator_args, dict):
            expression = calculator_args.get("expression")
            if isinstance(expression, str) and expression.strip():
                return expression

    return query
