from pathlib import Path

import pytest

from shannon_py.sandbox.python_worker import PythonSandboxWorker
from shannon_py.sandbox.workspace import FileGuard, WorkspaceAccessError, WorkspaceManager


def test_file_guard_resolves_paths_inside_workspace(tmp_path: Path) -> None:
    guard = FileGuard(tmp_path)

    resolved = guard.resolve("nested/file.txt")

    assert resolved == (tmp_path / "nested" / "file.txt").resolve()


def test_file_guard_rejects_path_traversal(tmp_path: Path) -> None:
    guard = FileGuard(tmp_path)

    with pytest.raises(WorkspaceAccessError, match="Path traversal"):
        guard.resolve("../outside.txt")


def test_file_guard_rejects_absolute_path(tmp_path: Path) -> None:
    guard = FileGuard(tmp_path)

    with pytest.raises(WorkspaceAccessError, match="Absolute paths"):
        guard.resolve(Path.cwd())


async def test_python_worker_runs_code_in_session_workspace(tmp_path: Path) -> None:
    worker = PythonSandboxWorker(
        WorkspaceManager(tmp_path),
        timeout_seconds=2,
        max_output_chars=1_000,
    )

    result = await worker.run("session_worker", "print('hello')")

    assert result.success is True
    assert result.stdout == "hello\n"
    assert result.return_code == 0


async def test_python_worker_times_out(tmp_path: Path) -> None:
    worker = PythonSandboxWorker(
        WorkspaceManager(tmp_path),
        timeout_seconds=1,
        max_output_chars=1_000,
    )

    result = await worker.run("session_timeout", "while True:\n    pass\n")

    assert result.success is False
    assert result.error == "Python execution timed out after 1 seconds."


async def test_python_worker_rejects_output_over_limit(tmp_path: Path) -> None:
    worker = PythonSandboxWorker(
        WorkspaceManager(tmp_path),
        timeout_seconds=2,
        max_output_chars=10,
    )

    result = await worker.run("session_output", "print('x' * 100)")

    assert result.success is False
    assert result.error == "Python execution output exceeded 10 characters."
