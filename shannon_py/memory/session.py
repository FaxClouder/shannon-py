from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class MessageRole(StrEnum):
    USER = "user"
    ASSISTANT = "assistant"


class ConversationMessage(BaseModel):
    role: MessageRole
    content: str
    task_id: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    metadata: dict[str, Any] = Field(default_factory=dict)


class Session(BaseModel):
    session_id: str
    messages: list[ConversationMessage] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class InMemorySessionRepository:
    def __init__(self) -> None:
        self._messages: dict[str, list[ConversationMessage]] = {}

    async def append_message(self, session_id: str, message: ConversationMessage) -> None:
        self._messages.setdefault(session_id, []).append(message)

    async def list_messages(self, session_id: str) -> list[ConversationMessage]:
        return list(self._messages.get(session_id, []))

    async def get_session(self, session_id: str) -> Session:
        return Session(session_id=session_id, messages=await self.list_messages(session_id))
