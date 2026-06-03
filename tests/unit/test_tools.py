from shannon_py.tools import CalculatorTool, ToolExecutor, ToolRegistry


async def test_tool_executor_runs_registered_calculator() -> None:
    registry = ToolRegistry()
    registry.register(CalculatorTool())
    executor = ToolExecutor(registry)

    result = await executor.execute("calculator", {"expression": "2 + 3 * 4"})

    assert result.success is True
    assert result.content == "14"
    assert result.metadata["tool_name"] == "calculator"


async def test_calculator_rejects_unsupported_expression() -> None:
    registry = ToolRegistry()
    registry.register(CalculatorTool())
    executor = ToolExecutor(registry)

    result = await executor.execute("calculator", {"expression": "__import__('os').system('dir')"})

    assert result.success is False
    assert result.error == "Unsupported arithmetic expression."


async def test_tool_executor_returns_controlled_error_for_missing_tool() -> None:
    executor = ToolExecutor(ToolRegistry())

    result = await executor.execute("missing", {})

    assert result.success is False
    assert result.error == "Tool not found: missing"
