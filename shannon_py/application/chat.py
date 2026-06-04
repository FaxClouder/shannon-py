from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from shannon_py.llm.providers import LLMProvider, LLMRequest


class ChatMessage(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str


class ChatCompletionRequest(BaseModel):
    model: str = "mock-default"
    messages: list[ChatMessage] = Field(default_factory=list)
    temperature: float | None = None
    stream: bool = False


class ChatCompletionChoice(BaseModel):
    index: int
    message: ChatMessage
    finish_reason: str = "stop"


class ChatCompletionUsage(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class ChatCompletionResponse(BaseModel):
    id: str
    object: str = "chat.completion"
    model: str
    choices: list[ChatCompletionChoice]
    usage: ChatCompletionUsage = Field(default_factory=ChatCompletionUsage)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ChatCompletionService:
    def __init__(self, provider: LLMProvider) -> None:
        self._provider = provider

    async def complete(self, request: ChatCompletionRequest) -> ChatCompletionResponse:
        prompt = "\n".join(
            f"{message.role}: {message.content}" for message in request.messages
        )
        response = await self._provider.complete(
            LLMRequest(prompt=prompt, context={"model": request.model})
        )
        return ChatCompletionResponse(
            id=f"chatcmpl_{response.provider}_{response.model}",
            model=request.model,
            choices=[
                ChatCompletionChoice(
                    index=0,
                    message=ChatMessage(role="assistant", content=response.content),
                )
            ],
            metadata=response.metadata | {"provider": response.provider, "model": response.model},
        )
