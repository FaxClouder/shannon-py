from __future__ import annotations

from typing import Any

from shannon_py.tools import ToolExecutor, ToolRegistry, ToolResult, ToolSpec


class ToolService:
    def __init__(self, registry: ToolRegistry, executor: ToolExecutor) -> None:
        self._registry = registry
        self._executor = executor

    async def list_tools(self) -> list[ToolSpec]:
        return self._registry.list_specs()

    async def execute(self, tool_name: str, arguments: dict[str, Any]) -> ToolResult:
        return await self._executor.execute(tool_name, arguments)
