from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from shannon_py.llm.providers import LLMProvider, LLMRequest


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
    def __init__(self, provider: LLMProvider) -> None:
        self._provider = provider

    async def run(self, graph_input: ResearchGraphInput) -> ResearchGraphOutput:
        response = await self._provider.complete(
            LLMRequest(
                prompt=f"Research summary request: {graph_input.query}",
                context=graph_input.context,
            )
        )
        sources = [
            {
                "title": "Mock internal research source",
                "source_type": "mock",
                "url": None,
            }
        ]
        return ResearchGraphOutput(
            output=f"Research summary:\n{response.content}",
            metadata={
                "mode": "research",
                "sources": sources,
                "provider": response.provider,
                "model": response.model,
            },
        )
