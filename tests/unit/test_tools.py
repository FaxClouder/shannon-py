from pathlib import Path

from shannon_py.sandbox.python_worker import PythonSandboxWorker
from shannon_py.sandbox.workspace import WorkspaceManager
from shannon_py.tools import CalculatorTool, PythonExecTool, ToolExecutor, ToolRegistry


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


async def test_python_exec_tool_runs_in_sandbox_workspace(tmp_path: Path) -> None:
    registry = ToolRegistry()
    registry.register(PythonExecTool(PythonSandboxWorker(WorkspaceManager(tmp_path))))
    executor = ToolExecutor(registry)

    result = await executor.execute(
        "python_exec",
        {"session_id": "session_tool", "code": "print(2 + 5)"},
    )

    assert result.success is True
    assert result.content == "7\n"
    assert result.metadata["session_id"] == "session_tool"


async def test_python_exec_tool_requires_session_and_code(tmp_path: Path) -> None:
    registry = ToolRegistry()
    registry.register(PythonExecTool(PythonSandboxWorker(WorkspaceManager(tmp_path))))
    executor = ToolExecutor(registry)

    result = await executor.execute("python_exec", {"session_id": "session_tool"})

    assert result.success is False
    assert result.error == "python_exec requires a non-empty code string."
