from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

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
    def __init__(self, tool_executor: ToolExecutor) -> None:
        self._tool_executor = tool_executor

    async def run(self, graph_input: ReactGraphInput) -> ReactGraphOutput:
        expression = _extract_calculator_expression(graph_input.query, graph_input.context)
        tool_result = await self._tool_executor.execute(
            "calculator",
            {"expression": expression},
        )

        if tool_result.success:
            output = f"Calculator result: {tool_result.content}"
        else:
            output = f"Calculator failed: {tool_result.error}"

        return ReactGraphOutput(
            output=output,
            tool_name="calculator",
            tool_result=tool_result,
            metadata={
                "mode": "react",
                "tool_name": "calculator",
                "tool_success": tool_result.success,
            },
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
