from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from shannon_py.agent import AgentRole, AgentRuntime, AgentSpec
from shannon_py.llm.providers import LLMProvider


class SimpleGraphInput(BaseModel):
    task_id: str
    workflow_id: str
    session_id: str
    query: str = Field(min_length=1)
    context: dict[str, Any] = Field(default_factory=dict)


class SimpleGraphOutput(BaseModel):
    output: str
    provider: str
    model: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class SimpleGraph:
    def __init__(
        self,
        provider: LLMProvider,
        runtime: AgentRuntime | None = None,
    ) -> None:
        self._provider = provider
        self._runtime = runtime or AgentRuntime(provider=provider)

    @property
    def runtime(self) -> AgentRuntime:
        return self._runtime

    async def run(self, graph_input: SimpleGraphInput) -> SimpleGraphOutput:
        result = await self._runtime.run_simple(
            AgentSpec(role=AgentRole.ASSISTANT, name="simple"),
            graph_input.workflow_id,
            graph_input.task_id,
            graph_input.session_id,
            graph_input.query,
            graph_input.context,
        )
        return SimpleGraphOutput(
            output=result.output or "",
            provider=result.metadata.get("provider", self._provider.name),
            model=result.metadata.get("model", getattr(self._provider, "model", "mock-default")),
            metadata=result.metadata,
        )
