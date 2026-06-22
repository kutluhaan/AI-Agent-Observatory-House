"""Pydantic schemas — MCP server CRUD + discovery (F7.2)."""
from __future__ import annotations

import uuid
from typing import Annotated, Any

from pydantic import BaseModel, Field


class CreateMcpServerRequest(BaseModel):
    name: Annotated[str, Field(min_length=1, max_length=120)]
    url: Annotated[str, Field(min_length=1, max_length=500)]
    api_key: str | None = None


class UpdateMcpServerRequest(BaseModel):
    name: Annotated[str, Field(min_length=1, max_length=120)] | None = None
    url: Annotated[str, Field(min_length=1, max_length=500)] | None = None
    api_key: str | None = None
    is_active: bool | None = None


class McpServerResponse(BaseModel):
    id: uuid.UUID
    name: str
    url: str
    has_api_key: bool
    is_active: bool
    created_at: str
    updated_at: str

    @classmethod
    def from_orm(cls, obj: Any) -> "McpServerResponse":
        return cls(
            id=obj.id,
            name=obj.name,
            url=obj.url,
            has_api_key=bool(obj.encrypted_api_key),
            is_active=obj.is_active,
            created_at=obj.created_at.isoformat(),
            updated_at=obj.updated_at.isoformat(),
        )


class McpToolInfo(BaseModel):
    name: str
    description: str
    input_schema: dict[str, Any]
