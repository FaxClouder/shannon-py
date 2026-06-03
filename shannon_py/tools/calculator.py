from __future__ import annotations

import ast
import operator
from typing import Any

from shannon_py.tools.core import ToolResult, ToolSpec


class CalculatorTool:
    spec = ToolSpec(
        name="calculator",
        description="Evaluate a basic arithmetic expression.",
        args_schema={
            "type": "object",
            "properties": {
                "expression": {
                    "type": "string",
                    "description": "Arithmetic expression using numbers and +, -, *, /, **.",
                }
            },
            "required": ["expression"],
        },
        permissions=[],
        dangerous=False,
        timeout_seconds=5,
    )

    async def ainvoke(self, arguments: dict[str, Any]) -> ToolResult:
        expression = arguments.get("expression")
        if not isinstance(expression, str) or not expression.strip():
            return ToolResult(
                success=False,
                content="",
                error="calculator requires a non-empty expression string.",
                metadata={"tool_name": self.spec.name},
            )

        try:
            value = _evaluate_expression(expression)
        except ValueError as exc:
            return ToolResult(
                success=False,
                content="",
                error=str(exc),
                metadata={"tool_name": self.spec.name, "expression": expression},
            )

        return ToolResult(
            success=True,
            content=str(value),
            metadata={"tool_name": self.spec.name, "expression": expression},
        )


def _evaluate_expression(expression: str) -> int | float:
    try:
        parsed = ast.parse(expression, mode="eval")
    except SyntaxError as exc:
        raise ValueError("Invalid arithmetic expression.") from exc

    return _evaluate_node(parsed.body)


def _evaluate_node(node: ast.AST) -> int | float:
    binary_operators = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
        ast.Pow: operator.pow,
    }
    unary_operators = {
        ast.UAdd: operator.pos,
        ast.USub: operator.neg,
    }

    if isinstance(node, ast.Constant) and isinstance(node.value, int | float):
        return node.value

    if isinstance(node, ast.BinOp):
        operator_func = binary_operators.get(type(node.op))
        if operator_func is None:
            raise ValueError("Unsupported arithmetic operator.")
        return operator_func(_evaluate_node(node.left), _evaluate_node(node.right))

    if isinstance(node, ast.UnaryOp):
        operator_func = unary_operators.get(type(node.op))
        if operator_func is None:
            raise ValueError("Unsupported arithmetic operator.")
        return operator_func(_evaluate_node(node.operand))

    raise ValueError("Unsupported arithmetic expression.")
