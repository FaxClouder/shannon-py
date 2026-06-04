from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from shannon_py.agent import AgentRole, AgentRuntime, AgentSpec
from shannon_py.llm.providers import LLMProvider


class ResearchGraphInput(BaseModel):
    task_id: str
    workflow_id: str
    session_id: str
    query: str = Field(min_length=1)
    context: dict[str, Any] = Field(default_factory=dict)


class ResearchGraphOutput(BaseModel):
    output: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class ResearchGraph:
    def __init__(
        self,
        provider: LLMProvider,
        runtime: AgentRuntime | None = None,
    ) -> None:
        self._provider = provider
        self._runtime = runtime or AgentRuntime(provider=provider)

    async def run(self, graph_input: ResearchGraphInput) -> ResearchGraphOutput:
        result = await self._runtime.run_research(
            AgentSpec(role=AgentRole.RESEARCHER, name="research"),
            graph_input.workflow_id,
            graph_input.task_id,
            graph_input.session_id,
            graph_input.query,
            graph_input.context,
        )
        sources = result.metadata.get("sources", [])
        return ResearchGraphOutput(
            output=result.output or "",
            metadata={
                **result.metadata,
                "mode": "research",
                "sources": sources,
                "token_usage": result.token_usage,
            },
        )
