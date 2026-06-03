from __future__ import annotations

from typing import Any, Protocol

from pydantic import BaseModel, Field


class LLMRequest(BaseModel):
    prompt: str = Field(min_length=1)
    context: dict[str, Any] = Field(default_factory=dict)


class LLMResponse(BaseModel):
    content: str
    provider: str
    model: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class LLMProvider(Protocol):
    name: str
    model: str

    async def complete(self, request: LLMRequest) -> LLMResponse:
        raise NotImplementedError


class MockProvider:
    name = "mock"

    def __init__(self, model: str = "mock-default") -> None:
        self.model = model

    async def complete(self, request: LLMRequest) -> LLMResponse:
        return LLMResponse(
            content=f"Mock response for: {request.prompt}",
            provider=self.name,
            model=self.model,
            metadata={"mock": True},
        )
