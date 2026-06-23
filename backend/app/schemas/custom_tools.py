"""Pydantic schemas — kullanıcı tanımlı HTTP tool'ları (B1 / #1)."""
from __future__ import annotations

import re
import uuid
from typing import Annotated, Any

from pydantic import BaseModel, Field, field_validator

_NAME_RE = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")
_METHODS = {"GET", "POST", "PUT", "PATCH", "DELETE"}


def _validate_name(v: str) -> str:
    if not _NAME_RE.match(v):
        raise ValueError("name yalnız harf/rakam/_/- içermeli (1-64) — LLM tool adı olarak kullanılır.")
    if v.startswith("mcp__") or v in {"delegate", "team_share", "team_board", "think", "web_search", "read_url"}:
        raise ValueError(f"'{v}' ayrılmış/yerleşik bir tool adıyla çakışıyor; başka ad seç.")
    return v


def _validate_method(v: str) -> str:
    v = (v or "GET").upper()
    if v not in _METHODS:
        raise ValueError(f"method şunlardan biri olmalı: {', '.join(sorted(_METHODS))}")
    return v


class CreateCustomToolRequest(BaseModel):
    name: Annotated[str, Field(min_length=1, max_length=64)]
    description: Annotated[str, Field(max_length=2000)] = ""
    method: str = "GET"
    url: Annotated[str, Field(min_length=1, max_length=1000)]
    headers: dict[str, str] | None = None
    parameters: dict[str, Any] = Field(default_factory=lambda: {"type": "object", "properties": {}})
    timeout_seconds: Annotated[int, Field(ge=1, le=120)] = 20

    _vn = field_validator("name")(_validate_name)
    _vm = field_validator("method")(_validate_method)


class UpdateCustomToolRequest(BaseModel):
    name: Annotated[str, Field(min_length=1, max_length=64)] | None = None
    description: Annotated[str, Field(max_length=2000)] | None = None
    method: str | None = None
    url: Annotated[str, Field(min_length=1, max_length=1000)] | None = None
    headers: dict[str, str] | None = None
    parameters: dict[str, Any] | None = None
    timeout_seconds: Annotated[int, Field(ge=1, le=120)] | None = None
    is_active: bool | None = None

    @field_validator("name")
    @classmethod
    def _vn(cls, v: str | None) -> str | None:
        return _validate_name(v) if v is not None else v

    @field_validator("method")
    @classmethod
    def _vm(cls, v: str | None) -> str | None:
        return _validate_method(v) if v is not None else v


class CustomToolResponse(BaseModel):
    id: uuid.UUID
    name: str
    description: str
    method: str
    url: str
    parameters: dict[str, Any]
    timeout_seconds: int
    header_names: list[str]   # değerler gizli; yalnız anahtar adları
    is_active: bool
    created_at: str
    updated_at: str

    @classmethod
    def from_orm(cls, obj: Any, header_names: list[str]) -> "CustomToolResponse":
        return cls(
            id=obj.id, name=obj.name, description=obj.description, method=obj.method, url=obj.url,
            parameters=obj.parameters or {}, timeout_seconds=obj.timeout_seconds,
            header_names=header_names, is_active=obj.is_active,
            created_at=obj.created_at.isoformat(), updated_at=obj.updated_at.isoformat(),
        )


class TestCustomToolRequest(BaseModel):
    arguments: dict[str, Any] = Field(default_factory=dict)
