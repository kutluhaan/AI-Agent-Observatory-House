"""Pydantic schemas — Conversation (sohbet thread) CRUD + mesaj gönderme (Faz 1)."""
from __future__ import annotations

import uuid
from typing import Annotated, Any

from pydantic import BaseModel, Field


class CreateConversationRequest(BaseModel):
    title: str | None = None


class RenameConversationRequest(BaseModel):
    title: Annotated[str, Field(min_length=1, max_length=200)]


class PostMessageRequest(BaseModel):
    input: Annotated[str, Field(min_length=1)]
    stream: bool = True


class ConversationSummary(BaseModel):
    id: uuid.UUID
    agent_id: uuid.UUID
    title: str
    created_at: str
    last_message_at: str
    message_count: int = 0

    @classmethod
    def from_orm(cls, obj: Any, message_count: int = 0) -> "ConversationSummary":
        return cls(
            id=obj.id,
            agent_id=obj.agent_id,
            title=obj.title,
            created_at=obj.created_at.isoformat(),
            last_message_at=obj.last_message_at.isoformat(),
            message_count=message_count,
        )


class MessageResponse(BaseModel):
    id: uuid.UUID
    role: str
    content: str
    segments: list[Any] | None = None
    trace_id: str | None = None
    error: str | None = None
    created_at: str

    @classmethod
    def from_orm(cls, obj: Any) -> "MessageResponse":
        return cls(
            id=obj.id,
            role=obj.role,
            content=obj.content,
            segments=obj.segments,
            trace_id=obj.trace_id,
            error=obj.error,
            created_at=obj.created_at.isoformat(),
        )


class ConversationDetail(BaseModel):
    id: uuid.UUID
    agent_id: uuid.UUID
    title: str
    created_at: str
    messages: list[MessageResponse]
