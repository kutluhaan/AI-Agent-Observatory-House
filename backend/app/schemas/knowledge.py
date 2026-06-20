"""Pydantic schemas — Agent bilgi öğeleri (Faz 4)."""
from __future__ import annotations

import uuid
from typing import Annotated, Any

from pydantic import BaseModel, Field, field_validator

from app.models.agent_knowledge import KNOWLEDGE_KINDS


class CreateKnowledgeRequest(BaseModel):
    kind: str
    name: Annotated[str, Field(min_length=1, max_length=200)]
    content: Annotated[str, Field(min_length=1)]

    @field_validator("kind")
    @classmethod
    def validate_kind(cls, v: str) -> str:
        if v not in KNOWLEDGE_KINDS:
            raise ValueError(f"kind must be one of: {', '.join(KNOWLEDGE_KINDS)}")
        return v


class UpdateKnowledgeRequest(BaseModel):
    name: Annotated[str, Field(min_length=1, max_length=200)] | None = None
    content: Annotated[str, Field(min_length=1)] | None = None
    is_active: bool | None = None


class KnowledgeResponse(BaseModel):
    id: uuid.UUID
    kind: str
    name: str
    content: str
    is_active: bool
    created_at: str
    updated_at: str

    @classmethod
    def from_orm(cls, obj: Any) -> "KnowledgeResponse":
        return cls(
            id=obj.id,
            kind=obj.kind,
            name=obj.name,
            content=obj.content,
            is_active=obj.is_active,
            created_at=obj.created_at.isoformat(),
            updated_at=obj.updated_at.isoformat(),
        )
