from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from shannon_py.llm.providers import LLMProvider, LLMRequest


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
    def __init__(self, provider: LLMProvider) -> None:
        self._provider = provider

    async def run(self, graph_input: SimpleGraphInput) -> SimpleGraphOutput:
        response = await self._provider.complete(
            LLMRequest(prompt=graph_input.query, context=graph_input.context)
        )
        return SimpleGraphOutput(
            output=response.content,
            provider=response.provider,
            model=response.model,
            metadata=response.metadata,
        )
