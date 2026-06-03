from __future__ import annotations

import asyncio
from typing import Any, Protocol

from pydantic import BaseModel, Field


class ToolSpec(BaseModel):
    name: str
    description: str
    args_schema: dict[str, Any] = Field(default_factory=dict)
    permissions: list[str] = Field(default_factory=list)
    dangerous: bool = False
    timeout_seconds: int = Field(default=30, ge=1)


class ToolResult(BaseModel):
    success: bool
    content: str
    artifact_refs: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None


class ShannonTool(Protocol):
    spec: ToolSpec

    async def ainvoke(self, arguments: dict[str, Any]) -> ToolResult:
        raise NotImplementedError


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, ShannonTool] = {}

    def register(self, tool: ShannonTool) -> None:
        self._tools[tool.spec.name] = tool

    def get(self, name: str) -> ShannonTool | None:
        return self._tools.get(name)

    def list_specs(self) -> list[ToolSpec]:
        return [tool.spec for tool in self._tools.values()]


class ToolExecutor:
    def __init__(self, registry: ToolRegistry) -> None:
        self._registry = registry

    async def execute(self, name: str, arguments: dict[str, Any]) -> ToolResult:
        tool = self._registry.get(name)
        if tool is None:
            return ToolResult(
                success=False,
                content="",
                error=f"Tool not found: {name}",
                metadata={"tool_name": name},
            )

        try:
            return await asyncio.wait_for(
                tool.ainvoke(arguments),
                timeout=tool.spec.timeout_seconds,
            )
        except TimeoutError:
            return ToolResult(
                success=False,
                content="",
                error=f"Tool timed out after {tool.spec.timeout_seconds} seconds.",
                metadata={"tool_name": name},
            )
        except Exception as exc:
            return ToolResult(
                success=False,
                content="",
                error=str(exc),
                metadata={"tool_name": name},
            )
