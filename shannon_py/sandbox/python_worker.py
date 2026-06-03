from __future__ import annotations

import asyncio
import sys
from dataclasses import dataclass

from shannon_py.sandbox.workspace import WorkspaceManager


@dataclass(frozen=True)
class PythonExecutionResult:
    success: bool
    stdout: str
    stderr: str
    return_code: int | None
    error: str | None = None


class PythonSandboxWorker:
    def __init__(
        self,
        workspace_manager: WorkspaceManager,
        timeout_seconds: int = 5,
        max_output_chars: int = 20_000,
    ) -> None:
        self._workspace_manager = workspace_manager
        self._timeout_seconds = timeout_seconds
        self._max_output_chars = max_output_chars

    async def run(self, session_id: str, code: str) -> PythonExecutionResult:
        workspace = self._workspace_manager.get_workspace(session_id)
        script_path = workspace.root / "__python_exec__.py"
        script_path.write_text(code, encoding="utf-8")

        process = await asyncio.create_subprocess_exec(
            sys.executable,
            str(script_path),
            cwd=workspace.root,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        try:
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                process.communicate(),
                timeout=self._timeout_seconds,
            )
        except TimeoutError:
            process.kill()
            await process.communicate()
            return PythonExecutionResult(
                success=False,
                stdout="",
                stderr="",
                return_code=None,
                error=f"Python execution timed out after {self._timeout_seconds} seconds.",
            )

        stdout = stdout_bytes.decode("utf-8", errors="replace").replace("\r\n", "\n")
        stderr = stderr_bytes.decode("utf-8", errors="replace").replace("\r\n", "\n")
        if len(stdout) + len(stderr) > self._max_output_chars:
            return PythonExecutionResult(
                success=False,
                stdout=stdout[: self._max_output_chars],
                stderr="",
                return_code=process.returncode,
                error=f"Python execution output exceeded {self._max_output_chars} characters.",
            )

        return PythonExecutionResult(
            success=process.returncode == 0,
            stdout=stdout,
            stderr=stderr,
            return_code=process.returncode,
            error=None if process.returncode == 0 else "Python execution failed.",
        )
