from __future__ import annotations

from typing import Any

from shannon_py.sandbox.python_worker import PythonSandboxWorker
from shannon_py.tools.core import ToolResult, ToolSpec


class PythonExecTool:
    def __init__(self, worker: PythonSandboxWorker) -> None:
        self._worker = worker
        self.spec = ToolSpec(
            name="python_exec",
            description="Execute Python code in an isolated session workspace.",
            args_schema={
                "type": "object",
                "properties": {
                    "session_id": {
                        "type": "string",
                        "description": "Session workspace identifier.",
                    },
                    "code": {
                        "type": "string",
                        "description": "Python code to execute.",
                    },
                },
                "required": ["session_id", "code"],
            },
            permissions=["approval"],
            dangerous=True,
            timeout_seconds=10,
        )

    async def ainvoke(self, arguments: dict[str, Any]) -> ToolResult:
        session_id = arguments.get("session_id")
        code = arguments.get("code")
        if not isinstance(session_id, str) or not session_id.strip():
            return ToolResult(
                success=False,
                content="",
                error="python_exec requires a non-empty session_id string.",
                metadata={"tool_name": self.spec.name},
            )
        if not isinstance(code, str) or not code.strip():
            return ToolResult(
                success=False,
                content="",
                error="python_exec requires a non-empty code string.",
                metadata={"tool_name": self.spec.name, "session_id": session_id},
            )

        execution = await self._worker.run(session_id=session_id, code=code)
        return ToolResult(
            success=execution.success,
            content=execution.stdout,
            metadata={
                "tool_name": self.spec.name,
                "session_id": session_id,
                "stderr": execution.stderr,
                "return_code": execution.return_code,
            },
            error=execution.error,
        )
