from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


class WorkspaceAccessError(ValueError):
    pass


@dataclass(frozen=True)
class Workspace:
    session_id: str
    root: Path


class FileGuard:
    def __init__(self, workspace_root: Path) -> None:
        self._workspace_root = workspace_root.resolve()

    def resolve(self, relative_path: str | Path) -> Path:
        candidate = Path(relative_path)
        if candidate.is_absolute():
            raise WorkspaceAccessError("Absolute paths are not allowed.")
        if any(part == ".." for part in candidate.parts):
            raise WorkspaceAccessError("Path traversal is not allowed.")

        resolved = (self._workspace_root / candidate).resolve()
        if not resolved.is_relative_to(self._workspace_root):
            raise WorkspaceAccessError("Path escapes the session workspace.")
        return resolved


class WorkspaceManager:
    def __init__(self, root: str | Path = ".sandbox-workspaces") -> None:
        self._root = Path(root).resolve()

    def get_workspace(self, session_id: str) -> Workspace:
        workspace_root = self._root / session_id
        workspace_root.mkdir(parents=True, exist_ok=True)
        return Workspace(session_id=session_id, root=workspace_root)

    def file_guard(self, session_id: str) -> FileGuard:
        return FileGuard(self.get_workspace(session_id).root)
