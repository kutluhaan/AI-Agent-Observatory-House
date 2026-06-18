"""
Pydantic schemas — Agent CRUD ve run endpoint'leri.
"""
from __future__ import annotations

import uuid
from typing import Annotated, Any

from pydantic import BaseModel, Field, field_validator

from app.services.providers.factory import SUPPORTED_PROVIDERS

_TOOL_NAMES_MAX = 20
_MAX_STEPS_LIMIT = 50
_TIMEOUT_MAX = 600


class CreateAgentRequest(BaseModel):
    name: Annotated[str, Field(min_length=1, max_length=200)]
    description: str | None = None
    system_prompt: Annotated[str, Field(min_length=1)]
    provider: str
    model: Annotated[str, Field(min_length=1, max_length=200)]
    temperature: Annotated[float, Field(ge=0.0, le=2.0)] = 0.7
    max_tokens: Annotated[int | None, Field(gt=0)] = None
    max_steps: Annotated[int, Field(ge=1, le=_MAX_STEPS_LIMIT)] = 10
    timeout_seconds: Annotated[int, Field(ge=5, le=_TIMEOUT_MAX)] = 120
    tool_names: list[str] = Field(default_factory=list, max_length=_TOOL_NAMES_MAX)

    @field_validator("provider")
    @classmethod
    def validate_provider(cls, v: str) -> str:
        if v not in SUPPORTED_PROVIDERS:
            raise ValueError(f"Provider must be one of: {', '.join(sorted(SUPPORTED_PROVIDERS))}")
        return v

    @field_validator("tool_names")
    @classmethod
    def validate_tool_names(cls, v: list[str]) -> list[str]:
        seen: set[str] = set()
        for name in v:
            if name in seen:
                raise ValueError(f"Duplicate tool name: '{name}'")
            seen.add(name)
        return v


class UpdateAgentRequest(BaseModel):
    name: Annotated[str, Field(min_length=1, max_length=200)] | None = None
    description: str | None = None
    system_prompt: Annotated[str, Field(min_length=1)] | None = None
    provider: str | None = None
    model: Annotated[str, Field(min_length=1, max_length=200)] | None = None
    temperature: Annotated[float, Field(ge=0.0, le=2.0)] | None = None
    max_tokens: Annotated[int | None, Field(gt=0)] = None
    max_steps: Annotated[int, Field(ge=1, le=_MAX_STEPS_LIMIT)] | None = None
    timeout_seconds: Annotated[int, Field(ge=5, le=_TIMEOUT_MAX)] | None = None
    tool_names: list[str] | None = None
    is_active: bool | None = None

    @field_validator("provider")
    @classmethod
    def validate_provider(cls, v: str | None) -> str | None:
        if v is not None and v not in SUPPORTED_PROVIDERS:
            raise ValueError(f"Provider must be one of: {', '.join(sorted(SUPPORTED_PROVIDERS))}")
        return v

    @field_validator("tool_names")
    @classmethod
    def validate_tool_names(cls, v: list[str] | None) -> list[str] | None:
        if v is None:
            return v
        seen: set[str] = set()
        for name in v:
            if name in seen:
                raise ValueError(f"Duplicate tool name: '{name}'")
            seen.add(name)
        return v


class AgentResponse(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    system_prompt: str
    provider: str
    model: str
    temperature: float
    max_tokens: int | None
    max_steps: int
    timeout_seconds: int
    tool_names: list[str]
    is_active: bool
    created_by: uuid.UUID | None
    created_at: str
    updated_at: str

    @classmethod
    def from_orm(cls, agent: Any) -> "AgentResponse":
        return cls(
            id=agent.id,
            name=agent.name,
            description=agent.description,
            system_prompt=agent.system_prompt,
            provider=agent.provider,
            model=agent.model,
            temperature=agent.temperature,
            max_tokens=agent.max_tokens,
            max_steps=agent.max_steps,
            timeout_seconds=agent.timeout_seconds,
            tool_names=agent.tool_names or [],
            is_active=agent.is_active,
            created_by=agent.created_by,
            created_at=agent.created_at.isoformat(),
            updated_at=agent.updated_at.isoformat(),
        )


class RunAgentRequest(BaseModel):
    input: Annotated[str, Field(min_length=1)]
    stream: bool = True


class RunAgentSyncResponse(BaseModel):
    trace_id: str
    content: str
    steps_taken: int
    finish_reason: str
    total_usage: dict[str, int]
